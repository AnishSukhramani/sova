# PRD Generator Prompt — Sova

> Paste this prompt into the Claude Console PRD generator agent, alongside the three attached documents.

---

## Prompt

You have been given three documents. Read all three completely before generating anything.

**Document 1 — `sova-agent-context.md`**
This is the master project context document. It tells you what Sova is, who is building it, what the business goal is, the technology stack, the full sub-fragment inventory (112 data collectors), the intelligence tools layer, the lead scoring formula, compliance constraints, and what you are being asked to produce. This is your primary source of truth for intent and requirements.

**Document 2 — `subfragment-strategy-map.md`**
This is the complete strategy document for every data collection strategy. It contains 32 strategies, 116 sub-fragments, 28 intelligence tools, the lead scoring model with signal decay, build validation flags (what to drop, replace, merge, deprioritize), TCPA/FCC compliance requirements, and open questions. Use this as the canonical reference for the data layer — every sub-fragment name, what it collects, how it collects it, and what compliance risks apply.

**Document 3 — `learnings-from-eva.md`**
This is a forensic architectural analysis of a production-grade multi-agent system (Eva) built on the same tech stack: Django, PostgreSQL, Redis, Celery, LangGraph, Anthropic Claude. It maps every applicable architectural pattern from Eva to Sova's four layers. This document is your architectural Bible. Every technical decision in the PRD should be informed by or justified against the patterns documented here. Do not invent architecture from scratch — extract it from this document and adapt it to Sova's specific context.

---

## Your Task

Generate a **comprehensive Product Requirements Document (PRD)** for Sova. This PRD will be handed directly to a Claude Code implementation agent that will write the actual code. It must be precise enough that the implementation agent makes zero ambiguous decisions — every technical choice must already be made for it.

The PRD must be technically complete, not product-marketing complete. No fluff. No vague goals. Every section should answer: *"Given this requirement, exactly what does the implementation agent build?"*

---

## PRD Structure — Required Sections

Generate every section below. Do not skip any. Do not merge sections. Each section has specific requirements.

---

### Section 1 — Project Overview

Write 2–3 dense paragraphs covering:
- What Sova is and what problem it solves (from `sova-agent-context.md` §1 and §2)
- The business context: 200 → 2,000 client locations, why generic outreach fails, why signal-based intelligence wins
- What Sova is NOT (not the AI receptionist product, not a CRM, not a chatbot in v1)
- Who the developer is and what that means for code style (junior developer, learning Django, code must be explained)

---

### Section 2 — System Architecture

Write a complete architectural description of Sova's four-layer model. For each layer, specify:

**Layer 1 — Data Collector Fragments**
- Definition: what a sub-fragment is, its contract (collects from one source, writes to one DB table, knows nothing else)
- How sub-fragments are implemented: Celery tasks, Celery Beat scheduling, independent execution
- The eight patterns from `learnings-from-eva.md` Layer 1 that every sub-fragment must implement:
  1. Tenacity retry (3 attempts, exponential backoff) on all external HTTP calls and DB writes
  2. Django cache mutex (`cache.add`) to prevent duplicate concurrent runs per practice
  3. `SubFragmentRunLog` model update after every run (name, last_run_at, status, records_written, error_message)
  4. Pydantic output schema validated before every DB write
  5. Sensitive data sanitization before logging (phone numbers, emails via regex redaction)
  6. `asyncio.wait_for` / `requests timeout=30` on every external HTTP call
  7. `SovaConfig` class import for all knobs (no hardcoded values anywhere)
  8. `connections.close_all()` in finally block of every Celery task
- Specify the `SovaConfig` class structure with every configurable value
- Specify the `SubFragmentRunLog` Django model fields exactly

**Layer 2 — Intelligence Tools**
- Definition: what a tool is, its contract (reads from DB, answers one business question, no data collection)
- How tools are implemented: async Python functions, called on demand via API or chatbot
- The ten patterns from `learnings-from-eva.md` Layer 2 that every LLM-based tool must implement:
  1. Pydantic structured output (`llm.with_structured_output(Schema)`) on every LLM call — schema defined before prompt
  2. Anthropic prompt caching (`cache_control: ephemeral`) on system prompts for batch LLM calls
  3. Two-level knowledge cache: in-process dict (15-min TTL) for slow-changing data, Redis for request-scoped data
  4. Parallel DB reads with `asyncio.gather` + `Semaphore(8)` cap
  5. Confidence scoring: HIGH (n > 500), MODERATE (n = 100–500), LOW (n < 100)
  6. pgvector knowledge base semantic retrieval (cosine similarity ≥ 0.75 threshold for direct answer)
  7. SQL safety layer for any LLM-generated queries (DANGEROUS_SQL_PATTERNS, ALLOWED_TABLES, statement timeout, auto-LIMIT)
  8. Error handling: every tool catches all exceptions internally, returns string error — never raises
  9. Partial result synthesis on `GraphRecursionError` using a secondary lightweight LLM call
  10. Token caps on all injected context (define specific char limits per tool)

**Layer 3 — Orchestrator Brain**
- Definition: thin coordination layer, no business logic
- How it's implemented: Celery Beat schedules, `SubFragmentRunLog` health checks, task status tracking
- The seven patterns from `learnings-from-eva.md` Layer 3:
  1. `SovaConversation` + `SovaTaskRun` Django models (specify every field)
  2. HTTP 202 + `run_id` polling pattern for long-running tool invocations
  3. Cooperative cancellation via Redis flag checked at every LangGraph node entry
  4. Celery hard (900s) and soft (840s) time limits on every task
  5. Per-event-loop async resource management (`AsyncPostgresSaver` keyed by loop ID)
  6. `connections.close_all()` in finally blocks
  7. Health monitoring API endpoint showing last-run status for every sub-fragment

**Layer 4 — Chatbot Agent (v2 — design now, build later)**
- Mark this as v2 explicitly
- Document the complete design so the implementation is straightforward when the time comes
- The ten patterns from `learnings-from-eva.md` Layer 4:
  1. LangGraph 2-node `StateGraph(MessagesState)`: `agent` → `tools` → loop → END
  2. `AsyncPostgresSaver` checkpointer from `langgraph-checkpoint-postgres`
  3. LLM mode router using Haiku at temperature=0 — `SovaRoutingDecision` Pydantic schema
  4. Context auto-summarization at 15+ messages, keep last 5 verbatim
  5. Redis SSE streaming: RPUSH to event list (24h TTL) + PUBLISH to channel + cursor-based replay
  6. Five DRF API endpoints: create thread, submit query (202), poll status, SSE stream, cancel
  7. Tool registry: all 28 intelligence tools defined with `@tool` decorator and docstrings the LLM reads
  8. `asgiref.sync_to_async` bridge for all Django ORM calls inside async LangGraph nodes
  9. `SovaConversation.messages` JSONField for user-visible history alongside LangGraph checkpoint
  10. Rate limiting: 10 requests/min/user on the query endpoint

---

### Section 3 — Technology Stack

Produce an exact dependency list. For every package, specify: package name, version pin (where known from Eva's stack or established best practice), and its specific role in Sova. Do not list packages Sova does not need. Reference `learnings-from-eva.md` Technology Checklist and `sova-agent-context.md` §3 Technology Preferences.

Required packages to cover at minimum:
- `django`, `djangorestframework`, `django-cors-headers`, `drf-yasg`
- `celery`, `django-celery-beat`, `redis`, `django-redis`
- `psycopg2`, `psycopg-pool`
- `pgvector`
- `langchain-core`, `langchain-anthropic`, `langchain-openai`
- `langgraph`, `langgraph-checkpoint-postgres`
- `langsmith`
- `pydantic` v2
- `tenacity`
- `httpx`, `beautifulsoup4`, `feedparser`
- `sentry-sdk[django,celery]`
- `asgiref`
- `sqlparse`

Also specify what is explicitly NOT included and why (Prefect, Daytona, OpenSWE, mem0ai, Qdrant, FAISS, text-embedding-3-large).

---

### Section 4 — Django Project Structure

Specify the complete Django project file structure. Every app, every module, every file. Use a tree format. Justify every structural decision. Do not invent apps — derive the structure from what Sova actually needs.

Required apps to specify:
- `core` — shared models, config, utilities, base classes
- `collectors` — all 110+ sub-fragment Celery tasks, one file per strategy group
- `tools` — all 28 intelligence tools, one file per tool
- `orchestrator` — health monitoring, scheduling coordination, task status
- `chatbot` — LangGraph graph, streaming, API endpoints (v2, scaffold now)
- `knowledge` — pgvector knowledge base, build_index command, YAML source files

For each app, specify:
- `models.py` — what models live here
- `tasks.py` — what Celery tasks live here (if applicable)
- `views.py` — what DRF views live here (if applicable)
- `serializers.py` — what serializers live here (if applicable)

---

### Section 5 — Database Schema

Design the complete PostgreSQL schema for Sova. Every table. Every column. Every index. Every constraint.

**Core tables (required):**

`practices` — the master practice record (every dental/medical practice in the US)
- Derive the exact fields from `sova-agent-context.md` and the NPPES data model
- Include: npi (PK), practice_name, address, city, state, zip, phone, specialty_taxonomy_code, practice_type (solo/group), is_active, created_at, updated_at

`lead_scores` — one row per practice per scoring run
- Include: id, practice_npi (FK), composite_score, fit_score, operational_pain_score, timing_score, first_party_intent_score, technographic_score, human_route_score, geography_score, tier (HOT/WARM/COLD), scored_at, modifiers_applied (JSONField), signal_decay_applied (JSONField)

`sub_fragment_run_log` — health tracking for every sub-fragment
- Include: id, name, last_run_at, last_run_status, records_written, error_message, next_expected_run_at

`sova_conversations` — chatbot conversation sessions (v2)
- Derive from `learnings-from-eva.md` §4.9

`sova_task_runs` — status tracking for tool invocations
- Derive from `learnings-from-eva.md` §3.1

`sova_knowledge` — pgvector knowledge base
- Include: id, content (TextField), embedding (VectorField, 1536 dimensions — text-embedding-3-small), item_type (Literal: faq/playbook/case_study/objection_handler/competitor_comparison), metadata (JSONField), created_at

**Sub-fragment output tables — one per strategy group:**
Design a table for each of the following, deriving fields from `subfragment-strategy-map.md`:

1. `job_postings` — all job portal collectors (dentalpost, indeed, ihiredental, ziprecruiter, linkedin_jobs)
2. `glassdoor_reviews` — glassdoor_collector output
3. `social_metrics` — facebook_api_collector, linkedin_api_collector
4. `youtube_data` — youtube_competitor_monitor
5. `tiktok_data` — tiktok_industry_monitor
6. `conference_signals` — conference_website_monitor, conference_social_tracker
7. `newsletter_items` — email_inbox_reader + newsletter_classifier output
8. `forum_posts` — reddit_scout, dentaltown_forum_scout, facebook_groups_scout, quora_scout
9. `google_places_data` — google_places_collector, clinic_hours_change_monitor
10. `website_crawl_data` — website_crawler, booking_tech_detector, contact_friction_scorer, mobile_conversion_friction_scanner, new_patient_promo_detector, patient_financing_badge_detector, bilingual_demand_detector
11. `rss_articles` — rss_feed_monitor, google_news_collector, dental_podcast_monitor
12. `competitor_ads` — facebook_ads_library_collector, google_ads_intelligence_collector, linkedin_ads_library_collector
13. `competitor_snapshots` — competitor_website_monitor, competitor_product_monitor
14. `competitor_signals` — competitor_client_scout, competitor_jobs_tracker, crunchbase_monitor, competitor_pr_monitor, weave_truelark_displacement_monitor, competitor_churn_poison_monitor
15. `review_data` — yelp_collector, healthgrades_collector, zocdoc_listing_detector, review_response_rate_tracker
16. `lifecycle_events` — npi_new_registration_monitor, dental_broker_listing_monitor, dental_school_new_licensee_monitor, building_permit_monitor, multi_location_expansion_detector, business_license_monitor, commercial_real_estate_scout
17. `government_data` — cms_enrollment_collector, sba_loan_monitor, oig_exclusion_checker, hrsa_hpsa_monitor, bls_staffing_heatmap
18. `insurance_data` — insurance_network_collector, insurance_plan_change_monitor, insurance_ppo_density_monitor, dental_insurer_credentialing_monitor
19. `champion_signals` — champion_job_change_tracker
20. `enrichment_data` — hunter_enricher, linkedin_profile_enricher, phone_validator
21. `technographic_signals` — pms_signal_extractor, pms_migration_detector
22. `access_audit_results` — live_answer_audit, after_hours_coverage_audit
23. `availability_signals` — same_day_availability_scanner
24. `staff_transition_signals` — office_manager_turnover_detector, associate_arrival_detector, answering_service_vendor_loss_monitor
25. `intent_signals` — website_visitor_deanonymizer, bombora_b2b_intent_integration, branded_search_spike_monitor, first_party_voice_demo_tracker
26. `dso_signals` — dso_expansion_monitor, saturation_zip_analyzer
27. `market_signals` — google_trends_monitor, weather_disruption_monitor, ce_enrollment_monitor, local_biz_journal_monitor
28. `burnout_scores` — staff_burnout_aggregator, patient_access_complaint_velocity, dental_staffing_agency_monitor
29. `community_signals` — dental_community_mention_tracker, peer_influence_mapper, practice_advisor_network_mapper, referral_network_mapper

For each table, specify at minimum: primary key, practice_npi foreign key (where applicable), source identifier, collected_at timestamp, and the 3–5 most important signal-carrying columns. Add appropriate indexes (practice_npi, collected_at, source).

---

### Section 6 — Sub-fragment Implementation Specification

This is the largest and most important section. For every one of the 110 v1 sub-fragments listed in `sova-agent-context.md` §4 (exclude the two v2 X/Twitter ones), produce an implementation specification.

Group them by strategy (as in `subfragment-strategy-map.md`). For each sub-fragment, specify:

1. **Celery task signature** — function name, parameters, return type
2. **Schedule** — how frequently it runs (hourly / daily / weekly / monthly / event-triggered)
3. **Data source** — URL, API endpoint, SDK call
4. **Authentication** — which environment variable holds the key (if any)
5. **Output table** — which DB table it writes to
6. **Output fields** — the specific columns it writes per record
7. **Compliance flag** — copy from `subfragment-strategy-map.md` Build Validation section if flagged (Drop / Replace method / Deprioritize)
8. **Rate limiting** — what the source allows and how to stay within it
9. **Special handling** — anything non-obvious (CSV streaming for NPPES, HTML diff for staff pages, entity resolution for NPPES delta, etc.)

For sub-fragments flagged as "Deprioritize" in `subfragment-strategy-map.md` Build Validation section, include them but mark clearly: `STATUS: DEPRIORITIZED — build last`. For sub-fragments flagged as "Do Not Build As Described / Replace Method", specify the replacement method explicitly.

---

### Section 7 — Intelligence Tools Specification

For each of the 28 tools listed in `sova-agent-context.md` §5, produce a complete specification:

1. **Function signature** — async Python function name, parameters, return type
2. **Business question answered** — one sentence
3. **Input tables read** — which sub-fragment output tables it queries
4. **LLM calls** — which calls are made, which model, what Pydantic output schema
5. **Output schema** — the complete Pydantic model the tool returns
6. **Caching** — whether tool output is cached, TTL
7. **Confidence rating logic** — how HIGH/MODERATE/LOW is determined for this tool's output
8. **@tool docstring** — the exact docstring the LangGraph chatbot will read (written as if instructing an LLM when to use this tool)

Pay special attention to these five tools — they are the most complex and most important:
- **Lead Score** — must implement the full weighted formula from `sova-agent-context.md` §6 including exponential signal decay and all HOT qualification criteria
- **Outreach Intelligence Brief** — must produce the owner-facing message and OM-facing message separately (from `subfragment-strategy-map.md` Fragment 8 and Fragment 21)
- **Revenue Rescue Planner** — must use pgvector knowledge base for case study retrieval (from `subfragment-strategy-map.md` Fragment 20)
- **Trust Vector** — must use pgvector semantic search to match proof assets (from `subfragment-strategy-map.md` Fragment 25)
- **ICP Accuracy & Signal Calibration Monitor** — the feedback loop tool that keeps scoring weights current (from `subfragment-strategy-map.md` Fragment 26)

---

### Section 8 — Lead Scoring Model

Write the complete technical specification for the lead scoring system. Do not summarize — be complete.

Include:
- The exact weighted formula from `sova-agent-context.md` §6
- How each component score is computed (which tables, which signals, what normalization to 0–100)
- Every bounded modifier with its exact value and the signal condition that triggers it
- The full signal decay implementation: `Decayed Value = Raw Value × e^(−ln(2) × days_since_signal / half_life)` with a table of every signal type and its half-life
- HOT qualification: all six conditions that must simultaneously be true
- The `LeadScore` Django model (storing composite score + all component scores + modifiers + decay metadata)
- The `Signal` Django model (storing individual raw signals with collected_at, allowing decay recomputation)
- How decay recomputation is triggered (daily Celery task)
- How score history is versioned (each recompute creates a new `LeadScore` row, not an update)

---

### Section 9 — Celery Task Architecture

Specify the complete Celery setup:

**Queues** — what queues exist and what goes in each:
- `default` — general tasks
- `collectors` — all sub-fragment tasks (can be throttled independently)
- `tools` — tool invocation tasks (higher priority, lower volume)
- `health` — health check and monitoring tasks

**Celery Beat schedule** — the complete `CELERY_BEAT_SCHEDULE` dict. For every sub-fragment, specify the cron expression or interval. Group them by cadence:
- Hourly: (e.g., `live_answer_audit` spot checks, `reputation_shock_detector`)
- Daily: (e.g., `google_places_collector`, `dentalpost_collector`, `competitor_pr_monitor`)
- Weekly: (e.g., `nppes_collector` delta, `website_crawler`, `competitor_product_monitor`)
- Monthly: (e.g., full `nppes_collector` refresh, `oig_exclusion_checker`, `bls_staffing_heatmap`)
- On-event: (e.g., `newsletter_classifier` triggered by `email_inbox_reader` completion)

**Task base class** — specify a `SovaBaseTask(celery.Task)` that all sub-fragments inherit from, implementing:
- Automatic `SubFragmentRunLog` update on success and failure
- Automatic `connections.close_all()` in after_return
- Automatic Sentry exception capture
- The distributed mutex pattern

**Worker configuration** — concurrency settings, prefetch multiplier, task serializer

---

### Section 10 — API Design

Specify the complete REST API. For every endpoint:
- HTTP method + URL path
- Request body fields (name, type, required, validation rules)
- Response body fields
- HTTP status codes returned
- Authentication method
- Rate limiting applied

Required endpoints:

```
Health & Monitoring
  GET  /api/v1/health/collectors/          → sub-fragment health status
  GET  /api/v1/health/                     → overall system health

Practices
  GET  /api/v1/practices/                  → list with filters (state, specialty, tier)
  GET  /api/v1/practices/<npi>/            → single practice full record
  GET  /api/v1/practices/<npi>/signals/    → all signals collected for this practice

Lead Intelligence
  GET  /api/v1/leads/hot/                  → HOT leads, filterable
  GET  /api/v1/leads/warm/                 → WARM leads, filterable
  POST /api/v1/tools/lead-score/           → compute/refresh lead score (202 + run_id)
  POST /api/v1/tools/outreach-brief/       → generate outreach brief (202 + run_id)
  POST /api/v1/tools/revenue-rescue/       → generate revenue rescue plan (202 + run_id)

Competitive Intelligence
  GET  /api/v1/intelligence/competitive/   → latest competitive report
  GET  /api/v1/intelligence/market/        → latest market report

Task Management
  GET  /api/v1/tasks/<run_id>/             → poll task status
  GET  /api/v1/tasks/<run_id>/stream/      → SSE event stream
  POST /api/v1/tasks/<run_id>/cancel/      → cancel running task

Chatbot (v2 — scaffold now)
  POST /api/v1/chatbot/conversations/                              → create thread
  POST /api/v1/chatbot/conversations/<thread_id>/query/           → submit (202)
  GET  /api/v1/chatbot/tasks/<run_id>/                            → poll status
  GET  /api/v1/chatbot/tasks/<run_id>/stream/                     → SSE stream
  POST /api/v1/chatbot/tasks/<run_id>/cancel/                     → cancel

Knowledge Base (internal)
  POST /api/v1/knowledge/rebuild/          → trigger knowledge index rebuild
```

---

### Section 11 — Docker Compose Configuration

Specify the complete `docker-compose.yml`. Every service. Every environment variable reference. Every volume. Every port mapping. Every health check.

Required services:
- `db` — PostgreSQL 16 with pgvector extension
- `redis` — Redis 7
- `web` — Django + Gunicorn
- `celery-worker-collectors` — Celery worker for the `collectors` queue
- `celery-worker-tools` — Celery worker for the `tools` queue
- `celery-beat` — Celery Beat scheduler
- `flower` — Celery monitoring UI (port 5555)

For each service specify:
- Image
- Environment variables (reference to `.env` file, not values)
- Volumes
- Ports
- Depends_on with health checks
- Restart policy

Also specify the `.env.example` file with every required environment variable name and a comment explaining what it is and where to get it.

---

### Section 12 — Knowledge Base Design

Specify the complete pgvector knowledge base:

**Source files structure:**
```
knowledge/
  yaml/
    outreach_playbooks.yaml    → pitch angles by ICP type
    objection_handlers.yaml    → common objections + responses
    competitor_comparisons.yaml → Sova vs each competitor
    icp_profiles.yaml          → ICP type definitions
  case_studies/
    *.md                       → individual case studies (one per client type)
```

**YAML schema** for each file type — what fields each entry must have.

**`build_knowledge_index` management command** — step-by-step implementation spec:
1. Load all YAML files and .md files
2. For each item, generate embedding using `text-embedding-3-small` (1536 dimensions)
3. Write to `sova_knowledge` table (upsert by content hash)
4. Log counts: items processed, inserted, updated, skipped

**Retrieval pattern** — the `search_knowledge` function that tools call, including cosine distance threshold (0.75), k=3, result formatting for LLM prompt injection.

---

### Section 13 — Compliance & Legal Requirements

Extract every compliance flag from `subfragment-strategy-map.md` Compliance & Legal Risk Flags section and Build Validation section and present them as hard implementation requirements:

For each flagged sub-fragment:
- What the legal/ToS risk is
- What the required mitigation is
- Whether it requires pre-production legal sign-off (yes/no)

Also include the full TCPA/FCC requirements from the TCPA section of `subfragment-strategy-map.md` — these affect the product itself, not just data collection.

---

### Section 14 — Phased Build Plan

Produce a phased implementation roadmap. Derive the phases from `learnings-from-eva.md` Build Order Recommendation and `sova-agent-context.md` §8. For each phase:
- Name and goal
- Exact list of what to build (file names, function names, model names)
- What "done" looks like (acceptance criteria)
- Estimated relative complexity (Low / Medium / High)
- Dependencies (what must be in place before this phase starts)

Required phases:
- **Phase 0 — Foundation**: Django project skeleton, Docker Compose, `SovaConfig`, shared utilities, `SubFragmentRunLog`, Sentry, base Celery setup
- **Phase 1 — Practice Data Foundation**: NPPES collector, Google Places collector, practice master table, health monitoring endpoint
- **Phase 2 — Job Signal Layer**: All 6 job portal sub-fragments, job_postings table, `pms_signal_extractor` computation
- **Phase 3 — Competitor Intelligence**: All 11 competitor intelligence sub-fragments, competitor tables
- **Phase 4 — Lifecycle & Government Data**: All lifecycle event sub-fragments, all government data sub-fragments
- **Phase 5 — Lead Scoring Tool**: Full lead score formula implementation, `LeadScore` model, signal decay daily task, `/api/v1/leads/hot/` endpoint
- **Phase 6 — Outreach Intelligence**: Outreach Brief tool, Revenue Rescue Planner, pgvector knowledge base
- **Phase 7 — Access & Availability**: Live answer audit, after-hours audit, review platform expansion, access signals
- **Phase 8 — Competitive Ads Intelligence**: Google Ads collector, LinkedIn Ads collector, YouTube competitor monitor, TikTok monitor
- **Phase 9 — Remaining Collectors**: All remaining sub-fragments not covered in previous phases
- **Phase 10 — Chatbot Interface (v2)**: LangGraph graph, AsyncPostgresSaver, DRF API surface, Redis SSE streaming, all tools bound as LangGraph nodes

---

### Section 15 — Open Questions & Decisions Required Before Implementation

List every unresolved decision the implementation agent cannot make on its own. Derive these from `subfragment-strategy-map.md` Open Questions section and add any new ones identified during PRD generation.

For each open question:
- State the question precisely
- State the options
- State the implication of each option for implementation
- Flag whether it blocks a specific phase

---

## Constraints for the PRD Agent

1. **Do not invent requirements.** Every requirement must be traceable to one of the three attached documents.
2. **Do not be vague.** "The system should handle errors gracefully" is not a requirement. "Every sub-fragment must catch `requests.RequestException`, log the error to `SubFragmentRunLog.error_message`, set `last_run_status='failed'`, and re-raise for Tenacity to retry up to 3 times" is a requirement.
3. **Be opinionated on architecture.** The implementation agent is a junior developer. Do not present options — make the decision and document it. Reference `learnings-from-eva.md` for justification.
4. **Code snippets are welcome and encouraged.** Where a pattern is non-obvious (the cache mutex, the prompt caching setup, the async checkpointer per loop), include a pseudocode or Python snippet. The implementation agent will use these as starting templates.
5. **Completeness over brevity.** This PRD will be long. That is correct. An incomplete PRD produces an incomplete system. Do not truncate any section.
6. **Cross-reference the three documents constantly.** When specifying a requirement, cite which document it came from. This makes the PRD auditable.
7. **Sub-fragment specification is the most important output.** Section 6 will be the longest section. It should be. There are 110 sub-fragments to specify. Do not skip any. Do not produce a summary table instead of a full spec. The implementation agent needs a spec, not a summary.
