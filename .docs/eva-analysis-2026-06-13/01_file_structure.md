# 01 — Eva File Structure

Eva lives **entirely** in `neurality_admin_backend`. Nothing in `neurality_backend` belongs to Eva. The package root is `admin_app/services/eval_agent/`. The HTTP surface is `admin_app/api/eval_agent/`. The async/scheduled surface is `prefect_app/eva_investigations/`. Django models live in `admin_app/models/admin_evals.py`.

All paths below are relative to `/Users/anishsukhramani/Documents/GitHub/Neurality/`.

## Tree

```
neurality_admin_backend/
├── admin_app/
│   ├── api/eval_agent/
│   │   ├── __init__.py                            # public re-exports of view classes
│   │   └── views.py                               # DRF API surface (~21 view classes)
│   │
│   ├── models/
│   │   └── admin_evals.py                         # EvalAgentConversation, EvalAgentReports, KnowledgeEmbedding
│   │
│   └── services/eval_agent/
│       │
│       ├── __init__.py                            # 1-line package marker
│       ├── config.py                              # EvalAgentConfig (models, limits, SQL safety, LangSmith)
│       ├── models.py                              # Pydantic state schemas (AgentState, SREAgentState, MultiAgentState, ...)
│       ├── checkpointer.py                        # AsyncPostgresSaver wiring (per-event-loop)
│       ├── mode_router.py                         # LLM mode classifier (chatbot | deep_search_{bi,sre,multi})
│       ├── multi_agent.py                         # Supervisor coordinator (BI + SRE blackboard)
│       ├── deep_agent_stream.py                   # Redis pub/sub stream events for live runs
│       ├── prompts.py                             # All system prompts (2,398 lines)
│       ├── utils.py                               # SQL safety, table allowlist, partial-report synthesis
│       ├── report_document.py                     # Markdown → PDF compiler (currently unused)
│       │
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── bi_agent.py                        # BIAgent class (1,505 lines) — LangGraph BI workflow
│       │   └── sre_agent.py                       # SREAgent class (3,279 lines, ~1,300 are vestigial comments)
│       │
│       ├── chatbot/
│       │   ├── __init__.py                        # 1-line marker
│       │   ├── entrypoint.py                      # Custom ReAct chatbot graph (agent ↔ tools)
│       │   ├── prompts.py                         # CHATBOT_SYSTEM_PROMPT, BI_SKILL_PROMPT, TECHNICAL_SKILL_PROMPT, ...
│       │   └── utils.py                           # Message serialization, timestamps, skill registry
│       │
│       ├── skills/                                # LLM-driven sub-routines used by BI agent
│       │   ├── __init__.py                        # Re-exports DiscoverSkill, CrossValidateSkill, ContextualizeSkill, RememberSkill
│       │   ├── skill_utils.py                     # run_llm_with_tools, make_db_and_knowledge_tools, prompt formatting
│       │   ├── discover.py                        # DiscoverSkill — Sample-Pattern-Quantify
│       │   ├── cross_validate.py                  # CrossValidateSkill — two-source validation
│       │   ├── contextualize.py                   # ContextualizeSkill — baseline comparison
│       │   └── remember.py                        # RememberSkill — knowledge-base writer
│       │
│       ├── tools/                                 # External-system tool wrappers (LangChain @tool)
│       │   ├── __init__.py                        # Re-exports the canonical tool surface
│       │   ├── db_client.py                       # PostgresClient + safety pipeline
│       │   ├── db_tools.py                        # @tool list_tables / describe_table / run_query
│       │   ├── validation_tool.py                 # SQLValidationTool — safety/lint/injection scorer
│       │   ├── vector_knowledge_tool.py           # VectorKnowledgeTool — YAML + pgvector accessor
│       │   ├── codebase_context_tool.py           # grep_codebase, list_codebase_*, get_file_summary
│       │   ├── gcp_tools.py                       # GCP Cloud Logging — call-debug fetchers
│       │   ├── github_mcp_client.py               # GitHub MCP (HTTP) — search_code, get_file_contents
│       │   ├── langfuse_tools.py                  # Langfuse REST — get_langfuse_session_call_logs
│       │   ├── sre_tools.py                       # Langfuse compact format — get_langfuse_call_traces (180k tok budget)
│       │   └── twilio_tools.py                    # Twilio Voice debug (call SID / conference SID)
│       │
│       ├── knowledge/
│       │   ├── __init__.py
│       │   ├── store.py                           # KnowledgeStore ABC + DatabaseKnowledgeStore (pgvector) + LocalKnowledgeStore (FAISS)
│       │   ├── embedding.py                       # OpenAI text-embedding-3-large singleton (3072 dims)
│       │   ├── build_index.py                     # CLI: rebuild knowledge index from markdown files
│       │   ├── load_from_files.py                 # Markdown → KnowledgeItem chunkers
│       │   ├── investigation_skills.py            # Per-feature SRE playbook loader (knowledge/skills/*.md)
│       │   ├── call_debug_context.py              # voice_call_debug.md prefetch helpers + call_flows parser
│       │   │
│       │   ├── files/                             # Knowledge source markdown (legacy)
│       │   │   ├── FAQ.md
│       │   │   ├── BASELINES.md
│       │   │   ├── KNOWN_ISSUES.md
│       │   │   ├── INVESTIGATION_PATTERNS.md
│       │   │   └── SCHEMA_REFERENCE.md
│       │   │
│       │   ├── files_yaml/                        # Authoritative YAML knowledge (current)
│       │   │   ├── FAQ.yaml
│       │   │   ├── BASELINES.yaml
│       │   │   ├── KNOWN_ISSUES.yaml
│       │   │   ├── INVESTIGATION_PATTERNS.yaml
│       │   │   └── SCHEMA_REFERENCE.yaml
│       │   │
│       │   └── skills/                            # SRE investigation playbooks (loaded as markdown)
│       │       ├── general_skill.md
│       │       ├── voice_call_debug.md
│       │       ├── sms_chat_debug.md
│       │       └── web_scheduler.md
│       │
│       ├── memory/                                # Mem0 + Qdrant — currently DISABLED (call sites commented out)
│       │   ├── __init__.py                        # Re-exports MemoryManager, get_bi_memory, get_sre_memory, format_memory_context
│       │   └── manager.py                         # MemoryManager class (Mem0 backend, Qdrant vector store)
│       │
│       └── docs/                                  # Planning docs (NOT current spec; reflect design intent, partly out-of-sync)
│           ├── eval.md
│           ├── sre+bi_agent.md
│           ├── chatbot.md
│           └── memory.md
│
└── prefect_app/eva_investigations/
    ├── __init__.py
    ├── deployments.py                             # Deployment name constants + submit_eva_*_deployment()
    ├── flows.py                                   # @flow process_eva_{investigation_mention,customer_feedback,technical_issue,query,brain_curator}
    └── runners/
        ├── __init__.py
        └── eva.py                                 # End-to-end runners called by each flow (685 lines)
```

## Other Files Eva Reads or Depends On (Not Owned by Eva)

These files are external to the `eval_agent` package but referenced by Eva. Listed for completeness.

| Path | Role |
|---|---|
| `admin_backend/config.py` | Source of all secret/env settings: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `LANGFUSE_*`, `LANGSMITH_*`, `GCP_LOGS_PROJECT_ID`, `EVALS_GCP_SA_KEY`, `GITHUB_TOKEN`, `CODEBASE_REPO_URL`, `CODEBASE_INDEX_DIR`, `QDRANT_URL`, `QDRANT_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `CELERY_BROKER_URL`, `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` |
| `admin_backend/db_context.py` | `get_data_environment()` → "prod" / "staging" / "testing" |
| `admin_backend/gcp_sa.py` | `parse_gcp_service_account_dict()` — parses `EVALS_GCP_SA_KEY` JSON |
| `admin_app/models/retellai.py` | `RetellAICall`, `RetellAICallMetadata` |
| `admin_app/models/messaging.py` | `ChatSession`, `FeedbackConversation`, `InteractionFeedback` |
| `admin_app/models/billing.py` | `CallUsageRecord` |
| `admin_app/models/call_insights.py` | `CallInsight` |
| `admin_app/services/codebase_indexer/indexer.py` | `Indexer`, `IndexerConfig` — Qdrant indexer (used by codebase_context_tool, currently disabled) |
| `admin_app/services/codebase_indexer/github_app_auth.py` | `is_github_app_configured`, `get_installation_token` — GitHub App OAuth for MCP |
| `admin_app/services/slack_service.py` | `slack_post_message`, `slack_update_message`, `strip_bot_mention`, `postprocess_text_for_slack` |
| `admin_app/lib/redis_pubsub.py` | `get_redis_client()` — used by `deep_agent_stream` |
| `celery_app/tasks/deep_agent_tasks.py` | `run_deep_engineer_agent` — Celery task body invoked by Prefect runners (eager) |
| `celery_app/tasks/eval_agent_tasks.py` | `run_eval_agent_investigation` — legacy SRE fallback Celery task |
| `celery_app/tasks/slack_tasks.py` | `process_new_slack_thread`, `process_existing_slack_thread`, `_find_existing_conversation`, `_patch_assistant_message_slack_delivery_metadata`, `_sync_eval_conversation_mode_for_slack_dispatch` |
| `celery_app/tasks/feedback_eva_tasks.py` | Customer-feedback wiring (`_build_feedback_eva_query`, `_load_feedback_eva_thread`, locks) |
| `celery_app/tasks/call_insight_eva_tasks.py` | Technical-issue wiring (`_build_call_insight_eva_query`, locks) |
| `celery_app/tasks/codebase_indexer_tasks.py` | Defines `"sre_codebase"` Qdrant collection name — must match codebase_context_tool |

## Files Categorized by Role

### Entry points
- `admin_app/api/eval_agent/views.py` — REST + SSE
- `prefect_app/eva_investigations/flows.py` — Prefect deployments
- `admin_app/services/eval_agent/chatbot/entrypoint.py` — Chatbot turn invoker

### Core control plane
- `mode_router.py` — selects mode
- `multi_agent.py` — coordinator (supervisor/worker/blackboard)
- `checkpointer.py` — Postgres checkpointer factory
- `config.py` — limits, models, SQL safety patterns

### LangGraph workers
- `agents/bi_agent.py` — BI workflow
- `agents/sre_agent.py` — SRE workflow (single-loop ReAct or LangGraph tier path)
- `chatbot/entrypoint.py` — Chatbot ReAct graph

### Skills (used by BI agent)
- `skills/discover.py`, `cross_validate.py`, `contextualize.py`, `remember.py`
- `skills/skill_utils.py` — shared LLM-with-tools runtime

### Tool wrappers (one file per external system)
- `tools/db_tools.py` + `db_client.py` + `validation_tool.py` → Postgres
- `tools/gcp_tools.py` → Google Cloud Logging
- `tools/langfuse_tools.py` + `sre_tools.py` → Langfuse
- `tools/twilio_tools.py` → Twilio Voice
- `tools/github_mcp_client.py` → GitHub MCP (HTTP)
- `tools/codebase_context_tool.py` → Qdrant + ripgrep (Qdrant disabled)
- `tools/vector_knowledge_tool.py` → Knowledge base accessor

### Knowledge layer
- `knowledge/store.py`, `embedding.py`, `build_index.py`, `load_from_files.py`
- `knowledge/investigation_skills.py`, `call_debug_context.py`
- `knowledge/files/*.md`, `files_yaml/*.yaml`, `skills/*.md`

### Memory layer (currently disabled)
- `memory/manager.py`

### Streaming and persistence
- `deep_agent_stream.py` — Redis-backed SSE events
- `report_document.py` — markdown → PDF (disabled)

### Prompts (one file)
- `prompts.py` — every system prompt for routing, planning, skills, SRE pipeline, reports
- `chatbot/prompts.py` — chatbot-specific prompts

### Django models
- `admin_app/models/admin_evals.py` — `EvalAgentConversation`, `EvalAgentReports`, `KnowledgeEmbedding`

### Prefect surface
- `prefect_app/eva_investigations/deployments.py` — submit helpers
- `prefect_app/eva_investigations/flows.py` — `@flow` definitions
- `prefect_app/eva_investigations/runners/eva.py` — end-to-end pipeline bodies
