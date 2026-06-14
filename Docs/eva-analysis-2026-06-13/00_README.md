# Eva — Complete Replication Documentation

**Generated:** 2026-06-13
**Subject:** Eva, the eval / investigation agent in `neurality_admin_backend`
**Scope:** Read-only forensic analysis. No production code was modified.

---

## What Eva Is, in One Paragraph

Eva is a multi-agent **investigation** platform that acts as the first line of defense against product issues at Neurality. It exposes a chatbot (default mode), a Deep-Search BI agent (analytics with reasoning), a Deep-Search SRE agent (root-cause for voice calls), and a multi-agent supervisor that coordinates the two. It is invoked four ways: REST API (DRF), Slack `@app_mention`, Prefect-triggered automation flows (customer feedback / technical-issue detection), and a manually launched query flow. The agents run **LangGraph** workflows over an **AgentState** persisted by an async **Postgres checkpointer**, talk to Anthropic Claude for reasoning, OpenAI `text-embedding-3-large` for embeddings, **pgvector** for a curated knowledge base, **Mem0 + Qdrant** for cross-session memory (disabled in current code), and six evidence sources: Postgres (read-replica), GCP Cloud Logging, Langfuse traces, Twilio Voice debug, GitHub MCP for live code, and a Qdrant-indexed codebase RAG (disabled, replaced by ripgrep + GitHub MCP).

## Document Map

| File | Step | What's in it |
|---|---|---|
| `01_file_structure.md` | Step 1, 2 | Full file tree of every Eva file across both backends + role of each |
| `02_tech_stack.md` | Step 3 | Every Python package Eva uses, with version, ecosystem, and per-file role |
| `03_external_services.md` | Step 4 | Anthropic, OpenAI, GCP, Langfuse, Twilio, GitHub, Qdrant, Prefect, Postgres — endpoint by endpoint |
| `04_llms_and_prompts.md` | Step 5 | Every LLM call site, model, params, prompt, schema enforcement, response parsing |
| `05_github_external_refs.md` | Step 6 | External GitHub repos, GitHub MCP, GitHub App auth, embedded patterns |
| `06_functions_and_classes.md` | Step 7 | The function & class inventory, grouped by category |
| `07_architecture.md` | Step 8 | Triggering, input flow, pipeline stages, scoring, retries, parallelism, outputs, configuration |
| `08_data_schemas.md` | Step 9 | Pydantic models, Django models, vector schema, request/response shapes |
| `09_replication_checklist.md` | Step 10 | Numbered checklist to rebuild Eva in a fresh environment |

## Tooling Caveats

- **`agent.py`** referenced in some legacy docs is **not part of the current code path**. The active entry points are `agents/bi_agent.py`, `agents/sre_agent.py`, `multi_agent.py`, and `chatbot/entrypoint.py`. The `docs/eval.md` and `docs/sre+bi_agent.md` files are **planning docs**, not specs of current behavior.
- **`Eva` and `Eval Agent`** are used interchangeably in the codebase. The package path is `admin_app.services.eval_agent`. The user-facing brand is *Eva*.
- **Mem0 is currently disabled.** All `get_bi_memory()` / `get_sre_memory()` / `save_to_memory()` call sites are commented out. The wiring is intact for re-enabling.
- **Qdrant semantic codebase search is currently disabled.** `search_codebase` returns a static disabled message; SRE uses **GitHub MCP + ripgrep** instead.
- **PDF export is currently disabled.** `EvalAgentExportReportView` returns HTTP 503; the GCS-PDF pipeline is fully commented out.
- The codebase contains **~1,300 lines of commented-out vestigial SRE pipeline** (old `transcript_read → trace_read → code_context → hypothesize → plan → parallel_fetch → correlate → plan_update` topology). The current SRE graph collapses these into two tier ReAct nodes.
- Model id strings like `claude-haiku-4-5-20251001`, `claude-sonnet-4-6`, `claude-opus-4-5-20251101`, `gpt-5.4` appear in the config verbatim. These are the exact strings the code passes to the SDKs and are captured as-is in this documentation.

## How to Use This Documentation

Read top-to-bottom for an end-to-end understanding. Section `09_replication_checklist.md` is the actionable build sheet. Function-level detail lives in `06_functions_and_classes.md`. When the documentation says "see `path:line`," those references are accurate as of the snapshot date.
