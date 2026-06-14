SOVA — Scalable Systems Architecture
Table of Contents
Executive Architecture Summary
System-Level Architecture
Layer-by-Layer Deep Dive
Data Architecture & Schema Design
Infrastructure & Deployment Topology
Scalability Analysis & Bottleneck Strategy
Cross-Cutting Concerns
Risk Register & Mitigations
Architecture Decision Records

1. Executive Architecture Summary
1.1 What Sova Is
Sova is a pure backend intelligence system — not a CRM, not the AI receptionist product, not a user-facing application in v1. It is an autonomous data pipeline that continuously collects signals from 110+ internet sources, transforms them into composite lead scores, and generates actionable outreach intelligence for Neurality Health's sales team.
1.2 Architecture Philosophy
The architecture is governed by three principles derived from the PRD's constraints:
Principle
Rationale
Implication
Database-as-communication-bus
Sub-fragments must never call each other directly. PostgreSQL is the only shared state.
Every component writes to and reads from well-defined tables. No message passing between collectors.
Correctness before optimization
Primary developer is learning Django. System must be understandable.
Idiomatic Django patterns, no premature abstractions, explained code.
Design for 10x, build for 1x
Scale from 200K practices now to 2M+ records, 2,000 clients by 2027.
Schema design and queue architecture support 10x growth. Actual deployment starts single-node Docker Compose.

1.3 Four-Layer Architecture Overview
Copy
┌─────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL CONSUMERS                                │
│     Sales Team (API) │ Future Frontend │ CRM Webhooks               │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────────────┐
│  LAYER 4 — CHATBOT AGENT (v2 — scaffold now, build Phase 10)       │
│  LangGraph StateGraph │ Mode Router │ AsyncPostgresSaver            │
│  Redis SSE Streaming │ 5 DRF Endpoints │ Context Summarization      │
└─────────────────┬───────────────────────────────────────────────────┘
                  │ calls tools on demand
┌─────────────────▼───────────────────────────────────────────────────┐
│  LAYER 3 — ORCHESTRATOR BRAIN                                       │
│  Celery Beat Scheduling │ SubFragmentRunLog Health Tracking          │
│  SovaTaskRun Status │ HTTP 202 Polling │ Cooperative Cancellation    │
│  Health Monitoring Endpoint │ Connection Cleanup                     │
└─────────┬───────────────────────────────────────┬───────────────────┘
          │ schedules collectors                   │ invokes tools
┌─────────▼───────────────┐    ┌──────────────────▼──────────────────┐
│  LAYER 1 — DATA          │    │  LAYER 2 — INTELLIGENCE TOOLS       │
│  COLLECTOR FRAGMENTS     │    │                                      │
│  110+ Celery Tasks       │    │  28 async Python functions           │
│  Each: 1 source → 1 table│    │  Each: N tables → 1 business answer │
│  8 mandatory patterns    │    │  10 mandatory patterns               │
│  Tenacity retry          │    │  Pydantic structured LLM output     │
│  Redis distributed mutex │    │  Prompt caching                      │
│  Pydantic validation     │    │  Parallel DB reads                   │
│  Run logging             │    │  Confidence scoring                  │
│  Sensitive data sanitize │    │  pgvector knowledge base             │
│  HTTP timeouts           │    │  SQL safety layer                    │
│  SovaConfig              │    │  Error handling (never raise)        │
│  Connection cleanup      │    │  Token caps                          │
└─────────┬───────────────┘    └──────────────────┬──────────────────┘
          │ writes                                 │ reads
┌─────────▼─────────────────────────────────────────▼─────────────────┐
│              POSTGRESQL (with pgvector)                               │
│  practices │ signals │ lead_scores │ 29 sub-fragment output tables   │
│  sova_knowledge │ sub_fragment_run_log │ sova_conversations          │
│  sova_task_runs │ LangGraph checkpoint tables                        │
└─────────────────────────────────────────────────────────────────────┘
          ▲
┌─────────┴───────────────────────────────────────────────────────────┐
│              REDIS                                                    │
│  Celery Broker │ Django Cache (mutex locks) │ SSE pub/sub buffers    │
│  Cancellation flags │ Knowledge cache TTL                            │
└─────────────────────────────────────────────────────────────────────┘

2. System-Level Architecture
2.1 Process Topology (Docker Compose)
The system runs as 7 cooperating processes in Docker Compose:
Copy
┌──────────────────────────────────────────────────────────────┐
│                    Docker Compose Network                      │
│                                                                │
│  ┌─────────┐  ┌───────────────────┐  ┌───────────────────┐   │
│  │   db    │  │      redis        │  │      web          │   │
│  │ PG16 +  │  │  Redis 7 Alpine   │  │  Gunicorn (4w)    │   │
│  │ pgvector│  │  Broker + Cache   │  │  Django REST API  │   │
│  │ :5432   │  │  :6379            │  │  :8000            │   │
│  └────┬────┘  └────────┬──────────┘  └────────┬──────────┘   │
│       │                │                       │              │
│  ┌────┴────────────────┴───────────────────────┴──────────┐  │
│  │              Shared Docker Network                      │  │
│  └────┬────────────────┬──────────────┬───────────────────┘  │
│       │                │              │                       │
│  ┌────┴──────────┐ ┌──┴────────┐ ┌───┴──────────┐           │
│  │ celery-worker │ │ celery-   │ │ celery-beat  │           │
│  │ -collectors   │ │ worker-   │ │ DB Scheduler │           │
│  │ Q: collectors │ │ tools     │ │              │           │
│  │    default    │ │ Q: tools  │ │              │           │
│  │ Concurrency:8│ │    llm    │ │              │           │
│  └──────────────┘ │ Conc.: 4  │ └──────────────┘           │
│                    └───────────┘                              │
│  ┌──────────────┐                                            │
│  │   flower     │  Celery monitoring UI                      │
│  │   :5555      │                                            │
│  └──────────────┘                                            │
└──────────────────────────────────────────────────────────────┘
Why this topology:
Process
Justification
db (pgvector/pgvector:pg16)
Single Postgres instance with pgvector extension pre-installed. Handles all relational data + vector similarity search. No separate vector DB needed.
redis (redis:7-alpine)
Triple duty: Celery message broker, Django cache backend (for mutex locks), and future SSE pub/sub. Single Redis instance is sufficient at this scale.
web (gunicorn, 4 workers)
Django REST API serving health checks, practice queries, tool invocations, and future chatbot endpoints. Gunicorn with 4 sync workers handles the API load.
celery-worker-collectors (concurrency 8)
Dedicated to data collection tasks. 8 concurrent workers can process scraping/API calls in parallel. --prefetch-multiplier 1 prevents one slow collector from blocking others.
celery-worker-tools (concurrency 4)
Handles intelligence tool invocations and LLM-dependent tasks. Lower concurrency controls Anthropic API cost. Separate queue prevents tool invocations from starving collectors.
celery-beat
Single-instance scheduler using django_celery_beat.schedulers:DatabaseScheduler. Database-backed schedules allow runtime schedule modification without redeployment.
flower
Real-time Celery monitoring dashboard. Shows task throughput, failure rates, and worker health.

2.2 Queue Architecture
Copy
                   ┌─────────────────────────────────┐
                    │         Celery Beat              │
                    │   (DatabaseScheduler)            │
                    └──────────┬──────────────────────┘
                               │ dispatches tasks
                    ┌──────────▼──────────────────────┐
                    │         Redis Broker             │
                    │                                  │
                    │  Queue: collectors ─────────┐    │
                    │  Queue: default ────────────┤    │
                    │  Queue: tools ──────────────┤    │
                    │  Queue: llm ────────────────┘    │
                    └──────────┬──────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼────┐  ┌───────▼──────┐  ┌──────▼───────┐
    │ Worker Pool  │  │ Worker Pool  │  │  (future)    │
    │ collectors   │  │ tools + llm  │  │  chatbot     │
    │ + default    │  │              │  │  worker      │
    │ c=8          │  │ c=4          │  │              │
    └──────────────┘  └──────────────┘  └──────────────┘
Queue separation rationale:
collectors (c=8): High-volume I/O-bound tasks. 110+ sub-fragments producing ~200K practice records. These are mostly HTTP fetches and DB writes. Higher concurrency is safe because they're I/O-bound, not CPU-bound.
tools (c=4, higher priority): Intelligence computations triggered on-demand. Lead scoring reads from 10+ tables per practice. Lower concurrency prevents database connection exhaustion during parallel reads.
llm (c=2, cost control): LLM-dependent tasks like newsletter_classifier, outreach_brief. Concurrency of 2 caps Anthropic API concurrent requests, controlling cost.
default (c=4): Health checks, housekeeping tasks, one-off maintenance. Shared with collectors worker.
2.3 Data Flow — End-to-End Signal Lifecycle
Here's how a single signal flows through the system from detection to sales action:
Copy
EXTERNAL SOURCE                    LAYER 1                  DATABASE
(e.g., DentalPost)                (Collector)              (PostgreSQL)
       │                              │                         │
       │  HTTP fetch (hourly)         │                         │
       ├─────────────────────────────►│                         │
       │                              │  Pydantic validate      │
       │                              │  ──────────────►        │
       │                              │  Write job_postings     │
       │                              │  ──────────────────────►│
       │                              │  Update RunLog          │
       │                              │  ──────────────────────►│
       │                              │                         │
       │                              │                         │
                                                                │
LAYER 2 (Tool)                                                  │
       │  Daily batch: recompute_all_lead_scores                │
       │◄───────────────────────────────────────────────────────│
       │  Read signals, job_postings, reviews...                │
       │  (asyncio.gather with Semaphore(8))                    │
       │                                                        │
       │  Apply decay function per signal                       │
       │  Compute 7-component weighted score                    │
       │  Apply bounded modifiers                               │
       │  Evaluate HOT qualification (6 conditions)             │
       │                                                        │
       │  Write new lead_scores row (versioned)                 │
       │───────────────────────────────────────────────────────►│
       │                                                        │
                                                                │
LAYER 3 (API)                                                   │
       │  GET /api/v1/leads/hot/?state=TX                       │
       │◄───────────────────────────────────────────────────────│
       │  Returns: [{npi, name, score, tier, top_signal}]       │
       │                                                        │
       │  POST /api/v1/tools/outreach-brief/                    │
       │  → HTTP 202 {run_id, status_url}                       │
       │                                                        │
LAYER 2 (Tool, async)                                           │
       │  Claude Sonnet: generate personalized brief            │
       │  pgvector: retrieve matching case study                │
       │  Write result to SovaTaskRun                           │
       │───────────────────────────────────────────────────────►│
       │                                                        │
SALES REP                                                       │
       │  GET /api/v1/tasks/<run_id>/                           │
       │  → {status: "completed", result: {outreach_brief}}     │

3. Layer-by-Layer Deep Dive
3.1 Layer 1 — Data Collector Fragments (Sub-fragments)
3.1.1 Architectural Pattern
Every sub-fragment follows an identical execution pattern, enforced through SovaBaseTask:
Copy
┌──────────────────────────────────────────────────────────────┐
│                   SovaBaseTask Lifecycle                       │
│                                                                │
│  1. before_start()                                             │
│     └─ Record collector name                                   │
│                                                                │
│  2. EXECUTE (the actual collector logic)                       │
│     ├─ Acquire Redis mutex (cache.add, 300s timeout)          │
│     ├─ Fetch data (sova_retry: 3 attempts, exp backoff)       │
│     ├─ Validate via Pydantic schema                           │
│     ├─ Write to PostgreSQL (batch where possible)             │
│     └─ Return records_written count                            │
│                                                                │
│  3. on_success()                                               │
│     └─ SubFragmentRunLog: status='success', records=N          │
│                                                                │
│  4. on_failure()                                               │
│     └─ SubFragmentRunLog: status='failed', error=str(exc)      │
│                                                                │
│  5. after_return() [ALWAYS executes]                           │
│     └─ connections.close_all()                                 │
└──────────────────────────────────────────────────────────────┘
3.1.2 Collector Scheduling Strategy
The PRD defines four scheduling tiers based on source volatility:
Tier
Interval
Examples
Rationale
High-frequency
Every 4h
email_inbox_reader
Newsletter intelligence is time-sensitive. Competitor announcements appear in newsletters before press.
Daily
Every 24h
dentalpost_collector, indeed_collector, reddit_scout, champion_job_change_tracker
Job postings and community pain signals have 14-21 day half-lives. Daily collection ensures signal freshness.
Weekly
7 days
yelp_collector, competitor_product_monitor, website_crawler, social platform collectors
Review data and competitor changes are meaningful over weekly windows. Reduces API costs.
Monthly
30 days
nppes_collector (full refresh), oig_exclusion_checker, bls_staffing_heatmap
Government data updates monthly. Full NPPES refresh is a 7GB CSV stream.

Critical scheduling constraint: The recompute_all_lead_scores task runs daily at 2:00 AM UTC, after all daily collectors have completed their runs. This ensures scores reflect the freshest data.
3.1.3 Failure Isolation Model
Copy
  Sub-fragment A (FAILED)     Sub-fragment B (HEALTHY)    Sub-fragment C (HEALTHY)
         │                            │                            │
         │ writes NOTHING             │ writes to table_B          │ writes to table_C
         │                            │                            │
         ▼                            ▼                            ▼
   ┌──────────┐               ┌──────────┐                ┌──────────┐
   │ table_A  │               │ table_B  │                │ table_C  │
   │ (stale   │               │ (fresh)  │                │ (fresh)  │
   │  data)   │               │          │                │          │
   └──────────┘               └──────────┘                └──────────┘
         │                            │                            │
         └────────────────────────────┼────────────────────────────┘
                                      │
                              ┌───────▼────────┐
                              │  Lead Score    │
                              │  Tool          │
                              │  (degrades     │
                              │   gracefully — │
                              │   uses stale   │
                              │   table_A data │
                              │   at reduced   │
                              │   confidence)  │
                              └────────────────┘
Key isolation properties:
Each collector writes to its own dedicated table
No collector depends on another collector's output (database-as-bus pattern)
A failed collector produces stale data, not missing data
The Lead Score tool applies confidence weighting — signals from stale collectors get downgraded to LOW confidence (×0.5 weight)
3.1.4 Merge Groups (Architecture-Level Optimization)
The PRD specifies four merge groups to eliminate duplicate HTTP fetches:
Copy
MERGE GROUP 1: Technographic Crawl
┌──────────────────────────────────────────────────┐
│  Single HTTP fetch per practice website           │
│                                                    │
│  ┌────────────────┐  ┌──────────────────────┐     │
│  │ website_crawler │  │ booking_tech_detector│     │
│  └────────┬───────┘  └──────────┬───────────┘     │
│           │                      │                  │
│  ┌────────┴───────┐  ┌──────────┴───────────┐     │
│  │ bilingual_     │  │ patient_financing_   │     │
│  │ demand_detector│  │ badge_detector       │     │
│  └────────┬───────┘  └──────────┬───────────┘     │
│           │                      │                  │
│           └──────────┬───────────┘                  │
│                      ▼                              │
│           ┌──────────────────┐                      │
│           │ website_crawl_   │                      │
│           │ data (one table) │                      │
│           └──────────────────┘                      │
└──────────────────────────────────────────────────┘

MERGE GROUP 2: Competitor Pipeline
  competitor_website_monitor ──MERGED INTO──► competitor_product_monitor
  (one change-detection pipeline per competitor URL)

MERGE GROUP 3: Conference Social
  conference_social_tracker ──MERGED INTO──► facebook_api_collector
                                              + linkedin_api_collector
  (query presets targeting conference page accounts)

MERGE GROUP 4: News Ingestion
  google_news_collector + rss_feed_monitor + competitor_pr_monitor
  ──MERGED INTO──► One ingestion queue + one classifier
3.2 Layer 2 — Intelligence Tools
3.2.1 Tool Execution Model
Tools are async Python functions in sova/tools/, each answering exactly one business question. They read from sub-fragment tables (never write to them) and produce structured intelligence output.
Copy
┌─────────────────────────────────────────────────────────────┐
│                    Tool Invocation Flow                       │
│                                                               │
│  Trigger (API endpoint / Celery task / future chatbot)        │
│     │                                                         │
│     ▼                                                         │
│  ┌─────────────────────────────────────────┐                  │
│  │  Tool Function                          │                  │
│  │  (e.g., compute_lead_score)             │                  │
│  │                                          │                  │
│  │  1. Parallel DB reads (asyncio.gather)  │                  │
│  │     ├─ job_postings                     │                  │
│  │     ├─ google_places_data               │                  │
│  │     ├─ lifecycle_events                 │                  │
│  │     ├─ technographic_signals            │                  │
│  │     ├─ review_data                      │                  │
│  │     ├─ access_audit_results             │                  │
│  │     ├─ intent_signals                   │                  │
│  │     ├─ dso_signals                      │                  │
│  │     ├─ champion_signals                 │                  │
│  │     └─ enrichment_data                  │                  │
│  │     (Semaphore(8) caps concurrency)     │                  │
│  │                                          │                  │
│  │  2. Apply signal decay function          │                  │
│  │     raw × e^(-ln(2) × days / half_life) │                  │
│  │                                          │                  │
│  │  3. Compute component scores (0-100)     │                  │
│  │     Fit(0.20) + Pain(0.25) + Timing(0.20)│                 │
│  │     + Intent(0.15) + Tech(0.10)          │                  │
│  │     + Human(0.05) + Geo(0.05)            │                  │
│  │                                          │                  │
│  │  4. Apply bounded modifiers              │                  │
│  │     Champion: +8, Ownership: +6, etc.    │                  │
│  │                                          │                  │
│  │  5. Evaluate HOT qualification           │                  │
│  │     (all 6 conditions must be true)      │                  │
│  │                                          │                  │
│  │  6. Return LeadScoreResult (Pydantic)    │                  │
│  └─────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
3.2.2 LLM Integration Architecture
Tools that use LLM calls (Outreach Brief, Revenue Rescue, Competitive Report) follow a strict pattern:
Copy
┌──────────────────────────────────────────────────────────┐
│                LLM Tool Invocation Pattern                 │
│                                                            │
│  1. SCHEMA FIRST                                           │
│     Define Pydantic output model BEFORE writing prompt     │
│     class OutreachBrief(BaseModel): ...                    │
│                                                            │
│  2. KNOWLEDGE RETRIEVAL (pgvector)                         │
│     ┌──────────────────┐     ┌────────────────────┐       │
│     │ Query embedding  │────►│ sova_knowledge     │       │
│     │ (text-embedding- │     │ HNSW cosine index  │       │
│     │  3-small, 1536d) │     │ threshold ≥ 0.75   │       │
│     └──────────────────┘     └────────────────────┘       │
│                                                            │
│  3. CONTEXT ASSEMBLY (token-capped)                        │
│     signals_context = truncate(all_signals,                │
│       MAX_OUTREACH_BRIEF_SIGNALS_CHARS=8000)               │
│     case_study = pgvector_match                            │
│                                                            │
│  4. LLM CALL (structured output + prompt caching)          │
│     ┌──────────────────────────────────────────┐          │
│     │ SystemMessage:                            │          │
│     │   cache_control: {"type": "ephemeral"}    │◄── CACHED│
│     │   "You are a dental sales intelligence..." │          │
│     ├──────────────────────────────────────────┤          │
│     │ HumanMessage:                             │          │
│     │   {signals_context + case_study}          │◄── VARIES│
│     └──────────────────────────────────────────┘          │
│     llm.with_structured_output(OutreachBrief)              │
│                                                            │
│  5. ERROR HANDLING (never raise)                           │
│     try: ... except Exception: return error string         │
└──────────────────────────────────────────────────────────┘
Prompt caching economics: For a batch of 50 outreach briefs, a 2,000-token system prompt costs ~$0.15 without caching vs ~$0.003 with cache_control: ephemeral. At scale (generating briefs for all HOT leads daily), this represents 60-80% token cost reduction.
3.2.3 Tool Dependency Graph
Copy
                         ┌──────────────────┐
                          │   LEAD SCORE     │ (Daily batch + on-demand)
                          │   (composite)    │
                          └────────┬─────────┘
                                   │ depends on
         ┌─────────────┬──────────┼──────────┬──────────────┐
         ▼             ▼          ▼          ▼              ▼
   ┌──────────┐ ┌──────────┐ ┌────────┐ ┌────────┐  ┌──────────┐
   │ Fit Score│ │ Intent   │ │Timing/ │ │Techno- │  │ Access   │
   │          │ │ Score    │ │Transn. │ │graphic │  │ Failure  │
   │          │ │          │ │Window  │ │Opport. │  │ Index    │
   └──────────┘ └──────────┘ └────────┘ └────────┘  └──────────┘
         │                                                  │
         └──────────────────────┬────────────────────────────┘
                                │ feeds into
                    ┌───────────▼───────────┐
                    │   OUTREACH BRIEF      │
                    │   (per HOT lead)      │
                    │   Uses: Lead Score +  │
                    │   all signal tables + │
                    │   sova_knowledge      │
                    └───────────┬───────────┘
                                │ enriched by
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                   ▼
     ┌──────────────┐ ┌──────────────┐   ┌──────────────┐
     │ Revenue      │ │ Trust        │   │ Buying       │
     │ Rescue       │ │ Vector       │   │ Committee    │
     │ Planner      │ │              │   │ Intelligence │
     └──────────────┘ └──────────────┘   └──────────────┘
3.3 Layer 3 — Orchestrator Brain
The orchestrator is intentionally thin — it contains no business logic. Its responsibilities are:
Copy
┌─────────────────────────────────────────────────────────┐
│              ORCHESTRATOR RESPONSIBILITIES                │
│                                                           │
│  1. SCHEDULING (Celery Beat)                              │
│     ├─ Every collector has a defined crontab/interval     │
│     ├─ DatabaseScheduler allows runtime modification      │
│     └─ Score recomputation at 2:00 AM UTC daily           │
│                                                           │
│  2. HEALTH MONITORING                                     │
│     ├─ Hourly: check_collector_health                     │
│     │   ├─ Stale: last_run_at > 2× expected_interval      │
│     │   └─ Silent fail: status=success, records=0         │
│     └─ GET /api/v1/health/collectors/ endpoint             │
│                                                           │
│  3. TASK STATUS TRACKING                                  │
│     ├─ SovaTaskRun model                                  │
│     │   status: pending → running → completed/failed      │
│     ├─ HTTP 202 pattern for async tool invocations        │
│     └─ GET /api/v1/tasks/<run_id>/ polling endpoint       │
│                                                           │
│  4. COOPERATIVE CANCELLATION                              │
│     ├─ Redis key: sova:cancel:{run_id}                    │
│     ├─ POST /api/v1/tasks/<run_id>/cancel/                │
│     └─ Backstop: Celery hard time limit (900s)            │
└─────────────────────────────────────────────────────────┘
3.4 Layer 4 — Chatbot Agent (v2 — Design Now, Build Phase 10)
The chatbot is architecturally prepared but not built until Phase 10. The key insight from the Eva reference system is that the chatbot is a thin orchestration layer over the same tools that the API exposes:
Copy
┌──────────────────────────────────────────────────────┐
│               CHATBOT GRAPH (LangGraph)               │
│                                                        │
│   START ──► [Mode Router] ──► chatbot mode             │
│                            ──► deep_analysis mode      │
│                            ──► report_generation mode   │
│                                                        │
│   chatbot mode:                                        │
│   ┌───────────────────────────────────────────┐       │
│   │                                           │       │
│   │   ┌──────────┐    ┌──────────────────┐   │       │
│   │   │  agent   │──►│     tools        │   │       │
│   │   │  (LLM)   │   │  (Sova tools)    │   │       │
│   │   │          │◄──│                  │   │       │
│   │   └──────┬───┘    └──────────────────┘   │       │
│   │          │ no tool calls                   │       │
│   │          ▼                                 │       │
│   │        END                                 │       │
│   └───────────────────────────────────────────┘       │
│                                                        │
│   Checkpointer: AsyncPostgresSaver (per event loop)    │
│   Recursion limit: 25                                  │
│   Context summarization: at 15+ messages               │
│   Streaming: Redis SSE (RPUSH + PUBLISH dual-write)    │
└──────────────────────────────────────────────────────┘

4. Data Architecture & Schema Design
4.1 Entity-Relationship Overview
Copy
                       ┌───────────────────┐
                        │    practices      │ (master record)
                        │    PK: npi        │
                        └─────────┬─────────┘
                                  │ 1
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                     │
              │ *                 │ *                   │ *
    ┌─────────▼────┐   ┌────────▼─────────┐   ┌──────▼────────┐
    │   signals    │   │   lead_scores    │   │ 29 sub-fragment│
    │   (central   │   │   (versioned,   │   │ output tables  │
    │    store)    │   │    is_latest)   │   │ (job_postings, │
    │              │   │                 │   │  google_places, │
    │              │   │                 │   │  review_data,   │
    └──────────────┘   └─────────────────┘   │  lifecycle_evts,│
                                              │  competitor_ads,│
                                              │  etc.)          │
                                              └────────────────┘
4.2 Core Table Strategy
The database has three categories of tables:
Category 1: Core Domain (3 tables)
practices — Master record, NPI as primary key, ~200K rows growing to ~200K+
signals — Central signal store with decay metadata, high-write volume
lead_scores — Versioned scoring output, is_latest denormalized flag for fast queries
Category 2: Sub-fragment Output (29 tables)
Each follows identical pattern: id, practice_npi (FK, indexed), source, 3-5 domain columns, metadata JSONB, collected_at (indexed)
Composite index on (practice_npi, collected_at) for time-range queries per practice
Category 3: System Tables (5 tables)
sub_fragment_run_log — Health tracking
sova_conversations — Chatbot sessions (v2)
sova_task_runs — Async task status
sova_knowledge — pgvector knowledge base
LangGraph checkpoint tables (auto-created)
4.3 Indexing Strategy
The indexing strategy is designed for the two dominant query patterns:
Pattern 1: "Give me all signals for practice X in the last N days" (Tool reads)
sql
Copy
-- Hit by: Lead Score, Outreach Brief, Revenue Rescue, etc.
-- Covered by: composite index (practice_npi, collected_at) on every output table
SELECT * FROM job_postings 
WHERE practice_npi = '1234567890' 
AND collected_at > NOW() - INTERVAL '180 days'
ORDER BY collected_at DESC;
Pattern 2: "Give me all HOT leads in state X" (API queries)
sql
Copy
-- Hit by: GET /api/v1/leads/hot/?state=TX
-- Covered by: composite index (tier, is_latest) on lead_scores
--           + index on state in practices
SELECT p.*, ls.composite_score, ls.tier
FROM practices p
JOIN lead_scores ls ON ls.practice_npi = p.npi
WHERE ls.tier = 'HOT' AND ls.is_latest = TRUE AND p.state = 'TX'
ORDER BY ls.composite_score DESC
LIMIT 50;
4.4 Signal Decay Architecture
Signal decay is a read-time computation, not a write-time mutation. Signals are stored with their raw values and half-life metadata. Decay is computed when the Lead Score tool reads them:
Copy
┌─────────────────────────────────────────────────────────┐
│                    SIGNAL DECAY MODEL                     │
│                                                           │
│  Storage (signals table):                                 │
│    raw_value = 85.0                                       │
│    half_life_days = 14  (for job postings)                │
│    collected_at = 2026-06-01T00:00:00Z                    │
│                                                           │
│  Read-time computation (Lead Score tool):                  │
│    days_since = (now - collected_at).days = 12             │
│    decayed = 85.0 × e^(-ln(2) × 12 / 14) = 46.3          │
│                                                           │
│  Why read-time, not write-time:                            │
│    1. No daily batch to update 200K+ signal rows           │
│    2. Decay is always computed with "now", never stale     │
│    3. Historical raw_value preserved for calibration       │
│    4. Half-lives can be tuned without rewriting data       │
└─────────────────────────────────────────────────────────┘
4.5 Lead Score Versioning
Lead scores are append-only with an is_latest denormalized flag:
Copy
┌────────────────────────────────────────────────────────┐
│              LEAD SCORE VERSIONING                       │
│                                                          │
│  Day 1: Practice ABC scored                              │
│    id=1, practice_npi=ABC, composite=72, is_latest=TRUE  │
│                                                          │
│  Day 2: Recomputation with new signals                   │
│    id=1, practice_npi=ABC, composite=72, is_latest=FALSE │
│    id=2, practice_npi=ABC, composite=84, is_latest=TRUE  │
│                                                          │
│  Benefits:                                                │
│    1. Full scoring history for calibration tool            │
│    2. No UPDATE contention on hot rows                     │
│    3. Easy rollback: set old row is_latest=TRUE            │
│    4. Score drift detection: compare versions              │
└────────────────────────────────────────────────────────┘

5. Infrastructure & Deployment Topology
5.1 Resource Sizing (Current → Target)
Resource
Current (200 clients)
Target (2,000 clients, end 2027)
Growth Factor
Practices in DB
~200,000
~200,000 (market is fixed)
1x
Signals/month
~500K rows
~5M rows
10x
Lead scores
~200K versions
~2M versions/year
10x
Celery tasks/day
~500
~5,000
10x
LLM calls/day
~200
~2,000
10x
PostgreSQL size
~5 GB
~50 GB
10x
Redis memory
~128 MB
~512 MB
4x

5.2 Scaling Path (When to Scale What)
Copy
PHASE: LOCAL DOCKER COMPOSE (now → 500 clients)
   db: Single PG16 instance, 4GB RAM allocated
   redis: Single instance, 256MB maxmemory
   web: 4 gunicorn workers
   celery-workers: 2 containers (collectors=8, tools=4)
   Cost: $0/month (local dev)

PHASE: SINGLE VPS (500 → 1,000 clients)
   ┌─────────────────────────────────────────┐
   │  Single VPS: 8 CPU, 32GB RAM, 500GB SSD │
   │  Docker Compose (identical config)       │
   │  PG data volume: local SSD               │
   │  Est. cost: $100-200/month               │
   └─────────────────────────────────────────┘

PHASE: MANAGED SERVICES (1,000 → 2,000 clients)
   ┌──────────┐  ┌──────────┐  ┌──────────────────┐
   │ Managed  │  │ Managed  │  │ Container service│
   │ PG (RDS/ │  │ Redis    │  │ (ECS/Cloud Run)  │
   │ Cloud SQL│  │ (Elasti- │  │ web + workers    │
   │ pgvector)│  │ cache)   │  │                  │
   └──────────┘  └──────────┘  └──────────────────┘
   Horizontal scaling: add celery worker containers
   Vertical scaling: upgrade PG instance class
   Est. cost: $500-1,000/month
5.3 PostgreSQL Scaling Strategy
The primary scaling concern is PostgreSQL, which handles all state:
Short-term (now → 1 year):
Single instance is sufficient. 200K practices × 30 columns ≈ 50MB for master table.
Signal table with 5M rows/year ≈ 2GB/year at 400 bytes/row.
All 29 output tables combined ≈ 10GB/year.
pgvector HNSW index on sova_knowledge (hundreds of rows) is trivially small.
Medium-term (1-2 years):
Add pg_partitioning on signals table by collected_at (monthly partitions)
Archive lead_scores where is_latest = FALSE AND scored_at < 6 months ago
Connection pooling with PgBouncer if worker count exceeds PG max_connections
Long-term (if needed):
Read replicas for tool queries (tools only read, never write)
Separate PG instance for LangGraph checkpoint tables (high-write, low-read)

6. Scalability Analysis & Bottleneck Strategy
6.1 Bottleneck Heat Map
Copy
Component         Bottleneck Risk   Mitigation
────────────────  ────────────────  ──────────────────────────────────
NPPES 7GB CSV     HIGH (memory)     Stream row-by-row with csv module
                                     bulk_create(batch_size=5000)
                                     Filter dental taxonomy codes in-stream

Google Places API HIGH (cost)       Priority queue: HOT/WARM first
                                     Max 5,000 practices/daily run
                                     Cache results for 24h

Anthropic API     MODERATE (cost)   Prompt caching (60-80% reduction)
                                     Haiku for routing/classification
                                     Sonnet only for generation
                                     LLM queue concurrency=2

PG connections    MODERATE (pool)   connections.close_all() in finally
                                     --prefetch-multiplier 1
                                     PgBouncer at scale

Redis memory      LOW               24h TTL on SSE buffers
                                     No persistent state in Redis
                                     maxmemory-policy: allkeys-lru

Celery task       LOW               Separate queues by type
queue backlog                        Monitor via Flower
                                     Scale workers horizontally
6.2 Cost Projection
Component
Monthly Cost (200 clients)
Monthly Cost (2,000 clients)
Google Places API
~$150 (5K calls/day × 30 × $0.001)
~$750 (25K calls/day)
Anthropic API (Haiku)
~$20 (classification tasks)
~$100
Anthropic API (Sonnet)
~$50 (outreach briefs)
~$250
OpenAI Embeddings
~$5 (knowledge base)
~$10
Hunter.io
~$50 (HOT leads only)
~$200
Proxycurl
~$100 (champion tracking)
~$300
Infrastructure
$0 (local) → $200 (VPS)
$500-1,000 (managed)
Total
~$375-575
~$2,110-2,610


7. Cross-Cutting Concerns
7.1 Observability Stack
Copy
┌──────────────────────────────────────────────────────┐
│                OBSERVABILITY ARCHITECTURE              │
│                                                        │
│  ┌────────────┐  ┌────────────┐  ┌────────────────┐  │
│  │   Sentry   │  │ LangSmith  │  │   Flower       │  │
│  │            │  │            │  │                │  │
│  │ Exceptions │  │ LLM traces │  │ Celery tasks   │  │
│  │ from Django│  │ Input/     │  │ Throughput,    │  │
│  │ + Celery   │  │ output/    │  │ failures,      │  │
│  │            │  │ tokens/    │  │ queue depth    │  │
│  │            │  │ latency    │  │                │  │
│  └────────────┘  └────────────┘  └────────────────┘  │
│                                                        │
│  ┌────────────────────────────────────────────────┐   │
│  │        SubFragmentRunLog (custom)              │   │
│  │  Per-collector health: last_run, status,       │   │
│  │  records_written, error_message                │   │
│  │  Exposed via GET /api/v1/health/collectors/     │   │
│  └────────────────────────────────────────────────┘   │
│                                                        │
│  ┌────────────────────────────────────────────────┐   │
│  │        drf-yasg (Swagger)                      │   │
│  │  Auto-generated API documentation              │   │
│  │  Interactive endpoint testing                   │   │
│  └────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
7.2 Security Model
Copy
┌─────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                        │
│                                                           │
│  1. API Authentication                                    │
│     └─ API key auth on all endpoints (except health)      │
│                                                           │
│  2. Data Sanitization                                     │
│     └─ sanitize_for_log() on all log output               │
│        Redacts phone numbers and emails                   │
│                                                           │
│  3. SQL Safety (chatbot v2)                               │
│     ├─ DANGEROUS_SQL_PATTERNS blocklist                   │
│     ├─ ALLOWED_TABLES whitelist                           │
│     ├─ SET LOCAL statement_timeout = 30s                  │
│     └─ Auto-add LIMIT 1000                               │
│                                                           │
│  4. Sensitive Data Handling                                │
│     ├─ No raw IPs stored (website_visitor_deanonymizer)   │
│     ├─ Pydantic validation before all DB writes           │
│     └─ .env for all secrets (never in code)               │
│                                                           │
│  5. Rate Limiting (chatbot v2)                            │
│     └─ 10 req/min/user on query endpoint                  │
│                                                           │
│  6. Compliance Guardrails                                 │
│     ├─ LinkedIn: Proxycurl only, no browser automation    │
│     ├─ Facebook: Graph API first, public-only fallback    │
│     ├─ Glassdoor: Summary-level only                      │
│     ├─ live_answer_audit: Legal sign-off required          │
│     └─ OIG exclusion: Immediate disqualification          │
└─────────────────────────────────────────────────────────┘
7.3 Django App Structure Rationale
The project is organized into 6 Django apps, each with a clear responsibility boundary:
App
Purpose
Why Separate
core/
Practice model, SubFragmentRunLog, Signal, LeadScore, shared utilities
Every other app depends on these models. Utilities (retry, logging, cache) are shared.
collectors/
All 110+ sub-fragment Celery tasks, their Pydantic schemas, and output models
Tasks are grouped by strategy in tasks/ subdirectory. Keeps the massive collector codebase isolated from tool logic.
tools/
28 intelligence tools, their Pydantic schemas, DRF views for invocation
Tools read from collector tables but never write to them. Clear dependency direction: tools → core ← collectors.
orchestrator/
SovaTaskRun, health endpoints, scheduling coordination
Thin layer. Contains no business logic — just plumbing.
chatbot/
LangGraph graph, checkpointer, router, streaming, summarization (v2 scaffold)
Scaffolded now, built Phase 10. Separate app because it introduces new dependencies (langgraph, psycopg-pool).
knowledge/
SovaKnowledge model, DatabaseKnowledgeStore, YAML/MD source files
pgvector-dependent. Cleanly separated so it can be rebuilt independently.


8. Risk Register & Mitigations
#
Risk
Impact
Likelihood
Mitigation
1
NPPES 7GB file OOMs during processing
Master table fails to populate
Medium
Stream row-by-row with csv module. batch_size=5000 for bulk_create. Never load full file into memory.
2
Google Places API cost overrun
Budget exceeded without full coverage
High
Priority queue (HOT/WARM first). Max 5K calls/daily. 24h cache TTL. Monitor spend weekly.
3
Indeed/ZipRecruiter blocks scrapers
Job signal goes dark
High
Content hash dedup across sources. Multiple overlapping sources (5 job boards). Rotating user-agents. Respectful rate limiting.
4
Lead score model drifts from reality
HOT leads don't convert
Medium
Signal Calibration Monitor tool (monthly). Does NOT auto-adjust — surfaces recommendations for human review. Start with 78 threshold, recalibrate after 3-6 months.
5
Celery worker connection pool exhaustion
Tasks fail silently
Medium
connections.close_all() in finally block of every task (enforced by SovaBaseTask). --prefetch-multiplier 1.
6
LLM costs spike from uncontrolled usage
Budget blown
Low
Separate llm queue with concurrency=2. Prompt caching. Haiku for classification, Sonnet only for generation. Token caps per tool.
7
TCPA/FCC violation in live_answer_audit
$500-$1,500 per call fines
High
Legal sign-off required before production. No false identity on calls. Build code in dev/staging, deploy only after legal approval.
8
Single PostgreSQL instance becomes bottleneck
Scoring latency increases
Low (2+ years out)
Partition signals by month. Read replicas for tools. PgBouncer for connection pooling. Archive old lead_scores.


9. Architecture Decision Records
ADR-001: PostgreSQL + pgvector vs. Separate Vector Database
Decision: Use pgvector within the same PostgreSQL instance.
Context: The knowledge base (playbooks, case studies, competitor comparisons) needs semantic similarity search. Options were: FAISS (in-memory), Qdrant (separate service), or pgvector (PostgreSQL extension).
Rationale:
pgvector is already required for the pgvector/pgvector:pg16 Docker image
Knowledge base is ~hundreds of documents, not millions — HNSW index on small dataset is fast
No operational overhead of a separate vector DB service
Consistent backup/restore with the rest of the data
The PRD explicitly excludes FAISS and Qdrant
Trade-off: If knowledge base grows to 100K+ documents, pgvector performance may degrade. At that point, evaluate dedicated vector DB. Current projection: <1,000 documents for years.
ADR-002: Celery Beat vs. Prefect for Orchestration
Decision: Use Celery Beat with DatabaseScheduler.
Context: The PRD explicitly states Celery Beat. The Eva reference system uses Prefect, but the PRD overrides this.
Rationale:
110+ sub-fragments need independent scheduling — Celery Beat handles this natively
DatabaseScheduler allows runtime schedule modification via Django admin without code changes
No additional infrastructure (Prefect requires its own server)
Prefect's DAG orchestration value (multi-step pipeline dependencies) isn't needed — sub-fragments are independent
The PRD explicitly lists Prefect in the "NOT included" table
Trade-off: If complex multi-step pipeline dependencies emerge (e.g., "run X only after Y and Z complete"), Celery chains/chords handle simple cases. Prefect would be reconsidered only if this becomes unmanageable.
ADR-003: Anthropic Claude vs. OpenAI for All LLM Tasks
Decision: Use Anthropic Claude (Haiku for classification, Sonnet for generation) for all LLM tasks. OpenAI only for embeddings.
Context: The original project context document mentioned OpenAI gpt-4o-mini. The PRD resolves this: Anthropic Claude for all tasks.
Rationale:
Consistency with Eva reference patterns (prompt caching, structured output)
Anthropic's cache_control: ephemeral provides 60-80% token cost reduction on batch processing
with_structured_output() via langchain-anthropic is proven in Eva
Single LLM provider simplifies API key management and cost tracking
OpenAI text-embedding-3-small for embeddings only (5x cheaper than large, 90%+ quality)
ADR-004: Append-Only Lead Scores vs. Update-in-Place
Decision: New lead score computation creates a new row. Old row gets is_latest=FALSE.
Rationale:
Full scoring history is required by the Signal Calibration Monitor tool (monthly)
No UPDATE contention on hot rows during daily batch recomputation
Easy rollback if a bad scoring run occurs
Score drift detection: compare is_latest=TRUE vs previous versions
The (tier, is_latest) composite index makes HOT lead queries fast
Trade-off: Table grows by ~200K rows per daily run. At 365 runs/year = 73M rows/year. Mitigated by archiving non-latest rows older than 6 months to a lead_scores_archive table.
ADR-005: Redis for Three Duties vs. Separate Services
Decision: Single Redis instance serves as Celery broker, Django cache backend, and SSE pub/sub.
Rationale:
At current scale (<512MB), all three uses fit comfortably in a single Redis instance
No persistent state stored in Redis (all durable state is in PostgreSQL)
Celery broker messages are transient (acknowledged on completion)
Mutex locks have 300s TTL (auto-expire)
SSE buffers have 24h TTL (auto-expire)
maxmemory-policy: allkeys-lru prevents memory exhaustion
Trade-off: At 2,000+ clients with heavy SSE streaming, consider splitting Celery broker onto a separate Redis instance to prevent SSE pub/sub traffic from affecting task delivery latency.

This architecture is designed to evolve through the 11 phases defined in the PRD, starting with Phase 0 (Foundation) and progressively building each layer while maintaining the strict contract boundaries between them. Every decision can be revisited as the system scales, but the foundational patterns — database-as-communication-bus, collector independence, tool-level business logic, and thin orchestration — remain constant.

