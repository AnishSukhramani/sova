# 09 — Summary + Replication Checklist

## Technologies used (flat list, one-line role each)

| Technology | Role |
|---|---|
| Python 3.12 | Runtime |
| Poetry | Dependency management |
| Django 5.1.1 | ORM, settings, request routing, cache, sync↔async bridges |
| Django REST Framework 3.15.2 | API views, serializers, Token authentication |
| pgvector 0.3.3 | Vector column type + `CosineDistance` for knowledge semantic search |
| psycopg2, psycopg_pool | Postgres drivers (sync and async pools) |
| Redis (via `django-redis` + `redis` client) | SSE pub/sub, mutex locks, caches |
| LangChain Core 1.x | Message types, `@tool` decorator, runtime configuration |
| LangChain Anthropic 1.x | `ChatAnthropic` — every Anthropic LLM call |
| LangChain OpenAI 1.x | `OpenAIEmbeddings(model="text-embedding-3-large")` — only embedder |
| LangChain MCP Adapters 0.2 | `MultiServerMCPClient` — wraps GitHub MCP HTTP transport |
| LangGraph 1.x | `StateGraph`, conditional edges, `MessagesState` |
| LangGraph Postgres Checkpointer 3.x | `AsyncPostgresSaver` / `PostgresSaver` — per-thread graph state persistence |
| LangSmith 0.8.x | Optional tracing dashboard |
| Pydantic 2.10 | Every state, request, response, structured-output schema |
| FAISS (faiss-cpu 1.9) | Alternate `LocalKnowledgeStore` (IndexFlatIP) — not the default path |
| Qdrant (qdrant-client) | Mem0 backend + codebase indexer backend (both currently disabled) |
| Mem0 (mem0ai 1.x) | Cross-session memory layer (currently disabled) |
| sqlparse 0.5 | SQL parsing for safety/limit detection |
| tenacity 8 | Retries on DB queries |
| Twilio SDK 9.3.2 | Call / Conference debug |
| Langfuse REST (direct urllib) | Per-call LLM trace fetcher |
| Google Cloud Logging 3.12 | Cloud Run log fetcher for SRE call debug |
| Google Auth 2.47 | Service Account auth (`EVALS_GCP_SA_KEY`) and ADC |
| Google Cloud Storage 2.18 | PDF report uploads (currently disabled) |
| Prefect 3.7.1 | Workflow orchestration (5 deployments) |
| Celery 5.4 | In-process task body invocation via `task.apply()` |
| pygithub 2.x + PyJWT[crypto] | GitHub App installation token signing |
| Anthropic Claude (Haiku / Sonnet / Opus) | Reasoning LLM |
| OpenAI `text-embedding-3-large` | Embedding model (3072 dims) |
| GitHub MCP (`api.githubcopilot.com/mcp/`) | Live repo code/file/commit access via Bearer auth |
| Sentry SDK 2.27 | Exception capture |
| xhtml2pdf 0.2 | Markdown → PDF (currently unused) |
| asgiref `sync_to_async` | Django ORM bridge for async LangGraph nodes |
| ripgrep (`rg` binary on PATH) | Local fast text search for code |
| LiveKit | Voice agent runtime; Eva reads its Cloud Run logs but does not call LiveKit APIs directly |
| Retell AI | Voice agent product; Eva reads `RetellAICall` rows (no SDK call from Eva) |

## External dependencies Eva cannot run without

1. **Anthropic Claude API** — `ANTHROPIC_API_KEY`. All reasoning.
2. **Postgres** with pgvector extension — for app data, knowledge base, and LangGraph checkpoints.
3. **Redis** — for SSE streams and mutex locks.
4. **OpenAI Embeddings API** — `OPENAI_API_KEY`. Required if knowledge base is populated (`text-embedding-3-large`).
5. **Django settings module** — `admin_backend/config.py` is the single source of secrets.

Eva functions degrade gracefully without (but is significantly less capable):
- LangSmith (no tracing).
- Mem0 + Qdrant (currently disabled anyway).
- GCS (PDF export is currently disabled anyway).
- GitHub MCP (SRE code-context lookups fall back to local ripgrep).

## What Eva evaluates

Eva is **not a benchmark scorer**. It is an **investigation agent** that produces **markdown reports** answering operational questions about Neurality's voice-AI platform. Specifically:

- **BI** — Business-intelligence questions: *Why did booking rate drop?*, *Which locations underperform?*, *Is automation rate above baseline?* — answered by SQL queries against ~72 Postgres tables (call insights, appointments, agents, locations, campaigns), interpreted against curated baselines (22% negative on failures, 61% l1_pass, etc.), and rendered as a `FINDINGS_REPORT_FORMAT` markdown report.
- **SRE** — Root-cause questions about specific calls or operational behavior: *Why did call X fail?*, *Which code change caused the agent to hang up?* — answered by correlating Langfuse traces, GCP Cloud Run logs, Twilio call/conference debug, and live GitHub code via MCP, rendered as an `INVESTIGATION REPORT` markdown report.
- **Multi-agent** — Cross-domain questions that need both: *Did the deploy on Monday cause the booking-rate drop?* — coordinated by a supervisor with a shared blackboard.
- **Chatbot** — Quick single-turn answers via tool-backed conversation, with the option to escalate to deep search.

**Criteria** (assessed by the LLM following rubric prompts):
- **Confidence** (High / Moderate / Low) — based on sample size, source diversity, time-stability.
- **Evidence citations** — required for every claim (span/trace id, code file:line, DB query, log line + timestamp).
- **Cross-validation** — `CrossValidateSkill` measures the same metric two ways; discrepancy ratio itself is a finding.
- **Baseline comparison** — `ContextualizeSkill` measures delta vs platform baseline.
- **Pattern saturation** — `DiscoverSkill` iterates until "Other/Unclear" ≤ 6%.

---

## Replication checklist — set up Eva from scratch in a fresh environment

Numbered, in order. Each step is actionable.

### Accounts and credentials

1. **Get an Anthropic API key** at console.anthropic.com. Set `ANTHROPIC_API_KEY` in your Django settings or environment. Test access to models with the strings used by Eva (`claude-haiku-4-5-20251001`, `claude-sonnet-4-6`, etc.). **Note:** these are internal codename IDs; you may need to substitute real model IDs (e.g. `claude-haiku-4-5-20251001`, `claude-sonnet-4-5-20250929`) or update the `AVAILABLE_MODELS` list in `config.py` to match models you have access to.
2. **Get an OpenAI API key** at platform.openai.com. Set `OPENAI_API_KEY`. Confirm access to `text-embedding-3-large` (3072 dims).
3. **Get GitHub access** — either:
   - Create a GitHub App with `Contents: Read` permission, install on your code repo, and configure `admin_app/services/codebase_indexer/github_app_auth.py` with the app id, private key, and installation id. The token will be auto-fetched. OR
   - Create a PAT with `repo` scope and set `GITHUB_TOKEN`.
4. **Set up GCP** — create a service account with `roles/logging.viewer` (and `roles/logging.viewAccessor` for cross-project). Download the JSON key, base64-encode it, and set `EVALS_GCP_SA_KEY` (or save to file and use ADC). Set `GCP_LOGS_PROJECT_ID` to the project that hosts your LiveKit Cloud Run services.
5. **Set up Langfuse** — self-host or sign up at langfuse.com. Create a project, get the public/secret key pair. Set `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`. Confirm your voice-agent runtime is configured to emit traces with `sessionId = nhapp_retellaicall.id` (UUID).
6. **Set up Twilio** — if you need Voice debug. Set `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`.
7. **(Optional) Set up Prefect** — install Prefect Cloud or self-host. Get the API URL + key (`PREFECT_API_URL`, `PREFECT_API_KEY`). Without this, you can still run the chatbot path and the direct Celery deep-engineer path; you lose only the auto-scheduled Slack/feedback/technical-issue flows.
8. **(Optional) Set up LangSmith** — sign up at smith.langchain.com. Get an API key. Set `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_ENDPOINT`, `LANGSMITH_PROJECT`.
9. **(Optional) Set up Slack** — create a Slack app with `app_mentions:read` and `chat:write`. Set `SLACK_WEBHOOK_SECRET`. Wire it to your Eva HTTP endpoint that submits the `process-eva-investigation-mention` Prefect deployment.
10. **(Optional) Set up Qdrant + Mem0** — these are currently disabled. To re-enable, provision Qdrant (cloud or self-hosted), set `QDRANT_URL` + `QDRANT_API_KEY`, and uncomment the Mem0 call sites in `bi_agent.py::_memory_load_node` and `_remember_node`, and `sre_agent.py::_context_load_node` and `_save_to_memory`.

### Infrastructure

11. **Provision a Postgres database** with the `pgvector` extension enabled. Create a database for the app and configure Django's `DATABASES["default"]`, `DATABASES["read_db"]`, and (if multi-env) `read_db_staging`, `default_staging`.
12. **Provision Redis** (single-node or cluster). Configure `CELERY_BROKER_URL` and `REDIS_URL`. Configure `django-redis` as the cache backend.
13. **(Optional) Provision GCS bucket** for PDF report uploads. Currently unused by Eva (`EvalAgentExportReportView` returns 503); only needed if you re-enable that view.
14. **Install ripgrep** (`rg`) on the worker hosts. Eva calls it via subprocess in `codebase_context_tool.py`.
15. **Clone your codebase repo** to `CODEBASE_REPO_ROOT` on the worker hosts. Set `CODEBASE_REPO_URL` (the GitHub URL) for MCP repo-scoping. Set `CODEBASE_INDEX_DIR` if you intend to re-enable the Qdrant indexer.

### Application setup

16. **Clone the `neurality_admin_backend` repository.** All of Eva lives under `admin_app/services/eval_agent/`, `admin_app/api/eval_agent/`, `admin_app/models/admin_evals.py`, and `prefect_app/eva_investigations/`.
17. **Install dependencies:**
    ```bash
    poetry install
    ```
    Pin Python `^3.12`. Lockfile resolves langgraph, langchain, langchain-anthropic, langchain-openai, prefect, mem0ai, qdrant-client, faiss-cpu, etc.
18. **Run Django migrations:**
    ```bash
    poetry run python manage.py migrate
    ```
    This creates the `nhapp_evalagentconversation`, `nhapp_evalagentreports`, and `nhapp_knowledgeembedding` tables. The LangGraph checkpointer tables are auto-created on first `setup()` call.
19. **Populate the knowledge base** (one-time, then rerun on changes):
    ```bash
    poetry run python -m admin_app.services.eval_agent.knowledge.build_index
    ```
    This reads `admin_app/services/eval_agent/knowledge/files/*.md`, chunks them via `load_from_files.py`, embeds each chunk with OpenAI `text-embedding-3-large`, and writes `KnowledgeEmbedding` rows. **Authoritative content lives in `knowledge/files_yaml/*.yaml`** — non-FAQ knowledge is loaded from YAML at query time, not from the pgvector index.

### Smoke tests

20. **Verify Anthropic + OpenAI connectivity:**
    ```bash
    poetry run python -c "from langchain_anthropic import ChatAnthropic; from admin_backend.config import ANTHROPIC_API_KEY; print(ChatAnthropic(model='claude-haiku-4-5-20251001', api_key=ANTHROPIC_API_KEY).invoke('ping').content)"
    poetry run python -c "from langchain_openai import OpenAIEmbeddings; from admin_backend.config import OPENAI_API_KEY; print(len(OpenAIEmbeddings(model='text-embedding-3-large', openai_api_key=OPENAI_API_KEY).embed_query('test')))"
    ```
    Expected: text response and `3072`.
21. **Verify pgvector knowledge search:**
    ```bash
    poetry run python -c "
    from admin_app.services.eval_agent.knowledge.store import DatabaseKnowledgeStore
    s = DatabaseKnowledgeStore()
    print(s.search('What is the automation rate?', k=3))
    "
    ```
22. **Verify checkpointer setup:**
    ```bash
    poetry run python -c "
    import asyncio
    from admin_app.services.eval_agent.checkpointer import get_async_postgres_checkpointer
    asyncio.run(get_async_postgres_checkpointer())
    "
    ```
    Expected: log message "Async Postgres checkpointer setup completed (checkpoint tables created/verified)."
23. **Start the Django dev server:**
    ```bash
    poetry run python manage.py runserver 8001
    ```
24. **Create a thread via API:**
    ```bash
    curl -X POST http://localhost:8001/api/v1/eval-agent/threads/ \
      -H "Authorization: Token <your_token>" \
      -H "Content-Type: application/json" \
      -d '{}'
    ```
    Returns a `conversation_id` and `thread_id`.
25. **Submit a chatbot query:**
    ```bash
    curl -X POST http://localhost:8001/api/v1/eval-agent/query/ \
      -H "Authorization: Token <your_token>" \
      -H "Content-Type: application/json" \
      -d '{
        "query": "How many calls did we get yesterday?",
        "auto_route": true,
        "thread_id": "<thread_id_from_step_24>"
      }'
    ```
    Returns HTTP 202 with `job_id`.
26. **Poll for status:**
    ```bash
    curl http://localhost:8001/api/v1/eval-agent/query/<job_id>/ \
      -H "Authorization: Token <your_token>"
    ```
    Expected: eventually `status: "completed"` with `result.report_markdown`.
27. **Test deep-search SRE end-to-end:**
    Submit a query like *"Why did call <real_call_uuid> fail?"* and confirm:
    - Mode router picks `deep_search_sre`.
    - SRE intake resolves the call_id.
    - `_call_trace_fetch_node` fetches Langfuse + GCP in parallel.
    - The single-loop ReAct (`run_agent`) runs ≤ 30 rounds.
    - Returns a markdown report following the `SRE_CONCLUDE_PROMPT` shape.

### Production deployment

28. **Set up Cloud Run jobs for Prefect.** Each `@flow` in `prefect_app/eva_investigations/flows.py` is one Cloud Run Job submitted via `submit_eva_*_deployment`. Configure Prefect work pools and deployments accordingly.
29. **Configure Celery worker** for `run_deep_engineer_agent` and `run_eval_agent_investigation` tasks. Even though Prefect runners call `.apply()` (eager), Direct API calls via `POST .../deep-engineer/threads/<id>/runs/` enqueue to the broker.
30. **Configure SSE endpoint** behind a reverse proxy that supports streaming (set `X-Accel-Buffering: no` for nginx, etc.).
31. **Set up Sentry** with the project's DSN. Eva relies on the project-wide `sentry-sdk[django]` initialization.
32. **Verify LangSmith traces** appear in the configured project after a few investigations.
33. **(Production hardening)** Set `USE_DEEP_ENGINEER_FOR_INVESTIGATION = True` (default). Set `OUTBOUND_MODE` in non-prod (project convention). Confirm Token-based DRF auth, not Bearer.

### Optional re-enable steps

34. **Re-enable Mem0** — provision Qdrant, set `QDRANT_URL`/`QDRANT_API_KEY`, fix the dimension mismatch (1536 in `MemoryManager._ensure_initialized` vs 3072 of `text-embedding-3-large` — pick one), uncomment Mem0 call sites in BI and SRE agent nodes.
35. **Re-enable Qdrant codebase semantic search** — set `QDRANT_URL`/`QDRANT_API_KEY`, run the `codebase_indexer_tasks` job that populates the `"sre_codebase"` collection, and re-enable the `search_codebase` tool body.
36. **Re-enable PDF export** — uncomment the body of `EvalAgentExportReportView.post`, confirm GCS access, confirm `xhtml2pdf` is installed.

### Verification matrix

| Path | Test command | Expected behavior |
|---|---|---|
| Chatbot | `POST .../query/` with simple metric question | Routes to chatbot, single-turn answer |
| BI deep search | `POST .../query/` with "why did booking rate drop" | Routes to `deep_search_bi`, runs discover → contextualize, returns markdown report |
| SRE deep search | `POST .../query/` with specific call UUID + "why did this fail" | Routes to `deep_search_sre`, runs single-loop ReAct, returns INVESTIGATION REPORT |
| Multi-agent | `POST .../query/` with mixed BI+SRE question | Routes to `deep_search_multi`, coordinator runs both agents, returns merged report |
| Slack mention | `@eva ...` in a Slack channel | Posts placeholder, runs SRE-only deep search, updates Slack message |
| Customer feedback | New `InteractionFeedback` row | Auto-fires `process-eva-customer-feedback` flow |
| Technical issue | `CallInsight.call_outcome_sub` transitions to "Technical Issue" | Auto-fires `process-eva-technical-issue` flow |
| Cancellation | `POST .../runs/<id>/cancel/` mid-run | Prefect/Celery cancellation, SSE emits `run_cancellation_requested` |

### Known caveats / future work

- **Model id mismatch tolerance.** Eva uses internal codename IDs (`claude-haiku-4-5-20251001`, `claude-sonnet-4-6`, `gpt-5.4`). If those don't map to your provider's actual model names, update `EvalAgentConfig.AVAILABLE_MODELS`, `DEFAULT_MODEL`, `ROUTING_MODEL`, `DEEP_ENGINEER_MODEL`, `DEEP_ENGINEER_OPENAI_MODEL`, and `DEEP_ENGINEER_RUBRIC_MODEL` accordingly.
- **Dimension mismatch in `MemoryManager`.** `embedding_model_dims: 1536` vs `text-embedding-3-large` (3072 native). Resolve before re-enabling Mem0.
- **~1,300 lines of vestigial code** in `agents/sre_agent.py` (commented-out old topology). Safe to leave; not in the active execution path.
- **`run_agent` (single-loop) bypasses the LangGraph checkpointer.** Multi-session resume works for the chatbot and BI agent; SRE single-loop runs are stateless across calls. To make SRE resumable, switch the public `investigate()` path to call `_investigate_impl` instead.
- **Schema preloading commented out in BI** — agents now use `get_table_schema(table_name)` on demand. Performance is fine; only the prompt no longer holds the full schema.
- **`agent.py` (referenced in `docs/eval.md`) does not exist.** The current entry points are `agents/bi_agent.py`, `agents/sre_agent.py`, `multi_agent.py`, `chatbot/entrypoint.py`. The docs files are aspirational, not current spec.

---

## You're set up when

- A `POST .../query/` with a real BI question returns a fully-rendered `FINDINGS_REPORT_FORMAT` markdown report.
- A `POST .../query/` with a real call UUID + "why did this fail" returns an `INVESTIGATION REPORT` with evidence citations.
- The chatbot answers a follow-up question on the same `thread_id` (resume works).
- LangSmith shows a complete trace tree for each run (if enabled).
- The pgvector knowledge base returns relevant hits for a FAQ query.

## Final notes

This documentation reflects the state of Eva as of the snapshot date (2026-06-13). The code path that **actually runs in production** is summarized in `07_architecture.md` section 3. When the codebase deviates from the planning docs in `admin_app/services/eval_agent/docs/`, **the code is correct; the planning docs are aspirational**.

For per-file detail, see `06_functions_and_classes.md`. For per-prompt detail, see `04_llms_and_prompts.md`. For per-service detail, see `03_external_services.md`. For per-schema detail, see `08_data_schemas.md`.
