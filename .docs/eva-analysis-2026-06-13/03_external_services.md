# 03 — Third-Party Services and External APIs

Every external system Eva touches, with credentials (variable names only), endpoints/methods called, what's stored/read, and whether it's required.

---

## 1. Anthropic — Claude (LLM)

- **What it is:** Claude family LLMs. Eva's reasoning engine.
- **How Eva uses it:** All LLM inference. Mode routing, BI planning + replanning, BI skill execution, knowledge-base answer formatting, BI report rendering, SRE intake, SRE tier-1 + tier-2 ReAct loops, SRE conclude, SRE hypothesis revision, conversation/mode-switch summarization, chatbot turns, partial-report synthesis.
- **SDK / lib:** `langchain_anthropic.ChatAnthropic` (calls Anthropic Messages API). Models requested by ID string (passed verbatim from `EvalAgentConfig.AVAILABLE_MODELS`).
- **Credentials:** `ANTHROPIC_API_KEY` (from `admin_backend.config`).
- **Models used (verbatim strings the code sends to the SDK):**
  - `claude-haiku-4-5-20251001` — `EvalAgentConfig.DEFAULT_MODEL` and `ROUTING_MODEL` and `DEEP_ENGINEER_RUBRIC_MODEL`
  - `claude-opus-4-5-20251101`
  - `claude-sonnet-4-5-20250929`
  - `claude-sonnet-4-6` — `DEEP_ENGINEER_MODEL` and Slack default
- **Anthropic-specific features used:**
  - **Prompt caching** via `cache_control: {"type": "ephemeral"}` blocks. Used in: `multi_agent.py::_supervisor_llm_route_async`, `multi_agent.py::_merge_reports`, `sre_agent.py::run_agent` (system prompt), `sre_agent.py::_conclude_node` (via `_human_message_with_cache`), `skills/skill_utils.py::run_llm_with_tools`.
  - **Structured output** via `llm.with_structured_output(SchemaClass)` for Pydantic-validated returns.
  - **Tool binding** via `llm.bind_tools(tools)` for ReAct loops.
- **Per-call parameters (typical):** `temperature=EvalAgentConfig.TEMPERATURE (0.3)`, `max_tokens=EvalAgentConfig.MAX_TOKENS (4096)` (SRE clamps to `min(4096, MAX_TOKENS)`), `timeout=120s` (BI) / `60s` (mode router, summarizers) / `30s` (supervisor), `max_retries=2` (BI only). Mode router uses `temperature=0`, `max_tokens=1024`.
- **Required?** Yes. Eva does not function without this.

---

## 2. OpenAI — Embeddings

- **What it is:** OpenAI Embeddings API.
- **How Eva uses it:** Embeds knowledge items, queries, and Mem0 memories for vector search.
- **SDK / lib:** `langchain_openai.OpenAIEmbeddings`.
- **Credentials:** `OPENAI_API_KEY` (from `admin_backend.config`, falls back to `os.environ`).
- **Model used (verbatim):** `text-embedding-3-large` (3072 dimensions native; matches `KnowledgeEmbedding.embedding = VectorField(dimensions=3072)`).
- **Endpoints called (via SDK):** `POST /v1/embeddings`.
- **Methods used:** `embed_query(text)`, `embed_documents(texts)`.
- **Required?** Required when knowledge base or Mem0 are used. Optional if knowledge base is empty and FAQ check is disabled (rare).
- **Notes:**
  - `MemoryManager` config hard-codes `embedding_model_dims: 1536`, which appears inconsistent with `text-embedding-3-large` (native 3072). This is either intentional Mem0 truncation behavior or a stale constant. Since Mem0 is currently disabled, the discrepancy is dormant.
  - The deep-engineer config also references `DEEP_ENGINEER_OPENAI_MODEL = "gpt-5.4"` as a fallback chat model when `DEEP_ENGINEER_DEFAULT_PROVIDER == "openai"` (default is `"anthropic"`).

---

## 3. Google Cloud Logging (GCP)

- **What it is:** Cloud Logging — read-only log inspection.
- **How Eva uses it:** Fetches Cloud Run logs for a specific call window. Two scopes:
  1. **Call-debug scope** — `livekit-agents-prod` (or `livekit-agents-staging`); used to correlate Langfuse traces with infrastructure events for a single call.
  2. **Broad scope** — adds `backend-api` (or `backend-api-v2`), `celery-default-prod` (or staging), `celery-beat-prod` (or staging).
- **SDK / lib:** `google-cloud-logging` (`google.cloud.logging.Client.list_entries`).
- **Credentials:**
  - `EVALS_GCP_SA_KEY` (from `admin_backend.config`) — JSON SA key (preferred), parsed by `admin_backend.gcp_sa.parse_gcp_service_account_dict`, scope `https://www.googleapis.com/auth/logging.read`.
  - Fallback: `google.auth.default(scopes=[_LOGGING_READ_SCOPE])` (ADC).
- **Project resolution:** `GCP_LOGS_PROJECT_ID` env (preferred) → `GOOGLE_CLOUD_PROJECT` env → SA `project_id`.
- **Cloud Logging filter shape (built dynamically):**
  ```
  timestamp >= "<rfc3339>" AND timestamp <= "<rfc3339>"
    AND resource.type="cloud_run_revision"
    AND (resource.labels.service_name="livekit-agents-prod" [OR ...])
    [AND SEARCH("<phone variant>") [OR SEARCH("<other variant>")]]
  ```
- **Pagination / caps:** `max_results=MAX_LOG_ENTRIES_WITH_TRANSCRIPT (800)`, `max_chars=100_000`, ordered `timestamp asc`. Severity allowlist: `{DEFAULT, INFO, ERROR}`. Dedup by `(severity, service, msg)` fingerprint. Transcript lines starting with `"Transcript for twilio_"` are separated and appended in full as a `--- GCP call transcript (full textPayload) ---` section.
- **Required?** Required for SRE deep-search investigations of specific calls. Optional otherwise.

---

## 4. Langfuse — LLM trace observability

- **What it is:** Self-hosted (or Cloud) LLM observability — captures per-call traces of the voice agent (Retell + LiveKit) with input/output, latency, cost, model, tool calls.
- **How Eva uses it:** Loads call traces for a specific session (= `nhapp_retellaicall.id` UUID) to inspect what the voice agent said and did. Two variants:
  - `get_langfuse_session_call_logs(session_id)` — latest trace → latest v2 observation → merged input/output `call_logs` (system role messages stripped).
  - `get_langfuse_call_traces(session_id, limit)` — compact event list (keeps `agent_turn`, `user_turn`, `tts_request`, `llm_request`, `llm_response`, `llm_node`, `function_tool`; drops `tts_node`, `tts_request_run`, etc.), token budget 180,000.
- **SDK / lib:** None. Eva calls Langfuse's REST API directly with `urllib.request`.
- **Credentials:** `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` (from `admin_backend.config`).
- **Auth:** `Authorization: Basic <base64(PUBLIC_KEY:SECRET_KEY)>`.
- **Endpoints:**
  - `GET {host}/api/public/traces?sessionId=<id>&limit=100&page=N` — list traces for session.
  - `GET {host}/api/public/v2/observations?traceId=<id>&limit=100&fields=core,basic,metrics,io&cursor=...` — cursor-paginated observations (max 50 pages).
  - `GET {host}/api/public/observations?traceId=<id>&page=N` — v1 endpoint used by `sre_tools.py`.
- **Timeout:** 30s.
- **Call-age guard:** Calls younger than `LANGFUSE_CALL_MIN_AGE_MINUTES = 30` are rejected (`_is_call_old_enough_for_langfuse` checks `RetellAICall.created_at` or `ChatSession.created_at`).
- **Cache:** `eval_agent:langfuse_traces:<session_id>:<limit>` (Django cache, 3600s TTL).
- **Required?** Required for SRE deep-search. Optional otherwise.

---

## 5. Twilio Voice — REST debug

- **What it is:** Twilio Voice telephony platform.
- **How Eva uses it:** Fetches Call and Conference resources + Events when investigating warm-transfer / multi-leg call scenarios.
- **SDK / lib:** `twilio.rest.Client` (Twilio Python SDK 9.3.2).
- **Credentials:** `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` (from `admin_backend.config`).
- **Auth:** Basic auth (managed by SDK).
- **Endpoints (per Twilio REST naming):**
  - `GET /2010-04-01/Accounts/{AccountSid}/Calls/{CallSid}.json` — call resource.
  - `GET /2010-04-01/Accounts/{AccountSid}/Calls/{CallSid}/Events.json` — call events subresource (limit=100; auto-paginated by SDK).
  - `GET /2010-04-01/Accounts/{AccountSid}/Conferences/{ConferenceSid}.json` — conference resource.
  - `GET /2010-04-01/Accounts/{AccountSid}/Conferences/{ConferenceSid}/Participants.json` — paginated participants (page_size=100, max 500).
  - `GET .../Participants/{IdentityOrCallSid}.json` — individual participant.
- **Inputs:** Call SIDs (`CA...`) or Conference SIDs (`CF...`); regex `\bCF[0-9a-fA-F]{32}\b` finds conference SIDs inside call payloads.
- **Required?** Optional. Used only when warm transfers are involved.

---

## 6. GitHub — Live codebase access via MCP (Model Context Protocol)

- **What it is:** GitHub's hosted Copilot MCP server (`https://api.githubcopilot.com/mcp/`) provides streamable-HTTP MCP tools that query the live GitHub state.
- **How Eva uses it:** Live code search, file reads, directory listings, commit history. SRE agents use this for code-context lookups instead of the disabled Qdrant codebase indexer.
- **SDK / lib:** `langchain_mcp_adapters.client.MultiServerMCPClient`.
- **Transport:** `streamable_http`.
- **URL:** `https://api.githubcopilot.com/mcp/`.
- **Credentials (preferred order):**
  1. **GitHub App installation token** — via `admin_app.services.codebase_indexer.github_app_auth.get_installation_token()` when `is_github_app_configured()` is True.
  2. **PAT** — `GITHUB_TOKEN` or `GH_SECRET_KEY` (from `admin_backend.config`).
- **Auth header:** `Authorization: Bearer <token>`.
- **MCP tools called (by name):**
  - `search_code` — receives `query` (keyword + `in:file` + optional `repo:owner/name`).
  - `get_file_contents` — `owner, repo, path, ref` (forced to `"main"`).
  - `list_commits` — `owner, repo, path, sha, perPage` (camelCase parameter).
  - `list_files` / `list_repo_files` / `get_files` — falls back to `get_file_contents` if not available.
  - `get_repo_metadata` (with name candidates `get_repo_metdata`, `repo_metadata`, `get_repository_metadata`).
- **Repo resolution:** `parse_codebase_repo()` parses `CODEBASE_REPO_URL` (env) of the form `https://github.com/owner/repo.git` or `git@github.com:owner/repo.git`.
- **Caching:** Process-wide singleton client + tool list, `asyncio.Lock` for init race protection.
- **Required?** Required for the SRE single-loop ReAct path and for tier-1/tier-2 LangGraph paths. The chatbot also uses these tools.

---

## 7. Postgres (read replica + checkpoint DB)

- **What it is:** Application Postgres database (pgvector enabled).
- **How Eva uses it:**
  - **Read-only SQL** via `tools/db_client.py` (Django `connections["read_db"]` or `read_db_staging` / `default`).
  - **pgvector** for `KnowledgeEmbedding` table — semantic search of curated knowledge.
  - **LangGraph checkpointing** via `langgraph-checkpoint-postgres` (`AsyncPostgresSaver.from_conn_string(...)` using the `default` Django DB).
  - **Conversation persistence** in `EvalAgentConversation` and `EvalAgentReports`.
- **Connection:** Django ORM `connections["read_db"]` (default for read SQL); also constructs `psycopg_pool.ConnectionPool` / `psycopg_pool.AsyncConnectionPool` directly for the checkpointer (constructed from Django's default DB settings via URL-encoded string).
- **Safety:**
  - 30s `SET LOCAL statement_timeout` per query.
  - Hard table allowlist (`utils.py::ALLOWED_TABLES`, 72 tables).
  - `SQLValidationTool` — multiple checks (dangerous patterns, statement type, JOIN cap, injection patterns).
  - `apply_row_sample_limit_guard` adds `LIMIT` to row-sampling queries.
  - 2-attempt tenacity retries.
- **Required?** Yes. Eva cannot run without Postgres.

---

## 8. Qdrant (vector DB)

- **What it is:** Standalone vector database.
- **How Eva uses it:**
  - **Mem0 backend** — Currently disabled. `MemoryManager._ensure_initialized` configures `Memory.from_config({"vector_store": {"provider": "qdrant", "config": {url, api_key, collection_name, embedding_model_dims: 1536}}})`. Two collections: `bi_memory`, `sre_memory`.
  - **Codebase indexer backend** — Currently disabled. The collection is `"sre_codebase"`, embedding dimension 1536, model = OpenAI (`OPENAI_API_KEY` configured separately).
- **SDK / lib:** `qdrant-client` 1.12+ (constrained `<1.17.0` for numpy compatibility).
- **Credentials:** `QDRANT_URL`, `QDRANT_API_KEY` (from `admin_backend.config`, fallback to `os.environ`).
- **Required?** Currently not required (both consumers disabled).

---

## 9. Mem0 (cross-session memory)

- **What it is:** Open-source memory layer for LLM apps; uses Qdrant as vector store and OpenAI as embedder.
- **How Eva uses it:** Stores **episodic** (per-investigation history) and **semantic** (reusable patterns) memories under separate `user_id`s (`bi_agent`, `sre_agent`). Searched at start of each investigation; written at `_remember_node` / `_save_to_memory`.
- **SDK / lib:** `mem0ai >= 1.0.5` (`from mem0 import Memory`).
- **Config dict (stored in `MemoryManager._ensure_initialized`):**
  ```python
  {
    "vector_store": {"provider": "qdrant", "config": {url, api_key, collection_name, embedding_model_dims: 1536}},
    "embedder": {"provider": "openai", "config": {"model": "text-embedding-3-large", "api_key": OPENAI_API_KEY}}
  }
  ```
- **Methods called:** `client.search(query, user_id, limit, filters)`, `client.add(messages, user_id, metadata)`, `client.get_all(user_id, limit)`, `client.delete(memory_id)`.
- **Status:** **Disabled** — all call sites commented out.
- **Required?** No.

---

## 10. Prefect (workflow orchestration)

- **What it is:** Prefect Cloud or self-hosted server. Eva runs as Prefect flows on Cloud Run Jobs (one flow run per job).
- **How Eva uses it:** Five deployments:
  - `process-eva-customer-feedback`
  - `process-eva-technical-issue`
  - `process-eva-investigation-mention` (Slack)
  - `process-eva-query` (manual)
  - `process-eva-brain-curator`
- **SDK / lib:** `prefect 3.7.1`.
- **APIs called:**
  - `prefect.deployments.run_deployment(name, parameters, flow_run_name, timeout=0, tags, idempotency_key, as_subflow=False)` — submits a flow run (fire-and-forget when `timeout=0`).
  - `prefect.client.orchestration.get_client(sync_client=True)` — fetches flow run status; sets state to `Cancelled`.
  - `prefect.runtime.flow_run.id` / `prefect.runtime.flow_run.flow_name` — read inside a flow to rename it.
- **Auth:** Prefect API URL + key resolved by SDK from `PREFECT_API_URL` / `PREFECT_API_KEY` env vars (managed by deployment infrastructure, not by Eva code).
- **Required?** Required for Prefect-triggered investigations (Slack, customer feedback, technical issue, manual query). The chatbot and direct query API (via Celery) do not depend on Prefect.

---

## 11. Redis (pub/sub + cache)

- **What it is:** Redis server.
- **How Eva uses it:**
  - **SSE streaming** — `deep_agent_stream.py` publishes per-job events (`eval_agent:deep_stream:events:<job_id>` list, `:counter:`, `:channel:`, `:status:`) with `STREAM_TTL_SECONDS = 86400` (24h).
  - **Django cache** (`django-redis` backed) — investigation locks (`feedback_eva:lock:<id>`, `call_insight_eva:lock:<id>`), query-type classifier cache, file summary cache, Langfuse trace cache, Prefect flow run cache.
- **Credentials:** Project-level Redis URL (`CELERY_BROKER_URL` env, also `REDIS_URL`).
- **Required?** Yes for streaming and locks.

---

## 12. Google Cloud Storage (GCS) — disabled

- **What it is:** GCS for report PDF uploads.
- **How Eva used it:** `EvalAgentExportReportView` previously uploaded compiled report PDFs and returned signed URLs (7-day expiry).
- **SDK / lib:** `google-cloud-storage` 2.18.2.
- **Status:** Disabled — view returns HTTP 503. The original `StorageService.document_url_from_stored(...)` call is preserved in `EvalAgentConversationDetailView` for legacy `EvalAgentReports.document_url` lookup.
- **Required?** No.

---

## 13. Slack — bot mentions (via `slack_service`)

- **What it is:** Slack workspace API.
- **How Eva uses it:** Receives `@eva` mentions, posts placeholders, edits with results.
- **SDK / lib:** Not used directly by `eval_agent`; routed through `admin_app/services/slack_service.py` (`slack_post_message`, `slack_update_message`, `strip_bot_mention`, `postprocess_text_for_slack`).
- **Credentials:** Slack bot token + signing secret (`SLACK_WEBHOOK_SECRET` per provided context; resolved in `slack_service` which is outside `eval_agent`).
- **Endpoints:** `slack_service` calls Slack Web API directly.
- **Required?** Required only for Slack-triggered investigations.

---

## 14. LangSmith — tracing

- **What it is:** Hosted LangChain tracing dashboard.
- **How Eva uses it:** Optional tracing for all LangChain LLM calls and graph runs. Enabled when `LANGSMITH_TRACING` is truthy AND `LANGSMITH_API_KEY` is set (`EvalAgentConfig.is_langsmith_enabled`).
- **Configuration variables:** `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_ENDPOINT`, `LANGSMITH_PROJECT` (from `admin_backend.config`).
- **Required?** No.

---

## Quick reference — auth header / credential pattern matrix

| Service | Header / mechanism |
|---|---|
| Anthropic | SDK reads `ANTHROPIC_API_KEY`, sends `x-api-key: <key>` |
| OpenAI | SDK reads `OPENAI_API_KEY`, sends `Authorization: Bearer <key>` |
| GCP Cloud Logging | OAuth2 via service account JSON or ADC; scope `https://www.googleapis.com/auth/logging.read` |
| Langfuse | `Authorization: Basic <base64(PUBLIC_KEY:SECRET_KEY)>` |
| Twilio | Basic auth via SDK (`Client(account_sid, auth_token)`) |
| GitHub MCP | `Authorization: Bearer <github_app_installation_token | PAT>` |
| Qdrant | API key via SDK config |
| Prefect | API key from `PREFECT_API_KEY` env (via SDK) |
| Postgres | Django `DATABASES` settings (URL-encoded user:pass in checkpointer) |
| LangSmith | API key via `LANGSMITH_API_KEY` env (via langchain) |

## Secret variable names (no values)

`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_ENDPOINT`, `LANGSMITH_PROJECT`, `LANGSMITH_TRACING`, `GCP_LOGS_PROJECT_ID`, `EVALS_GCP_SA_KEY`, `GOOGLE_CLOUD_PROJECT`, `GITHUB_TOKEN`, `GH_SECRET_KEY`, `CODEBASE_REPO_URL`, `CODEBASE_INDEX_DIR`, `QDRANT_URL`, `QDRANT_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `CELERY_BROKER_URL`, `PREFECT_API_URL`, `PREFECT_API_KEY`, `SLACK_WEBHOOK_SECRET`.
