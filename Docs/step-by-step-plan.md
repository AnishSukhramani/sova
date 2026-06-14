SOVA — Complete Step-by-Step Path to Success
The Engineering Manager's Execution Manual for Claude Code

HOW TO USE THIS DOCUMENT
You (the founder) sit at the terminal. Claude Code builds. Each numbered step below is one focused Claude Code session. You paste the prompt, Claude Code executes, you verify the "Done When" criteria, then move to the next step. Do not skip steps. Do not combine steps. Each step builds on the previous one.
Convention used below:

🔧 CLAUDE CODE PROMPT = What you type/paste into Claude Code
✅ DONE WHEN = How you verify success before moving on
👤 FOUNDER ACTION = Something you do manually (not Claude Code)


PRE-FLIGHT: ENVIRONMENT SETUP
Step 0.0 — Create Project Directory & Environment File
👤 FOUNDER ACTION (do this yourself in terminal):
bashCopymkdir sova && cd sova
Then create your .env file manually with your real API keys:
bashCopycat > .env << 'EOF'
# Database
POSTGRES_DB=sova
POSTGRES_USER=sova
POSTGRES_PASSWORD=changeme_in_production
DATABASE_URL=postgresql://sova:changeme_in_production@db:5432/sova

# Redis
REDIS_URL=redis://redis:6379/0

# Django
DJANGO_SECRET_KEY=your-secret-key-generate-a-real-one
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# LLM
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here

# Observability
LANGSMITH_API_KEY=ls__your-key-here
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=sova
SENTRY_DSN=

# Data Source API Keys (add as you get them)
GOOGLE_MAPS_API_KEY=
HUNTER_API_KEY=
PROXYCURL_API_KEY=
FACEBOOK_APP_ID=
FACEBOOK_APP_SECRET=
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
YOUTUBE_API_KEY=
GMAIL_CREDENTIALS_PATH=/app/credentials/gmail.json
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
YELP_API_KEY=
JSEARCH_API_KEY=
SOVA_API_KEY=sova-dev-key-change-in-production
EOF
Step 0.1 — Create the CLAUDE.md Project Context File
👤 FOUNDER ACTION — Create this file so Claude Code understands the entire project:
bashCopycat > CLAUDE.md << 'CLAUDEEOF'
# SOVA — Claude Code Project Context

## What This Project Is
Sova is an autonomous marketing intelligence backend for Neurality Health (AI voice receptionist for dental practices). It collects signals from 110+ internet sources, scores them into composite lead scores, and generates outreach intelligence. Pure backend — no frontend in v1.

## Architecture (4 Layers)
- **Layer 1**: 110+ Celery task data collectors (sub-fragments), each writes to its own DB table
- **Layer 2**: 28 async intelligence tools that read from those tables and answer business questions
- **Layer 3**: Orchestrator (Celery Beat scheduling, health monitoring, task status tracking)
- **Layer 4**: Chatbot agent (v2 — scaffold now, build Phase 10)

## Critical Architecture Rules
1. **Database-as-communication-bus**: Sub-fragments NEVER call each other. PostgreSQL is the only shared state.
2. **Correctness before optimization**: Primary developer is learning Django. Idiomatic patterns, explained code.
3. **Design for 10x, build for 1x**: Schema supports 2M records. Deployment starts single-node Docker Compose.

## Tech Stack
- Django 4.2+, DRF, PostgreSQL 16 (pgvector), Redis 7, Celery 5.4+, LangGraph 1.0+, Anthropic Claude
- Docker Compose with 7 services: db, redis, web, celery-worker-collectors, celery-worker-tools, celery-beat, flower

## Django Apps (6)
- `core/` — Practice, SubFragmentRunLog, Signal, LeadScore, shared utilities
- `collectors/` — All 110+ sub-fragment Celery tasks, Pydantic schemas, output models
- `tools/` — 28 intelligence tools, Pydantic schemas, DRF views
- `orchestrator/` — SovaTaskRun, health endpoints, scheduling coordination
- `chatbot/` — LangGraph graph, checkpointer, router (v2 scaffold)
- `knowledge/` — SovaKnowledge model, DatabaseKnowledgeStore, YAML/MD sources

## 8 Mandatory Patterns for Every Sub-fragment
1. Tenacity retry (sova_retry: 3 attempts, exp backoff)
2. Django cache distributed mutex (cache.add, 300s timeout)
3. SubFragmentRunLog update on every execution
4. Pydantic output schema validation before DB write
5. Sensitive data sanitization (sanitize_for_log)
6. HTTP request timeout (30s for sync, 60s for async)
7. SovaConfig import for all configurable values
8. connections.close_all() in finally block

## 10 Mandatory Patterns for Every Intelligence Tool
1. Pydantic structured output on every LLM call
2. Anthropic prompt caching (cache_control: ephemeral)
3. Two-level knowledge cache (in-process dict + Redis)
4. Parallel DB reads (asyncio.gather with Semaphore(8))
5. Confidence scoring (HIGH/MODERATE/LOW)
6. pgvector knowledge base retrieval
7. SQL safety layer for chatbot
8. Tool error handling (never raise, always return)
9. Partial result synthesis on recursion limit
10. Token caps per tool

## Key Models
- `practices` — NPI as PK, ~200K rows
- `signals` — Central signal store with decay metadata
- `lead_scores` — Versioned (append-only, is_latest flag)
- `sub_fragment_run_log` — Health tracking per collector
- 29 sub-fragment output tables (job_postings, google_places_data, etc.)

## Commands Never to Run
- Never run git commands (developer manages git)
- Never modify .env directly (founder manages secrets)

## Testing
- After every model change: `docker compose exec web python manage.py makemigrations && docker compose exec web python manage.py migrate`
- After every endpoint: test with curl or the DRF browsable API
- After every Celery task: verify via Flower at localhost:5555

## LLM Configuration
- Classification/routing: claude-haiku-4-5-20251001
- Generation (outreach briefs, reports): claude-sonnet-4-6
- Embeddings only: text-embedding-3-small (OpenAI, 1536 dim)
CLAUDEEOF
✅ DONE WHEN: You have a sova/ directory containing .env and CLAUDE.md

PHASE 0 — FOUNDATION
Goal: Project skeleton, infrastructure, shared utilities. All 7 Docker services running. Health endpoint returns 200.

Step 0.2 — Requirements, Dockerfile, Docker Compose
🔧 CLAUDE CODE PROMPT:
CopyCreate the foundational project files for Sova. Do NOT initialize git. Create these files in the project root:

1. `requirements.txt` with these exact packages and version constraints:
   - django>=4.2,<5.1
   - djangorestframework>=3.15
   - django-cors-headers>=4.3
   - drf-yasg>=1.21
   - celery>=5.4
   - django-celery-beat>=2.6
   - redis>=5.0
   - django-redis>=5.4
   - psycopg[binary]>=3.1
   - langchain-core>=0.3
   - langchain-anthropic>=1.4
   - langsmith>=0.2
   - pydantic>=2.7
   - tenacity>=8.3
   - httpx>=0.27
   - beautifulsoup4>=4.12
   - feedparser>=6.0
   - sentry-sdk[django,celery]>=2.0
   - flower>=2.0
   - gunicorn>=22.0
   - python-dotenv>=1.0

2. `Dockerfile` — Python 3.12 slim base, install requirements, set workdir to /app, copy project

3. `docker-compose.yml` with these 7 services matching the architecture doc exactly:
   - db: pgvector/pgvector:pg16, health check, volume postgres_data
   - redis: redis:7-alpine, health check, volume redis_data
   - web: gunicorn with 4 workers on port 8000, depends on db+redis healthy
   - celery-worker-collectors: -Q collectors,default -c 8 --prefetch-multiplier 1
   - celery-worker-tools: -Q tools,llm -c 4 --prefetch-multiplier 1
   - celery-beat: DatabaseScheduler
   - flower: port 5555
   All app services use build context, env_file .env, volume mount .:/app, restart unless-stopped

4. `.env.example` with all environment variables (placeholder values, well-commented)
✅ DONE WHEN: All 4 files exist and docker compose config runs without errors

Step 0.3 — Django Project Scaffold
🔧 CLAUDE CODE PROMPT:
CopyCreate the Django project structure for Sova. The project package is `sova/` inside the project root (so sova/sova/ contains settings.py etc). Create:

1. `manage.py` at project root

2. `sova/__init__.py` with Celery app import:
   from .celery import app as celery_app
   __all__ = ('celery_app',)

3. `sova/settings.py` configured for:
   - Load env vars from .env using python-dotenv
   - INSTALLED_APPS: django defaults + rest_framework, corsheaders, drf_yasg, django_celery_beat, core, collectors, tools, orchestrator, chatbot, knowledge
   - DATABASES using DATABASE_URL env var parsed into Django format (use dj-database-url pattern manually or parse the URL)
   - CACHES with django-redis backend pointing to REDIS_URL
   - CELERY_BROKER_URL and CELERY_RESULT_BACKEND from REDIS_URL
   - CELERY_TASK_SERIALIZER = 'json', CELERY_ACCEPT_CONTENT = ['json']
   - CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
   - REST_FRAMEWORK with DEFAULT_PAGINATION_CLASS (PageNumberPagination, page_size=50)
   - Sentry SDK init if SENTRY_DSN is set
   - CORS_ALLOW_ALL_ORIGINS = True (dev only)
   - LangSmith settings from env vars

4. `sova/urls.py` with admin + api/v1/ URL namespace stubs for core, tools, orchestrator, chatbot

5. `sova/wsgi.py` and `sova/asgi.py`

6. `sova/celery.py` — Celery app configuration:
   - App name 'sova'
   - config_from_object django settings with CELERY_ namespace
   - autodiscover_tasks for collectors and orchestrator

7. `sova/config.py` — The complete SovaConfig class exactly as specified in the PRD (all constants: LLM models, scoring thresholds, celery timeouts, rate limits, chatbot settings, knowledge base settings, token caps, SQL safety patterns, signal decay half-lives, is_langsmith_enabled classmethod)

8. Create empty Django app directories with __init__.py for: core, collectors, tools, orchestrator, chatbot, knowledge — each with __init__.py, models.py, admin.py, and apps.py with correct app config
✅ DONE WHEN: docker compose up -d db redis starts, then docker compose run --rm web python manage.py check succeeds

Step 0.4 — Core Utilities (Shared Infrastructure)
🔧 CLAUDE CODE PROMPT:
CopyCreate the core utilities that every sub-fragment and tool in Sova will use. These go in core/utils/:

1. `core/utils/__init__.py`

2. `core/utils/retry.py` — The sova_retry decorator using tenacity:
   - stop_after_attempt(3)
   - wait_exponential(multiplier=1, min=1, max=10)
   - reraise=True
   Include a clear docstring explaining when and why to use it.

3. `core/utils/logging.py` — sanitize_for_log function:
   - Redacts phone numbers (10+ digits) with [PHONE]
   - Redacts emails with [EMAIL]
   - Returns sanitized string
   Include docstring with examples.

4. `core/utils/cache.py` — Distributed mutex helper:
   - Function acquire_lock(lock_key, timeout=300) using cache.add()
   - Function release_lock(lock_key) using cache.delete()
   - Context manager distributed_lock(lock_key, timeout=300) that handles acquire/release in try/finally
   Also include the two-level knowledge cache helper:
   - Module-level _KNOWLEDGE_CACHE dict
   - get_or_fill_cache(key, fetch_fn, ttl_seconds=900) function

5. `core/utils/tasks.py` — SovaBaseTask class (abstract Celery Task base):
   - before_start: records collector name
   - after_return: always calls connections.close_all()
   - on_success: updates SubFragmentRunLog with status='success', records_written, empty error
   - on_failure: updates SubFragmentRunLog with status='failed', error message truncated to 2000 chars
   Use update_or_create keyed on collector name.
   Include detailed comments explaining each lifecycle method for the learning developer.
✅ DONE WHEN: docker compose run --rm web python -c "from core.utils.retry import sova_retry; from core.utils.logging import sanitize_for_log; from core.utils.cache import distributed_lock; from core.utils.tasks import SovaBaseTask; print('All utilities imported successfully')" succeeds

Step 0.5 — Core Models (SubFragmentRunLog + Practice Foundation)
🔧 CLAUDE CODE PROMPT:
CopyCreate the core Django models in core/models.py. These are the foundation models that every other app depends on:

1. SubFragmentRunLog — exactly as specified in the PRD:
   - name: CharField(max_length=100, unique=True)
   - last_run_at: DateTimeField(null=True)
   - last_run_status: CharField(max_length=20, default='never_run')
   - records_written: IntegerField(default=0)
   - error_message: TextField(blank=True)
   - expected_interval_hours: IntegerField(default=24)
   - created_at: DateTimeField(auto_now_add=True)
   - updated_at: DateTimeField(auto_now=True)
   - Meta: db_table='sub_fragment_run_log', indexes on name and last_run_status
   - __str__ returns name with status

2. Practice — Master practice record, NPI as primary key:
   - npi: CharField(max_length=10, primary_key=True)
   - practice_name: CharField(max_length=255)
   - address_line1, address_line2: CharField(max_length=255, blank=True)
   - city: CharField(max_length=100, blank=True)
   - state: CharField(max_length=2, blank=True)
   - zip_code: CharField(max_length=10, blank=True)
   - phone: CharField(max_length=20, blank=True)
   - specialty_taxonomy_code: CharField(max_length=20, blank=True)
   - specialty_display: CharField(max_length=100, blank=True)
   - practice_type: CharField(max_length=20, blank=True) — solo/group
   - entity_type: CharField(max_length=20, blank=True) — individual/organization
   - website_url: CharField(max_length=500, blank=True)
   - domain: CharField(max_length=255, blank=True)
   - is_active: BooleanField(default=True)
   - is_current_client: BooleanField(default=False)
   - is_oig_excluded: BooleanField(default=False)
   - latitude: DecimalField(max_digits=10, decimal_places=7, null=True)
   - longitude: DecimalField(max_digits=10, decimal_places=7, null=True)
   - created_at, updated_at
   - Meta: db_table='practices', indexes on state, zip_code, specialty_taxonomy_code, is_active, practice_type, and composite (state, is_active)

3. Signal — Central signal store:
   - id: BigAutoField primary key
   - practice: ForeignKey to Practice on npi, db_index=True
   - signal_type: CharField(max_length=50), db_index=True
   - signal_source: CharField(max_length=50)
   - raw_value: FloatField
   - confidence: CharField(max_length=10) — High/Moderate/Low
   - evidence_count: IntegerField(default=1)
   - evidence_summary: TextField(blank=True)
   - half_life_days: IntegerField
   - collected_at: DateTimeField, db_index=True
   - expires_at: DateTimeField(null=True, blank=True)
   - metadata: JSONField(default=dict, blank=True)
   - Meta: db_table='signals', indexes on practice_npi, signal_type, collected_at, and composite (practice_npi, signal_type, collected_at)

4. LeadScore — Versioned scoring output:
   - id: BigAutoField primary key
   - practice: ForeignKey to Practice
   - composite_score: FloatField
   - fit_score, operational_pain_score, timing_score, first_party_intent_score, technographic_score, human_route_score, geography_score: FloatField(null=True)
   - tier: CharField(max_length=10) — HOT/WARM/COLD
   - modifiers_applied: JSONField(default=list)
   - signals_summary: JSONField(default=dict)
   - hot_qualification: JSONField(default=dict)
   - scored_at: DateTimeField, db_index=True
   - is_latest: BooleanField(default=True)
   - Meta: db_table='lead_scores', indexes on practice_npi, scored_at, tier, composite (tier, is_latest), composite (practice_npi, is_latest)

Also create core/admin.py registering all 4 models with useful list_display, list_filter, and search_fields.

After creating models, tell me to run makemigrations and migrate.
👤 FOUNDER ACTION after Claude Code finishes:
bashCopydocker compose run --rm web python manage.py makemigrations core
docker compose run --rm web python manage.py migrate
✅ DONE WHEN: Migrations succeed, docker compose run --rm web python manage.py shell -c "from core.models import Practice, SubFragmentRunLog, Signal, LeadScore; print('Models loaded')" works

Step 0.6 — Core API: Health Endpoint + Practice Views
🔧 CLAUDE CODE PROMPT:
CopyCreate the core API layer for Sova:

1. `core/serializers.py`:
   - PracticeListSerializer (npi, practice_name, city, state, specialty_display, is_active, is_current_client)
   - PracticeDetailSerializer (all fields)
   - SubFragmentRunLogSerializer (all fields)
   - SignalSerializer (all fields)
   - LeadScoreSerializer (all fields)

2. `core/views.py`:
   - SystemHealthView (GET /api/v1/health/) — no auth required, returns {"status": "healthy|degraded|unhealthy", "db": "ok|error", "redis": "ok|error", "celery": "ok|error"}. Check DB with connection.ensure_connection(), Redis with cache.set/get test, Celery with app.control.ping(timeout=2)
   - PracticeListView — DRF ListAPIView with filtering on state, specialty, is_active, pagination
   - PracticeDetailView — DRF RetrieveAPIView by NPI, includes latest lead score

3. `core/urls.py` with URL patterns for all views

4. Update `sova/urls.py` to include core.urls under api/v1/

5. Add simple API key authentication class in `core/authentication.py`:
   - SovaAPIKeyAuthentication checks for X-API-Key header matching SOVA_API_KEY env var
   - Apply to all views EXCEPT SystemHealthView
   - Add to REST_FRAMEWORK DEFAULT_AUTHENTICATION_CLASSES in settings

Make sure the health endpoint works without authentication. Add drf-yasg swagger URL at /api/docs/.
✅ DONE WHEN:
bashCopydocker compose up -d
curl http://localhost:8000/api/v1/health/
# Returns {"status": "healthy", "db": "ok", "redis": "ok", ...}
# Swagger docs visible at http://localhost:8000/api/docs/

Step 0.7 — Orchestrator: SovaTaskRun + SovaConversation Models
🔧 CLAUDE CODE PROMPT:
CopyCreate the orchestrator app models and API endpoints:

1. `orchestrator/models.py`:
   - SovaConversation — exactly as PRD specifies:
     conversation_id (UUID, unique), thread_id (CharField 255, unique), user_identifier (CharField 255), messages (JSONField default=list), mode (CharField 50, default="chatbot"), created_at, updated_at
   - SovaTaskRun — exactly as PRD specifies:
     run_id (UUID, unique), conversation (FK to SovaConversation, null=True, blank=True, SET_NULL), task_name (CharField 100), status (CharField 20, default="pending"), result (JSONField null=True), error (TextField blank=True), progress (CharField 255, blank=True), created_at, completed_at (null=True)

2. `orchestrator/serializers.py`:
   - SovaTaskRunSerializer (all fields)
   - TaskStatusSerializer (status, progress, result, error, created_at, completed_at)

3. `orchestrator/views.py`:
   - TaskStatusView (GET /api/v1/tasks/<run_id>/) — returns current task status
   - TaskCancelView (POST /api/v1/tasks/<run_id>/cancel/) — sets Redis cancellation key sova:cancel:{run_id}, returns {"cancelled": true}
   - CollectorHealthView (GET /api/v1/health/collectors/) — reads all SubFragmentRunLog entries, computes stale_collectors (last_run_at > 2x expected_interval) and silent_fail_collectors (status=success, records=0), returns structured JSON

4. `orchestrator/urls.py` with URL patterns

5. `orchestrator/tasks.py` — stub for:
   - check_collector_health task (hourly) — just logs for now
   - recompute_all_lead_scores task (daily 2AM UTC) — stub that logs "Lead score recomputation not yet implemented"

6. `orchestrator/admin.py` registering both models

7. Update sova/urls.py to include orchestrator.urls

Run makemigrations and migrate after.
👤 FOUNDER ACTION:
bashCopydocker compose run --rm web python manage.py makemigrations orchestrator
docker compose run --rm web python manage.py migrate
✅ DONE WHEN: curl -H "X-API-Key: sova-dev-key-change-in-production" http://localhost:8000/api/v1/health/collectors/ returns a valid JSON response

Step 0.8 — Celery Beat Schedule + Flower Verification
🔧 CLAUDE CODE PROMPT:
CopySet up the initial Celery Beat schedule in sova/settings.py. Add the CELERY_BEAT_SCHEDULE dict with these initial entries (all pointing to stubs or orchestrator tasks that exist):

1. 'health-check-hourly': task='orchestrator.tasks.check_collector_health', schedule=timedelta(hours=1)
2. 'lead-score-daily': task='orchestrator.tasks.recompute_all_lead_scores', schedule=crontab(hour=2, minute=0)

Make sure:
- The celery.py autodiscover includes ['collectors', 'orchestrator', 'tools']
- Import timedelta and crontab at the top of settings.py where the schedule is defined
- The orchestrator/tasks.py has both tasks properly decorated with @shared_task

Also create a simple smoke test task in orchestrator/tasks.py:
@shared_task(name='orchestrator.tasks.smoke_test')
def smoke_test():
    return "Celery is working"
👤 FOUNDER ACTION:
bashCopydocker compose up -d --build
# Wait 30 seconds for all services to start
docker compose exec web python -c "from orchestrator.tasks import smoke_test; result = smoke_test.delay(); print(f'Task ID: {result.id}')"
# Check Flower at http://localhost:5555 — you should see the task
✅ DONE WHEN: Flower dashboard at localhost:5555 shows workers online, smoke test task completed successfully

Step 0.9 — Create Django Superuser + Admin Verification
👤 FOUNDER ACTION:
bashCopydocker compose exec web python manage.py createsuperuser
# Follow prompts for username/email/password
✅ DONE WHEN: Django admin at http://localhost:8000/admin/ shows SubFragmentRunLog, Practice, Signal, LeadScore, SovaConversation, SovaTaskRun models

🎯 PHASE 0 COMPLETE CHECKPOINT: All 7 Docker services running. Health endpoint returns 200. Celery Beat running. Flower showing workers. Admin accessible. Sentry capturing test exceptions (if DSN configured). This is your foundation — everything builds on this.

PHASE 1 — PRACTICE DATA FOUNDATION
Goal: Master practice table populated with 180K+ dental records from NPPES. Google Places data flowing for test practices. Health endpoint shows collectors as "success".

Step 1.1 — Collectors App Structure + Pydantic Schemas
🔧 CLAUDE CODE PROMPT:
CopySet up the collectors app structure. Create:

1. `collectors/tasks/` directory with __init__.py
2. `collectors/tasks/practice_data.py` — empty file for now (NPPES + Google Places tasks will go here)
3. `collectors/schemas/` directory with __init__.py
4. `collectors/schemas/practice_schemas.py` — Pydantic schemas:
   - NPPESRecordSchema(BaseModel): npi, practice_name (provider_organization_name or first+last), address_line1, city, state, zip_code, phone, taxonomy_code, entity_type_code
   - GooglePlacesDataSchema(BaseModel): practice_npi, google_place_id, review_count (Optional[int]), star_rating (Optional[float]), review_velocity_30d (Optional[float]), phone_friction_count (int=0), phone_friction_keywords (List[str]=Field(default_factory=list)), opening_hours (Optional[dict]), response_rate (Optional[float])

5. `collectors/models.py` — Create the GooglePlacesData Django model:
   - id: BigAutoField
   - practice: ForeignKey(Practice, on_delete=CASCADE, related_name='google_places_data')
   - google_place_id: CharField(max_length=255, blank=True)
   - review_count: IntegerField(null=True)
   - star_rating: DecimalField(max_digits=2, decimal_places=1, null=True)
   - review_velocity_30d: FloatField(null=True)
   - phone_friction_count: IntegerField(default=0)
   - phone_friction_keywords: JSONField(default=list)
   - opening_hours: JSONField(null=True)
   - hours_changed: BooleanField(default=False)
   - hours_change_type: CharField(max_length=20, blank=True, null=True)
   - response_rate: FloatField(null=True)
   - collected_at: DateTimeField(auto_now_add=True)
   - Meta: db_table='google_places_data', indexes on (practice, collected_at)

6. `collectors/admin.py` — Register GooglePlacesData with useful list_display

Run makemigrations and migrate.
👤 FOUNDER ACTION:
bashCopydocker compose run --rm web python manage.py makemigrations collectors
docker compose run --rm web python manage.py migrate
✅ DONE WHEN: Migration succeeds, GooglePlacesData visible in admin

Step 1.2 — NPPES Collector (The Big One — 7GB CSV Streaming)
🔧 CLAUDE CODE PROMPT:
CopyBuild the nppes_collector Celery task in collectors/tasks/practice_data.py. This is the most critical collector — it populates the master practice table from the NPPES government CSV.

CRITICAL REQUIREMENTS:
- Stream the CSV row-by-row using Python's built-in csv module — NEVER load the 7GB file into memory
- Filter for dental taxonomy codes (codes starting with '122' which covers all dental specialties)
- Use bulk_create with update_conflicts=True for upsert, batch_size=5000
- Track records_written count for SubFragmentRunLog
- Use SovaBaseTask as the base class

Implementation:

1. Create the task with these attributes:
   @shared_task(bind=True, base=SovaBaseTask, name='collectors.tasks.practice_data.nppes_collector', queue='collectors', time_limit=7200, soft_time_limit=7000)

2. The task should:
   a. Download the NPPES monthly CSV from https://download.cms.gov/nppes/NPPES_Data_Dissemination_<month>_<year>.zip
      - For now, implement a helper that checks for a local file first at /app/data/nppes_data.csv — if not found, log that manual download is required and return 0
      - Add a TODO comment for implementing the actual download later
   b. Open the CSV with csv.DictReader, streaming row by row
   c. For each row, check if Healthcare Provider Taxonomy Code_1 starts with '122' (dental)
   d. Build a Practice model instance from the row, mapping NPPES columns to our fields:
      - NPI -> npi
      - Provider Organization Name (Legal Business Name) -> practice_name (or First Name + Last Name for individuals)
      - Provider First Line Business Practice Location Address -> address_line1
      - Provider Business Practice Location Address City Name -> city
      - Provider Business Practice Location Address State Name -> state
      - Provider Business Practice Location Address Postal Code -> zip_code (first 5 digits)
      - Provider Business Practice Location Address Telephone Number -> phone
      - Healthcare Provider Taxonomy Code_1 -> specialty_taxonomy_code
      - Entity Type Code -> entity_type ('1'='individual', '2'='organization')
   e. Collect in batches of 5000, then bulk_create with update_conflicts=True, unique_fields=['npi'], update_fields=[all updatable fields]
   f. Count total records written
   g. Return the count (SovaBaseTask.on_success will log it)

3. Handle errors gracefully — if a row is malformed, skip it and log warning, don't crash the entire import

4. Add a management command `core/management/commands/import_nppes.py` that calls the task synchronously for initial data load, accepting a --file argument for the CSV path

Include detailed comments explaining each section for the learning developer.
✅ DONE WHEN: The task can be imported without errors: docker compose exec web python -c "from collectors.tasks.practice_data import nppes_collector; print('NPPES collector ready')"

Step 1.3 — Google Places Collector
🔧 CLAUDE CODE PROMPT:
CopyBuild the google_places_collector Celery task in collectors/tasks/practice_data.py (same file as NPPES).

This collector fetches review data from Google Places API for a single practice at a time, dispatched by Celery.

1. Task definition:
   @shared_task(bind=True, base=SovaBaseTask, name='collectors.tasks.practice_data.google_places_collector', queue='collectors', time_limit=300, soft_time_limit=280)

2. Task signature: google_places_collector(self, practice_npi: str)

3. Implementation:
   a. Acquire distributed lock: sova:lock:google_places_collector:{practice_npi}
   b. Fetch practice from DB
   c. Use Google Places API (Text Search or Find Place) to find the practice by name + address
      - Use httpx with timeout=30
      - Use sova_retry decorator on the API call function
      - API key from settings/env: GOOGLE_MAPS_API_KEY
      - If no API key configured, log warning and return 0
   d. Extract: place_id, rating, user_ratings_total, opening_hours
   e. For reviews (if available via Place Details), detect phone friction keywords:
      Keywords: "couldn't get through", "voicemail", "on hold", "never answers", "no one answered", "can't reach", "busy signal"
   f. Validate through GooglePlacesDataSchema
   g. Create GooglePlacesData record
   h. Release lock in finally block
   i. Return 1 (one record written)

4. Also create a fan-out task:
   @shared_task(name='collectors.tasks.practice_data.google_places_batch')
   def google_places_batch(limit=5000):
       """Fan out Google Places collection for practices, HOT/WARM first."""
       # Get practices ordered by lead score tier (HOT first, then WARM, then COLD)
       # For each, dispatch google_places_collector.delay(npi)
       # Respect the limit parameter

5. Add the fan-out task to CELERY_BEAT_SCHEDULE in settings.py:
   'google-places-daily': schedule=crontab(hour=3, minute=0)

Include error handling that never crashes — if Google API returns an error, log it and return 0.
✅ DONE WHEN: Task imports successfully, fan-out task exists in schedule

Step 1.4 — Collector Health Monitoring Endpoint (Real Implementation)
🔧 CLAUDE CODE PROMPT:
CopyNow implement the real collector health monitoring in orchestrator/views.py and orchestrator/tasks.py:

1. Update `orchestrator/tasks.py` check_collector_health:
   - Query all SubFragmentRunLog entries
   - For each, check if last_run_at > now - (2 * expected_interval_hours) → stale
   - Check if last_run_status == 'success' and records_written == 0 → silent fail
   - Log results
   - Return summary dict

2. Update `orchestrator/views.py` CollectorHealthView:
   - GET /api/v1/health/collectors/ 
   - Returns JSON with:
     - "collectors": list of all SubFragmentRunLog entries serialized
     - "stale_collectors": list of names where last_run is stale
     - "silent_fail_collectors": list of names where status=success but records=0
     - "total_collectors": count
     - "healthy_collectors": count of non-stale, non-silent-fail with status=success

3. Ensure the endpoint requires API key auth

Add clear docstrings and comments explaining what "stale" and "silent fail" mean.
✅ DONE WHEN: curl -H "X-API-Key: ..." http://localhost:8000/api/v1/health/collectors/ returns proper structure with empty lists (no collectors have run yet)

PHASE 2 — JOB SIGNAL LAYER
Goal: Job postings flowing from at least 3 sources. PMS mentions extracted. Chronic repost detection working.

Step 2.1 — Job Postings Model + Schemas
🔧 CLAUDE CODE PROMPT:
CopyCreate the job postings data model and schemas:

1. `collectors/schemas/job_posting_schemas.py`:
   - JobPostingSchema(BaseModel): 
     practice_npi (Optional[str]), practice_name_raw (str), source (Literal["dentalpost","indeed","ihiredental","ziprecruiter","linkedin_jobs"]), job_title (str), posted_at (Optional[datetime]), description_text (str=""), pms_mentions (List[str]=Field(default_factory=list)), is_chronic_repost (bool=False), repost_count (int=1), is_front_desk_role (bool=True), bilingual_required (bool=False), migration_language_detected (bool=False), burnout_keywords_found (List[str]=Field(default_factory=list)), location_city (str=""), location_state (str=""), raw_url (str=""), content_hash (str="")

2. Add JobPosting model to `collectors/models.py`:
   - All fields from the PRD's job_postings table specification exactly
   - id: BigAutoField PK
   - practice: ForeignKey(Practice, null=True, blank=True, on_delete=SET_NULL, related_name='job_postings')
   - All other fields matching the schema
   - content_hash: CharField(max_length=64, unique=True, blank=True, null=True) for dedup
   - collected_at: DateTimeField(auto_now_add=True)
   - Meta: db_table='job_postings', indexes on practice (FK), source, posted_at, collected_at, and composite (practice, source, posted_at)

3. Register in collectors/admin.py with list_display showing practice, source, job_title, is_front_desk_role, is_chronic_repost, posted_at

4. Helper function in collectors/tasks/ for content hash dedup:
   def compute_content_hash(practice_name: str, job_title: str, location: str) -> str:
       import hashlib
       content = f"{practice_name.lower().strip()}|{job_title.lower().strip()}|{location.lower().strip()}"
       return hashlib.sha256(content.encode()).hexdigest()

5. Helper function for PMS mention extraction:
   PMS_PATTERNS = {"dentrix": r'\bdentrix\b', "eaglesoft": r'\beaglesoft\b', "open dental": r'\bopen\s*dental\b', "curve dental": r'\bcurve\s*(dental|hero)?\b', "denticon": r'\bdenticon\b', "practice works": r'\bpractice\s*works\b', "softdent": r'\bsoftdent\b', "abeldent": r'\babeldent\b'}
   def extract_pms_mentions(text: str) -> List[str]: ...

6. Helper function for burnout keyword detection:
   BURNOUT_KEYWORDS = ["high-energy", "fast-paced", "recent turnover", "team player needed", "must be flexible", "wear many hats", "high volume"]
   def detect_burnout_keywords(text: str) -> List[str]: ...

7. Helper function for chronic repost detection:
   def check_chronic_repost(practice_name: str, job_title: str, months=12) -> tuple[bool, int]:
       # Query JobPosting for same practice + similar title within N months
       # Return (is_chronic, count)

Run makemigrations and migrate.
👤 FOUNDER ACTION:
bashCopydocker compose run --rm web python manage.py makemigrations collectors
docker compose run --rm web python manage.py migrate
✅ DONE WHEN: JobPosting model in admin, all helper functions import correctly

Step 2.2 — DentalPost Collector
🔧 CLAUDE CODE PROMPT:
CopyBuild the dentalpost_collector in collectors/tasks/job_portals.py:

@shared_task(bind=True, base=SovaBaseTask, name='collectors.tasks.job_portals.dentalpost_collector', queue='collectors', time_limit=900, soft_time_limit=840)
def dentalpost_collector(self):

Implementation:
1. Fetch https://www.dentalpost.net/dental-jobs/ using httpx with timeout=30, sova_retry
2. Parse HTML with BeautifulSoup
3. Extract job listings — look for job cards/listings with: job title, practice/company name, location (city, state), posted date, job URL
4. For each listing:
   a. Compute content_hash from (practice_name, job_title, location)
   b. Skip if content_hash already exists in DB (dedup)
   c. Determine is_front_desk_role by checking title for: "front desk", "receptionist", "patient coordinator", "scheduling coordinator", "front office"
   d. Extract PMS mentions from description
   e. Detect burnout keywords
   f. Check chronic repost status
   g. Attempt NPI resolution: fuzzy match practice_name_raw + location against Practice table
   h. Validate through JobPostingSchema
   i. Create JobPosting record

5. Respect rate limiting: max 1 request/second (use time.sleep(1) between pages)
6. Return total records_written count

Add to CELERY_BEAT_SCHEDULE:
'dentalpost-daily': task path, schedule=crontab(hour=5, minute=0)

IMPORTANT: Include robust error handling. If the page structure changes, log a clear error message and return 0 — do not crash. The developer needs to understand where scraping broke.

Add comments explaining the BeautifulSoup selectors chosen and why, so when DentalPost changes their HTML, the developer knows what to update.
✅ DONE WHEN: Task imports and can be dispatched: docker compose exec web python -c "from collectors.tasks.job_portals import dentalpost_collector; print('Ready')"

Step 2.3 — Indeed Collector
🔧 CLAUDE CODE PROMPT:
CopyBuild the indeed_collector in collectors/tasks/job_portals.py (same file):

@shared_task(bind=True, base=SovaBaseTask, name='collectors.tasks.job_portals.indeed_collector', queue='collectors', time_limit=900, soft_time_limit=840)
def indeed_collector(self):

Same pattern as dentalpost_collector but:
1. Target: https://www.indeed.com/jobs?q=dental+front+desk (and similar queries for "dental+receptionist", "dental+patient+coordinator")
2. Rate limit: max 1 request per 2 seconds
3. Rotate user-agents from a list of 5-10 common browser UA strings
4. Content hash dedup against ALL job_postings (catches cross-platform duplicates)
5. source="indeed"

Add to CELERY_BEAT_SCHEDULE:
'indeed-daily': schedule=crontab(hour=5, minute=30)

Note in comments: Indeed may block scrapers. If response is not 200 or if no jobs are found, log clearly and return 0. This is an AMBER compliance collector.
✅ DONE WHEN: Task imports successfully

Step 2.4 — LinkedIn Jobs Collector (Licensed API)
🔧 CLAUDE CODE PROMPT:
CopyBuild the linkedin_jobs_collector in collectors/tasks/job_portals.py:

IMPORTANT: This does NOT scrape LinkedIn. It uses a licensed job data API (JSearch via RapidAPI or similar). The PRD explicitly states: "Do NOT scrape LinkedIn directly."

@shared_task(bind=True, base=SovaBaseTask, name='collectors.tasks.job_portals.linkedin_jobs_collector', queue='collectors', time_limit=900, soft_time_limit=840)
def linkedin_jobs_collector(self):

Implementation:
1. Use JSEARCH_API_KEY from env to call JSearch API (RapidAPI)
   - Endpoint: https://jsearch.p.rapidapi.com/search
   - Query: "dental front desk", "dental receptionist" 
   - Headers: X-RapidAPI-Key, X-RapidAPI-Host
2. If no API key configured, log warning and return 0
3. Parse results, extract PMS mentions from descriptions
4. source="linkedin_jobs"
5. Content hash dedup
6. Respect API rate limits

Add to CELERY_BEAT_SCHEDULE:
'linkedin-jobs-48h': schedule=crontab(hour=4, minute=0, day_of_week='1,3,5') — roughly every 48h
✅ DONE WHEN: Task imports, handles missing API key gracefully

Step 2.5 — iHireDental + ZipRecruiter Collectors
🔧 CLAUDE CODE PROMPT:
CopyBuild two more job collectors in collectors/tasks/job_portals.py:

1. ihiredental_collector:
   - Source: https://www.ihiredental.com/
   - Schedule: every 48h (crontab hour=6, minute=0, day_of_week='2,4,6')
   - Rate limit: 1 req/sec
   - source="ihiredental"
   - GREEN compliance

2. ziprecruiter_collector:
   - Source: https://www.ziprecruiter.com/
   - Schedule: every 48h (crontab hour=6, minute=30, day_of_week='2,4,6')
   - Rate limit: 1 req per 2 seconds
   - source="ziprecruiter"
   - AMBER compliance — may block

Both follow the identical pattern as dentalpost_collector: fetch, parse, extract, validate through Pydantic, dedup via content_hash, write to job_postings table.

Add both to CELERY_BEAT_SCHEDULE.
✅ DONE WHEN: All 5 job collectors import and are in the beat schedule

Step 2.6 — Job Portal API Endpoints
🔧 CLAUDE CODE PROMPT:
CopyCreate API endpoints for the job data:

1. Add to core/views.py (or create a new file):
   - PracticeSignalsView: GET /api/v1/practices/<npi>/signals/ — returns all signals for a practice ordered by collected_at desc, with query params signal_type and since (date filter)
   
2. Create collectors/views.py:
   - JobPostingsListView: GET /api/v1/job-postings/ — list with filters: source, is_front_desk_role, is_chronic_repost, state, since (date)
   - Serializer with all relevant fields

3. Create collectors/urls.py and wire into sova/urls.py

4. Update collectors/admin.py if not already done
✅ DONE WHEN: Job postings endpoint returns empty list (no data yet), signals endpoint works

PHASE 3 — COMPETITOR INTELLIGENCE
Goal: Weekly competitive data flowing from Facebook Ads Library, competitor product pages, PR mentions.

Step 3.1 — Competitor Output Models
🔧 CLAUDE CODE PROMPT:
CopyCreate competitor intelligence models in collectors/models.py:

1. CompetitorAd model (db_table='competitor_ads'):
   - id, competitor_name (indexed), platform (facebook/google/linkedin), ad_copy, creative_format, cta_text, target_geography (JSONField), estimated_spend_bracket, run_duration_days, is_active, first_seen_at, last_seen_at, collected_at
   - Indexes on competitor_name, platform, collected_at

2. CompetitorSnapshot model (db_table='competitor_snapshots'):
   - id, competitor_name (indexed), snapshot_type (pricing/features/changelog), content_hash, current_content (TextField), previous_content (TextField blank=True), changes_detected (JSONField default=list), collected_at

3. CompetitorSignal model (db_table='competitor_signals'):
   - id, competitor_name (indexed), signal_type (new_hire/funding/press/product_change/client_win), description, source, metadata (JSONField), collected_at

Register all in admin.py. Run makemigrations and migrate.
👤 FOUNDER ACTION:
bashCopydocker compose run --rm web python manage.py makemigrations collectors
docker compose run --rm web python manage.py migrate

Step 3.2 — Competitor Product Monitor + Facebook Ads Library Collector
🔧 CLAUDE CODE PROMPT:
CopyBuild competitor intelligence collectors in collectors/tasks/competitor_intel.py:

1. competitor_product_monitor:
   - Monitors competitor feature pages, pricing pages, changelogs
   - Define COMPETITOR_URLS dict with competitor name -> list of URLs to monitor
   - For each URL: fetch with httpx, compute SHA-256 hash, compare against last CompetitorSnapshot
   - If hash changed: store new snapshot with changes_detected
   - Schedule: weekly (Monday 2AM)
   - NOTE: competitor_website_monitor is MERGED INTO this — one change-detection pipeline per competitor URL

2. facebook_ads_library_collector:
   - Uses Meta Ad Library API (official, free)
   - Searches by competitor Facebook Page ID or keyword
   - Extracts: ad copy, creative format, CTA, run duration, targeting geography
   - If no FACEBOOK_APP_ID configured, log and return 0
   - Schedule: weekly (Monday 2:30AM)

Both use SovaBaseTask, proper error handling, rate limiting. Add to CELERY_BEAT_SCHEDULE.

Define the competitor list in SovaConfig or as a constant:
COMPETITORS = ["Arini", "TrueLark", "Rondah AI", "TensorLinks AI", "Viva AI", "mConsent", "AINORA", "NexHealth", "Weave", "HeyGent", "Dentina.AI"]
✅ DONE WHEN: Both tasks import, beat schedule updated

PHASE 4 — LIFECYCLE & GOVERNMENT DATA
Step 4.1 — Lifecycle Events Model + Government Data Model
🔧 CLAUDE CODE PROMPT:
CopyCreate lifecycle and government data models in collectors/models.py:

1. LifecycleEvent (db_table='lifecycle_events'):
   - id, practice (FK), event_type (CharField 50, indexed — values: new_npi, broker_listing, sold, permit, expansion, new_licensee, sba_loan), event_date, event_source, description, metadata (JSONField), collected_at
   - Indexes: practice, event_type, collected_at

2. GovernmentData (db_table='government_data'):
   - id, practice (FK, nullable for area-level data), data_type (CharField 50 — values: cms_enrollment, sba_loan, oig_exclusion, hrsa_hpsa, bls_staffing, medicaid_provider), source, value (JSONField), effective_date, collected_at
   - Indexes: practice, data_type, collected_at

Register both in admin. Run makemigrations and migrate.

Step 4.2 — OIG Exclusion Checker + Key Government Collectors
🔧 CLAUDE CODE PROMPT:
CopyBuild government data collectors in collectors/tasks/government.py:

1. oig_exclusion_checker:
   - Downloads HHS OIG LEIE exclusion list (monthly CSV from oig.hhs.gov)
   - Cross-references against practices table by provider name + NPI
   - Sets practice.is_oig_excluded = True for matches
   - This is an IMMEDIATE DISQUALIFIER — excluded practices are removed from all scoring
   - Schedule: monthly (day 5)
   - GREEN compliance

2. bls_staffing_heatmap:
   - Downloads BLS dental employment data via BLS API (api.bls.gov)
   - NAICS 621210 (Offices of Dentists)
   - Stores metro-level staffing data
   - Schedule: quarterly
   - GREEN compliance

3. Create stubs for the remaining government collectors (just task signatures + docstrings, no implementation):
   - cms_enrollment_collector
   - sba_loan_monitor
   - hrsa_hpsa_monitor

Add implemented tasks to CELERY_BEAT_SCHEDULE.

Step 4.3 — Lifecycle Event Collectors (Stubs + Key Ones)
🔧 CLAUDE CODE PROMPT:
CopyBuild lifecycle event collectors in collectors/tasks/lifecycle.py:

1. npi_new_registration_monitor — FULL IMPLEMENTATION:
   - Compares current NPPES data against previous month's snapshot
   - New dental NPIs (taxonomy starting with '122') = new practice opening
   - Creates LifecycleEvent with event_type='new_npi'
   - Schedule: weekly (Sunday 1AM)

2. Create STUBS with proper task signatures, docstrings, and "not yet implemented" logging for:
   - dental_broker_listing_monitor (AFTCO, Omni, Henry Schein Transitions scraping)
   - dental_school_new_licensee_monitor (state dental board scraping)
   - building_permit_monitor (county permit portal scraping)
   - multi_location_expansion_detector (NPPES entity resolution)

Each stub should: log that it's not yet implemented, update SubFragmentRunLog with status='not_implemented', return 0.

PHASE 5 — LEAD SCORING TOOL (Critical)
Goal: Lead scores computed for all practices with signals. HOT/WARM/COLD tiers assigned. Daily recomputation running.

Step 5.1 — Signal Decay Function + Lead Score Computation Engine
🔧 CLAUDE CODE PROMPT:
CopyBuild the lead scoring engine in tools/lead_score.py. This is the most critical intelligence tool in the system.

1. Signal Decay Function:
   import math
   def compute_decayed_value(raw_value: float, days_since_signal: int, half_life_days: int) -> float:
       """Exponential decay: raw × e^(-ln(2) × days / half_life)"""
       if days_since_signal <= 0:
           return raw_value
       return raw_value * math.exp(-math.log(2) * days_since_signal / half_life_days)

2. Lead Score Pydantic Schema in tools/schemas/lead_score_schemas.py:
   class LeadScoreResult(BaseModel):
       practice_npi: str
       composite_score: float
       fit_score: float
       operational_pain_score: float
       timing_score: float
       first_party_intent_score: float
       technographic_score: float
       human_route_score: float
       geography_score: float
       tier: Literal["HOT", "WARM", "COLD"]
       modifiers_applied: List[dict]
       signals_summary: dict
       hot_qualification: dict
       confidence: Literal["HIGH", "MODERATE", "LOW"]
       recommended_action: str

3. Core scoring function (async):
   async def compute_lead_score(practice_npi: str) -> LeadScoreResult:
   
   Implementation following the PRD exactly:
   a. Parallel DB reads using asyncio.gather with Semaphore(8):
      - job_postings, google_places_data, lifecycle_events, technographic_signals, review_data, access_audit_results, intent_signals, dso_signals, champion_signals, enrichment_data
      - Use sync_to_async for Django ORM queries
      - If a table doesn't exist yet (later phases), return empty list gracefully
   
   b. Apply signal decay to each signal based on its collected_at and half_life_days from SovaConfig
   
   c. Compute 7 component scores (0-100 each):
      - Fit (0.20): specialty match, size, tech gap, PMS detected, profile claimed
      - Operational Pain (0.25): job posting count, repost, burnout, phone friction, access failures, burnout scores, reputation shock
      - Timing (0.20): lifecycle event counts, staff transitions, insurance changes
      - First-Party Intent (0.15): demo calls, website visits, branded search
      - Technographic (0.10): PMS type, migration, booking tool, competitor client
      - Human Route (0.05): champion at practice, contact identified, peer connections
      - Geography (0.05): DSO proximity, staffing heatmap
   
   d. Weighted composite: sum of (weight × component)
   
   e. Apply bounded modifiers from PRD:
      - Champion moved: +8, Ownership transfer: +6, New practice: +5, Live-answer failure: +4, DSO nearby: +3, Demo call: +3
      - Inactive/dead phone: -6, Strong incumbent: -4
      - OIG excluded: DISQUALIFY (skip entirely)
   
   f. Clamp final score to 0-100
   
   g. Determine tier: >= 78 and all HOT conditions = HOT, >= 50 = WARM, else COLD
   
   h. HOT qualification check (all 6 must be true):
      - composite >= 78, fit >= 65
      - At least one pain signal AND one timing/intent signal
      - At least one signal within last 30 days
      - Owner/OM contact identified
      - No major disqualifier
   
   i. Return LeadScoreResult

4. Make the function work gracefully with missing data — if no signals exist for a component, score it as 0 with LOW confidence. The system must work from Phase 5 onward even if not all collectors are built yet.

Add extensive comments explaining the scoring logic for the learning developer.
✅ DONE WHEN: docker compose exec web python -c "from tools.lead_score import compute_lead_score; print('Lead score engine ready')"

Step 5.2 — Daily Lead Score Recomputation Task
🔧 CLAUDE CODE PROMPT:
CopyImplement the recompute_all_lead_scores task in orchestrator/tasks.py:

@shared_task(name='orchestrator.tasks.recompute_all_lead_scores', queue='tools', time_limit=3600, soft_time_limit=3500)
def recompute_all_lead_scores():
    """Daily batch: recompute lead scores for all practices with signals in last 180 days."""
    
    Implementation:
    1. Query practices that have at least one signal with collected_at > 180 days ago
    2. For each practice:
       a. Run compute_lead_score (use asyncio.run for the async function)
       b. Mark existing is_latest=True scores for this practice as is_latest=False
       c. Create new LeadScore row with is_latest=True
       d. Track count
    3. Process in batches of 100 to avoid memory issues
    4. Log progress every 1000 practices
    5. Return total practices scored

This runs daily at 2:00 AM UTC (already in CELERY_BEAT_SCHEDULE).

Also create a management command `core/management/commands/score_practice.py`:
- Takes --npi argument
- Runs compute_lead_score for a single practice and prints the result
- Useful for testing and debugging

Step 5.3 — HOT Leads API Endpoint
🔧 CLAUDE CODE PROMPT:
CopyCreate the HOT leads API endpoint:

1. In tools/views.py:
   - HotLeadsView: GET /api/v1/leads/hot/
     Query params: state, specialty, limit (max 50, default 10)
     Returns list of practices with tier=HOT, is_latest=True, ordered by composite_score DESC
     Each item includes: npi, practice_name, city, state, composite_score, tier, top_signal (most recent signal description)

2. In tools/serializers.py:
   - HotLeadSerializer with the fields above

3. In tools/urls.py — wire up the endpoint

4. Also create:
   - LeadScoreInvokeView: POST /api/v1/tools/lead-score/
     Body: {"practice_npi": "..."}
     Returns HTTP 202 with {"run_id": "...", "status_url": "/api/v1/tasks/<run_id>/"}
     Dispatches the scoring as a Celery task, creates SovaTaskRun with status=pending

5. Wire tools/urls.py into sova/urls.py
✅ DONE WHEN: curl -H "X-API-Key: ..." http://localhost:8000/api/v1/leads/hot/ returns empty list (no scored practices yet, but endpoint works)

PHASE 6 — OUTREACH INTELLIGENCE
Goal: Outreach briefs generated for HOT leads with personalized messages, revenue estimates, and trust pathways.

Step 6.1 — Knowledge Base (pgvector)
🔧 CLAUDE CODE PROMPT:
CopySet up the pgvector knowledge base:

1. Add to requirements.txt:
   - pgvector>=0.3
   - langchain-openai>=0.3

2. Create knowledge/models.py — SovaKnowledge model:
   - id: AutoField PK
   - content: TextField
   - embedding: VectorField(dimensions=1536) — from pgvector.django
   - item_type: CharField(max_length=30) — playbook/objection_handler/case_study/competitor_comparison/icp_profile
   - title: CharField(max_length=255)
   - metadata: JSONField(default=dict)
   - content_hash: CharField(max_length=64, unique=True)
   - created_at, updated_at
   - Meta: db_table='sova_knowledge'
   - Add HNSW index on embedding with vector_cosine_ops

3. Create knowledge/store.py — DatabaseKnowledgeStore class:
   - __init__: initializes OpenAIEmbeddings with text-embedding-3-small
   - search(query, k=3, item_type=None) -> List[dict]: embeds query, searches with CosineDistance < 0.25, returns results with score
   - upsert(content, item_type, title, metadata) -> bool: computes content_hash, creates or updates

4. Create knowledge/yaml/ directory with starter files:
   - outreach_playbooks.yaml (3-4 sample playbooks)
   - objection_handlers.yaml (3-4 common objections)
   - competitor_comparisons.yaml (2-3 competitor comparison entries)
   - icp_profiles.yaml (3 ICP profile types)

5. Create knowledge/case_studies/ with 2-3 sample .md files

6. Create management command core/management/commands/build_knowledge_index.py:
   - Loads all YAML and MD files
   - Computes SHA-256 content hash for each
   - Generates embeddings via OpenAI
   - Upserts to SovaKnowledge table
   - Logs: processed, inserted, updated, skipped counts

IMPORTANT: In settings.py, add after DATABASES definition:
   # Enable pgvector extension
Add a migration that runs CREATE EXTENSION IF NOT EXISTS vector;

Run makemigrations and migrate.
👤 FOUNDER ACTION:
bashCopydocker compose run --rm web python manage.py makemigrations knowledge
docker compose run --rm web python manage.py migrate
# Build the knowledge index (requires OPENAI_API_KEY):
docker compose run --rm web python manage.py build_knowledge_index

Step 6.2 — Outreach Brief Tool
🔧 CLAUDE CODE PROMPT:
CopyBuild the Outreach Brief intelligence tool in tools/outreach_brief.py:

1. Pydantic schema in tools/schemas/outreach_schemas.py:
   class OutreachBrief(BaseModel):
       practice_name: str
       why_hot: List[str]
       owner_message: str
       office_manager_message: str
       recommended_opener: str
       best_contact_channel: Literal["email", "linkedin", "phone"]
       urgency_window_days: int
       trust_pathway: Optional[str] = None
       revenue_rescue_estimate: Optional[float] = None

2. async def generate_outreach_brief(practice_npi: str) -> OutreachBrief:
   a. Parallel DB reads for all signal data for this practice
   b. Fetch latest lead score
   c. pgvector knowledge base search for matching case study and playbook
   d. Assemble context, truncate to MAX_OUTREACH_BRIEF_SIGNALS_CHARS = 8000
   e. LLM call using Claude Sonnet with:
      - SystemMessage with cache_control: {"type": "ephemeral"}
      - HumanMessage with practice signals + case study context
      - with_structured_output(OutreachBrief)
   f. Error handling: never raise, return error string if LLM fails

3. Add @tool decorator with docstring for future chatbot:
   "Generate a complete outreach intelligence brief for a practice..."

4. DRF endpoint:
   POST /api/v1/tools/outreach-brief/
   Body: {"practice_npi": "..."}
   Returns HTTP 202 + run_id
   Celery task executes the generation, writes to SovaTaskRun

5. Add to tools/urls.py

Step 6.3 — Revenue Rescue Planner + Trust Vector Tools
🔧 CLAUDE CODE PROMPT:
CopyBuild two more critical intelligence tools:

1. tools/revenue_rescue.py:
   class RevenueRescuePlan(BaseModel):
       monthly_revenue_leakage: float
       evidence: List[str]
       before_after_projection: str
       objection_preemption: str
       owner_pitch_angle: str
       om_pitch_angle: str
       case_study_match: Optional[str] = None
   
   async def compute_revenue_rescue(practice_npi: str) -> RevenueRescuePlan
   - Reads: google_places_data, review_data, access_audit_results, availability_signals, intent_signals
   - Uses pgvector to find matching case study
   - 1x Claude Sonnet call with structured output
   - Context: MAX_REVENUE_RESCUE_EVIDENCE_CHARS = 6000
   - POST /api/v1/tools/revenue-rescue/ endpoint (HTTP 202)

2. tools/trust_vector.py:
   class TrustPathway(BaseModel):
       type: Literal["peer", "specialty", "operational", "geographic", "advisor"]
       description: str
       strength: float
   
   class TrustVectorResult(BaseModel):
       pathways: List[TrustPathway]
       best_proof_asset: str
       strength_score: float
   
   async def compute_trust_vector(practice_npi: str) -> TrustVectorResult
   - Reads: community_signals, conference_signals, enrichment_data, champion_signals
   - 1x pgvector search for best case study match
   - POST /api/v1/tools/trust-vector/ endpoint (HTTP 202)

Both tools follow the 10 mandatory patterns: Pydantic output, prompt caching, error handling (never raise), token caps, confidence scoring.

PHASES 7-9 — REMAINING COLLECTORS & TOOLS
Step 7-9.1 — Remaining Sub-fragment Output Models
🔧 CLAUDE CODE PROMPT:
CopyCreate ALL remaining sub-fragment output table models in collectors/models.py. Each follows the standard pattern from the PRD: BigAutoField PK, practice FK (nullable where appropriate), source, 3-5 domain-specific columns, metadata JSONField, collected_at with index.

Create these models (following the PRD Section 5 specifications for tables 6-29):

1. WebsiteCrawlData (db_table='website_crawl_data')
2. SocialMetrics (db_table='social_metrics')
3. ForumPost (db_table='forum_posts')
4. NewsletterItem (db_table='newsletter_items')
5. RssArticle (db_table='rss_articles')
6. InsuranceData (db_table='insurance_data')
7. ChampionSignal (db_table='champion_signals')
8. EnrichmentData (db_table='enrichment_data')
9. TechnographicSignal (db_table='technographic_signals')
10. AccessAuditResult (db_table='access_audit_results')
11. AvailabilitySignal (db_table='availability_signals')
12. StaffTransitionSignal (db_table='staff_transition_signals')
13. IntentSignal (db_table='intent_signals')
14. DSOSignal (db_table='dso_signals')
15. MarketSignal (db_table='market_signals')
16. BurnoutScore (db_table='burnout_scores')
17. CommunitySignal (db_table='community_signals')
18. YouTubeData (db_table='youtube_data')
19. TikTokData (db_table='tiktok_data')
20. ConferenceSignal (db_table='conference_signals')
21. ReviewData (db_table='review_data') — with platform, review_count, star_rating, is_claimed, is_listed, response_rate, reputation_shock, complaint_velocity_30d

Each model should have:
- Appropriate domain-specific fields (use the PRD for guidance, or sensible defaults with JSONField metadata for flexibility)
- Composite index on (practice, collected_at) where practice FK exists
- __str__ method
- Registered in admin.py

Run makemigrations and migrate.
👤 FOUNDER ACTION:
bashCopydocker compose run --rm web python manage.py makemigrations collectors
docker compose run --rm web python manage.py migrate

Step 7-9.2 — Remaining Collector Task Stubs
🔧 CLAUDE CODE PROMPT:
CopyCreate stub files for ALL remaining collector task modules. Each file should have properly decorated task stubs with correct signatures, docstrings explaining what they'll do, correct queue assignments, and "not yet implemented" logging. Every stub must use SovaBaseTask and return 0.

Create these files in collectors/tasks/:

1. social_platforms.py — stubs for: facebook_api_collector, linkedin_api_collector, facebook_hyperbrowser_agent (note: AMBER), youtube_competitor_monitor, tiktok_industry_monitor

2. conferences.py — stubs for: conference_website_monitor

3. newsletters.py — stubs for: email_inbox_reader, newsletter_classifier (note: uses LLM queue)

4. opinion_platforms.py — stubs for: reddit_scout, dentaltown_forum_scout

5. website_monitoring.py — stubs for: website_crawler, rss_feed_monitor

6. google_cloud.py — stubs for: google_news_collector, google_trends_monitor

7. review_platforms.py — stubs for: yelp_collector, healthgrades_collector, review_response_rate_tracker, reputation_shock_detector

8. local_market.py — stubs for: business_license_monitor, commercial_real_estate_scout

9. partnerships.py — stubs for: dental_supplier_monitor, insurance_network_collector, insurance_plan_change_monitor, dental_insurer_credentialing_monitor, insurance_ppo_density_monitor

10. enrichment.py — stubs for: hunter_enricher, linkedin_profile_enricher (Proxycurl), phone_validator

11. champion.py — stubs for: champion_job_change_tracker

12. technographic.py — stubs for: pms_signal_extractor, booking_tech_detector, bilingual_demand_detector, g2_intent_monitor, pms_migration_detector, patient_financing_badge_detector

13. intent_signals.py — stubs for: website_visitor_deanonymizer, bombora_b2b_intent_integration, branded_search_spike_monitor, first_party_voice_demo_tracker

14. dso_intelligence.py — stubs for: dso_expansion_monitor, saturation_zip_analyzer

15. community_intel.py — stubs for: dental_community_mention_tracker, peer_influence_mapper, practice_advisor_network_mapper, referral_network_mapper

16. associations.py — stubs for: ada_member_finder_scraper, dental_specialty_association_scraper, aadom_member_intelligence_collector, beckers_dental_review_scraper

17. burnout_signals.py — stubs for: dental_staffing_agency_monitor, staff_burnout_aggregator, patient_access_complaint_velocity

18. access_audit.py — stubs for: live_answer_audit (note: LEGAL SIGN-OFF REQUIRED), after_hours_coverage_audit, same_day_availability_scanner, new_patient_promo_detector, contact_friction_scorer, mobile_conversion_friction_scanner

19. staff_transition.py — stubs for: office_manager_turnover_detector, associate_arrival_detector, answering_service_vendor_loss_monitor

20. first_party.py — stubs for: lost_deal_reason_miner, direct_mail_response_tracker

Each stub should log: f"{self.name} is not yet implemented — stub only"

Step 7-9.3 — Remaining Intelligence Tool Stubs
🔧 CLAUDE CODE PROMPT:
CopyCreate stub files for ALL remaining intelligence tools in tools/. Each should have:
- The async function signature with correct type hints
- Pydantic output schema
- @tool decorator with docstring for future chatbot
- "Not yet implemented" return with appropriate default values
- DRF endpoint stub that returns HTTP 501 "Not Yet Implemented"

Create these files:

1. tools/fit_score.py — compute_fit_score(practice_npi) -> FitScoreResult
2. tools/intent_score.py — compute_intent_score(practice_npi) -> IntentScoreResult
3. tools/transition_window.py — detect_transition_window(practice_npi) -> TransitionWindowResult
4. tools/access_failure_index.py — compute_access_failure_index(practice_npi) -> AccessFailureResult
5. tools/competitive_leaderboard.py — generate_competitive_leaderboard() -> LeaderboardResult
6. tools/competitive_report.py — generate_competitive_report() -> CompetitiveReport
7. tools/market_report.py — generate_market_report() -> MarketReport
8. tools/client_health.py — compute_client_health(practice_npi) -> ClientHealthResult
9. tools/churn_warning.py — detect_churn_risk(practice_npi) -> ChurnWarningResult
10. tools/practice_growth.py — predict_practice_growth(practice_npi) -> GrowthPrediction
11. tools/displacement_engine.py — analyze_displacement(practice_npi) -> DisplacementResult
12. tools/buying_committee.py — identify_buying_committee(practice_npi) -> BuyingCommitteeResult
13. tools/influence_map.py — map_influence_network(practice_npi) -> InfluenceMapResult
14. tools/local_pressure.py — compute_local_pressure(zip_code) -> LocalPressureResult
15. tools/signal_calibration.py — run_signal_calibration() -> CalibrationReport
16. tools/content_generation.py — generate_content_suggestions() -> ContentSuggestions
17. tools/dso_pipeline.py — score_dso_account(practice_npi) -> DSOPipelineResult
18. tools/staff_stability.py — compute_staff_stability(practice_npi) -> StaffStabilityResult
19. tools/relocation_detector.py — detect_relocation(practice_npi) -> RelocationResult
20. tools/ce_engagement.py — compute_ce_engagement(practice_npi) -> CEEngagementResult
21. tools/financial_stress.py — compute_financial_stress(practice_npi) -> FinancialStressResult
22. tools/competitive_churn.py — analyze_competitive_churn(practice_npi) -> CompetitiveChurnResult
23. tools/persona_stitcher.py — stitch_persona(practice_npi) -> PersonaMap
24. tools/regulatory_watch.py — check_regulatory_updates() -> RegulatoryWatchResult

Wire all endpoints into tools/urls.py.

PHASE 10 — CHATBOT INTERFACE (v2 Scaffold)
Step 10.1 — Chatbot Scaffold
🔧 CLAUDE CODE PROMPT:
CopyScaffold the chatbot app for v2. Create the code structure and placeholder implementations:

1. chatbot/models.py — SovaConversation is already in orchestrator. Just import it.

2. chatbot/graph.py — Scaffold the LangGraph StateGraph:
   - Import StateGraph, MessagesState, START, END from langgraph
   - Define build_sova_chatbot_graph(checkpointer) function
   - Create 2-node graph: agent -> tools -> agent loop
   - Add TODO comments for full implementation
   - Return "Chatbot not yet implemented" for now

3. chatbot/checkpointer.py — Scaffold AsyncPostgresSaver per-loop caching:
   - _async_checkpointers dict keyed by loop ID
   - get_async_postgres_checkpointer() function
   - TODO comments referencing Eva patterns

4. chatbot/router.py — Scaffold mode router:
   - SovaRoutingDecision Pydantic schema (route, reason)
   - route_query() function stub
   
5. chatbot/streaming.py — Scaffold Redis SSE:
   - publish_stream_event() function stub
   - SSE event type constants

6. chatbot/summarization.py — Scaffold context summarization:
   - summarize_old_messages() function stub

7. chatbot/views.py — Scaffold 5 DRF endpoints (all return 501):
   - CreateThreadView: POST /api/v1/conversations/
   - SubmitQueryView: POST /api/v1/conversations/<thread_id>/query/
   - TaskStatusView: GET /api/v1/tasks/<run_id>/ (reuse orchestrator)
   - SSEStreamView: GET /api/v1/tasks/<run_id>/stream/
   - CancelView: POST /api/v1/tasks/<run_id>/cancel/ (reuse orchestrator)

8. chatbot/serializers.py — SovaQueryInputSerializer

9. chatbot/urls.py — wire all endpoints

10. Update sova/urls.py to include chatbot.urls

FINAL VERIFICATION
Step FINAL — Full System Smoke Test
👤 FOUNDER ACTION:
bashCopy# Rebuild everything
docker compose down
docker compose up -d --build

# Wait for all services to be healthy
sleep 30

# 1. Health check
curl http://localhost:8000/api/v1/health/
# Should return {"status": "healthy"}

# 2. Collector health
curl -H "X-API-Key: sova-dev-key-change-in-production" \
  http://localhost:8000/api/v1/health/collectors/
# Should return collector list

# 3. Practices endpoint
curl -H "X-API-Key: sova-dev-key-change-in-production" \
  http://localhost:8000/api/v1/practices/
# Should return empty paginated list

# 4. HOT leads endpoint
curl -H "X-API-Key: sova-dev-key-change-in-production" \
  http://localhost:8000/api/v1/leads/hot/
# Should return empty list

# 5. Tool invocation
curl -X POST -H "X-API-Key: sova-dev-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{"practice_npi": "1234567890"}' \
  http://localhost:8000/api/v1/tools/lead-score/
# Should return 202 with run_id

# 6. Swagger docs
# Open http://localhost:8000/api/docs/ in browser

# 7. Flower
# Open http://localhost:5555 — should show 2 workers (collectors, tools)

# 8. Django admin
# Open http://localhost:8000/admin/ — all models visible

# 9. Celery Beat
docker compose logs celery-beat | head -20
# Should show "beat: Starting..." and scheduled tasks
✅ SYSTEM IS COMPLETE WHEN:

All 7 Docker services healthy
Health endpoint returns 200
All API endpoints respond correctly
Flower shows both worker pools
Celery Beat is scheduling tasks
Django admin shows all models
Swagger docs render all endpoints
Foundation is ready for data: next step is downloading NPPES CSV and running the initial import


POST-BUILD: FIRST DATA LOAD
👤 FOUNDER ACTION — Once the system is running:
bashCopy# 1. Download NPPES data (~7GB)
mkdir -p data
# Download from https://download.cms.gov/nppes/ manually
# Place CSV in data/nppes_data.csv

# 2. Run initial NPPES import
docker compose exec web python manage.py import_nppes --file /app/data/nppes_data.csv

# 3. Build knowledge index (requires OPENAI_API_KEY)
docker compose exec web python manage.py build_knowledge_index

# 4. Run a test lead score
docker compose exec web python manage.py score_practice --npi <any_npi_from_db>

EXECUTION SUMMARY
PhaseStepsWhat You GetPre-flight0.0-0.1Project dir, .env, CLAUDE.mdPhase 00.2-0.9Full infrastructure, 7 services, health API, adminPhase 11.1-1.4NPPES collector, Google Places, practice DBPhase 22.1-2.65 job portal collectors, job APIPhase 33.1-3.2Competitor monitoring pipelinePhase 44.1-4.3Lifecycle events, government dataPhase 55.1-5.3Lead scoring engine, HOT leads APIPhase 66.1-6.3Knowledge base, outreach brief, revenue rescue, trust vectorPhase 7-97-9.1 to 7-9.3All remaining models, collector stubs, tool stubsPhase 1010.1Chatbot scaffold (v2)
Total Steps: ~30 focused Claude Code sessions, each building on the last, each independently verifiable.
The system is designed to be useful from Phase 5 onward — once practices are loaded and lead scoring works, the sales team gets value. Every subsequent phase adds more signal sources and more intelligent tools.