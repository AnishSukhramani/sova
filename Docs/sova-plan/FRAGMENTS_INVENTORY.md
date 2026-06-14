# FRAGMENTS_INVENTORY.md — Legacy Fragments Reference

Every fragment from the legacy Node.js system is documented here.
Use this as the source of truth when porting each fragment to Django Python.

---

## Fragment: `jobs`

**Legacy file:** `workers/lib/job-signal.js`
**Run command (legacy):** `pnpm run worker -- jobs`
**Django target:** `fragments/jobs.py` + `python manage.py run_fragment jobs`

### What it does
1. Fetches job listings from DentalPost (HTML page + JSON-LD structured data)
2. Parses each listing for: practice name, domain, job title, location, date posted
3. Normalizes job titles (e.g., "Front Office Coordinator" → "front_desk")
4. Writes each listing to `job_post_history_athena`
5. Checks if the same practice has posted the same normalized role 3+ times in the past 12 months
6. Emits `job_frontdesk` signal for any new front desk posting
7. Emits `chronic_turnover` signal if chronic re-posting detected

### Inputs
- DentalPost HTML pages (public, no auth required)
- Environment: none required

### Outputs (DB writes)
- `job_post_history_athena` (→ `sova_job_post_history`): one row per job listing
- `signals_athena` (→ `sova_signal`): `job_frontdesk` signals
- `signals_athena` (→ `sova_signal`): `chronic_turnover` signals

### Key logic to replicate
```python
# Chronic turnover detection
posts_in_last_year = JobPostHistory.objects.filter(
    practice=practice,
    job_title_norm="front_desk",
    date_posted__gte=one_year_ago
).count()

if posts_in_last_year >= 3:
    Signal.objects.create(type="chronic_turnover", practice=practice, strength=posts_in_last_year)
```

### Python dependencies needed
- `httpx` — fetch DentalPost pages
- `beautifulsoup4` — parse HTML
- Standard `json` — parse JSON-LD

---

## Fragment: `reviews`

**Legacy file:** `workers/lib/reviews.js`
**Run command (legacy):** `pnpm run worker -- reviews`
**Django target:** `fragments/reviews.py` + `python manage.py run_fragment reviews`

### What it does
1. For each known practice domain, calls Google Places API to find the place
2. Fetches the practice's reviews
3. Scans review text for phone-related negative keywords:
   - "couldn't get through", "no answer", "voicemail", "busy", "hold", "wait", "hang up"
4. Emits `phone_friction` signal with review snippet as metadata

### Inputs
- `practices_athena` table (practice domains)
- Google Maps API (`GOOGLE_MAPS_API_KEY`)

### Outputs (DB writes)
- `signals_athena` (→ `sova_signal`): `phone_friction` signals

### Key logic to replicate
```python
PHONE_FRICTION_KEYWORDS = [
    "couldn't get through", "no answer", "voicemail full",
    "busy signal", "on hold", "wait time", "hung up"
]

for review in place_reviews:
    if any(kw in review.text.lower() for kw in PHONE_FRICTION_KEYWORDS):
        Signal.objects.create(
            type="phone_friction",
            practice=practice,
            strength=1,
            metadata={"review_snippet": review.text[:200], "rating": review.rating}
        )
```

### Python dependencies needed
- `google-api-python-client` — Google Places API

---

## Fragment: `nppes`

**Legacy file:** `workers/lib/nppes.js`
**Run command (legacy):** `pnpm run worker -- nppes`
**Django target:** `fragments/nppes.py` + `python manage.py run_fragment nppes`

### What it does
1. Reads a large NPPES CSV file (NPI registry — official US provider database)
2. Filters for dental/medical provider types
3. For each provider: extracts NPI, practice name, address, phone
4. Upserts into `practices_athena` — creates new or enriches existing records

### Inputs
- Local NPPES CSV file path (`NPPES_CSV_PATH` env var)

### Outputs (DB writes)
- `practices_athena` (→ `sova_practice`): upsert by NPI number

### Key logic to replicate
```python
import csv

DENTAL_TAXONOMY_CODES = ["122300000X", "1223G0001X", "1223P0221X"]  # dentist codes

with open(nppes_path, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row["Healthcare Provider Taxonomy Code_1"] in DENTAL_TAXONOMY_CODES:
            Practice.objects.update_or_create(
                npi=row["NPI"],
                defaults={
                    "name": row["Provider Organization Name (Legal Business Name)"],
                    "phone": row["Provider Business Practice Location Address Telephone Number"],
                    ...
                }
            )
```

### Python dependencies needed
- Standard `csv` module (no external deps)

---

## Fragment: `website`

**Legacy file:** `workers/lib/website.js`
**Run command (legacy):** `pnpm run worker -- website`
**Django target:** `fragments/website.py` + `python manage.py run_fragment website`

### What it does
1. For each practice with a known domain, fetches the homepage
2. Checks for presence of online booking widgets / automation features:
   - Looks for Zocdoc, Doctible, NexHealth, Kareo, Weave booking iframe/scripts
   - Checks for "book online", "schedule appointment" call-to-action links
3. If none found → emits `low_automation` signal

### Inputs
- `practices_athena` table (practice domains)

### Outputs (DB writes)
- `signals_athena` (→ `sova_signal`): `low_automation` signals

### Key logic to replicate
```python
BOOKING_INDICATORS = [
    "zocdoc.com", "doctible.com", "nexhealth.com", "kareo.com",
    "book online", "schedule appointment", "request appointment"
]

html = httpx.get(f"https://{practice.domain}").text.lower()
has_booking = any(indicator in html for indicator in BOOKING_INDICATORS)

if not has_booking:
    Signal.objects.create(type="low_automation", practice=practice, strength=1)
```

### Python dependencies needed
- `httpx` — fetch website
- `beautifulsoup4` — optional, for cleaner parsing

---

## Fragment: `tech_stack`

**Legacy file:** `workers/lib/tech-stack.js`
**Run command (legacy):** `pnpm run worker -- tech_stack`
**Django target:** `fragments/tech_stack.py` + `python manage.py run_fragment tech_stack`

### What it does
1. Fetches the practice website
2. Scans HTML source for signatures of legacy practice management systems (PMS):
   - Dentrix, Eaglesoft, Carestream, PracticeWorks, Dentimax
3. Optionally calls BuiltWith API for deeper tech stack detection
4. If legacy PMS found → emits `legacy_tech_stack` signal

### Inputs
- `practices_athena` table (practice domains)

### Outputs (DB writes)
- `signals_athena` (→ `sova_signal`): `legacy_tech_stack` signals

### Key logic to replicate
```python
LEGACY_PMS_SIGNATURES = [
    "dentrix", "eaglesoft", "carestream", "practiceworks",
    "dentimax", "softdent", "patterson dental"
]

html = httpx.get(f"https://{practice.domain}").text.lower()
matches = [pms for pms in LEGACY_PMS_SIGNATURES if pms in html]

if matches:
    Signal.objects.create(
        type="legacy_tech_stack",
        practice=practice,
        strength=len(matches),
        metadata={"detected_systems": matches}
    )
```

### Python dependencies needed
- `httpx`
- `beautifulsoup4`

---

## Fragment: `score`

**Legacy file:** `workers/lib/scoring.js`
**Run command (legacy):** `pnpm run worker -- score`
**Django target:** `fragments/score.py` + `python manage.py run_fragment score`

### What it does
1. Reads all practices that have signals
2. For each practice, sums signal weights (see constants below)
3. Caps score at 100
4. Checks evidence gate: must have at least one "strong signal" type
5. Deduplicates: only one opportunity per practice per day
6. Respects `OPPORTUNITY_DAILY_CAP` (default 50)
7. Calls OpenAI to generate a summary paragraph
8. Writes opportunity + evidence rows to DB

### Signal weights
```python
SIGNAL_WEIGHTS = {
    "job_frontdesk": 35,
    "chronic_turnover": 20,
    "legacy_tech_stack": 20,
    "phone_friction": 15,
    "low_automation": 15,
    "new_practice": 10,
    "competitor_xray_engagement": 10,
}
STRONG_SIGNAL_TYPES = {"job_frontdesk", "chronic_turnover", "phone_friction"}
MAX_SCORE = 100
```

### Inputs
- `signals_athena` table
- `practices_athena` table
- `OPPORTUNITY_DAILY_CAP` env var
- OpenAI API

### Outputs (DB writes)
- `opportunities_athena` (→ `sova_opportunity`): scored opportunity per practice
- `evidence_athena` (→ `sova_evidence`): supporting evidence per opportunity

### Python dependencies needed
- `openai`

---

## Fragment: `ad_library`

**Legacy file:** `workers/lib/ad-library.js`
**Run command (legacy):** `pnpm run worker -- ad_library`
**Django target:** `fragments/ad_library.py` + `python manage.py run_fragment ad_library`

### What it does
1. Uses Hyperbrowser to navigate Meta Ad Library
2. Searches for competitors running dental/voice AI ads
3. Tracks ad headlines, run duration, frequency
4. Writes to `voice_ai_competitors_athena` and `voice_ai_ad_snapshots_athena`

### Inputs
- `COMPETITOR_FB_PAGES_JSON` — JSON list of competitor Facebook pages to monitor
- `HYPERBROWSER_API_KEY`

### Outputs (DB writes)
- `voice_ai_competitors_athena` (→ `sova_voice_ai_competitor`)
- `voice_ai_ad_snapshots_athena` (→ `sova_voice_ai_ad_snapshot`)

### Python dependencies needed
- `hyperbrowser-sdk` (Python package, or use `playwright` as alternative)

---

## Fragment: `competitor_xray`

**Legacy file:** `workers/lib/competitor-xray.js`
**Run command (legacy):** `pnpm run worker -- competitor_xray`
**Django target:** `fragments/competitor_xray.py`

### What it does
1. Uses Hyperbrowser to scrape engagement on competitor LinkedIn posts
2. Extracts commenters — potential warm leads (practice owners engaging with competitors)
3. Emits `competitor_xray_engagement` signals for matched practices

### Inputs
- `XRAY_LINKEDIN_POST_URLS` — JSON list of competitor LinkedIn post URLs to monitor
- `HYPERBROWSER_API_KEY`

### Outputs (DB writes)
- `signals_athena` (→ `sova_signal`): `competitor_xray_engagement` signals

### Python dependencies needed
- `hyperbrowser-sdk` or `playwright`

---

## Fragment: `voice_ai_scout`

**Legacy file:** `workers/lib/voice-ai-scout.js`
**Run command (legacy):** `pnpm run worker -- voice_ai_scout`
**Django target:** `fragments/voice_ai_scout.py`

### What it does
Tracks voice AI competitors in the healthcare/dental market:
1. Monitors Meta Ad Library for healthcare voice AI ads
2. Monitors Creator Marketplace
3. Writes competitor profiles and ad snapshots

### Inputs
- `HYPERBROWSER_API_KEY`

### Outputs (DB writes)
- `voice_ai_competitors_athena` (→ `sova_voice_ai_competitor`)
- `voice_ai_ad_snapshots_athena` (→ `sova_voice_ai_ad_snapshot`)

---

## Build Priority Order

Port fragments in this order (easiest → most external dependencies):

1. `score` — pure DB logic, no external APIs, verifiable immediately
2. `nppes` — file-based, no API, large but simple
3. `jobs` — HTTP + HTML parsing, no auth
4. `website` — HTTP + HTML parsing, no auth
5. `tech_stack` — HTTP + HTML parsing, no auth
6. `reviews` — requires Google Maps API key
7. `ad_library` — requires Hyperbrowser (complex)
8. `competitor_xray` — requires Hyperbrowser (complex)
9. `voice_ai_scout` — requires Hyperbrowser (complex)

---

## New Fragments (Not in Legacy — Build After Migration)

| Fragment | Purpose | Priority |
|---|---|---|
| `outreach` | Draft personalized cold email from lead signals | High |
| `content` | Generate LinkedIn/blog posts from aggregate signal data | High |
| `feedback` | Track conversions and content performance | Medium |
| `email_send` | Send drafted emails via SendGrid/Postmark | Medium |
| `seo` | Generate SEO landing page content | Low |
