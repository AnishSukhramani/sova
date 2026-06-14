# MIGRATION_PLAN.md — Sova Build Phases

This is the step-by-step plan for building the Sova Django backend.
Each phase ends with a checkpoint — Anish reviews and approves before the next phase starts.

Track the current phase by marking **[DONE]**, **[IN PROGRESS]**, or **[PENDING]** next to each item.

---

## Phase 0 — Project Skeleton `[PENDING]`

**Goal:** A running Django server with DB connection. Nothing else.

Steps:
- [ ] Create new GitHub repo: `sova`
- [ ] Copy `sova-plan/` folder into repo root
- [ ] `pip install django djangorestframework django-environ psycopg2-binary`
- [ ] `django-admin startproject sova .`
- [ ] Configure `settings.py`:
  - Read from `.env` using `django-environ`
  - Set `DATABASES` to local PostgreSQL
  - Add `rest_framework` to `INSTALLED_APPS`
- [ ] Create `.env` with local DB credentials
- [ ] Create the `sova` database in pgAdmin 4
- [ ] Run `python manage.py migrate` (applies Django built-in migrations)
- [ ] Run `python manage.py runserver` — confirm it loads at `localhost:8000`

**Checkpoint:** Server runs, DB connects, `/admin` loads at `localhost:8000/admin`

---

## Phase 1 — Core Models `[PENDING]`

**Goal:** All four core tables exist in PostgreSQL, visible in Django Admin.

Steps:
- [ ] Create `core` app — abstract `BaseModel` (uuid id, created_at, updated_at)
- [ ] Create `practices` app — `Practice` model
- [ ] Create `signals_app` app — `Signal` model with type enum
- [ ] Create `opportunities` app — `Opportunity` model + `Evidence` model
- [ ] Register all models in Django Admin
- [ ] Run `makemigrations` + `migrate`
- [ ] Open pgAdmin 4 — confirm tables exist with correct columns

**Checkpoint:** All tables visible in pgAdmin 4 and Django Admin. Can create a test Practice record via Admin.

---

## Phase 2 — REST API Endpoints `[PENDING]`

**Goal:** All core endpoints return data. Can be tested with curl or Postman.

Steps:
- [ ] Add DRF serializers for Practice, Signal, Opportunity, Evidence
- [ ] Add DRF views (ListAPIView, RetrieveAPIView) for each
- [ ] Wire up URLs in `sova/urls.py`
- [ ] Test with curl:
  - `GET /api/practices/`
  - `GET /api/opportunities/`
  - `GET /api/signals/`
- [ ] Add basic filtering (opportunities by score, signals by type)

**Checkpoint:** All GET endpoints return JSON. Filtering works.

---

## Phase 3 — Fragment Runner `[PENDING]`

**Goal:** Can run `python manage.py run_fragment <name>` and it dispatches to the right fragment.

Steps:
- [ ] Create `fragments` app
- [ ] Create `run_fragment` management command (dispatcher)
- [ ] Port `scoring.py` constants and score calculation logic
- [ ] Implement `score` fragment first (pure DB logic, no external APIs)
- [ ] Test: insert dummy signals, run `python manage.py run_fragment score`, confirm opportunities created

**Checkpoint:** Score fragment runs end-to-end on dummy data. Opportunities appear in DB.

---

## Phase 4 — Jobs Fragment `[PENDING]`

**Goal:** `python manage.py run_fragment jobs` scrapes DentalPost and writes signals.

Steps:
- [ ] Port `workers/lib/job-signal.js` to Python (`fragments/jobs.py`)
- [ ] Use `httpx` + `beautifulsoup4` for HTML parsing
- [ ] Write `job_frontdesk` and `chronic_turnover` signals to `sova_signal`
- [ ] Write job post history to a new `sova_job_post_history` table
- [ ] Test with real DentalPost URL

**Checkpoint:** Signals written to DB from live DentalPost data.

---

## Phase 5 — Reviews Fragment `[PENDING]`

**Goal:** `python manage.py run_fragment reviews` finds phone friction signals.

Steps:
- [ ] Port `workers/lib/reviews.js` to Python (`fragments/reviews.py`)
- [ ] Use `google-api-python-client` for Google Places API
- [ ] Write `phone_friction` signals
- [ ] Test with a known practice domain

**Checkpoint:** Phone friction signals written for at least one real practice.

---

## Phase 6 — Website + Tech Stack Fragments `[PENDING]`

**Goal:** Detect `low_automation` and `legacy_tech_stack` signals from practice websites.

Steps:
- [ ] Port `workers/lib/website.js` → `fragments/website.py`
- [ ] Port `workers/lib/tech-stack.js` → `fragments/tech_stack.py`
- [ ] Use `httpx` for page fetch, `beautifulsoup4` for parsing
- [ ] Write signals for detected patterns

**Checkpoint:** Signals generated from a real practice website.

---

## Phase 7 — NPPES Fragment `[PENDING]`

**Goal:** Ingest NPPES CSV and populate `sova_practice` table.

Steps:
- [ ] Port `workers/lib/nppes.js` → `fragments/nppes.py`
- [ ] Use Python `csv` module for streaming large CSV
- [ ] Upsert practices by NPI

**Checkpoint:** Practice table populated from local NPPES CSV file.

---

## Phase 8 — Chat Agent `[PENDING]`

**Goal:** `POST /api/chat/` works — Sova AI responds with context from the DB.

Steps:
- [ ] Create `chat` app
- [ ] Port tool logic (opportunities, signals, practices, evidence queries)
- [ ] Port system prompt and user prompt builder
- [ ] Port OpenAI streaming logic using Python `openai` SDK
- [ ] Wire up `POST /api/chat/` endpoint (streaming SSE response)
- [ ] Test with curl: send a message, receive a streamed response

**Checkpoint:** Chat endpoint streams a response that references real DB data.

---

## Phase 9 — Classification `[PENDING]`

**Goal:** `POST /api/opportunities/<id>/classify/` runs OpenAI classification.

Steps:
- [ ] Create `classifier` app
- [ ] Port classification prompt and response parsing
- [ ] Update opportunity `recommended_*` fields
- [ ] Test via curl on a real opportunity

**Checkpoint:** Classification runs and updates DB record.

---

## Phase 10 — Social Publishing `[PENDING]`

**Goal:** Can draft and publish a post to Facebook or LinkedIn from an opportunity.

Steps:
- [ ] Create `social` app with `SocialPost` and `SocialAccount` models
- [ ] Port Facebook Graph API call
- [ ] Port LinkedIn REST API call
- [ ] Add `POST /api/social/publish/` endpoint
- [ ] Test with a real social account token

**Checkpoint:** Post published to at least one channel.

---

## Phase 11 — Dockerization `[PENDING]`

**Goal:** Entire backend runs in Docker with one command.

Steps:
- [ ] Write `Dockerfile` for Django app
- [ ] Write `docker-compose.yml` with services: web, db, redis
- [ ] Test: `docker compose up` → all services run
- [ ] Confirm all fragments still work inside container

**Checkpoint:** `docker compose up` starts everything. All endpoints respond.

---

## Phase 12 — GCP Deployment `[PENDING]`

**Goal:** Backend running on GCP Cloud Run.

Steps:
- [ ] Push Docker image to GCP Artifact Registry
- [ ] Create Cloud Run service
- [ ] Set up GCP Cloud SQL (PostgreSQL) as production DB
- [ ] Set environment variables in Cloud Run
- [ ] Update Next.js frontend `NEXT_PUBLIC_API_URL` to point at Cloud Run URL

**Checkpoint:** API accessible at a public GCP URL. Frontend talks to Django.

---

## Deferred (Post-Phase 12)

These are the "missing fragments" that extend beyond replicating legacy:
- `outreach` fragment — personalized cold email from lead signals
- `content` fragment — auto-generate LinkedIn/blog posts from aggregate data
- `feedback` fragment — track which leads converted, which content drove clicks
- Celery + Redis — replace management commands with proper async task queue
- Celery Beat — replace manual cron with scheduled tasks
- New chat SDK — replace the primitive Next.js chat with the preferred SDK
