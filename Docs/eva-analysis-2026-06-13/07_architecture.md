# 07 — End-to-End Architecture

How Eva runs, from trigger to output. Every stage, every hand-off, every limit.

---

## 1. Triggering — how a Eva run is started

Eva has **four** ways to be invoked. Each path eventually produces an `EvalAgentConversation` row (or attaches to an existing one) and dispatches to one of the agents.

### 1.1 REST API (DRF) — synchronous and async paths

**Surface:** `admin_app/api/eval_agent/views.py`. All under base path `api/v1/eval-agent/`. Auth: `self.get_user()` (DRF Token auth, header `Authorization: Token <token>` per project convention).

**Entry points relevant to invocation:**

| URL | Method | What it does |
|---|---|---|
| `POST .../threads/` | Creates a new `EvalAgentConversation` thread (mode=chatbot). Returns `conversation_id`, `thread_id`. Equivalent staging view writes to `default_staging` DB alias. |
| `POST .../query/` | The primary entry. Accepts `query` (or `cancel=true` + `job_id`). When auto_route=True (default), runs the LLM mode router to pick chatbot vs deep_search_{bi,sre,multi}. When `auto_route=False`, uses explicit `deep_search`/`BI`/`SRE` flags. Submits via Prefect deployment (`submit_eva_query_deployment`). Returns HTTP 202 with `job_id = Prefect flow_run_id`. |
| `POST .../deep-engineer/threads/<thread_id>/runs/` | Alternative: enqueues a Celery `run_deep_engineer_agent` task directly (without Prefect). Returns `run_id`, `stream_url`, `cancel_url`. |
| `GET .../query/<job_id>/` | Polls status. Checks Prefect cache first; else Celery `AsyncResult`. Returns `pending|running|completed|failed|cancelled` plus `result` payload. |
| `GET .../deep-engineer/threads/<thread_id>/runs/<run_id>/stream/` | SSE stream of run events (10s keepalive heartbeats, `Last-Event-ID` resume). Terminates when meta.terminal=True. |
| `POST .../deep-engineer/threads/<thread_id>/runs/<run_id>/cancel/` | Cancellation. Prefect: `set_flow_run_state(Cancelled(message=...))`. Celery: `celery_app.control.revoke(run_id, terminate=False)`. |

**`EvalAgentQueryView.InputSerializer` fields:**
- `env: ChoiceField(["prod", "staging"], default="prod")`
- `cancel: BooleanField, default=False`
- `job_id: CharField` (required when cancel=true)
- `query: CharField` (required when not cancelling)
- `context: CharField` (optional supplemental text)
- `location_id: IntegerField` (optional)
- `time_window: CharField, default="30 days"`
- `model: CharField` (e.g. `claude-haiku-4-5-20251001`)
- `deep_search: BooleanField, default=False`
- `auto_route: BooleanField, default=True` — when True, mode router decides
- `thread_id: CharField` (optional; create-on-missing)
- `BI: BooleanField, default=False`, `SRE: BooleanField, default=False` (both True = 400 error)

**File uploads (multipart):** `request.FILES.getlist("files")` or single `request.FILES.get("file")`. Validated by `_validate_query_uploads`:
- Extensions: PNG, JPG, JPEG, GIF, WEBP, PDF, MP3.
- Sizes: image ≤10MB, PDF ≤25MB, audio ≤25MB.
- Filename ≤120 chars, sanitized to alnum/`-_.`.

Stored under `/user-uploads/{uuid_hex}_{safe_name}` via `write_thread_artifact_bytes` (deep-engineer artifact store).

### 1.2 Slack `@app_mention`

Routed through Prefect deployment `process-eva-investigation-mention`. Slack webhook handler (in `slack_service.py`, outside `eval_agent`) verifies `SLACK_WEBHOOK_SECRET`, posts a placeholder, then submits the Prefect deployment with `payload` (Slack event) and `request_meta` (placeholder_ts).

**Inside the Prefect flow:** `runners/eva.py::run_slack_app_mention(payload, request_meta, on_eval_thread_resolved)`:
- Resolves `slack_env` (prod | staging).
- `query = strip_bot_mention(raw_text, slack_env).strip()`.
- Finds or creates `EvalAgentConversation` keyed on Slack thread_ts + team_id + channel.
- Updates Slack placeholder to "Starting the Investigation..."
- Builds router thread context from prior thread messages + `build_mode_router_conversation_block`.
- Routes via `plan_eval_agent_dispatch(query, auto_route=False, deep_search=True, BI=False, SRE=True, thread_context_for_router=...)`. **Slack is always SRE-only deep_search.**
- Calls `_run_investigation_inline(...)`.
- Calls `_update_slack_with_result(...)` to post the final answer.

### 1.3 Prefect-triggered automation flows

| Flow | Trigger | Runner |
|---|---|---|
| `process-eva-customer-feedback` | Customer feedback creation (via `InteractionFeedback`) | `run_customer_feedback_investigation(feedback_id, feedback_message_id, env)` |
| `process-eva-technical-issue` | CallInsight transitions to `call_outcome_sub="Technical Issue"` | `run_technical_issue_investigation(call_insight_id, call_id, env)` |
| `process-eva-query` | Manual UI submission | `run_query_investigation(query, context, thread_id, location_id, model, env, uploaded_artifacts, flow_run_id)` |
| `process-eva-investigation-mention` | Slack mention (see 1.2) | `run_slack_app_mention` |
| `process-eva-brain-curator` | Brain curator handoff (deep-engineer feedback loop) | `run_brain_curator_handoff` (in `celery_app.tasks.deep_agent_tasks`) |

Each flow:
- Acquires a Django-cache mutex (`feedback_eva:lock:<id>` / `call_insight_eva:lock:<id>` with TTL).
- Loads or creates `EvalAgentConversation`.
- Updates conversation `mode="deep_search"`, increments `deep_searches`.
- Calls `_run_deep_engineer_inline(...)` → `run_deep_engineer_agent.apply(kwargs=...)` (Celery eager — runs in-process, returns dict).
- Closes Django connections in `finally`.

### 1.4 Direct chatbot (no Prefect, no Celery)

The chatbot path bypasses Prefect entirely. The DRF view directly calls `invoke_chatbot_with_progress` (from `chatbot/entrypoint.py`), which:
- Builds the chatbot LangGraph compiled with the **async Postgres checkpointer**.
- Runs the agent for one turn, keyed on `thread_id`.
- Reports progress events (currently via callback hooks; production streaming wires through `deep_agent_stream`).

---

## 2. Input data

### 2.1 What Eva receives

- **User query** (string) — the question.
- **Context** (optional string) — supplemental text from API, Slack thread, or feedback ticket.
- **thread_id / conversation_id** — for resume of multi-turn or multi-investigation conversations.
- **location_id / org_id / call_id** — passed explicitly, or resolved by `discover_skill._resolve_location_from_query_with_name` (BI) / `_intake_node` (SRE).
- **time_window** — default `"30 days"`. Used by skills in SQL `WHERE created_at > NOW() - INTERVAL ...`.
- **model** — overrides default (`claude-haiku-4-5-20251001`).
- **Uploaded files** — images/PDFs/audio. Persisted as artifacts; not directly read by Eva (consumed by Deep Engineer downstream).

### 2.2 What Eva reads from DB

- `EvalAgentConversation.messages` — prior conversation turns (chatbot + deep_search both stored).
- `nhapp_retellaicall` — for call_id, retell_call_id, caller_phone_number, location_id, organization_id.
- `nhapp_chatsession` — alternative session resolution.
- `nhapp_callusagerecord` — for `agent_call_start_time` / `agent_call_end_time` to build GCP log window.
- `nhapp_location` / `nhapp_organization` — for name → id resolution.
- `nhapp_callinsight` — primary BI data source (sentiment, outcome, l1_pass, etc.).
- `nhapp_*` — 72 tables in the allowlist (see `utils.py::ALLOWED_TABLES`).
- `KnowledgeEmbedding` — pgvector for semantic search of curated knowledge.

### 2.3 Format normalization

- Phone numbers: `_normalize_caller_phone` → E.164 (`+1xxxxxxxxxx`).
- Call ID resolution: 3-level fallback (`RetellAICall.id UUID` → `ChatSession.id UUID` → `RetellAICall.retell_call_id` string).
- Timestamps: ISO-8601 with `Z` suffix (`format_eval_message_timestamp_utc_z`).

---

## 3. The pipeline — every stage in order

Eva has **five** distinct execution paths. Each is a separate LangGraph or ReAct loop.

### 3.1 Mode routing (gateway)

**Where:** `mode_router.py::plan_eval_agent_dispatch`. Called by `EvalAgentQueryView` and Slack runner.

**Decision tree:**
1. If `auto_route=False`: use `deep_search` flag directly. `False` → chatbot. `True` → multi/bi/sre based on flags.
2. If `auto_route=True`: LLM call to Haiku with `QUERY_MODE_ROUTING_PROMPT` and prior thread context.

**Output:** `EvalAgentDispatchPlan(use_deep_search, BI, SRE, routed_mode, routing_reason, router_model)`.

**Modes:**
- `chatbot` — Quick answer (single conversational turn with tools).
- `deep_search_bi` — Full BI investigation.
- `deep_search_sre` — Full SRE investigation.
- `deep_search_multi` — Both, with coordinator handoffs.

### 3.2 Chatbot path

**Graph:** `chatbot/entrypoint.py::_build_chatbot_graph`. Two nodes (`agent`, `tools`), conditional edge from `agent` → `tools` if `tool_calls` else END.

**Per-turn flow:**
1. `set_chatbot_invocation_context()` — Init per-turn todo list ContextVar.
2. Build `system_prompt = _build_chatbot_resolved_system_prompt()` — substitutes datetime, table list (dynamic from YAML), accessible tables block, investigation patterns block.
3. Load prior messages from DB (`_load_chatbot_prior_messages_from_db`) if Postgres has no checkpoint for `thread_id`.
4. Append current `HumanMessage(user_message)` (optionally prefixed with `context_summary`).
5. `astream({"messages": messages_in}, config=invoke_config, stream_mode="values")` over the compiled graph (recursion_limit=25). Each chunk emits a progress event (`thinking`, `calling_tools`, `tool_result`, `writing_answer`).
6. ReAct loop: `agent_node` calls `llm.bind_tools(all_tools).invoke(SystemMessage + trimmed_messages)`. If `tool_calls`, `tools_node` dispatches in parallel (semaphore 8). Loops until no tool_calls.
7. Returns `(response_text, thread_id, updated_messages_for_db)`.

**Tools available to chatbot:**
- DB tools: `list_tables`, `describe_table`, `run_query`, `get_distinct_values`, `get_table_schema`, `get_table_list`, `check_faq`, `search_knowledge`, `get_baselines`, `get_investigation_patterns`, `get_file_content`.
- Technical: `get_langfuse_session_call_logs_tool`, `get_gcp_logs_tool`, `grep_codebase`, `get_call_debug_context`.
- GitHub MCP: `search_code`, `get_file_contents`, `list_directory`, `list_commits`.
- Meta: `write_todos`.

**Recursion handling:** `is_recursion_limit_error(e)` → `synthesize_chatbot_partial_reply(user_message, partial_messages, llm)`.

### 3.3 BI deep-search

**Graph:** `agents/bi_agent.py::_build_workflow`. State schema `AgentState`. Entry node `memory_load`.

```
memory_load
  ├─ FAQ hit → report (early exit)
  ├─ final_response → END
  └─ otherwise → knowledge_router
                   ├─ knowledge hit (≥0.75 cosine) → knowledge_answer → END
                   └─ otherwise → plan_generation
                                    → skill_executor
                                         ├─ discover → plan_update
                                         ├─ cross_validate → plan_update
                                         └─ contextualize → plan_update
                                                              ├─ next step pending → skill_executor (loop)
                                                              └─ all done → remember → report → END
```

**Stage descriptions:**

1. **`memory_load`** — Mem0 read disabled. Calls `_run_mandatory_checks(query)`:
   - `knowledge_tool.check_faq(query)` — semantic match against FAQs (≥0.5 threshold) → FAQ hit → short-circuit to `report`.
   - Refills 15-min-TTL `_KNOWLEDGE_CACHE` with `get_investigation_patterns`, `get_baselines`, `get_known_issues`.
   - LLM call (structured `_BIRoutingDecision`) → sets `pending_intent` ∈ {discover, contextualize, cross_validate, clarify}. Clarify is coerced to discover.

2. **`knowledge_router`** — `_knowledge_store.search(query, k=1)`. If `score ≥ 0.75` (class constant `KNOWLEDGE_HIT_THRESHOLD`), set `knowledge_hit=True`, `knowledge_item={..}`.

3. **`knowledge_answer`** — If knowledge hit, LLM call (no structured output) with inline "Answer using ONLY..." prompt. Returns `BIQueryResponse(finding, confidence=HIGH, methods="Answer from knowledge base (vector search)", supporting_data={source, type}, caveats=["Single source; consider investigation for deeper validation."])`. **Terminates run (→ END).**

4. **`plan_generation`** — LLM call (structured `BIInvestigationPlanOutput`) with `BI_PLAN_GENERATION_PROMPT`. Produces 1+ `InvestigationPlanStep` (skill ∈ {discover, contextualize, cross_validate}, goal, status="pending").

5. **`skill_executor`** — Reads `bi_plan_index`, marks current step `in_progress`, sets `current_intent` for routing.

6. **`discover` / `cross_validate` / `contextualize`** — Each calls the respective skill via `skill.execute(query, context=memory+context, location_id, organization_id, location_name, organization_name, skills_run, mandatory_knowledge)`. Skill does ReAct loop (3 rounds max) with DB+knowledge tools, returns structured node output. Appended to `findings`, `skills_run`. Resolved location/org IDs flow back to state.

7. **`plan_update`** — Marks current step "completed". Calls `_revise_plan_bi(plan, next_index, latest_finding, query)` — LLM call with `BI_PLAN_REVISION_PROMPT` that strictly preserves completed steps and revises remaining pending steps.

8. **`remember`** — Mem0 write disabled. Computes `conclusion_confidence` from findings.

9. **`report`** — `_build_structured_report(state)` — LLM call (`FINDINGS_REPORT_FORMAT` as system) with truncated findings (`MAX_FINDINGS_CHUNKS=5`, `MAX_FINDINGS_MD_CHARS=25000`). Returns markdown.

**State:** Pydantic `AgentState`. Persisted via async Postgres checkpointer keyed on `thread_id`. **No reducers** — every update replaces the full state object; LangGraph's checkpointer captures snapshots.

**Per-event-loop compilation:** `_investigate_impl` caches compiled graphs by `id(asyncio.get_running_loop())`. Required because `AsyncPostgresSaver` is loop-bound.

### 3.4 SRE deep-search — **single-loop ReAct (the live path)**

**Entry:** `agents/sre_agent.py::investigate(...)` → `run_agent(...)`.

**Pre-loop priming (sequentially, not via LangGraph):**
1. If `skip_trace_path=False`: `_intake_node` → `_call_trace_fetch_node` → `_context_load_node`, each merged via `_merge_state_updates`.
2. If `skip_trace_path=True`: `_direct_investigation_node` only.

**Then a ReAct loop (up to 30 rounds):**

1. System prompt = `SRE_SINGLE_LOOP_SYSTEM_PROMPT` + appended `voice_call_debug.md` if loaded; wrapped in `cache_control: {"type": "ephemeral"}`.
2. User message = `_build_sre_runtime_user_message(state)` — structured "what to investigate" block (user query, prior context, parsed investigation request, GCP/Langfuse correlation, prefetched trace, prefetched transcript, non-transcript logs, shared findings).
3. Tools = `_build_sre_loop_tools(state=...)` — combines cached `_sre_tools_cache` + per-state inline tools (`add_investigation_todo`, `list_investigation_todos`, `get_prefetched_trace_context`, `get_gcp_logs_from_state`, `get_prefetched_gcp_transcript`, `get_sre_investigation_skill`, `mark_checked`).
4. Messages trimmed via `_trim_sre_messages_for_llm(messages, 32)` — never start with orphan ToolMessage.
5. `llm.bind_tools(tools).ainvoke(llm_input, config=invoke_config)` — single LLM call per round.
6. If no `tool_calls`: return `AgentResponse(final_text=..., tool_rounds=N, checked_items=...)`. Exit.
7. Else: execute tools in parallel via `asyncio.gather(_execute_one_sre_tool_async(tc, tools_by_name) for tc in tool_calls)`, append `ToolMessage`s, next round.
8. If loop exhausts (30 rounds): `_run_sre_no_tool_synthesis(messages, ...)` — final no-tool call forcing inconclusive answer with Evidence checked / Remaining unknowns / Next missing evidence. Return `AgentResponse(inconclusive=True)`.

**No LangGraph checkpointer is used in `run_agent`.** State is mutated in-process via `_merge_state_updates`.

### 3.5 SRE deep-search — LangGraph tier path (alternate, reachable via `_investigate_impl`)

**Graph nodes:**
1. `route_entry` — no-op, conditional edge to intake or direct_investigation.
2. `intake` (or `direct_investigation`).
3. `call_trace_fetch` — parallel Langfuse + GCP fetch via `asyncio.gather`.
4. `context_load` — loads `voice_call_debug.md`.
5. `investigation_node` (Tier 1) — ReAct loop (max 25 rounds) with `SRE_TIER_INVESTIGATION_PROMPT` (mode=tier1). Structured output `TierInvestigationDecision`. Tools: codebase + GitHub MCP + DB + GCP (with `get_gcp_logs_from_state`) + Twilio + `get_sre_investigation_skill`.
6. **`_route_after_tier1`**: if `tier1_decision.resolved`, → `conclude`. Else → `deep_investigation_node`.
7. `deep_investigation_node` (Tier 2) — ReAct loop with `SRE_TIER_INVESTIGATION_PROMPT` (mode=tier2). Receives tier-1's structured decision + notes + unresolved_threads. Includes `trace_exception` tool; omits `get_gcp_logs_from_state` (uses live `get_gcp_logs_for_call_session`).
8. `conclude` — LLM call (no structured output) with `SRE_CONCLUDE_PROMPT` (prompt-cached). Picks `confirmed_root_cause` by precedence: tier1 → tier2 → plan_update → first CONFIRMED → "no confirmed root cause".

**Note:** The public `SREAgent.investigate()` calls `run_agent()` (3.4), not `_investigate_impl` (3.5). Path 3.5 is reachable only via direct caller using `_investigate_impl`.

### 3.6 Multi-agent (supervisor + worker + blackboard)

**Entry:** `multi_agent.py::MultiAgentCoordinator.investigate(...)`.

**Graph:** `supervisor → {bi_node | sre_node | merge_node}`, where `bi_node`/`sre_node` loop back to `supervisor`. Compiled per-event-loop.

**Supervisor decision (`_supervisor_node`):**
- Reads `state.handoff_count`, `state.last_agent_called`, `state.bi_findings`, `state.sre_findings`, `state.shared_findings`.
- If `bi_only=True` → run BI once → finish.
- If `sre_only=True` → run SRE once → finish.
- If `handoff_count >= MAX_HANDOFFS (3)` → finish.
- Else: LLM call (Haiku, temp 0, max_tokens 20) with `SUPERVISOR_PLANNING_PROMPT`. Returns one of `{bi, sre, sre_skip_trace, finish}`.

**Worker hand-off:** Each worker (`_bi_node` / `_sre_node`) builds context = `mem0_X_context (disabled) + previous blackboard findings + state.context`, calls the respective agent's `investigate(...)`, appends `[BI]\n<report>` or `[SRE]\n<report>` to `shared_findings`, sets `bi_findings`/`sre_findings`, increments `handoff_count`, returns to supervisor.

**Merge (`_merge_node`):**
- If `final_report` already set (e.g. BI returned clarify response), preserve it.
- Else if both reports present → `_merge_reports(query, bi, sre)` (LLM call with `MULTI_AGENT_REPORT_PROMPT`, cached).
- Else use whichever is non-empty.

---

## 4. Scoring

Eva does not produce a numeric score. It produces **markdown reports** with structured sections. **Confidence** is the closest thing to a score and is assigned by the LLM following rubric prompts:

### Confidence rubric (BI)

From `FINDINGS_REPORT_FORMAT`:
- **High** — `n > 500`, multiple independent sources agree, stable across time windows.
- **Moderate** — `n = 100-500`, single reliable source, minor uncertainties.
- **Low** — `n < 100`, inference-based, significant data gaps, exploratory only.

`_extract_confidence_from_findings(findings)` rolls up confidence labels into a single overall string.

### Confidence rubric (SRE)

From `SRE_CONCLUDE_PROMPT`:
- **HIGH** — Failure point confirmed by 2+ independent signals; cause singular and consistent.
- **MEDIUM** — Failure point confirmed; one alternative cannot be fully ruled out.
- **LOW** — Failure point observed but two or more causes equally plausible.

The SRE conclude prompt explicitly distinguishes **system logging limitations** (NOT a confidence-lowering factor; reported as a fix) from **genuine investigative uncertainty** (lowers confidence).

### Sample-size policy (BI)

From `config.py`:
- `HIGH_CONFIDENCE_THRESHOLD = 500`
- `MODERATE_CONFIDENCE_THRESHOLD = 100`

Below 100 = Low (directional only).

### Cross-validation discrepancy ratio (BI)

From `CROSS_VALIDATE_PROMPT` and `CrossValidateNodeOutput.metrics.discrepancy_ratio`. A 30x gap between methods is itself a finding (instrumentation gap).

---

## 5. Error handling and retries

### 5.1 LLM errors

- **`langgraph.errors.GraphRecursionError`** — Detected via `is_recursion_limit_error(exc)`. BI/SRE/Chatbot all recover by calling `synthesize_partial_report` or `synthesize_chatbot_partial_reply` with the partial state's findings/messages.
- **Tool execution timeout** — `asyncio.wait_for(timeout=TOOL_TIMEOUT=60s)` wraps each tool call. Timeout → tool returns `"Error: tool timed out"`-style ToolMessage; LLM observes and proceeds.
- **Anthropic API error** — `ChatAnthropic(..., max_retries=2)` for BI; no retries for SRE or coordinator. On final failure, individual nodes catch `Exception`, log, and continue with default values (e.g. supervisor defaults to `bi` if LLM returns garbage).
- **Mode router failure** — `plan_eval_agent_dispatch` catches `Exception`, defaults to chatbot with explanation in `routing_reason`.

### 5.2 Database errors

- **Tenacity retries** — `PostgresClient.execute_query` and `search_tables` retry 2 times with 1s wait. Retries any `Exception`.
- **Statement timeout** — `SET LOCAL statement_timeout = '30000'` (30s) per query. Exceeded → `QueryCanceledError` returned to caller.
- **Row cap** — `len(rows) > MAX_QUERY_RESULTS (10000)` raises before returning.
- **Validation failure** — `_validate_sql` and `_validate_tables` raise `ValueError` before execution. The `@tool run_query` catches and returns a soft error string instructing the agent to "try a simpler query."

### 5.3 External API errors

- **Langfuse** — All `_langfuse_get` failures (`HTTPError`, `URLError`, `JSONDecodeError`, `OSError`) → return `None`. Upstream wraps as `{"error": ...}` dict.
- **Twilio** — All errors wrapped in `TwilioToolResult(ok=False, error=str(exc))`. 404 on Call Events specifically returns empty list + explanatory note.
- **GitHub MCP** — Missing token or adapter import → `None` client; tools return empty strings. `raise_on_error=False` for tool wrappers.
- **GCP Cloud Logging** — Permission-denied errors detected by `_permission_denied_guidance`, returning IAM grant hint. Empty windows trigger optional fallback without SEARCH() terms.
- **Indexer (Qdrant codebase)** — Missing OPENAI_API_KEY/QDRANT_URL → indexer skipped; tools return `"⚠️ Codebase index is not available."`. Errors cached per env in `_indexer_last_error_by_env`.

### 5.4 Individual-example failures (the "example" here is a single tool/skill call)

- **Skill error** — Skill's `execute()` wraps in try/except inside `run_llm_with_tools`. Errors become tool messages; the LLM observes and continues.
- **Tool error** — Returned as `ToolMessage(content="Error: ...", tool_call_id=tid, name=tool_name)`. Never raises out of the loop.
- **Node-level exception** — Each LangGraph node's outer try/except returns a default state update (e.g. `_intake_node` fallback to `with_structured_output`).
- **Whole-investigation failure** — `InvestigationCancelled` short-circuits to a cancellation response. Other exceptions surface in the API as HTTP 500 (or in Slack as `"Sorry — the eval agent failed..."`).

### 5.5 Cancellation

- API: `POST .../query/` with `cancel=true&job_id=<id>` → Prefect `set_flow_run_state(Cancelled)` or Celery `revoke(terminate=False)`.
- Agents poll `cancellation_check` callback at every node entry; raise `InvestigationCancelled` on True.
- SSE: emits `run_cancellation_requested` event.

---

## 6. Parallelism

### 6.1 Tool calls (within one LLM round)

- **Chatbot:** `_tool_messages_from_last_ai_async` parallelizes via `asyncio.gather` with a `Semaphore(8)` cap.
- **SRE single-loop:** Same pattern — `asyncio.gather(_execute_one_sre_tool_async(tc, ...) for tc in tool_calls)`. No explicit semaphore cap.

### 6.2 Pipeline stages (across nodes)

- **SRE `_call_trace_fetch_node`:** Langfuse + GCP fetches run in parallel via `asyncio.gather(asyncio.to_thread(_sync_langfuse), asyncio.to_thread(_sync_gcp))`.
- **Multi-agent BI/SRE:** Run **sequentially** (supervisor decides one at a time); blackboard `shared_findings` is the hand-off mechanism. Not parallel.

### 6.3 Eva instances (across requests)

- Each Prefect flow run = one Cloud Run Job = one process.
- Concurrent flow runs are independent processes; LangGraph checkpointer keyed on `thread_id` ensures each conversation has isolated state.
- The async checkpointer is cached **per event loop** (Celery + eager `.apply()` reuses the loop; Prefect flow runs each get their own loop).

### 6.4 Rate limiting

- **API:** `EvalAgentConfig.API_RATE_LIMIT = 10` queries per minute per user (advisory; enforcement happens upstream of the view).
- **Anthropic / OpenAI / Langfuse / etc.:** No explicit rate limiting in Eva — relies on SDK / API quotas.
- **Langfuse age check:** `LANGFUSE_CALL_MIN_AGE_MINUTES = 30` blocks calls fetched too soon (tracing incomplete).
- **GitHub MCP:** Singleton client + asyncio.Lock at init.

---

## 7. Output and storage

### 7.1 Where results go

- **`EvalAgentReports.state` JSONField** — Holds `report_markdown`, `user_visible_final_response`, `artifact_files`, `error`, `details`, `document_error`, `cancelled`, `report_format`. One row per deep-search run.
- **`EvalAgentConversation.messages` JSONField** — All conversation messages (chatbot + deep_search), tagged with `source`, `is_final`, `timestamp`.
- **`EvalAgentConversation.findings_compressed` JSONField** — (Reserved for future use; not actively populated.)
- **`EvalAgentConversation.findings_report` TextField** — Markdown report (mirrored from `EvalAgentReports.state.report_markdown`).
- **Redis stream events** — Per-job event list (`eval_agent:deep_stream:events:<job_id>`, TTL 24h) for SSE replay.
- **Artifact store** — Files written under `/user-uploads/{uuid_hex}_{safe_name}` and durable Eva files (`/memories/...`, `/playbooks/...`) via `write_thread_artifact_bytes` (the deep-engineer artifact store).
- **Slack thread** — Final result is `slack_update_message`'d into the placeholder.
- **GCS (currently unused)** — PDF reports were uploaded with 7-day signed URLs; pipeline disabled.

### 7.2 Result format

- **Primary:** Markdown report.
- **Chatbot:** Plain text reply (markdown welcome but informal).
- **Multi-agent merged:** Single unified markdown report (sections from both BI and SRE).
- **PDF (disabled):** `compile_findings_report_to_pdf` produces PDF bytes via xhtml2pdf.

### 7.3 Streaming

SSE format:
```
id: <event_id>
event: <event_name>
data: <json_payload>

```

Event types include `run_enqueued`, `run_started`, `activity` (progress messages), `tool_call`, `tool_result`, `partial_text`, `final_text`, `run_completed`, `run_failed`, `run_cancelled`, `run_cancellation_requested`, keepalive pings.

Resume: SSE clients send `Last-Event-ID` header; the view filters events with `id > last_event_id` and replays.

Heartbeat: 10s keepalive.

### 7.4 Checkpoints (intermediate state)

- LangGraph state is checkpointed at every super-step via `AsyncPostgresSaver`. Tables: `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` (created by `checkpointer.setup()`).
- Mid-run state can be resumed by passing the same `thread_id` to `ainvoke`.

### 7.5 Report retention

- `EvalAgentConversation` and `EvalAgentReports` are persisted indefinitely.
- Redis stream events: 24h TTL.
- Knowledge cache: 15min (BI).
- Investigation pattern cache: 15min.
- Langfuse trace cache: 60min.
- File summary cache: 30min.
- Exception trace cache: 30min.

### 7.6 Visualization

No built-in dashboard. Output is consumed via:
- Admin web app (separate Next.js repo) → calls these DRF endpoints → renders markdown.
- Slack thread updates.
- LangSmith (when enabled) — full trace UI.

---

## 8. Configuration

### 8.1 Environment variables

Provided via Django `settings` (`admin_backend/config.py`):
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
- `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`
- `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_ENDPOINT`, `LANGSMITH_PROJECT`
- `GCP_LOGS_PROJECT_ID`, `EVALS_GCP_SA_KEY` (JSON), `GOOGLE_CLOUD_PROJECT`
- `GITHUB_TOKEN` (or `GH_SECRET_KEY`), `CODEBASE_REPO_URL`, `CODEBASE_INDEX_DIR`, `CODEBASE_REPO_ROOT`
- `QDRANT_URL`, `QDRANT_API_KEY`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`
- `CELERY_BROKER_URL` (Redis), `REDIS_URL`
- `PREFECT_API_URL`, `PREFECT_API_KEY`
- `SLACK_WEBHOOK_SECRET`

### 8.2 EvalAgentConfig knobs (already enumerated in `04_llms_and_prompts.md`)

Highlights:
- `USE_DEEP_ENGINEER_FOR_INVESTIGATION = True` — Toggles between Deep Engineer (default) and legacy `run_eval_agent_investigation`.
- `AVAILABLE_MODELS` — 4-model list (Haiku, Sonnet 4.5, Sonnet 4.6, Opus 4.5).
- `DEFAULT_MODEL = "claude-haiku-4-5-20251001"` — Default for chatbot, BI agent, SRE agent.
- `DEEP_ENGINEER_MODEL = "claude-sonnet-4-6"`, `DEEP_ENGINEER_OPENAI_MODEL = "gpt-5.4"`.
- `DEEP_ENGINEER_RECURSION_LIMIT = 1000`, `_MODEL_CALL_RUN_LIMIT = 50`, `_TOOL_CALL_RUN_LIMIT = 200`.
- `DEEP_ENGINEER_INTERPRETER_ENABLED = True`, `_TIMEOUT_SECONDS = 5.0`, `_MEMORY_LIMIT_BYTES = 64MB`, `_MAX_RESULT_CHARS = 4000`, `_MAX_PTC_CALLS = 64`.
- `ROUTING_MODEL = "claude-haiku-4-5-20251001"`.
- `TEMPERATURE = 0.3`, `MAX_TOKENS = 4096`, `TOOL_TIMEOUT = 60`.
- `HIGH_CONFIDENCE_THRESHOLD = 500`, `MODERATE_CONFIDENCE_THRESHOLD = 100`.
- All token caps (MAX_*) — see `04_llms_and_prompts.md`.
- `DANGEROUS_SQL_PATTERNS` — regex list blocking INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, CREATE, GRANT, REVOKE, EXEC, EXECUTE, multi-statement.
- `SKILLS_CONFIG` — per-skill triggers, max_iterations, baselines.
- `MEM0_BI_COLLECTION = "bi_memory"`, `MEM0_SRE_COLLECTION = "sre_memory"`, `MEM0_SEARCH_LIMIT = 5`, `MEM0_CONFIDENCE_THRESHOLD = 0.7`.

### 8.3 CLI flags / arguments

`knowledge/build_index.py`:
- `--local` — Use `LocalKnowledgeStore` (FAISS) instead of `DatabaseKnowledgeStore` (pgvector).

### 8.4 Files Eva reads at startup

- `knowledge/files_yaml/*.yaml` — Authoritative knowledge (FAQ, BASELINES, KNOWN_ISSUES, INVESTIGATION_PATTERNS, SCHEMA_REFERENCE).
- `knowledge/skills/*.md` — SRE investigation playbooks (general_skill, voice_call_debug, sms_chat_debug, web_scheduler).
- `knowledge/files/*.md` — Legacy markdown (used by `load_from_files.py` when (re)building the pgvector index).

### 8.5 What is loaded lazily

- `BIAgent` and `SREAgent` inside `MultiAgentCoordinator` — only instantiated when first needed.
- GitHub MCP client + tools — singleton, locked init.
- Codebase indexer — per-env singleton.
- Mem0 client — lazy in `MemoryManager._ensure_initialized` (currently disabled).
