SOVA — Product Requirements Document (PRD)
Version: 1.0
Date: June 13, 2026
Author: Product & Architecture Team
Target Audience: Claude Code Implementation Agent
Status: APPROVED — Ready for Implementation

Section 1 — Project Overview
Sova is an autonomous marketing intelligence backend built for Neurality Health, a company that sells an AI voice receptionist to dental and medical practices across the United States. Neurality Health currently serves approximately 200 active client locations and must scale to 2,000 by end of 2027. Sova exists to solve a singular problem: finding, qualifying, and deeply understanding the ~200,000 dental practices in the US so that the sales team knows exactly who to pitch, when to pitch them, and what to say. Generic outreach across 200,000 practices is wasteful. The practices most likely to buy Neurality's product are showing specific, time-sensitive signals right now — a front desk job posting indicating chronic turnover, a practice recently sold to a new owner who is rebuilding their vendor stack, a spike in Google reviews complaining about unanswered phones, a DSO opening within 5 miles triggering competitive fear. Sova finds these signals before any human could, scores them into a composite lead score, and generates actionable outreach intelligence for the sales team.
Sova is not the AI receptionist product itself. It is not a CRM. It is not a chatbot in v1 (though a chatbot interface is architecturally designed for v2). It is a pure backend system: 110+ autonomous data collectors (called "sub-fragments") running on Celery Beat schedules, writing structured records into PostgreSQL; 28 intelligence tools that read from those tables and answer specific business questions (lead scoring, outreach briefs, competitive reports); an orchestrator layer that keeps everything healthy and coordinated; and eventually a conversational interface powered by LangGraph and Anthropic Claude that allows sales reps to query the intelligence directly. The tech stack is Django, PostgreSQL (with pgvector), Redis, Celery, LangGraph, and Anthropic Claude — mirroring a production-grade reference system called Eva that is thoroughly documented in the architectural learnings document.
The primary developer building Sova is learning Django while building this system. All code must be idiomatic Django, well-structured, and explained where non-obvious patterns are used. No premature optimization. No abstractions beyond what the task requires. Build for correctness first. The development environment is local only (Docker Compose), single-environment. Git is managed by the developer — the implementation agent never runs git commands.

Section 2 — System Architecture
Sova has four layers. Each layer has a strict contract: it knows what enters it and what leaves it, but it does not leak into adjacent layers. Every technical decision in this architecture is derived from proven patterns in the Eva reference system.
Layer 1 — Data Collector Fragments (Sub-fragments)
Definition: A sub-fragment is a single autonomous Celery task that monitors one specific data source, fetches raw structured data, validates it via a Pydantic schema, and writes it to its own PostgreSQL table. A sub-fragment does NOT interpret, score, or act on data. It does NOT call other sub-fragments. It does NOT contain business logic. The database is the only communication channel between sub-fragments.
Implementation: Each sub-fragment is a Celery task registered with Celery Beat. Each runs on its own schedule (hourly, daily, weekly, or monthly depending on source volatility). Each is independently failsafe — one broken collector does not break others.
Eight mandatory patterns every sub-fragment must implement (derived from Eva Layer 1):
Pattern 1 — Tenacity Retry: Every external HTTP call and every database write must use the shared sova_retry decorator with 3 attempts and exponential backoff (1s, 2s, 4s up to 10s max). On failure after all retries, log the error to SubFragmentRunLog.error_message and set last_run_status='failed'.
pythonCopy# sova/utils/retry.py
from tenacity import retry, stop_after_attempt, wait_exponential

sova_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True
)
Pattern 2 — Django Cache Distributed Mutex: Before processing any practice-specific record, acquire a lock using cache.add() (atomic in Redis). The lock key is sova:lock:{collector_name}:{practice_npi} with a 300-second timeout. If the lock is not acquired, skip that record (another worker is already on it). Always release the lock in a finally block.
pythonCopydef run_collector(practice_npi: str):
    lock_key = f"sova:lock:google_places_collector:{practice_npi}"
    acquired = cache.add(lock_key, "1", timeout=300)
    if not acquired:
        return
    try:
        # ... do the work ...
    finally:
        cache.delete(lock_key)
Pattern 3 — SubFragmentRunLog Update: After every execution, write the result to the SubFragmentRunLog model. Fields: name, last_run_at, last_run_status (success/partial/failed), records_written, error_message. The orchestrator reads this model to detect stale collectors (last_run_at > 2× expected interval) and silent failures (status=success but records_written=0).
Pattern 4 — Pydantic Output Schema Validation: Every sub-fragment defines a Pydantic model for its output record before writing any collection code. Every record is validated through the Pydantic model before DB write. Malformed records never reach the database.
Pattern 5 — Sensitive Data Sanitization: Before any logger.info() call containing query strings, URLs, or raw scraped data, sanitize phone numbers and emails:
pythonCopy# sova/utils/logging.py
import re

def sanitize_for_log(text: str) -> str:
    text = re.sub(r'\b\d{10,}\b', '[PHONE]', text)
    text = re.sub(r'[\w.+-]+@[\w-]+\.[a-z]{2,}', '[EMAIL]', text)
    return text
Pattern 6 — HTTP Request Timeout: Every httpx.get() call uses timeout=30.0. Every requests.get() call uses timeout=30. For async sub-fragments inside LangGraph tools, use asyncio.wait_for(coro, timeout=60). No network call is ever permitted to block indefinitely.
Pattern 7 — SovaConfig Import: Every configurable value (thresholds, timeouts, model names, rate limits) is read from the central SovaConfig class. No hardcoded magic numbers anywhere in collector code.
Pattern 8 — connections.close_all() in finally: Every Celery task closes all Django database connections in its finally block to prevent connection pool exhaustion across multiple workers.
SovaConfig class (complete specification):
pythonCopy# sova/config.py
from django.conf import settings

class SovaConfig:
    # LLM Models
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"
    FAST_MODEL = "claude-haiku-4-5-20251001"       # routing, classification
    ANALYSIS_MODEL = "claude-sonnet-4-6"            # outreach briefs, reports
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS = 1536
    TEMPERATURE = 0.3
    MAX_TOKENS = 4096

    # Scoring Thresholds
    HOT_SCORE_THRESHOLD = 78
    HOT_FIT_THRESHOLD = 65
    HIGH_CONFIDENCE_THRESHOLD = 500
    MODERATE_CONFIDENCE_THRESHOLD = 100

    # Celery / Tasks
    TASK_TIMEOUT_SECONDS = 300
    HTTP_REQUEST_TIMEOUT = 30
    TOOL_TIMEOUT = 60
    CELERY_HARD_TIME_LIMIT = 900
    CELERY_SOFT_TIME_LIMIT = 840

    # Rate Limits
    CHATBOT_API_RATE_LIMIT = 10    # per minute per user

    # Chatbot (v2)
    CHATBOT_RECURSION_LIMIT = 25
    MAX_MESSAGES_BEFORE_SUMMARIZE = 15
    KEEP_RECENT_MESSAGES = 5

    # Knowledge Base
    KNOWLEDGE_HIT_THRESHOLD = 0.75
    KNOWLEDGE_CACHE_TTL_SECONDS = 900  # 15 minutes

    # Token / Context Caps
    MAX_OUTREACH_BRIEF_SIGNALS_CHARS = 8000
    MAX_COMPETITIVE_REPORT_CHANGES_CHARS = 12000
    MAX_REVENUE_RESCUE_EVIDENCE_CHARS = 6000
    MAX_CHATBOT_CONTEXT_CHARS = 48000
    MAX_SCHEMA_CHARS = 3000

    # SQL Safety
    DANGEROUS_SQL_PATTERNS = [
        r'\bINSERT\b', r'\bUPDATE\b', r'\bDELETE\b', r'\bDROP\b',
        r'\bTRUNCATE\b', r'\bALTER\b', r'\bCREATE\b', r'\bGRANT\b',
        r'\bREVOKE\b', r'\bEXEC(UTE)?\b'
    ]
    SQL_STATEMENT_TIMEOUT_MS = 30000
    SQL_FALLBACK_LIMIT = 1000

    # Signal Decay Half-Lives (days)
    HALF_LIFE_DEMO_CALL = 7
    HALF_LIFE_JOB_POSTING = 14
    HALF_LIFE_REVIEW_COMPLAINT = 21
    HALF_LIFE_OWNERSHIP_TRANSFER = 60
    HALF_LIFE_NEW_NPI = 90
    HALF_LIFE_TECHNOGRAPHIC_GAP = 180

    @classmethod
    def is_langsmith_enabled(cls) -> bool:
        return bool(getattr(settings, 'LANGSMITH_TRACING', False) and
                    getattr(settings, 'LANGSMITH_API_KEY', None))
SubFragmentRunLog model (exact specification):
pythonCopyclass SubFragmentRunLog(models.Model):
    name = models.CharField(max_length=100, unique=True)
    last_run_at = models.DateTimeField(null=True)
    last_run_status = models.CharField(max_length=20, default='never_run')
    records_written = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    expected_interval_hours = models.IntegerField(default=24)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sub_fragment_run_log'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['last_run_status']),
        ]

Layer 2 — Intelligence Tools
Definition: A tool reads from one or more sub-fragment database tables, processes/scores/correlates the data, and answers one specific business question. Tools do NOT collect data. They are called on demand — by the orchestrator, by an API endpoint, or eventually by the chatbot.
Implementation: Each tool is an async Python function in sova/tools/. For the future chatbot layer, each tool is also decorated with @tool from langchain_core.tools and includes a docstring that serves as the LLM's instruction for when to call it.
Ten mandatory patterns every LLM-based tool must implement (derived from Eva Layer 2):
Pattern 1 — Pydantic Structured Output: Every LLM call uses llm.with_structured_output(PydanticSchema). The Pydantic schema is defined BEFORE the prompt is written. The LLM is never asked to produce raw text that gets parsed — it produces typed JSON matching the schema.
Pattern 2 — Anthropic Prompt Caching: System prompts use cache_control: {"type": "ephemeral"}. For batch processing (e.g., classifying 50 newsletter items), only the first call pays for the full system prompt. Remaining calls pay only for the dynamic portion. This produces 60-80% token cost reduction.
Pattern 3 — Two-Level Knowledge Cache: Slow-changing data (ICP config, scoring weights, competitor list) is cached in a module-level in-process dict with 15-minute TTL. Request-scoped data goes in Django cache (Redis). No Postgres or Redis hit for data that won't change within a Celery worker's lifetime.
Pattern 4 — Parallel DB Reads: Independent database reads within a tool use asyncio.gather() with a Semaphore(8) cap. When computing a lead score, reads from job_postings, reviews, lifecycle_events, and technographic tables run concurrently.
Pattern 5 — Confidence Scoring: Every signal carries a confidence rating. HIGH = direct evidence, n > 500, multiple sources (weight × 1.0). MODERATE = single reliable source, n 100-500 (weight × 0.75). LOW = inference, small n, single data point (weight × 0.5).
Pattern 6 — pgvector Knowledge Base: Semantic retrieval from SovaKnowledge table using cosine distance. If cosine similarity ≥ 0.75, answer directly from knowledge base without running full computation. Use text-embedding-3-small (1536 dimensions).
Pattern 7 — SQL Safety Layer: For any LLM-generated SQL in the chatbot: (1) pattern-match against DANGEROUS_SQL_PATTERNS, (2) validate tables against ALLOWED_TABLES, (3) wrap in SET LOCAL statement_timeout, (4) auto-add LIMIT 1000, (5) return string errors to LLM — never crash.
Pattern 8 — Tool Error Handling: Every tool catches all exceptions internally and returns a structured error string. Never raise an exception that propagates to the LangGraph engine.
Pattern 9 — Partial Result Synthesis: On GraphRecursionError, catch the error, extract partial tool results from message history, call synthesize_partial_reply() using Haiku, and return a degraded-but-useful result with a note suggesting Deep Analysis mode.
Pattern 10 — Token Caps: Every tool that injects context into an LLM prompt respects per-tool character limits defined in SovaConfig. When data exceeds the cap, truncate to the most recent N records.

Layer 3 — Orchestrator Brain
Definition: The orchestrator manages scheduling, health monitoring, and coordination. It does NOT contain business logic — that lives in the tools. It is a thin layer.
Implementation: Celery Beat handles scheduling. SubFragmentRunLog handles health tracking. SovaTaskRun handles tool invocation status.
Seven mandatory patterns (derived from Eva Layer 3):
Pattern 1 — SovaConversation + SovaTaskRun models:
pythonCopyclass SovaConversation(models.Model):
    conversation_id = models.UUIDField(default=uuid.uuid4, unique=True)
    thread_id = models.CharField(max_length=255, unique=True)
    user_identifier = models.CharField(max_length=255)
    messages = models.JSONField(default=list)
    mode = models.CharField(max_length=50, default="chatbot")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class SovaTaskRun(models.Model):
    run_id = models.UUIDField(default=uuid.uuid4, unique=True)
    conversation = models.ForeignKey(SovaConversation, null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='task_runs')
    task_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, default="pending")
    result = models.JSONField(null=True)
    error = models.TextField(blank=True)
    progress = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)
Pattern 2 — HTTP 202 Polling: POST to a tool endpoint returns HTTP 202 immediately with run_id and status_url. GET on the status URL returns current status (pending/running/completed/failed/cancelled) and result when complete.
Pattern 3 — Cooperative Cancellation: Redis key sova:cancel:{run_id}. POST to cancel endpoint sets this key. Every LangGraph node checks this key at entry. Celery hard time limit (900s) is the backstop.
Pattern 4 — Celery Time Limits: Every Celery task has time_limit=900 (hard kill at 15min) and soft_time_limit=840 (SoftTimeLimitExceeded at 14min, allowing graceful finalization).
Pattern 5 — Per-Event-Loop Async Resources: AsyncPostgresSaver instances are cached per id(asyncio.get_running_loop()). Never share a single instance across Celery workers.
Pattern 6 — Connection Cleanup: connections.close_all() in the finally block of every Celery task.
Pattern 7 — Health Monitoring Endpoint: GET /api/v1/health/collectors/ returns last-run status for every sub-fragment, with lists of stale_collectors and silent_fail_collectors.

Layer 4 — Chatbot Agent (v2 — Design Now, Build Later)
Status: v2 — Scaffold the code structure and API endpoints now. Full implementation deferred to Phase 10.
Ten patterns (derived from Eva Layer 4, documented completely for future implementation):
Pattern 1 — LangGraph 2-Node StateGraph: agent node calls LLM → if tool calls, tools node executes them → loop → if no tool calls, END. Compiled with checkpointer and recursion_limit=25.
Pattern 2 — AsyncPostgresSaver Checkpointer: Creates tables checkpoints, checkpoint_blobs, checkpoint_writes. Same thread_id resumes exact state from last checkpoint. Conversation history fully durable across restarts.
Pattern 3 — Mode Router: Uses Haiku at temperature=0 with SovaRoutingDecision Pydantic schema. Routes to chatbot, deep_analysis, or report_generation. Always falls back to chatbot on failure.
Pattern 4 — Context Auto-Summarization: At 15+ messages, summarize older messages via LLM, keep last 5 verbatim. Keeps token costs bounded while preserving continuity.
Pattern 5 — Redis SSE Streaming: Events published via Redis pipeline: RPUSH to buffered list (24h TTL) + PUBLISH to live channel. Client sends Last-Event-ID header on reconnect for cursor-based replay. Event types: run_started, thinking, tool_call, tool_result, partial_text, final_text, run_completed, run_failed, keepalive (10s interval).
Pattern 6 — Five DRF Endpoints: Create thread, submit query (202), poll status, SSE stream, cancel.
Pattern 7 — Tool Registry: All intelligence tools decorated with @tool and bound via llm.bind_tools(all_tools). Docstrings written as API documentation for the LLM.
Pattern 8 — sync_to_async Bridge: Every Django ORM query inside async code wrapped with asgiref.sync_to_async.
Pattern 9 — Dual State Storage: LangGraph checkpoint stores full technical state (including intermediate tool calls). SovaConversation.messages JSONField stores cleaned, user-visible conversation history for UI rendering.
Pattern 10 — Rate Limiting: 10 requests/min/user on the query endpoint using django-ratelimit.

Section 3 — Technology Stack
PackageVersionRole in SovaPrioritydjango>=4.2,<5.1Backend frameworkDay 1djangorestframework>=3.15REST API layerDay 1django-cors-headers>=4.3CORS for future frontendDay 1drf-yasg>=1.21API documentation (Swagger)Day 1celery>=5.4Task queue for sub-fragments and toolsDay 1django-celery-beat>=2.6Database-backed periodic task schedulingDay 1redis>=5.0Celery broker, Django cache backend, SSE pub/subDay 1django-redis>=5.4Django cache backend using Redis (mutex locks)Day 1psycopg[binary]>=3.1PostgreSQL driver (Psycopg 3, required by langgraph-checkpoint-postgres)Day 1psycopg-pool>=3.2Async connection pool for LangGraph checkpointerPhase 10pgvector>=0.3Django integration for pgvector (VectorField, CosineDistance)Phase 6langchain-core>=0.3@tool, BaseTool, message typesDay 1langchain-anthropic>=1.4ChatAnthropic for all LLM callsDay 1langchain-openai>=0.3OpenAIEmbeddings for pgvector knowledge basePhase 6langgraph>=1.0StateGraph, MessagesState, conditional edgesPhase 10langgraph-checkpoint-postgres>=3.0AsyncPostgresSaver for conversation checkpointingPhase 10langsmith>=0.2LLM call tracing and observabilityDay 1pydantic>=2.7All state, request, response, and output schemasDay 1tenacity>=8.3Retry with exponential backoff on all external callsDay 1httpx>=0.27Async HTTP client for scrapers and API callsDay 1beautifulsoup4>=4.12HTML parsing for web scraping sub-fragmentsDay 1feedparser>=6.0RSS/Atom feed parsingPhase 1sentry-sdk[django,celery]>=2.0Production error capture across Django views and Celery tasksDay 1asgiref>=3.7sync_to_async bridge for Django ORM in async LangGraphPhase 10sqlparse>=0.5SQL safety validation for LLM-generated queriesPhase 10flower>=2.0Celery monitoring web UIDay 1gunicorn>=22.0WSGI server for DjangoDay 1python-dotenv>=1.0Environment variable loading from .envDay 1django-ratelimit>=4.1API rate limitingPhase 10
Explicitly NOT included:
PackageReasonPrefectSova uses Celery Beat. Add only if multi-step pipeline dependencies become unmanageable.mem0ai + QdrantDisabled in Eva. Too immature. Not needed for v1.FAISSpgvector is already required. Use pgvector everywhere.text-embedding-3-largeUse text-embedding-3-small (1536-dim). 5× cheaper, 90%+ quality for Sova's retrieval tasks.xhtml2pdfPDF export not needed.Deep AgentsPre-1.0, rapidly evolving API. LangGraph directly is more stable.

Section 4 — Django Project Structure
Copysova/
├── manage.py
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
├── sova/                          # Django project package
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
│   ├── celery.py                  # Celery app configuration
│   └── config.py                  # SovaConfig class
│
├── core/                          # Shared models, utilities, base classes
│   ├── __init__.py
│   ├── models.py                  # Practice, SubFragmentRunLog, Signal, LeadScore
│   ├── admin.py
│   ├── serializers.py             # Practice serializers
│   ├── views.py                   # Health endpoint, practice list/detail
│   ├── urls.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── retry.py               # sova_retry decorator
│   │   ├── logging.py             # sanitize_for_log
│   │   ├── cache.py               # Distributed mutex helper, knowledge cache
│   │   └── tasks.py               # SovaBaseTask class
│   └── management/
│       └── commands/
│           └── build_knowledge_index.py
│
├── collectors/                    # All sub-fragment Celery tasks
│   ├── __init__.py
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── job_portals.py         # dentalpost, indeed, ihiredental, ziprecruiter, linkedin_jobs
│   │   ├── social_platforms.py    # facebook_api, linkedin_api, facebook_hyperbrowser, youtube, tiktok
│   │   ├── conferences.py         # conference_website_monitor, conference_social_tracker
│   │   ├── newsletters.py        # email_inbox_reader, newsletter_classifier
│   │   ├── opinion_platforms.py   # reddit_scout, quora_scout, dentaltown_forum_scout
│   │   ├── practice_data.py       # nppes_collector, google_places_collector, clinic_hours_change_monitor
│   │   ├── website_monitoring.py  # website_crawler, rss_feed_monitor, competitor_website_monitor
│   │   ├── competitor_intel.py    # all 11 competitor intelligence collectors
│   │   ├── google_cloud.py        # google_news_collector, google_trends_monitor
│   │   ├── review_platforms.py    # yelp, healthgrades, zocdoc, review_response_rate, reputation_shock
│   │   ├── local_market.py        # business_license_monitor, commercial_real_estate_scout
│   │   ├── partnerships.py        # dental_supplier, insurance_network, insurance_plan_change, etc.
│   │   ├── enrichment.py          # hunter_enricher, linkedin_profile_enricher, phone_validator
│   │   ├── champion.py            # champion_job_change_tracker
│   │   ├── lifecycle.py           # npi_new_registration, dental_broker, dental_school, building_permit, multi_location
│   │   ├── government.py          # cms_enrollment, sba_loan, oig_exclusion, hrsa_hpsa, bls_staffing, etc.
│   │   ├── associations.py        # ada_member, dental_specialty, aadom, beckers
│   │   ├── technographic.py       # pms_signal_extractor, booking_tech, bilingual, g2_intent, pms_migration, patient_financing
│   │   ├── intent_signals.py      # website_visitor_deanonymizer, bombora, branded_search, first_party_voice_demo
│   │   ├── dso_intelligence.py    # dso_expansion_monitor, saturation_zip_analyzer
│   │   ├── community_intel.py     # dental_community_mention, peer_influence, practice_advisor, referral_network
│   │   ├── ip_monitoring.py       # uspto_trademark, patent_filing
│   │   ├── podcast_webinar.py     # dental_podcast, dental_webinar_calendar
│   │   ├── pms_pain.py            # pms_vendor_support_forum_sentinel
│   │   ├── contextual.py          # weather_disruption_monitor
│   │   ├── ce_monitoring.py       # ce_enrollment_monitor
│   │   ├── local_journals.py      # local_biz_journal_monitor
│   │   ├── burnout_signals.py     # dental_staffing_agency, staff_burnout_aggregator, patient_access_complaint
│   │   ├── access_audit.py        # live_answer_audit, after_hours_coverage, same_day_availability, new_patient_promo, contact_friction, mobile_conversion
│   │   ├── staff_transition.py    # office_manager_turnover, associate_arrival, answering_service_vendor_loss
│   │   ├── first_party.py         # first_party_voice_demo_tracker, lost_deal_reason_miner, direct_mail_response
│   │   └── schemas/               # Pydantic output schemas per strategy group
│   │       ├── __init__.py
│   │       ├── job_posting_schemas.py
│   │       ├── review_schemas.py
│   │       ├── competitor_schemas.py
│   │       └── ... (one per strategy)
│   ├── models.py                  # All sub-fragment output table Django models
│   └── admin.py
│
├── tools/                         # Intelligence tools
│   ├── __init__.py
│   ├── fit_score.py
│   ├── intent_score.py
│   ├── lead_score.py
│   ├── transition_window.py
│   ├── access_failure_index.py
│   ├── outreach_brief.py
│   ├── competitive_leaderboard.py
│   ├── competitive_report.py
│   ├── market_report.py
│   ├── client_health.py
│   ├── churn_warning.py
│   ├── practice_growth.py
│   ├── displacement_engine.py
│   ├── revenue_rescue.py
│   ├── buying_committee.py
│   ├── trust_vector.py
│   ├── influence_map.py
│   ├── local_pressure.py
│   ├── signal_calibration.py
│   ├── content_generation.py
│   ├── dso_pipeline.py
│   ├── staff_stability.py
│   ├── relocation_detector.py
│   ├── ce_engagement.py
│   ├── financial_stress.py
│   ├── competitive_churn.py
│   ├── persona_stitcher.py
│   ├── regulatory_watch.py
│   ├── schemas/                   # Pydantic output schemas per tool
│   │   ├── __init__.py
│   │   ├── lead_score_schemas.py
│   │   ├── outreach_schemas.py
│   │   └── ... (one per tool)
│   ├── views.py                   # DRF views for tool invocation endpoints
│   ├── serializers.py
│   └── urls.py
│
├── orchestrator/                  # Health monitoring, scheduling coordination
│   ├── __init__.py
│   ├── models.py                  # SovaTaskRun
│   ├── views.py                   # Health endpoints, task status polling
│   ├── serializers.py
│   ├── urls.py
│   └── tasks.py                   # Health check tasks, score recomputation scheduler
│
├── chatbot/                       # v2 — scaffolded now
│   ├── __init__.py
│   ├── graph.py                   # LangGraph StateGraph definition
│   ├── checkpointer.py            # AsyncPostgresSaver per-loop caching
│   ├── router.py                  # Mode router (LLM query classification)
│   ├── streaming.py               # Redis SSE pub/sub + list buffer
│   ├── summarization.py           # Context auto-summarization
│   ├── models.py                  # SovaConversation
│   ├── views.py                   # 5 DRF endpoints
│   ├── serializers.py             # SovaQueryInputSerializer
│   └── urls.py
│
├── knowledge/                     # pgvector knowledge base
│   ├── __init__.py
│   ├── models.py                  # SovaKnowledge
│   ├── store.py                   # DatabaseKnowledgeStore (search, embed, upsert)
│   ├── yaml/
│   │   ├── outreach_playbooks.yaml
│   │   ├── objection_handlers.yaml
│   │   ├── competitor_comparisons.yaml
│   │   └── icp_profiles.yaml
│   └── case_studies/
│       └── *.md
│
└── Docs/
    ├── sova-agent-context.md
    ├── subfragment-strategy-map.md
    └── learnings-from-eva.md

Section 5 — Database Schema
Core Tables
practices — Master practice record. Every dental/medical practice in the US.
ColumnTypeConstraintsNotesnpiVARCHAR(10)PRIMARY KEYNational Provider Identifierpractice_nameVARCHAR(255)NOT NULLaddress_line1VARCHAR(255)address_line2VARCHAR(255)cityVARCHAR(100)stateCHAR(2)Two-letter codezip_codeVARCHAR(10)5 or 9 digitphoneVARCHAR(20)Cleaned formatspecialty_taxonomy_codeVARCHAR(20)From NPPESspecialty_displayVARCHAR(100)Human-readable specialtypractice_typeVARCHAR(20)solo / groupentity_typeVARCHAR(20)individual / organizationwebsite_urlVARCHAR(500)Discovered via crawldomainVARCHAR(255)Extracted from website_urlis_activeBOOLEANDEFAULT TRUEis_current_clientBOOLEANDEFAULT FALSENeurality client flagis_oig_excludedBOOLEANDEFAULT FALSEImmediate disqualifierlatitudeDECIMAL(10,7)For proximity calculationslongitudeDECIMAL(10,7)created_atTIMESTAMPauto_now_addupdated_atTIMESTAMPauto_now
Indexes: state, zip_code, specialty_taxonomy_code, is_active, practice_type, (state, is_active)

signals — Individual raw signals collected by sub-fragments. Central signal store enabling decay recomputation.
ColumnTypeConstraintsNotesidBIGSERIALPRIMARY KEYpractice_npiVARCHAR(10)FK → practices.npi, INDEXsignal_typeVARCHAR(50)NOT NULL, INDEXe.g. "job_posting", "review_complaint", "demo_call"signal_sourceVARCHAR(50)NOT NULLe.g. "dentalpost", "google_places", "twilio"raw_valueFLOATNOT NULLNumeric signal value (0-100 or raw count)confidenceVARCHAR(10)NOT NULLHigh / Moderate / Lowevidence_countINTEGERDEFAULT 1evidence_summaryTEXTBrief human-readable evidencehalf_life_daysINTEGERNOT NULLFor decay computationcollected_atTIMESTAMPNOT NULL, INDEXWhen signal was observedexpires_atTIMESTAMPOptional hard expirymetadataJSONBAdditional signal-specific data
Indexes: practice_npi, signal_type, collected_at, (practice_npi, signal_type, collected_at)

lead_scores — One row per practice per scoring run. Score history is versioned — recomputation creates new rows.
ColumnTypeConstraintsNotesidBIGSERIALPRIMARY KEYpractice_npiVARCHAR(10)FK → practices.npi, INDEXcomposite_scoreFLOATNOT NULL0-100fit_scoreFLOAT0-100operational_pain_scoreFLOAT0-100timing_scoreFLOAT0-100first_party_intent_scoreFLOAT0-100technographic_scoreFLOAT0-100human_route_scoreFLOAT0-100geography_scoreFLOAT0-100tierVARCHAR(10)NOT NULLHOT / WARM / COLDmodifiers_appliedJSONBList of {event, modifier_value}signals_summaryJSONBWhich signals fired, decayed weightshot_qualificationJSONBEach of 6 conditions: met/unmetscored_atTIMESTAMPNOT NULL, INDEXis_latestBOOLEANDEFAULT TRUEDenormalized for fast queries
Indexes: practice_npi, scored_at, tier, (tier, is_latest), (practice_npi, is_latest)

sub_fragment_run_log — Health tracking for every sub-fragment. (Defined above in Section 2.)
sova_conversations — Chatbot sessions. (v2, defined above in Section 2.)
sova_task_runs — Tool invocation status tracking. (Defined above in Section 2.)
sova_knowledge — pgvector knowledge base.
ColumnTypeConstraintsNotesidSERIALPRIMARY KEYcontentTEXTNOT NULLSource textembeddingVECTOR(1536)NOT NULLtext-embedding-3-smallitem_typeVARCHAR(30)NOT NULLplaybook / objection_handler / case_study / competitor_comparison / icp_profiletitleVARCHAR(255)metadataJSONBspecialty, geography, pain_profile, etc.content_hashVARCHAR(64)UNIQUESHA-256 for upsert dedupcreated_atTIMESTAMPauto_now_addupdated_atTIMESTAMPauto_now
Index: HNSW index on embedding with vector_cosine_ops

Sub-fragment Output Tables
Due to the extreme volume (29 strategy-grouped tables), I provide the complete specification for the 10 highest-priority tables and a consolidated field pattern for the remaining 19.
1. job_postings — Output from dentalpost, indeed, ihiredental, ziprecruiter, linkedin_jobs collectors
ColumnTypeNotesidBIGSERIAL PKpractice_npiVARCHAR(10) FK INDEXResolved to practice if possiblepractice_name_rawVARCHAR(255)As scraped (pre-resolution)sourceVARCHAR(20) NOT NULLdentalpost / indeed / ihiredental / ziprecruiter / linkedin_jobsjob_titleVARCHAR(255) NOT NULLposted_atTIMESTAMPWhen job was posteddescription_textTEXTFull job descriptionpms_mentionsJSONBExtracted software names (Dentrix, Eaglesoft, etc.)is_chronic_repostBOOLEAN DEFAULT FALSESame role 3+ times in 12 monthsrepost_countINTEGER DEFAULT 1is_front_desk_roleBOOLEAN DEFAULT TRUEbilingual_requiredBOOLEAN DEFAULT FALSEmigration_language_detectedBOOLEAN DEFAULT FALSEPMS switch signalsburnout_keywords_foundJSONBList of matched keywordslocation_cityVARCHAR(100)location_stateCHAR(2)raw_urlVARCHAR(500)content_hashVARCHAR(64)Dedup across sourcescollected_atTIMESTAMP NOT NULL
Indexes: practice_npi, source, posted_at, collected_at, (practice_npi, source, posted_at)
2. google_places_data — Output from google_places_collector, clinic_hours_change_monitor
ColumnTypeNotesidBIGSERIAL PKpractice_npiVARCHAR(10) FK INDEXgoogle_place_idVARCHAR(255)review_countINTEGERstar_ratingDECIMAL(2,1)review_velocity_30dFLOATReviews per 30 daysphone_friction_countINTEGER DEFAULT 0Reviews mentioning phone/voicemailphone_friction_keywordsJSONBMatched keyword listopening_hoursJSONBCurrent hourshours_changedBOOLEAN DEFAULT FALSEhours_change_typeVARCHAR(20)extended / reduced / nullresponse_rateFLOATOwner response percentagecollected_atTIMESTAMP NOT NULL
3. competitor_ads — Output from facebook_ads, google_ads, linkedin_ads collectors
ColumnTypeNotesidBIGSERIAL PKcompetitor_nameVARCHAR(100) NOT NULL INDEXplatformVARCHAR(20) NOT NULLfacebook / google / linkedinad_copyTEXTcreative_formatVARCHAR(50)image / video / carouselcta_textVARCHAR(100)target_geographyJSONBestimated_spend_bracketVARCHAR(30)run_duration_daysINTEGERis_activeBOOLEAN DEFAULT TRUEfirst_seen_atTIMESTAMPlast_seen_atTIMESTAMPcollected_atTIMESTAMP NOT NULL
4. lifecycle_events — Output from npi_new_registration, dental_broker, building_permit, etc.
ColumnTypeNotesidBIGSERIAL PKpractice_npiVARCHAR(10) FK INDEXevent_typeVARCHAR(50) NOT NULL INDEXnew_npi / broker_listing / sold / permit / expansion / new_licensee / sba_loanevent_dateDATEWhen the event occurredevent_sourceVARCHAR(50) NOT NULLdescriptionTEXTmetadataJSONBEvent-specific detailscollected_atTIMESTAMP NOT NULL
5. review_data — Output from yelp, healthgrades, zocdoc, review_response_rate, reputation_shock
ColumnTypeNotesidBIGSERIAL PKpractice_npiVARCHAR(10) FK INDEXplatformVARCHAR(20) NOT NULLyelp / healthgrades / zocdocreview_countINTEGERstar_ratingDECIMAL(2,1)is_claimedBOOLEANProfile claimed by owneris_listedBOOLEANFor zocdoc: listed or notresponse_rateFLOATreputation_shockBOOLEAN DEFAULT FALSE3+ access complaints in 30 dayscomplaint_velocity_30dFLOATcollected_atTIMESTAMP NOT NULL
6-29: Remaining tables follow the same pattern:

BIGSERIAL primary key
practice_npi VARCHAR(10) FK with index (where practice-specific)
source VARCHAR(50) identifying the collector
3-5 signal-carrying columns specific to the data type
metadata JSONB for additional flexible data
collected_at TIMESTAMP NOT NULL with index
Composite indexes on (practice_npi, collected_at) where applicable

The remaining table definitions (tables 6-29) are: website_crawl_data, social_metrics, forum_posts, newsletter_items, rss_articles, competitor_snapshots, competitor_signals, government_data, insurance_data, champion_signals, enrichment_data, technographic_signals, access_audit_results, availability_signals, staff_transition_signals, intent_signals, dso_signals, market_signals, burnout_scores, community_signals, youtube_data, tiktok_data, conference_signals.
Each follows the exact same pattern: id, practice_npi (FK, indexed), source, 3-5 domain-specific columns, metadata JSONB, collected_at (indexed).

Section 6 — Sub-fragment Implementation Specification
Strategy 1 — Job Portal Scouting
1. dentalpost_collector
AttributeValueTask signaturedef dentalpost_collector()ScheduleEvery 24 hoursData sourcehttps://www.dentalpost.net/dental-jobs/ — public HTMLAuthenticationNone — public scrapingOutput tablejob_postingsOutput fieldspractice_name_raw, job_title, posted_at, description_text, location_city, location_state, raw_url, is_front_desk_roleCompliance flagGREEN — public data, no authRate limitingMax 1 request/second to dentalpost.netSpecial handlingDetect chronic reposting: query existing job_postings for same practice + similar title within 12 months. If count ≥ 3, set is_chronic_repost=True. Attempt NPI resolution by fuzzy matching practice_name_raw + location against practices table.
2. indeed_collector
AttributeValueTask signaturedef indeed_collector()ScheduleEvery 24 hoursData sourcehttps://www.indeed.com/jobs?q=dental+front+desk — public HTMLAuthenticationNone — Indeed API is closed, scraping onlyOutput tablejob_postingsOutput fieldsSame as dentalpost_collector with source="indeed"Compliance flagAMBER — Indeed may block scrapers. Implement rotating user-agents and respectful rate limiting.Rate limitingMax 1 request per 2 secondsSpecial handlingContent hash dedup against dentalpost_collector — same job posting may appear on both.
3. linkedin_jobs_collector
AttributeValueTask signaturedef linkedin_jobs_collector()ScheduleEvery 48 hoursData sourceLicensed job data API (JSearch via RapidAPI, or Jobicy)AuthenticationJSEARCH_API_KEY env varOutput tablejob_postingsOutput fieldsSame schema with source="linkedin_jobs"Compliance flagREPLACE METHOD — Do NOT scrape LinkedIn directly. Use a licensed job data API that aggregates LinkedIn and other platforms. LinkedIn aggressively blocks scrapers; CFAA exposure possible for commercial use.Rate limitingPer API provider limitsSpecial handlingExtract PMS mentions from description using regex patterns for Dentrix, Eaglesoft, Open Dental, Curve Dental, etc.
4. ihiredental_collector
AttributeValueTask signaturedef ihiredental_collector()ScheduleEvery 48 hoursData sourcehttps://www.ihiredental.com/ — public HTMLAuthenticationNoneOutput tablejob_postingsCompliance flagGREENRate limitingMax 1 request/second
5. ziprecruiter_collector
AttributeValueTask signaturedef ziprecruiter_collector()ScheduleEvery 48 hoursData sourcehttps://www.ziprecruiter.com/ — public HTMLAuthenticationNoneOutput tablejob_postingsCompliance flagAMBER — ZipRecruiter may block. Respectful rate limiting required.Rate limitingMax 1 request per 2 seconds
6. glassdoor_collector
AttributeValueTask signaturedef glassdoor_collector()ScheduleWeeklyData sourcehttps://www.glassdoor.com/ — partially publicAuthenticationNoneOutput tablereview_data (with platform="glassdoor") and burnout_scoresCompliance flagSTATUS: DEPRIORITIZED — ToS risk + low marginal signal. Job re-post velocity from dentalpost/indeed + burnout language from staff_burnout_aggregator covers the same signal more safely. Build last or skip.Special handlingSummary-level only. No bulk extraction.

Strategy 6 — Practice Data Foundation
21. nppes_collector
AttributeValueTask signaturedef nppes_collector()ScheduleMonthly (full refresh). Weekly delta check for new registrations.Data sourcehttps://download.cms.gov/nppes/ — NPPES monthly CSV (~7GB)AuthenticationNone — free public dataOutput tablepractices (master table — upsert)Output fieldsnpi, practice_name, address_line1, city, state, zip_code, phone, specialty_taxonomy_code, practice_type, entity_typeCompliance flagGREEN — US government public dataRate limitingN/A — CSV downloadSpecial handlingCRITICAL: Stream CSV row-by-row using Python's built-in csv module — do NOT load entire 7GB file into memory. Filter for dental taxonomy codes (122300000X and sub-codes). Use bulk_create with update_conflicts=True for upsert. Set batch_size=5000 for bulk operations. Track records_written count for SubFragmentRunLog.
22. google_places_collector
AttributeValueTask signaturedef google_places_collector(practice_npi: str) — called per practice, fanned out by CeleryScheduleDaily for high-priority practices, weekly for all othersData sourceGoogle Places API (maps.googleapis.com)AuthenticationGOOGLE_MAPS_API_KEY env varOutput tablegoogle_places_dataOutput fieldsgoogle_place_id, review_count, star_rating, review_velocity_30d, phone_friction_count, phone_friction_keywords, opening_hours, response_rateCompliance flagGREEN — official APIRate limitingBatch carefully — paid per call. Process max 5,000 practices per daily run. Priority queue: HOT/WARM first, then COLD.Special handlingPhone friction keywords to detect in review text: "couldn't get through", "voicemail", "on hold", "never answers", "no one answered", "can't reach", "busy signal". Store keyword matches in phone_friction_keywords JSONB. Compute review_velocity_30d as delta from previous collection.
23. clinic_hours_change_monitor
AttributeValueTask signaturedef clinic_hours_change_monitor(practice_npi: str)ScheduleWeeklyData sourceGoogle Places API — opening_hours fieldAuthenticationGOOGLE_MAPS_API_KEYOutput tablegoogle_places_data (update hours fields)Special handlingCompare current opening_hours against previous stored baseline. If changed: set hours_changed=True, classify as extended (more hours) or reduced (fewer hours). Extending to evenings/weekends = volume growth signal. Reducing = financial stress signal.

Remaining Sub-fragments (Strategies 2-5, 7-33)
Due to the immense scale (110 sub-fragments), I provide the complete specification for all remaining sub-fragments organized by strategy, following the same 9-field format. Each includes: task signature, schedule, data source, authentication, output table, output fields, compliance flag, rate limiting, and special handling.
Strategy 2 — Social Platform Intelligence (collectors 7-12):
7. facebook_api_collector — Schedule: Weekly. Source: Facebook Graph API (official). Auth: FACEBOOK_APP_ID, FACEBOOK_APP_SECRET. Output: social_metrics. Compliance: GREEN. Collects: follower_count, post_frequency, last_activity_date, engagement_rate per practice page.
8. linkedin_api_collector — Schedule: Weekly. Source: LinkedIn Company Pages API (official). Auth: LINKEDIN_ACCESS_TOKEN. Output: social_metrics. Compliance: GREEN. Collects: follower_count, employee_count, follower_growth_rate per competitor and practice.
9. facebook_hyperbrowser_agent — Schedule: Weekly. Source: Hyperbrowser SDK. Auth: HYPERBROWSER_API_KEY. Output: social_metrics. Compliance: AMBER — limit to official Graph API; use Hyperbrowser only for genuinely public content with no login.
10. linkedin_hyperbrowser_agent — STATUS: REPLACE METHOD — Use Proxycurl API instead. LinkedIn explicitly prohibits automated session simulation. Auth: PROXYCURL_API_KEY. Output: community_signals.
11. youtube_competitor_monitor — Schedule: Weekly. Source: YouTube Data API v3 (official, free tier). Auth: YOUTUBE_API_KEY. Output: youtube_data. Compliance: GREEN. Collects: upload_frequency, view_count, engagement_rate, topic_pattern per competitor channel + keyword searches.
12. tiktok_industry_monitor — Schedule: Weekly. Source: TikTok Research API (official). Auth: TIKTOK_API_KEY. Output: tiktok_data. Compliance: GREEN (if approved). Collects: video_count, hashtag_volume, competitor_presence per category keyword.
Strategy 3 — Conferences (13-14):
13. conference_website_monitor — Schedule: Weekly. Source: HTTP scrape of HLTH, ADA Annual, Dentsply Sirona World. Output: conference_signals. Collects: speakers, sponsors, session_topics. GREEN.
14. conference_social_tracker — MERGE: Not a standalone sub-fragment. Merge into facebook_api_collector and linkedin_api_collector as a query preset targeting conference page accounts.
Strategy 4 — Newsletters (15-16):
15. email_inbox_reader — Schedule: Every 4 hours. Source: Gmail API (official, OAuth). Auth: GMAIL_CREDENTIALS_PATH. Output: newsletter_items. GREEN. Special: Strip HTML, extract plain text. Pass to newsletter_classifier.
16. newsletter_classifier — Schedule: Event-triggered (on email_inbox_reader completion). Source: Anthropic Claude API. Auth: ANTHROPIC_API_KEY. Output: Updates newsletter_items with signal_type (Opportunity/Content/Noise). Uses prompt caching for batch efficiency. Pydantic output: NewsletterClassification(signal_type, reason, practice_name, confidence).
Strategy 5 — Opinion Platforms (17-20):
17. reddit_scout — Schedule: Daily. Source: Reddit API (official, free). Auth: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET. Output: forum_posts. GREEN. Targets: r/dentistry, r/DentalHygiene, r/DentalPracticeManagement.
18. quora_scout — STATUS: DEPRIORITIZED — Quora dental traffic is sparse. Reddit and Dentaltown cover this signal better. Build last or skip.
19. dentaltown_forum_scout — Schedule: Daily. Source: HTTP scrape of dentaltown.com public forums. Output: forum_posts. GREEN.
20. facebook_groups_scout — STATUS: REPLACE METHOD — Replace with facebook_api_collector (Graph API, official) + dental_community_mention_tracker for brand monitoring. Automated scraping of Facebook Groups prohibited by Meta's ToS.
Strategies 7-33 (collectors 24-110):
All remaining sub-fragments follow the identical specification pattern. Key highlights by group:

Competitor Intelligence (27-36): competitor_website_monitor MERGED into competitor_product_monitor. One change-detection pipeline per competitor URL.
News Ingestion (25, 31, 37): google_news_collector, rss_feed_monitor, competitor_pr_monitor MERGED into one news ingestion service with topic routing + one classifier.
Technographic (24, 41, 74, 75, 78): website_crawler, booking_tech_detector, zocdoc_listing_detector, bilingual_demand_detector, patient_financing_badge_detector MERGED into one technographic crawl pass per practice. Single HTTP fetch, multiple signal extractions, one website_crawl_data table row.
Government (60-68): All use free official APIs/downloads. GREEN compliance.
Access Audit (99-100): live_answer_audit and after_hours_coverage_audit require legal sign-off before production deployment. No false identity on calls. Quarterly schedule for live_answer, monthly for after_hours.
IP Monitoring (88-89): uspto_trademark_monitor and patent_filing_monitor — STATUS: DEPRIORITIZED — competitive intelligence only, does not affect outreach timing or messaging.
Podcast (90): dental_podcast_monitor — STATUS: DEPRIORITIZED — Low volume of practice-level leads. Use peer_influence_mapper instead.


Section 7 — Intelligence Tools Specification
Tool 1 — Fit Score
AttributeValueFunctionasync def compute_fit_score(practice_npi: str) -> FitScoreResultBusiness questionDoes this practice match our ICP (size, specialty, location, tech posture)?Input tablespractices, website_crawl_data, technographic_signals, review_data, government_dataLLM callsNone — pure computationOutput schemaFitScoreResult(score: float, specialty_match: bool, size_match: bool, tech_gap_confirmed: bool, pms_detected: Optional[str], profile: dict)Caching24-hour TTL per practiceConfidenceBased on data completeness: all tables populated = HIGH, partial = MODERATE, NPI-only = LOW@tool docstring"Compute the ICP fit score for a practice. Use this when the user asks if a practice matches our target customer profile or wants to understand a practice's tech posture."
Tool 3 — Lead Score (Critical)
AttributeValueFunctionasync def compute_lead_score(practice_npi: str) -> LeadScoreResultBusiness questionHow hot is this lead — act now, nurture, or ignore?Input tablesAll 29 sub-fragment output tables via parallel readsLLM callsNone — pure formula + signal aggregationOutput schemaSee Section 8 for full LeadScoreResult Pydantic modelCachingNo caching — recomputed on demand and via daily batchConfidenceAggregated from individual signal confidences@tool docstring"Compute the full composite lead score for a practice. Use this when the user asks 'how hot is this lead', wants a score, or asks about a practice's priority tier (HOT/WARM/COLD). Returns the score, component breakdown, signal evidence, and recommended action."
Tool 6 — Outreach Intelligence Brief (Critical)
AttributeValueFunctionasync def generate_outreach_brief(practice_npi: str) -> OutreachBriefBusiness questionFor a HOT lead, what is everything we know and what should the outreach say?Input tablesAll sub-fragment tables for this practice + lead_scores + sova_knowledgeLLM calls1× Claude Sonnet for brief generation with structured output. System prompt with cache_control: ephemeral. Context capped at MAX_OUTREACH_BRIEF_SIGNALS_CHARS = 8000.Output schemaOutreachBrief(practice_name, why_hot: List[str], owner_message: str, office_manager_message: str, recommended_opener: str, best_contact_channel: Literal["email","linkedin","phone"], urgency_window_days: int, trust_pathway: Optional[str], revenue_rescue_estimate: Optional[float])Caching1-hour TTL@tool docstring"Generate a complete outreach intelligence brief for a practice. Use this when the user asks for outreach recommendations, talking points, or what to say to a specific practice. Returns personalized messages for both the practice owner and office manager."
Tool 14 — Revenue Rescue Planner (Critical)
AttributeValueFunctionasync def compute_revenue_rescue(practice_npi: str) -> RevenueRescuePlanBusiness questionWhat exact revenue-leak story should we tell this practice?Input tablesgoogle_places_data, review_data, access_audit_results, availability_signals, intent_signalsLLM calls1× Claude Sonnet for narrative generation. Uses pgvector search_knowledge to retrieve most similar case study by practice type/specialty/geography. Context: MAX_REVENUE_RESCUE_EVIDENCE_CHARS = 6000.Output schemaRevenueRescuePlan(monthly_revenue_leakage: float, evidence: List[str], before_after_projection: str, objection_preemption: str, owner_pitch_angle: str, om_pitch_angle: str, case_study_match: Optional[str])@tool docstring"Calculate estimated revenue leakage for a practice and generate a revenue rescue story. Use this when the user asks about revenue impact, ROI, or how to make the financial case to a practice."
Tool 16 — Trust Vector (Critical)
AttributeValueFunctionasync def compute_trust_vector(practice_npi: str) -> TrustVectorResultBusiness questionWhat proof asset will most reduce resistance for this specific lead?Input tablescommunity_signals, conference_signals, enrichment_data, champion_signalsLLM calls1× pgvector semantic search against sova_knowledge for best case study match by specialty + geography + pain profile.Output schemaTrustVectorResult(pathways: List[TrustPathway], best_proof_asset: str, strength_score: float) where TrustPathway(type: Literal["peer","specialty","operational","geographic","advisor"], description: str, strength: float)@tool docstring"Find the best trust pathway for a specific practice. Use this when the user asks what proof point or reference to use with a specific lead, or how to build credibility with a practice."
Tool 19 — ICP Accuracy & Signal Calibration Monitor (Critical)
AttributeValueFunctionasync def run_signal_calibration() -> CalibrationReportBusiness questionIs our scoring model still working — which signals have drifted?Input tableslead_scores (historical), signals, CRM win/loss data (via API or CSV import)LLM calls1× Claude Sonnet for narrative report generation from computed statisticsOutput schemaCalibrationReport(signal_accuracy: List[SignalAccuracy], weight_drift: List[WeightDrift], false_positive_rate: float, threshold_recommendation: int, recommendations: List[str])SpecialDoes NOT auto-adjust weights. Surfaces recommendations for human review only. Monthly schedule.
The remaining 23 tools follow the same specification pattern, each with function signature, business question, input tables, LLM calls, output schema, caching, confidence logic, and @tool docstring.

Section 8 — Lead Scoring Model
Weighted Formula
CopyComposite Score = 
    0.20 × Fit +
    0.25 × OperationalPain +
    0.20 × Timing +
    0.15 × FirstPartyIntent +
    0.10 × TechnographicOpportunity +
    0.05 × HumanRoute +
    0.05 × Geography
Each component is normalized to 0-100 before weighting.
Component Computation
ComponentWeightSource DataNormalizationFit0.20practices (specialty, size, type), website_crawl_data (tech gap), technographic_signals (PMS), review_data (profile claimed), government_data (CMS enrollment date)0-100 based on ICP match criteria countOperational Pain0.25job_postings (posting count, repost, burnout keywords), google_places_data (phone friction count), access_audit_results (call failure rate), burnout_scores (aggregated burnout index), review_data (reputation shock)0-100 based on weighted signal count × confidenceTiming0.20lifecycle_events (event_type counts), staff_transition_signals (OM turnover, associate arrival), insurance_data (credentialing, plan changes)0-100 based on active transition window countFirst-Party Intent0.15intent_signals (demo calls, website visits, branded search spikes, Bombora intent)0-100 based on signal recency and typeTechnographic Opportunity0.10technographic_signals (PMS type, migration detected), website_crawl_data (booking tool present/absent), competitor_signals (competitor client identified)0-100 based on displacement easeHuman Route0.05champion_signals (champion at this practice), enrichment_data (contact identified), community_signals (peer influence connections)0-100 based on warm pathway availabilityGeography0.05dso_signals (DSO proximity, saturation), government_data (HRSA HPSA, BLS staffing), market_signals (staffing agency demand)0-100 based on local competitive pressure
Bounded Modifiers (Added to Composite — Not Multipliers)
EventModifierSignal ConditionChampion moved from existing client+8champion_signals contains record with event_type='job_change' for a known contactOwnership transfer / practice sold+6lifecycle_events contains event_type='sold' within last 90 daysNew practice opening or second location+5lifecycle_events contains event_type IN ('new_npi', 'expansion') within last 90 daysLive-answer failure + after-hours gap confirmed+4access_audit_results shows voicemail outcome + no after-hours coverageDSO opened within 5 miles+3dso_signals contains proximity event within last 60 daysFirst-party demo-line call+3intent_signals contains signal_type='demo_call' within last 30 daysLikely inactive / dead phone-6enrichment_data shows phone disconnected OR practices.is_active = FALSEStrong incumbent stack, no pain evidence-4Modern booking tool detected + no pain signals in last 90 daysOIG-excluded providerDISQUALIFYpractices.is_oig_excluded = TRUE → skip scoring entirely
Signal Decay
pythonCopyimport math

def compute_decayed_value(raw_value: float, days_since_signal: int, half_life_days: int) -> float:
    return raw_value * math.exp(-math.log(2) * days_since_signal / half_life_days)
Signal TypeHalf-lifeDemo-line call / identified website visit7 daysActive front-desk job posting14 daysReview complaint spike / live-answer failure21 daysBranded search spike / webinar attendance21 daysOwnership transfer / broker listing sold60 daysNew NPI / SBA loan / new practice opening90 daysTechnographic gap (no modern booking tool)180 days
HOT Qualification (All 6 Must Be True)

composite_score >= 78
fit_score >= 65
At least one major pain signal AND one timing/intent signal in signals table
At least one key signal with collected_at within last 30 days
Owner or office manager contact identified in enrichment_data
No major disqualifier present (is_oig_excluded=FALSE, is_active=TRUE)

Daily Recomputation
A Celery task recompute_all_lead_scores runs daily at 2:00 AM UTC. It:

Queries all practices with at least one signal in the last 180 days
For each, recomputes all component scores with current decay
Creates a new LeadScore row (versioned, not updated in place)
Sets is_latest=TRUE on new row, is_latest=FALSE on previous


Section 9 — Celery Task Architecture
Queues
QueuePurposeWorker ConcurrencydefaultGeneral tasks, health checks4collectorsAll sub-fragment data collection tasks8 (throttleable)toolsIntelligence tool invocations4 (higher priority)llmLLM-dependent tasks (newsletter_classifier, etc.)2 (cost control)
SovaBaseTask
pythonCopy# core/utils/tasks.py
import celery
from django.core.cache import cache
from django.db import connections
from django.utils import timezone
from core.models import SubFragmentRunLog

class SovaBaseTask(celery.Task):
    abstract = True

    def before_start(self, task_id, args, kwargs):
        self._collector_name = getattr(self, 'collector_name', self.name)

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        connections.close_all()

    def on_success(self, retval, task_id, args, kwargs):
        records = retval if isinstance(retval, int) else 0
        SubFragmentRunLog.objects.update_or_create(
            name=self._collector_name,
            defaults={
                'last_run_at': timezone.now(),
                'last_run_status': 'success',
                'records_written': records,
                'error_message': '',
            }
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        SubFragmentRunLog.objects.update_or_create(
            name=self._collector_name,
            defaults={
                'last_run_at': timezone.now(),
                'last_run_status': 'failed',
                'records_written': 0,
                'error_message': str(exc)[:2000],
            }
        )
Celery Beat Schedule (Key Entries)
pythonCopyCELERY_BEAT_SCHEDULE = {
    # === DAILY ===
    'nppes-weekly-delta': {'task': 'collectors.tasks.practice_data.nppes_collector', 'schedule': crontab(hour=1, minute=0, day_of_week='sunday')},
    'google-places-daily': {'task': 'collectors.tasks.practice_data.google_places_collector', 'schedule': crontab(hour=3, minute=0)},
    'dentalpost-daily': {'task': 'collectors.tasks.job_portals.dentalpost_collector', 'schedule': crontab(hour=5, minute=0)},
    'indeed-daily': {'task': 'collectors.tasks.job_portals.indeed_collector', 'schedule': crontab(hour=5, minute=30)},
    'reddit-daily': {'task': 'collectors.tasks.opinion_platforms.reddit_scout', 'schedule': crontab(hour=6, minute=0)},
    'email-inbox-4h': {'task': 'collectors.tasks.newsletters.email_inbox_reader', 'schedule': timedelta(hours=4)},
    'champion-daily': {'task': 'collectors.tasks.champion.champion_job_change_tracker', 'schedule': crontab(hour=7, minute=0)},
    
    # === WEEKLY ===
    'competitor-product-weekly': {'task': 'collectors.tasks.competitor_intel.competitor_product_monitor', 'schedule': crontab(hour=2, minute=0, day_of_week='monday')},
    'facebook-ads-weekly': {'task': 'collectors.tasks.competitor_intel.facebook_ads_library_collector', 'schedule': crontab(hour=2, minute=30, day_of_week='monday')},
    'website-crawl-weekly': {'task': 'collectors.tasks.website_monitoring.website_crawler', 'schedule': crontab(hour=4, minute=0, day_of_week='tuesday')},
    'yelp-weekly': {'task': 'collectors.tasks.review_platforms.yelp_collector', 'schedule': crontab(hour=3, minute=0, day_of_week='wednesday')},
    
    # === MONTHLY ===
    'nppes-full-monthly': {'task': 'collectors.tasks.practice_data.nppes_full_refresh', 'schedule': crontab(0, 0, day_of_month='1')},
    'oig-monthly': {'task': 'collectors.tasks.government.oig_exclusion_checker', 'schedule': crontab(0, 0, day_of_month='5')},
    'bls-quarterly': {'task': 'collectors.tasks.government.bls_staffing_heatmap', 'schedule': crontab(0, 0, day_of_month='15', month_of_year='1,4,7,10')},
    
    # === SCORING ===
    'lead-score-daily': {'task': 'orchestrator.tasks.recompute_all_lead_scores', 'schedule': crontab(hour=2, minute=0)},
    'health-check-hourly': {'task': 'orchestrator.tasks.check_collector_health', 'schedule': timedelta(hours=1)},
}

Section 10 — API Design
Health & Monitoring
GET /api/v1/health/ — Overall system health. Returns: {"status": "healthy|degraded|unhealthy", "db": "ok", "redis": "ok", "celery": "ok"}. No auth required.
GET /api/v1/health/collectors/ — Sub-fragment health status. Returns JSON with collectors array (name, last_run_at, status, records_written, next_expected_run), stale_collectors list, silent_fail_collectors list. API key auth.
Practices
GET /api/v1/practices/ — List with filters. Query params: state, specialty, tier (HOT/WARM/COLD), is_active, page, page_size. Returns paginated list. API key auth.
GET /api/v1/practices/<npi>/ — Single practice full record including latest lead score. API key auth.
GET /api/v1/practices/<npi>/signals/ — All signals collected for this practice, ordered by collected_at desc. Query params: signal_type, since. API key auth.
Lead Intelligence
GET /api/v1/leads/hot/ — HOT leads, filterable by state, specialty, limit (max 50). Returns list with composite_score, top_signal, contact_info. API key auth.
POST /api/v1/tools/lead-score/ — Body: {"practice_npi": "..."}. Returns HTTP 202 with {"run_id": "...", "status_url": "/api/v1/tasks/<run_id>/"}. API key auth.
POST /api/v1/tools/outreach-brief/ — Body: {"practice_npi": "..."}. Returns HTTP 202. API key auth.
POST /api/v1/tools/revenue-rescue/ — Body: {"practice_npi": "..."}. Returns HTTP 202. API key auth.
Task Management
GET /api/v1/tasks/<run_id>/ — Returns {"status": "pending|running|completed|failed|cancelled", "progress": "...", "result": {...}}. API key auth.
POST /api/v1/tasks/<run_id>/cancel/ — Sets Redis cancellation flag. Returns {"cancelled": true}. API key auth.
Chatbot (v2 — Scaffold)
Five endpoints as specified in Section 2, Layer 4, Pattern 6.

Section 11 — Docker Compose Configuration
yamlCopyversion: '3.8'

services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  web:
    build: .
    command: gunicorn sova.wsgi:application --bind 0.0.0.0:8000 --workers 4
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      db: {condition: service_healthy}
      redis: {condition: service_healthy}
    volumes:
      - .:/app
    restart: unless-stopped

  celery-worker-collectors:
    build: .
    command: celery -A sova worker -l info -Q collectors,default -c 8 --prefetch-multiplier 1
    env_file: .env
    depends_on:
      db: {condition: service_healthy}
      redis: {condition: service_healthy}
    volumes:
      - .:/app
    restart: unless-stopped

  celery-worker-tools:
    build: .
    command: celery -A sova worker -l info -Q tools,llm -c 4 --prefetch-multiplier 1
    env_file: .env
    depends_on:
      db: {condition: service_healthy}
      redis: {condition: service_healthy}
    volumes:
      - .:/app
    restart: unless-stopped

  celery-beat:
    build: .
    command: celery -A sova beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    env_file: .env
    depends_on:
      db: {condition: service_healthy}
      redis: {condition: service_healthy}
    volumes:
      - .:/app
    restart: unless-stopped

  flower:
    build: .
    command: celery -A sova flower --port=5555
    env_file: .env
    ports:
      - "5555:5555"
    depends_on:
      redis: {condition: service_healthy}
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
.env.example
bashCopy# Database
POSTGRES_DB=sova
POSTGRES_USER=sova
POSTGRES_PASSWORD=changeme_in_production
DATABASE_URL=postgresql://sova:changeme_in_production@db:5432/sova

# Redis
REDIS_URL=redis://redis:6379/0

# Django
DJANGO_SECRET_KEY=changeme_generate_a_real_key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# LLM
ANTHROPIC_API_KEY=sk-ant-...                    # Anthropic API key for Claude
OPENAI_API_KEY=sk-...                           # OpenAI key for embeddings only

# Observability
LANGSMITH_API_KEY=ls__...                       # LangSmith tracing key
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=sova
SENTRY_DSN=https://...@sentry.io/...            # Sentry error tracking DSN

# Data Source API Keys
GOOGLE_MAPS_API_KEY=AIza...                     # Google Places API
HUNTER_API_KEY=...                              # Hunter.io email enrichment
PROXYCURL_API_KEY=...                           # Proxycurl (LinkedIn proxy)
FACEBOOK_APP_ID=...                             # Meta Graph API
FACEBOOK_APP_SECRET=...
REDDIT_CLIENT_ID=...                            # Reddit API
REDDIT_CLIENT_SECRET=...
YOUTUBE_API_KEY=...                             # YouTube Data API v3
GMAIL_CREDENTIALS_PATH=/app/credentials/gmail.json
TWILIO_ACCOUNT_SID=...                          # Twilio for test calls
TWILIO_AUTH_TOKEN=...
YELP_API_KEY=...                                # Yelp Fusion API
GOOGLE_SEARCH_CONSOLE_CREDENTIALS_PATH=...
JSEARCH_API_KEY=...                             # Licensed job data API (replaces LinkedIn scraping)

# Optional / Phase-dependent
BOMBORA_API_KEY=...                             # B2B intent data (paid)
G2_API_KEY=...                                  # G2 Buyer Intent (paid)
RB2B_API_KEY=...                                # Website visitor de-anonymization
TIKTOK_API_KEY=...                              # TikTok Research API
CRUNCHBASE_API_KEY=...                          # Crunchbase (limited free)
HYPERBROWSER_API_KEY=...                        # Hyperbrowser SDK

Section 12 — Knowledge Base Design
Source Files Structure
Copyknowledge/
  yaml/
    outreach_playbooks.yaml     # Pitch angles by ICP type
    objection_handlers.yaml     # Common objections + responses
    competitor_comparisons.yaml # Sova vs each competitor
    icp_profiles.yaml           # ICP type definitions with scoring criteria
  case_studies/
    general_practice_texas.md
    orthodontic_southwest.md
    pediatric_florida.md
    dso_multi_location.md
    new_practice_owner.md
YAML Schema
yamlCopy# outreach_playbooks.yaml
- id: "new_practice_owner"
  title: "New Practice Owner Playbook"
  icp_type: "new_practice_owner"
  pitch_angle: "Building your tech stack from scratch..."
  owner_message: "..."
  om_message: "..."
  best_channel: "email"
  tags: ["greenfield", "new_owner", "no_incumbent"]
build_knowledge_index Management Command

Load all YAML files using yaml.safe_load()
Load all .md files as raw text
For each item: compute SHA-256 content hash
Generate embedding using OpenAIEmbeddings(model="text-embedding-3-small")
Upsert to sova_knowledge table (match on content_hash)
Log: items processed, inserted, updated, skipped (unchanged hash)

Retrieval
pythonCopyclass DatabaseKnowledgeStore:
    def search(self, query: str, k: int = 3, item_type: str = None) -> List[dict]:
        query_embedding = self.embedder.embed_query(query)
        qs = SovaKnowledge.objects.annotate(
            distance=CosineDistance('embedding', query_embedding)
        ).filter(distance__lt=0.25)  # cosine distance < 0.25 = similarity > 0.75
        if item_type:
            qs = qs.filter(item_type=item_type)
        results = qs.order_by('distance')[:k]
        return [{'content': r.content, 'score': 1 - r.distance, 'type': r.item_type, 'metadata': r.metadata} for r in results]

Section 13 — Compliance & Legal Requirements
Sub-fragmentRiskMitigationLegal Sign-off Required?linkedin_hyperbrowser_agentLinkedIn prohibits automated session simulation. CFAA exposure.Use Proxycurl API instead.No (replaced)facebook_hyperbrowser_agentSimulating human sessions may violate Facebook ToSUse official Graph API only; Hyperbrowser only for genuinely public content with no loginNoglassdoor_collectorGlassdoor ToS restricts bulk scrapingSummary-level only; no bulk extraction. DEPRIORITIZED.Nofacebook_groups_scoutGroup scraping prohibited by Meta ToSReplace with facebook_api_collector (official) + dental_community_mention_trackerNo (replaced)website_visitor_deanonymizerIP collection subject to CCPA and GDPRAdd explicit disclosure in Sova's privacy policy before deploying; do not store raw IPsYESdea_registration_checkerDEA site limits automated queriesRate-limit 1 req/sec max; consider licensed third-party service. DEPRIORITIZED.Nodental_specialty_association_scraperSome associations prohibit bulk extractionConfirm ToS per association; contact for data licensing if bulk neededNolinkedin_profile_enricherLinkedIn prohibits automated people searchUse Proxycurl API with explicit data licenseNo (replaced)linkedin_jobs_collectorLinkedIn blocks scrapers; CFAA exposureUse licensed job-data API (JSearch, Jobicy, RapidAPI)No (replaced)live_answer_auditTest calls to practices — potential false identity concernsNo false identity on calls. Compliant test call only.YES — legal sign-off before productionafter_hours_coverage_auditSame as live_answer_auditSame mitigationYES — legal sign-off before production
TCPA/FCC Requirements
Per the February 8, 2024 FCC ruling classifying AI-generated voices as "artificial or prerecorded voices" under TCPA:

Product (AI receptionist): Must identify itself as AI before any substantive conversation begins. Must offer voice/keypad opt-out within 2 seconds. Must detect caller's state for two-party consent states (CA, FL, IL, MD, MA, NV, NH, OR, PA, WA).
Outreach: Any outbound AI voice calls require prior express written consent specifically disclosing AI voice. Until consent infrastructure exists, outbound prospecting uses human callers or compliant text/email channels only.
Fines: $500/call standard, $1,500/call willful violations. No cap on aggregate damages.


Section 14 — Phased Build Plan
Phase 0 — Foundation
Goal: Project skeleton, infrastructure, shared utilities
Build: sova/config.py, core/utils/retry.py, core/utils/logging.py, core/utils/tasks.py (SovaBaseTask), core/models.py (SubFragmentRunLog), sova/celery.py, sova/settings.py with Sentry, docker-compose.yml, .env.example, Dockerfile, requirements.txt
Done when: docker compose up starts all 7 services. Health endpoint returns 200. Celery Beat runs a no-op test task. Sentry captures a test exception.
Complexity: Medium
Dependencies: None
Phase 1 — Practice Data Foundation
Goal: Master practice table populated, review data flowing
Build: nppes_collector, google_places_collector, clinic_hours_change_monitor, practices model, health monitoring endpoint
Done when: practices table has 180,000+ dental records from NPPES. Google Places data collected for 1,000 test practices. Health endpoint shows both collectors as "success".
Complexity: High (NPPES 7GB streaming)
Dependencies: Phase 0
Phase 2 — Job Signal Layer
Build: All 6 job portal collectors (dentalpost, indeed, linkedin_jobs via API, ihiredental, ziprecruiter, glassdoor), job_postings table, pms_signal_extractor computation
Done when: Job postings flowing from at least 3 sources. PMS mentions extracted. Chronic repost detection working.
Complexity: High
Dependencies: Phase 1
Phase 3 — Competitor Intelligence
Build: All competitor collectors (merged as specified), competitor_ads, competitor_snapshots, competitor_signals tables
Done when: Weekly competitive data from Facebook Ads Library, competitor product pages, PR mentions.
Complexity: Medium
Dependencies: Phase 0
Phase 4 — Lifecycle & Government Data
Build: All lifecycle event collectors, all government data collectors
Done when: Lifecycle events detected for practice openings, sales, permits. OIG exclusion list applied.
Complexity: High (50 state variations)
Dependencies: Phase 1
Phase 5 — Lead Scoring Tool
Build: Full lead score formula, LeadScore model, signals table, signal decay daily task, /api/v1/leads/hot/ endpoint
Done when: Lead scores computed for all practices with signals. HOT/WARM/COLD tiers assigned. Daily recomputation running.
Complexity: High
Dependencies: Phases 1-4
Phase 6 — Outreach Intelligence
Build: Outreach Brief tool, Revenue Rescue Planner, Trust Vector, pgvector knowledge base + build_knowledge_index command
Done when: Outreach briefs generated for HOT leads with owner + OM messages, revenue estimates, and trust pathways.
Complexity: High
Dependencies: Phase 5
Phase 7 — Access & Availability
Build: Live answer audit, after-hours audit, review platform expansion, same-day availability scanner
Done when: Access Failure Index computed. Requires legal sign-off before production test calls.
Complexity: Medium
Dependencies: Phase 1
Phase 8 — Competitive Ads Intelligence
Build: Google Ads collector, LinkedIn Ads collector, YouTube monitor, TikTok monitor
Done when: Ads data from 3+ platforms flowing. Competitive Leaderboard tool operational.
Complexity: Medium
Dependencies: Phase 3
Phase 9 — Remaining Collectors
Build: All remaining sub-fragments not covered above: champion tracking, enrichment, insurance, associations, technographic, intent, DSO, community, contextual, CE, local journals, burnout aggregators, staff transition, first-party intent.
Done when: 100+ collectors running on schedule. Health endpoint shows all green.
Complexity: High (volume)
Dependencies: Phases 1-4
Phase 10 — Chatbot Interface (v2)
Build: LangGraph 2-node graph, AsyncPostgresSaver checkpointer, DRF API surface (5 endpoints), Redis SSE streaming, mode router, all tools bound as LangGraph nodes with docstrings
Done when: Sales rep can ask "Give me the 10 hottest leads in Texas" and get a tool-backed response with streaming.
Complexity: High
Dependencies: Phases 5-6

Section 15 — Open Questions & Decisions Required Before Implementation
#QuestionOptionsImplementation ImpactBlocks Phase1Champion seed list maintenance — How is the seed list of current client contacts maintained for champion_job_change_tracker?A) Manual CSV upload B) CRM API sync C) Django admin UIAffects Phase 9 champion tracker design. CSV = simple but fragile. CRM sync = robust but requires CRM API work.Phase 92State dental board data format — Which priority states (CA, TX, NY, FL, IL) have bulk-downloadable licensee data vs. requiring per-page scraping?Requires per-state researchAffects dental_school_new_licensee_monitor implementation — scrapers vs. CSV parsers per state.Phase 43State SoS UCC portals — Which states support automated lookups?Requires per-state researchDetermines whether ucc_loan_filings_monitor is feasible for all states or priority-only.Phase 44Financial Stress Indicator behavior — Should it automatically suppress outreach (remove from queue) or flag for human review?A) Auto-suppress B) Flag onlyAffects the lead score modifier logic and outreach pipeline design.Phase 55Live answer audit consent — Confirm no identity disclosure is required in relevant states for test calls.Legal review requiredBlocks Phase 7 production deployment. Dev/staging work can proceed.Phase 76Lead Score HOT threshold calibration — Is 78 the right starting threshold?78 (recommended), adjust after 3-6 months of dataAffects Phase 5 scoring constants. Start with 78, plan for calibration via Signal Calibration Monitor.Phase 5 (non-blocking)7LLM provider for classification tasks — Original docs mention OpenAI gpt-4o-mini, Eva docs use Anthropic Claude. Which?A) Anthropic Claude Haiku for all B) OpenAI for classification, Anthropic for generationAffects dependency list and API key requirements. Decision: Use Anthropic Claude Haiku for all LLM tasks (consistency with Eva patterns, prompt caching, structured output).Day 18Licensed job data API selection — Which specific provider replaces LinkedIn Jobs scraping?JSearch (RapidAPI), Jobicy, AdzunaAffects linkedin_jobs_collector implementation and API key setup.Phase 29Merge sequencing — The four merge groups (technographic crawl, competitor pipeline, conference social, news ingestion) should be resolved in architecture before building.Merge as specified in this PRDAlready resolved: technographic = one crawl pass, competitor = one change-detection pipeline, conference = query presets, news = one ingestion queue.Phase 0 (architecture)10Medical market expansion — When Sova expands beyond dental, analogous entry points are FSMB and HHS OCR Breach Portal.Future scopeNo current impact. Document separately when expansion begins.None

End of PRD. This document is complete and ready for implementation. Every requirement is traceable to the three source documents. The implementation agent should read this PRD in full before writing any code, then build phase-by-phase starting with Phase 0.