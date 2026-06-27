"""
Practice-data collectors — NPPES (master practice import) and Google Places (review/hours).

NPPES is a one-time-per-month bulk load: a 7GB CSV streamed row-by-row and
bulk-upserted in 5000-row batches. The taxonomy filter keeps only dental
providers (codes starting with '122').

Google Places is per-practice: one task = one practice. A fan-out task picks
practices in tier order (HOT > WARM > COLD) and dispatches per-practice
collectors. Each per-practice run is protected by a distributed lock so two
workers don't double-fetch the same practice on the same day.
"""

import csv
import logging
from pathlib import Path
from typing import Optional

import httpx
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from core.utils.cache import distributed_lock
from core.utils.retry import sova_retry
from core.utils.tasks import SovaBaseTask

logger = logging.getLogger(__name__)


# ---------- NPPES constants ----------

# Dental taxonomy codes all start with '122' (per NPPES Healthcare Provider
# Taxonomy Code Set). Includes general dentists, oral surgeons, orthodontists,
# pediatric dentists, periodontists, prosthodontists, endodontists, and
# public-health dentists.
DENTAL_TAXONOMY_PREFIX = '122'

NPPES_BATCH_SIZE = 5000

# NPPES CSV column names (verified against the monthly public dissemination file).
NPPES_COL = {
    'npi': 'NPI',
    'org_name': 'Provider Organization Name (Legal Business Name)',
    'first_name': 'Provider First Name',
    'last_name': 'Provider Last Name (Legal Name)',
    'address': 'Provider First Line Business Practice Location Address',
    'city': 'Provider Business Practice Location Address City Name',
    'state': 'Provider Business Practice Location Address State Name',
    'zip_code': 'Provider Business Practice Location Address Postal Code',
    'phone': 'Provider Business Practice Location Address Telephone Number',
    'taxonomy': 'Healthcare Provider Taxonomy Code_1',
    'entity_type': 'Entity Type Code',
}


# ---------- Google Places constants ----------

GOOGLE_PLACES_FIND_URL = 'https://maps.googleapis.com/maps/api/place/findplacefromtext/json'
GOOGLE_PLACES_DETAILS_URL = 'https://maps.googleapis.com/maps/api/place/details/json'

# Phone-friction keywords scanned across review text. A practice with multiple
# reviews mentioning "couldn't get through" or "voicemail" is a strong
# operational-pain signal — exactly the wedge we sell into.
PHONE_FRICTION_KEYWORDS = (
    "couldn't get through",
    'voicemail',
    'on hold',
    'never answers',
    'no one answered',
    "can't reach",
    'busy signal',
)


# ============================================================
# NPPES collector
# ============================================================

@shared_task(
    bind=True,
    base=SovaBaseTask,
    name='collectors.tasks.practice_data.nppes_collector',
    queue='collectors',
    time_limit=7200,        # 2-hour hard kill (CSV is large)
    soft_time_limit=7000,
)
def nppes_collector(self, file_path: str = '/app/data/nppes_data.csv') -> int:
    """Stream the NPPES CSV, filter to dental providers, bulk-upsert into `practices`.

    Returns the number of practice rows written/updated. By convention the base
    task uses the return value as `records_written` in SubFragmentRunLog.

    The CSV is enormous (~7GB). It is streamed with csv.DictReader and never
    loaded into memory. Inserts happen in 5000-row batches via bulk_create with
    update_conflicts=True (PostgreSQL UPSERT).
    """
    # Lazy imports — these models load fine, but keeping imports close to use
    # makes the dependency structure obvious in the task body.
    from core.models import Practice

    csv_path = Path(file_path)
    if not csv_path.exists():
        logger.warning(
            'NPPES CSV not found at %s. Download the monthly file from '
            'https://download.cms.gov/nppes/ and place it at that path, '
            'or pass --file to the import_nppes management command.',
            csv_path,
        )
        return 0

    total_written = 0
    batch: list[Practice] = []
    skipped = 0

    with csv_path.open('r', encoding='utf-8', errors='replace') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                practice = _row_to_practice(row)
            except _RowSkipped:
                skipped += 1
                continue
            except Exception as exc:  # noqa: BLE001 — never crash the whole import
                logger.warning('Skipping malformed NPPES row: %s', exc)
                skipped += 1
                continue

            if practice is None:
                continue

            batch.append(practice)

            if len(batch) >= NPPES_BATCH_SIZE:
                total_written += _upsert_practice_batch(batch)
                batch = []
                if total_written % (NPPES_BATCH_SIZE * 5) == 0:
                    logger.info('NPPES progress: %s practices written', total_written)

        if batch:
            total_written += _upsert_practice_batch(batch)

    logger.info('NPPES import complete: %s written, %s skipped', total_written, skipped)
    return total_written


class _RowSkipped(Exception):
    """Internal signal — a row was intentionally filtered out (not an error)."""


def _row_to_practice(row: dict):
    """Convert one NPPES CSV row to a Practice model instance. Raises _RowSkipped if filtered."""
    from core.models import Practice

    taxonomy = (row.get(NPPES_COL['taxonomy']) or '').strip()
    if not taxonomy.startswith(DENTAL_TAXONOMY_PREFIX):
        raise _RowSkipped()

    npi = (row.get(NPPES_COL['npi']) or '').strip()
    if len(npi) != 10 or not npi.isdigit():
        raise _RowSkipped()

    entity_type_code = (row.get(NPPES_COL['entity_type']) or '').strip()
    entity_type = 'organization' if entity_type_code == '2' else 'individual'

    org_name = (row.get(NPPES_COL['org_name']) or '').strip()
    if org_name:
        practice_name = org_name
    else:
        first = (row.get(NPPES_COL['first_name']) or '').strip()
        last = (row.get(NPPES_COL['last_name']) or '').strip()
        practice_name = f'{first} {last}'.strip()

    if not practice_name:
        raise _RowSkipped()

    zip_full = (row.get(NPPES_COL['zip_code']) or '').strip()

    return Practice(
        npi=npi,
        practice_name=practice_name[:255],
        address_line1=(row.get(NPPES_COL['address']) or '').strip()[:255],
        city=(row.get(NPPES_COL['city']) or '').strip()[:100],
        state=(row.get(NPPES_COL['state']) or '').strip()[:2],
        zip_code=zip_full[:5],
        phone=(row.get(NPPES_COL['phone']) or '').strip()[:20],
        specialty_taxonomy_code=taxonomy[:20],
        entity_type=entity_type,
        updated_at=timezone.now(),  # auto_now doesn't fire on bulk_create+update_conflicts
    )


def _upsert_practice_batch(batch: list) -> int:
    """Bulk-upsert a batch of Practice instances. Returns the batch size."""
    from core.models import Practice

    Practice.objects.bulk_create(
        batch,
        batch_size=len(batch),
        update_conflicts=True,
        unique_fields=['npi'],
        update_fields=[
            'practice_name', 'address_line1', 'city', 'state', 'zip_code',
            'phone', 'specialty_taxonomy_code', 'entity_type', 'updated_at',
        ],
    )
    return len(batch)


# ============================================================
# Google Places collector
# ============================================================

@shared_task(
    bind=True,
    base=SovaBaseTask,
    name='collectors.tasks.practice_data.google_places_collector',
    queue='collectors',
    time_limit=300,
    soft_time_limit=280,
)
def google_places_collector(self, practice_npi: str) -> int:
    """Fetch Google Places data for one practice. Returns 1 on write, 0 otherwise."""
    from collectors.models import GooglePlacesData
    from collectors.schemas.practice_schemas import GooglePlacesDataSchema
    from core.models import Practice

    api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
    if not api_key:
        logger.warning('GOOGLE_MAPS_API_KEY not configured; skipping practice %s', practice_npi)
        return 0

    lock_key = f'sova:lock:google_places:{practice_npi}'
    with distributed_lock(lock_key, timeout=300) as got_lock:
        if not got_lock:
            logger.info('Another worker is collecting %s; skipping', practice_npi)
            return 0

        try:
            practice = Practice.objects.get(npi=practice_npi)
        except Practice.DoesNotExist:
            logger.warning('Practice %s not found in DB', practice_npi)
            return 0

        try:
            candidate = _gplaces_find_place(api_key, practice)
        except Exception as exc:  # noqa: BLE001 — never propagate to Celery
            logger.warning('Google Places find_place failed for %s: %s', practice_npi, exc)
            return 0

        if not candidate or not candidate.get('place_id'):
            logger.info('No Google Places match for %s', practice_npi)
            return 0

        place_id = candidate['place_id']

        try:
            details = _gplaces_details(api_key, place_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning('Google Places details failed for %s: %s', practice_npi, exc)
            details = {}

        friction_keywords = _scan_phone_friction(details.get('reviews') or [])

        try:
            validated = GooglePlacesDataSchema(
                practice_npi=practice_npi,
                google_place_id=place_id,
                review_count=details.get('user_ratings_total'),
                star_rating=details.get('rating'),
                phone_friction_count=len(friction_keywords),
                phone_friction_keywords=friction_keywords,
                opening_hours=details.get('opening_hours'),
            )
        except Exception as exc:  # noqa: BLE001 — Pydantic validation
            logger.warning('Google Places validation failed for %s: %s', practice_npi, exc)
            return 0

        GooglePlacesData.objects.create(
            practice=practice,
            google_place_id=validated.google_place_id or '',
            review_count=validated.review_count,
            star_rating=validated.star_rating,
            phone_friction_count=validated.phone_friction_count,
            phone_friction_keywords=validated.phone_friction_keywords,
            opening_hours=validated.opening_hours,
        )
        return 1


@sova_retry
def _gplaces_find_place(api_key: str, practice) -> Optional[dict]:
    """Find a Google place_id by practice name + address. Returns the first candidate or None."""
    query_parts = [
        practice.practice_name,
        practice.address_line1,
        practice.city,
        practice.state,
    ]
    query = ' '.join(p for p in query_parts if p)
    response = httpx.get(
        GOOGLE_PLACES_FIND_URL,
        params={
            'input': query,
            'inputtype': 'textquery',
            'fields': 'place_id,name,formatted_address,rating,user_ratings_total',
            'key': api_key,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    candidates = data.get('candidates') or []
    return candidates[0] if candidates else None


@sova_retry
def _gplaces_details(api_key: str, place_id: str) -> dict:
    """Fetch Place Details (reviews, hours, aggregated rating)."""
    response = httpx.get(
        GOOGLE_PLACES_DETAILS_URL,
        params={
            'place_id': place_id,
            'fields': 'reviews,opening_hours,rating,user_ratings_total',
            'key': api_key,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get('result') or {}


def _scan_phone_friction(reviews: list) -> list[str]:
    """Return the list of phone-friction keywords found across all review texts (deduplicated)."""
    found: list[str] = []
    for review in reviews:
        text = (review.get('text') or '').lower()
        for keyword in PHONE_FRICTION_KEYWORDS:
            if keyword in text and keyword not in found:
                found.append(keyword)
    return found


# ============================================================
# Fan-out
# ============================================================

@shared_task(name='collectors.tasks.practice_data.google_places_batch')
def google_places_batch(limit: int = 5000) -> int:
    """Fan out Google Places collection across practices in tier order.

    If LeadScore rows exist, practices are ordered HOT > WARM > COLD > unscored.
    Until Phase 5 produces real scores, this just iterates active, non-excluded
    practices by NPI. Returns the number of tasks dispatched.
    """
    from core.models import LeadScore, Practice

    active_qs = Practice.objects.filter(is_active=True, is_oig_excluded=False)

    if LeadScore.objects.filter(is_latest=True).exists():
        tier_rank = {'HOT': 0, 'WARM': 1, 'COLD': 2}
        score_map = dict(
            LeadScore.objects.filter(is_latest=True)
            .values_list('practice_id', 'tier'),
        )
        npis = sorted(
            active_qs.values_list('npi', flat=True),
            key=lambda npi: (tier_rank.get(score_map.get(npi), 3), npi),
        )
    else:
        npis = list(active_qs.values_list('npi', flat=True).order_by('npi'))

    dispatched = 0
    for npi in npis[:limit]:
        google_places_collector.delay(npi)
        dispatched += 1

    logger.info('google_places_batch dispatched %s tasks', dispatched)
    return dispatched
