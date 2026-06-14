# ARCHITECTURE.md — Sova Technical Decisions

Every significant technical decision is recorded here with its rationale.
Before changing any of these decisions, discuss with Anish first.

---

## ADR-001: Django over Node.js for the backend

**Decision:** Rebuild the backend in Django (Python), not Node.js.

**Rationale:**
- The existing Node.js backend was never planned — it evolved ad-hoc
- Python is the native ecosystem for AI/ML work (OpenAI, LangChain, BeautifulSoup, Playwright all have richer Python SDKs)
- Django + Celery is the industry standard for background task queues — far superior to pnpm shell scripts
- Django Admin gives free internal tooling (data visibility, manual overrides) with zero extra code
- Django REST Framework (DRF) makes clean, consistent APIs straightforward
- Anish wants to learn Django — this is also an educational objective

**Trade-off accepted:**
- Full rewrite cost (mitigated by keeping frontend untouched and reusing the same DB schema logic)

---

## ADR-002: Local PostgreSQL over Supabase

**Decision:** Use a local PostgreSQL instance (managed via pgAdmin 4) instead of Supabase.

**Rationale:**
- Supabase is hosted Postgres with a wrapper — the underlying DB engine is identical
- Anish already has pgAdmin 4 installed and has experience with it
- Local Postgres is free, has no API rate limits, and removes a dependency on an external service
- In production, a hosted Postgres (GCP Cloud SQL, Supabase, Railway) can be swapped in by just changing the connection string — no code changes needed
- Removes Supabase JS client dependency entirely

**Migration path:**
- Local PostgreSQL for development
- GCP Cloud SQL (managed Postgres) for production when deployment is ready
- Schema is identical — just a different `DATABASE_URL`

**Database naming:**
- Legacy tables used `_athena` suffix (e.g., `opportunities_athena`)
- New tables use `sova_` prefix via Django app labels (e.g., `sova_opportunities`)
- Django handles this via `app_label` and `db_table` in Meta classes

---

## ADR-003: Django Management Commands for fragments (not Celery yet)

**Decision:** Implement each fragment as a Django management command first. Add Celery later.

**Rationale:**
- Celery adds significant infrastructure complexity (Redis broker, worker processes, monitoring)
- For local development and learning, management commands are simpler and transparent
- `python manage.py run_fragment jobs` is easy to understand and debug
- Once the logic is stable and correct, wrapping it in a Celery task is straightforward

**Upgrade path:**
- Phase 1: `management/commands/run_fragment.py` dispatches to fragment classes
- Phase 2: Fragment classes become Celery tasks with `@app.task` decorator
- Phase 3: Celery Beat handles scheduling (replaces manual cron)

---

## ADR-004: Keep Next.js frontend untouched

**Decision:** Do not rewrite or modify the existing Next.js frontend in this phase.

**Rationale:**
- The frontend works and is not the source of architectural problems
- Rewriting the frontend simultaneously with the backend doubles the risk and timeline
- The frontend will eventually point its API calls at the Django backend instead of Next.js API routes — this is a config change, not a code rewrite
- A separate frontend decision (new chat SDK, UI overhaul) can be made after the backend is stable

**Future action:**
- When Django backend is stable, update `NEXT_PUBLIC_API_URL` in the Next.js app to point at Django
- Optionally replace the chat component with the preferred SDK at that time

---

## ADR-005: No Docker until local backend is stable

**Decision:** Build and run locally first. Dockerize only after all fragments run correctly.

**Rationale:**
- Docker adds complexity to the development loop (build times, volume mounts, networking)
- Debugging is harder inside a container when learning a new framework
- Containerization is a packaging concern, not a logic concern — it should come last

**Dockerization plan (when ready):**
```
docker-compose.yml
  services:
    web:      Django API (gunicorn)
    worker:   Celery worker
    beat:     Celery Beat scheduler
    redis:    Redis broker
    db:       PostgreSQL (or use GCP Cloud SQL in prod)
```

---

## ADR-006: OpenAI gpt-4o-mini for all AI calls

**Decision:** Use `gpt-4o-mini` for classification and chat, same as legacy system.

**Rationale:**
- Already proven in the legacy system
- Cost-effective for high-volume classification
- Can be upgraded to `gpt-4o` or `claude-opus-4-6` for specific tasks later

---

## Application Structure

```
sova/                          ← repo root (new GitHub repo)
├── manage.py
├── requirements.txt
├── .env                       ← never committed
├── .env.example               ← committed template
├── sova/                      ← Django project settings package
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                      ← shared utilities, base classes
│   ├── models.py              ← abstract base model (id, created_at, updated_at)
│   └── utils.py
├── practices/                 ← Practice model + CRUD endpoints
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
├── signals_app/               ← Signal model + ingestion (named to avoid Django signals conflict)
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
├── opportunities/             ← Opportunity + evidence models + scoring
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── scoring.py             ← scoring engine (ported from workers/lib/scoring.js)
│   └── urls.py
├── fragments/                 ← Fragment runner + all fragment logic
│   ├── management/
│   │   └── commands/
│   │       └── run_fragment.py   ← entry point: python manage.py run_fragment <name>
│   ├── jobs.py                ← jobs fragment (DentalPost)
│   ├── reviews.py             ← reviews fragment (Google Places)
│   ├── nppes.py               ← NPPES CSV ingest
│   ├── website.py             ← website automation detection
│   ├── tech_stack.py          ← legacy PMS detection
│   ├── score.py               ← scoring fragment
│   ├── ad_library.py          ← Meta Ad Library
│   └── competitor_xray.py     ← LinkedIn x-ray
├── chat/                      ← Chat agent (Sova AI)
│   ├── agent.py               ← core agent logic
│   ├── tools.py               ← tool definitions
│   ├── views.py               ← /api/chat endpoint
│   └── urls.py
├── classifier/                ← OpenAI classification
│   ├── classify.py
│   ├── views.py
│   └── urls.py
└── social/                    ← Social publishing
    ├── models.py
    ├── publishers.py          ← Facebook, LinkedIn
    ├── views.py
    └── urls.py
```

---

## API Endpoint Map

| Method | Endpoint | App | Description |
|---|---|---|---|
| GET | `/api/practices/` | practices | List practices |
| GET | `/api/practices/<id>/` | practices | Practice detail |
| GET | `/api/signals/` | signals_app | List signals (filter by type, practice) |
| GET | `/api/opportunities/` | opportunities | List opportunities (filter by score, state) |
| GET | `/api/opportunities/<id>/` | opportunities | Opportunity detail + evidence |
| POST | `/api/opportunities/<id>/classify/` | classifier | Run OpenAI classification |
| POST | `/api/opportunities/<id>/accept/` | opportunities | HITL accept/reject |
| POST | `/api/chat/` | chat | Chat message (streaming + non-streaming) |
| POST | `/api/social/publish/` | social | Publish to Facebook/LinkedIn |

---

## Signal Weight Constants

Replicated from `workers/lib/constants.js`:

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
MAX_SCORE = 100
OPPORTUNITY_DAILY_CAP = 50  # from env
STRONG_SIGNAL_TYPES = {"job_frontdesk", "chronic_turnover", "phone_friction"}
```

---

## Database Schema (Django models → PostgreSQL tables)

| Django Model | Table name | Key fields |
|---|---|---|
| `practices.Practice` | `sova_practice` | id, name, domain, phone, locations, npi_ids |
| `signals_app.Signal` | `sova_signal` | id, practice, type, strength, timestamp, metadata |
| `opportunities.Opportunity` | `sova_opportunity` | id, practice, score, summary, recommended_*, accepted_* |
| `opportunities.Evidence` | `sova_evidence` | id, opportunity, type, content, source_url |
| `social.SocialPost` | `sova_social_post` | id, channel, content, status, published_at |
| `social.SocialAccount` | `sova_social_account` | id, channel, account_id, access_token |

---

## Dependencies (requirements.txt baseline)

```
django>=4.2
djangorestframework>=3.15
django-environ>=0.11
psycopg2-binary>=2.9
openai>=1.0
requests>=2.31
beautifulsoup4>=4.12
httpx>=0.27
python-dotenv>=1.0
pydantic>=2.0
```

Add only when needed:
```
celery>=5.3          ← Phase 2 (task queue)
redis>=5.0           ← Phase 2 (Celery broker)
hyperbrowser-sdk     ← when scraping fragments are ported
google-api-python-client  ← when reviews/maps fragment is ported
```
