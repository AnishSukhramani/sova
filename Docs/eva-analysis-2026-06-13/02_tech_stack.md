# 02 — Complete Tech Stack

All Python, all from `neurality_admin_backend/pyproject.toml`. Pinned versions are what the lockfile resolves to. Eva's package paths are noted next to each entry. Entries not used by Eva (but listed in the same manifest) are excluded.

## Language and runtime

| Item | Version | Role |
|---|---|---|
| Python | `^3.12` | Runtime |
| Poetry | (build backend) | Dependency management |

## Web / API framework (used by Eva's HTTP surface)

| Package | Version | Role in Eva | Where used |
|---|---|---|---|
| `django` | `5.1.1` | ORM, settings, request routing, cache backend, async-sync bridges | `admin_app/api/eval_agent/views.py`, all `Model.objects.using(...)` calls, `django.utils.timezone`, `connections`, `cache.add/get/delete` |
| `djangorestframework` | `3.15.2` | API views, serializers, renderers | `views.py` — all view classes extend `BaseAPI`; `serializers.Serializer` for input validation |
| `django-cors-headers` | `4.4.0` | CORS for /api/* | Project-wide |
| `drf-yasg` | `1.21.8` | OpenAPI doc generation | Project-wide; Eva inherits |
| `django-redis` | `^5.4` | Cache backend | `cache.add(lock_key, ...)` in `runners/eva.py`, classifier/file-summary caches in `codebase_context_tool.py` |
| `pgvector` | `0.3.3` | pgvector field + `CosineDistance` | `admin_app/models/admin_evals.py::KnowledgeEmbedding.embedding`, `knowledge/store.py::DatabaseKnowledgeStore.search` |
| `psycopg2` | `^2.9.10` | Postgres driver (sync) | `tools/db_client.py` (via Django `connections`), `checkpointer.py` (`psycopg_pool.ConnectionPool`) |
| `redis` | `^5.0.1` | Redis client | `deep_agent_stream.py` (Redis pub/sub for stream events); also used through `django-redis` |

## LangChain / LangGraph stack (the core agent runtime)

| Package | Version | Role |
|---|---|---|
| `langchain` | `^1.0.0` | Umbrella package |
| `langchain-core` | `^1.0.0` | `BaseMessage`, `HumanMessage`, `SystemMessage`, `ToolMessage`, `AIMessage`, `tool` decorator, `BaseTool`, `RunnableConfig` |
| `langchain-anthropic` | `^1.0.0` | `ChatAnthropic` — all Anthropic LLM calls in Eva |
| `langchain-openai` | `^1.0.0` | `OpenAIEmbeddings(model="text-embedding-3-large")` — only embedder Eva uses |
| `langchain-community` | `^0.4` | Various tool helpers |
| `langchain-text-splitters` | `^1.0.0` | (Likely not used by Eva directly) |
| `langchain-experimental` | `^0.4` | (Likely not used by Eva directly) |
| `langchain-mcp-adapters` | `^0.2` | `MultiServerMCPClient` — wraps GitHub MCP over HTTP transport |
| `langgraph` | `^1.0.0` | `StateGraph`, `END`, `START`, `MessagesState`, conditional edges |
| `langgraph-checkpoint-postgres` | `^3.0.4` | `PostgresSaver`, `AsyncPostgresSaver.from_conn_string` — graph state persistence |
| `langsmith` | `^0.8.0` | LangSmith tracing (via env vars + `EvalAgentConfig.is_langsmith_enabled()`) |
| `agentevals` | `^0.0.9` | (Likely consumed by deep-engineer task, not by Eva directly) |
| `deepagents` | `0.6.8` (extras: quickjs) | Underpins the *deep-engineer* execution branch (a separate task referenced by `runners/eva.py`); Eva itself doesn't import this directly. |
| `daytona` / `langchain-daytona` | `^0.184.0` / `0.0.7` | Sandboxed code execution (deep-engineer interpreter); referenced but not by `eval_agent` package directly |
| `mcp` | `^1.0.0` | Underlies `langchain-mcp-adapters` |

## LLM provider SDKs (used directly by Eva)

| Package | Version | Role |
|---|---|---|
| `pydantic` | `^2.10.1` | All state schemas (`AgentState`, `SREAgentState`, `MultiAgentState`, `Hypothesis`, etc.) and `with_structured_output(schema)` validation |
| `instructor` | `1.4.3` | Used in deep-engineer paths (structured outputs); Eva uses LangChain's `with_structured_output` instead |
| `llama-index-core` | `0.12.9` | Not used by `eval_agent` |
| `llama-index-llms-openai` | `0.3.12` | Not used by `eval_agent` |

## Observability

| Package | Version | Role |
|---|---|---|
| `loguru` | `0.7.2` | Project logger (Eva uses stdlib `logging` directly, not Loguru — note: this is divergent from CLAUDE.md §10 which is for the main `nhapp/` package, but Eva is in `admin_app` and uses standard `logging.getLogger(__name__)`) |
| `sentry-sdk[django]` | `^2.27.0` | Exception capture in production |
| `google-cloud-logging` | `3.12.0` | `gcp_tools.py` — Cloud Logging client for SRE call-debug log fetches |

## Vector + Knowledge

| Package | Version | Role |
|---|---|---|
| `faiss-cpu` | `^1.9.0` | `LocalKnowledgeStore` (FAISS IndexFlatIP, alternative to pgvector — not the default path) |
| `qdrant-client` | `>=1.12.0,<1.17.0` | Used by `MemoryManager` (Mem0 backend) and the legacy codebase indexer (currently disabled) |
| `mem0ai` | `^1.0.5` | `mem0.Memory` — cross-session memory store (currently disabled in Eva) |

## SQL parsing and safety

| Package | Version | Role |
|---|---|---|
| `sqlparse` | `^0.5.0` | `utils.py::outer_statement_has_limit`, `query_exempt_from_row_limit`; `validation_tool.py::_check_query_syntax`, `_check_statement_type` |
| `tenacity` | `^8.0` | `tools/db_client.py::PostgresClient.execute_query` and `search_tables` — `stop_after_attempt(2)`, `wait_fixed(1)` |

## Voice and PMS adapters used by Eva tools

| Package | Version | Role |
|---|---|---|
| `twilio` | `9.3.2` | `tools/twilio_tools.py::TwilioVoiceDebugTool` — Call/Conference debug fetcher |
| `retell-sdk` | `5.20.0` | Eva does not import retell-sdk directly; it reads `RetellAICall` Django rows for `caller_phone_number` and `retell_call_id` |

## Workflow orchestration

| Package | Version | Role |
|---|---|---|
| `prefect` | `3.7.1` (Python `>=3.12,<3.15`) | `prefect_app/eva_investigations/flows.py`, `deployments.py`; `prefect.client.orchestration.get_client(sync_client=True)`, `prefect.deployments.run_deployment`, `prefect.runtime.flow_run`, `prefect.client.schemas.objects.StateType` |
| `celery` | `5.4.0` | Eva uses `task.apply(kwargs=...).get()` in Prefect runners (in-process eager); referenced for the deep-engineer task |
| `django-celery-beat` | `2.8.0` | Project-wide; Eva doesn't add beat schedules |

## GCP

| Package | Version | Role |
|---|---|---|
| `google-cloud-logging` | `3.12.0` | Eva calls `cloud_logging.Client(...)`, `client.list_entries(...)` |
| `google-auth` | `2.47.0` | `google.auth.default(scopes=...)` ADC, `google.oauth2.service_account.Credentials.from_service_account_info` |
| `google-cloud-storage` | `2.18.2` | Used for signed-URL generation in report export (currently disabled) |
| `google-api-core` | `2.21.0` | Underlies cloud client libs |
| `google-cloud-core` | `2.4.1` | Underlies cloud client libs |
| `google-cloud-pubsub` | `^2.31.1` | Not used by Eva directly |
| `google-crc32c` / `google-resumable-media` / `googleapis-common-protos` | (pinned) | Transitive |
| `google-cloud-tasks` | `^2.19.2` | Used in main backend, not by Eva |
| `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib` | (pinned) | Other GCP integrations (Gmail, OAuth flows) — not Eva |

## Storage and PDF (legacy)

| Package | Version | Role |
|---|---|---|
| `boto3` | `^1.35.0` | Project-wide (S3); Eva does not call directly |
| `xhtml2pdf` | `^0.2.11` | `report_document.py::compile_findings_report_to_pdf` (currently unused — `EvalAgentExportReportView` returns 503) |
| `weasyprint` | `^63.1` | Alternative PDF engine (not used by Eva) |
| `reportlab` | `^4.0` | PDF building (not used by Eva) |
| `matplotlib` | `^3.7` | Charts (not used by Eva) |
| `pypdf` | `^4.0` | PDF reading (not used by Eva) |
| `jinja2` | `^3.1.2` | Templating (project-wide) |

## Data and parsing

| Package | Version | Role |
|---|---|---|
| `pandas` | `2.2.3` | Project-wide |
| `openpyxl` | `^3.1.2` | Project-wide |
| `pyarrow` | `^21.0.0` | Project-wide |
| `dask` | `^2025.9.1` | Project-wide |
| `beautifulsoup4` | `4.12.3` | Project-wide |
| `tabula-py` | `2.9.3` | PDF table extraction |
| `tabulate` | `^0.9.0` | Used for rendering tables; pulled into prompts only |
| `unstructured-client` | `>=0.26.1,<1.0.0` | Document parsing |
| `diff-match-patch` | `20241021` | Generic diff |
| `jsonschema` | `4.23.0` | Schema validation |
| `phonenumbers` | `8.13.46` | E.164 normalization; used by `gcp_tools.py::_normalize_caller_phone` indirectly via `RetellAICall.caller_phone_number.as_e164` |
| `django-phonenumber-field` | `8.0.0` | `caller_phone_number` field on `RetellAICall` |
| `django-timezone-field` | `7.0` | Timezone-aware models |
| `tzdata` | `>=2025.2` | Timezone data |
| `gsm0338`, `unidecode` | `^1.0.0`, `^1.4.0` | SMS encoding/transliteration (project-wide) |

## Auth and HTTP

| Package | Version | Role |
|---|---|---|
| `PyJWT[crypto]` | `^2.8.0` | Token signing (project-wide; used by GitHub App auth via `github_app_auth.py`) |
| `requests` | `^2.32.0` | HTTP client; Eva uses `urllib.request` directly for Langfuse and prefers SDKs elsewhere |
| `aiohttp` | `^3.12.0` | Async HTTP (project-wide) |

## ML adjacencies (not used by Eva directly)

| Package | Version | Role |
|---|---|---|
| `scikit-learn` | `1.5.2` | Not used by Eva |
| `psutil` | `5.9.8` | Process metrics (not Eva) |
| `py-cpuinfo` | `^9.0.0` | CPU info (not Eva) |

## Browser automation

| Package | Version | Role |
|---|---|---|
| `playwright` | `^1.51.0` | E2E testing (not used at runtime by Eva) |
| `hyperbrowser` | `^0.41.0` | PMS RPA (used by main backend; not Eva) |

## Channels (real-time)

| Package | Version | Role |
|---|---|---|
| `channels` | `3.0.4` | Project-wide WebSocket support (not used by Eva's SSE) |
| `channels-redis` | `3.4.1` | Channels Redis backend |

## Notes on Eva-specific imports not in pyproject.toml

These appear as `import` statements in Eva but are stdlib:
`asyncio`, `concurrent.futures`, `contextvars`, `dataclasses`, `urllib.parse`, `urllib.request`, `urllib.error`, `json`, `logging`, `re`, `uuid`, `time`, `os`, `base64`, `datetime`, `enum`, `subprocess`, `typing`, `threading`, `pickle`.

## Imports That Eva Pulls Through Internal Modules

| Internal pkg | Used by | Role |
|---|---|---|
| `asgiref.sync.sync_to_async` | `chatbot/entrypoint.py`, `sre_agent.py`, `views.py` | Bridge Django ORM (sync) into async LangGraph nodes |
| `prefect.runtime.flow_run` | `flows.py` | Read current flow_run_id mid-flow |
| `prefect.client.orchestration` | `deployments.py`, `views.py` | Submit deployment, read state, cancel |
| `prefect.client.schemas.objects` | `views.py` | `StateType.CANCELLED` etc. |
