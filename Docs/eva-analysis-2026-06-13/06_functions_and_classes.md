# 06 — Function and Class Inventory

Grouped by category. Each entry lists name, file path, line range (where known), description, key parameters, returns, and notable side effects.

> Convention: side effects of "log writes via `logger.info/warning/error`" are universal and omitted. "External API call" means a network round trip to a third party.

---

## A. Configuration

### Class `EvalAgentConfig`
- **File:** `admin_app/services/eval_agent/config.py` (lines 7-167)
- **Purpose:** Central, class-attribute-based configuration. All knobs live here.
- **Notable class methods:**
  - `is_langsmith_enabled() -> bool` — True iff `LANGSMITH_TRACING` and `LANGSMITH_API_KEY` are set.
  - `is_query_safe(query: str) -> bool` — Returns False if any `DANGEROUS_SQL_PATTERNS` regex matches.

### Dataclass `EvalAgentDispatchPlan`
- **File:** `mode_router.py` (lines 73-89)
- **Fields:** `use_deep_search`, `BI`, `SRE`, `routed_mode`, `routing_reason`, `router_model`.
- **Methods:** `routing_metadata()` → dict for LangSmith metadata.

---

## B. State models (Pydantic) — see `08_data_schemas.md` for full field lists

The Pydantic models defined in `models.py`:

`ConfidenceLevel`, `BIQueryRequest`, `BIQueryResponse`, `InvestigationPatternItem`, `MandatoryKnowledge`, `FindingSummary`, `RoutingPlanStep`, `InvestigationPlanStep`, `BIInvestigationPlanOutput`, `TriageOutput`, `SRETriageOutput`, **`AgentState`**, `DatabaseQueryResult`, `KnowledgeSearchResult`, `SkillResult`, `DiscoverCategory`, `DiscoverData`, `DiscoverNodeOutput`, `CrossValidateMethod`, `CrossValidateNodeOutput`, `ContextualizeNodeOutput`, `SREFindings`, `InvestigationRequest`, `TurnNode`, `CallBehavior`, `FlowViolation`, `Hypothesis`, `FetchTask`, `FetchPlan`, `HypothesisEvaluation`, `CorrelationResult`, `PlanUpdateDecision`, `TranscriptReadSummary`, `TraceFailureAnalysis`, `TierInvestigationDecision`, **`MultiAgentState`**, **`SREAgentState`**.

---

## C. Mode routing

### `plan_eval_agent_dispatch(query, *, auto_route, deep_search, BI, SRE, thread_context_for_router=None) -> EvalAgentDispatchPlan`
- **File:** `mode_router.py` (lines 187-313)
- **Async:** No (calls LLM synchronously via SDK)
- **Purpose:** Decide whether to run chatbot vs deep search; if deep search, decide BI / SRE / multi.
- **Modes:**
  - **`auto_route=False`:** Manual routing. `deep_search=True` + flags decide mode. `deep_search=False` → chatbot.
  - **`auto_route=True`:** LLM mode router. Builds `ChatAnthropic(ROUTING_MODEL, temperature=0, max_tokens=1024)`, calls with `QUERY_MODE_ROUTING_PROMPT` system + structured output `ModeRoutingDecision`.
- **Fallback:** On any exception, returns chatbot plan with explanation in `routing_reason`.

### `build_mode_router_conversation_block(messages, supplemental_context, model_name) -> Optional[str]`
- **File:** `mode_router.py` (lines 27-58)
- **Purpose:** Build prior-thread + supplemental context for the router LLM.
- **Calls:** `utils.build_router_prior_context_for_llm`, `utils.build_router_supplemental_context_for_llm`.

### Class `ModeRoutingDecision(BaseModel)`
- **File:** `mode_router.py` (lines 61-69)
- **Fields:** `route ∈ {chatbot, deep_search_bi, deep_search_sre, deep_search_multi}`, `reason`, `confidence`, `signals`.

---

## D. Multi-agent coordinator

### Class `MultiAgentCoordinator`
- **File:** `multi_agent.py` (lines 95-575)
- **Purpose:** Orchestrate BI and SRE workers via a supervisor-worker LangGraph with shared blackboard (`shared_findings`).
- **Constants:** `MAX_HANDOFFS = 3`.
- **Constructor:** Builds `_supervisor_llm` (Haiku, temp=0, max_tokens=20), `_report_llm` (default model, temp=0.3, max_tokens=4096). Lazy-initializes `BIAgent` and `SREAgent`. Builds the workflow at init but compiles per-event-loop.
- **Key methods:**
  - `async investigate(query, context, location_id, time_window, thread_id, BI, SRE, progress_callback, cancellation_check, run_name, routing_metadata)` — public entry. Returns `(report, session_id, state_snapshot)`.
  - `_build_workflow()` → `StateGraph(MultiAgentState)` with nodes: `supervisor`, `bi_node`, `sre_node`, `merge_node`. Entry = supervisor; `supervisor` routes to bi/sre/merge; bi and sre loop back to supervisor; merge → END.
  - `async _supervisor_node(state)` — Reads handoff_count, last_agent_called, blackboard; calls `_supervisor_llm_route_async`; returns `{active_agent: bi|sre|None, sre_skip_trace?}`. Enforces `bi_only`, `sre_only`, `MAX_HANDOFFS` caps.
  - `async _bi_node(state, config)` — Calls `BIAgent.investigate`; appends report to `shared_findings`, `bi_findings`, increments `handoff_count`. Special-case: if BI returned a clarify response, set `final_report` and exit.
  - `async _sre_node(state, config)` — Calls `SREAgent.investigate`; appends to `shared_findings`, `sre_findings`, increments `handoff_count`.
  - `async _merge_node(state)` — Calls `_merge_reports(query, bi_report, sre_report)` if both present; else uses whichever is non-empty.
  - `async _merge_reports(query, bi_report, sre_report)` — LLM call with `MULTI_AGENT_REPORT_PROMPT` (cached). Returns merged markdown; falls back to raw concatenation on failure.

### `async _supervisor_llm_route_async(llm, query, shared_findings, handoff_count, last_agent_called, has_bi_findings, has_sre_findings) -> str`
- **File:** `multi_agent.py` (lines 46-92)
- **Purpose:** Single-word routing decision (`bi | sre | sre_skip_trace | finish`).
- **Anti-loop guards:** No-finish at handoff 0; default to `bi` on parse failure when no agent has run.

### Exception `InvestigationCancelled`
- **File:** `multi_agent.py` (lines 41-43), also defined in `agents/bi_agent.py` and `agents/sre_agent.py`.

---

## E. Postgres checkpointer (graph state persistence)

### `_make_conn_string() -> str`
- **File:** `checkpointer.py` (lines 37-46)
- Builds URL-encoded `postgresql://user:pass@host:port/dbname` from Django default DB settings.

### `get_async_checkpointer_context() -> AsyncIterator[Any]` (context manager)
- **File:** `checkpointer.py` (lines 49-65)
- **Purpose:** Recommended pattern for chatbot. Yields a per-call `AsyncPostgresSaver` via `from_conn_string`. Auto-calls `setup()`.

### `get_postgres_checkpointer() -> Optional[Any]`
- **File:** `checkpointer.py` (lines 68-108)
- **Purpose:** Global sync `PostgresSaver` singleton. Used by sync `graph.invoke()` only.
- **Backing pool:** `psycopg_pool.ConnectionPool(autocommit=True, prepare_threshold=0, row_factory=dict_row, min_size=1, max_size=20, open=True)`.

### `async get_async_postgres_checkpointer() -> Optional[Any]`
- **File:** `checkpointer.py` (lines 111-158)
- **Purpose:** Per-event-loop `AsyncPostgresSaver`. Cached in `_async_checkpointers: dict[loop_id, AsyncPostgresSaver]`. Used by BI/SRE/multi agent graphs (each Celery task gets its own loop and its own saver).
- **Backing pool:** `AsyncConnectionPool` with same settings.

---

## F. Streaming (Redis pub/sub)

### `publish_stream_event(job_id, *, event, data) -> dict`
- **File:** `deep_agent_stream.py` (lines 36-61)
- **Purpose:** Push an event to the per-job stream. Uses Redis pipeline:
  - `INCR` counter for `id`.
  - `RPUSH` to event list (`eval_agent:deep_stream:events:<job_id>`), `EXPIRE` 24h.
  - `SETEX` status key (`:status:<job_id>`) to `"running"` (or terminal event name when in `TERMINAL_EVENTS = {completed, failed, cancelled}`), TTL 24h.
  - `PUBLISH` to channel `:channel:<job_id>`.

### `get_buffered_events(job_id, *, after_id=0) -> list[dict]`
- **File:** `deep_agent_stream.py` (lines 64-79)
- Returns events from the list after `after_id` (cursor-based replay).

### `get_stream_status(job_id) -> Optional[str]` / `is_terminal_status(status) -> bool` / `stream_channel(job_id)`
- **File:** `deep_agent_stream.py` (lines 24-89)
- Small accessors used by `EvalAgentQueryStatusView`.

---

## G. Utilities

### SQL safety / table allowlist

- `outer_statement_has_limit(query) -> bool` — `utils.py` lines 68-97.
- `query_exempt_from_row_limit(query) -> bool` — `utils.py` lines 100-123. True for `GROUP BY`, `HAVING`, or global aggregates.
- `is_global_aggregate_select(query) -> bool` — `utils.py` lines 126-171.
- `apply_row_sample_limit_guard(query, fallback_limit) -> str` — `utils.py` lines 174-203. Adds `LIMIT <fallback_limit>` if needed.
- `add_query_safety_limits(query, limit=1000) -> str` — legacy alias.
- `extract_table_names(query) -> List[str]` — `utils.py` lines 215-223. Regex on `FROM|JOIN`. Returns lowercased identifiers.
- `ALLOWED_TABLES: frozenset` — `utils.py` lines 226-302. 72-table allowlist (nhapp_*).
- `table_access_allowed(raw_identifier, *, allowed_tables=None) -> bool` — `utils.py` lines 331-342.
- `validate_table_access(table_names, *, allowed_tables=None) -> bool` — `utils.py` lines 350-364.
- `sanitize_query_for_logging(query) -> str` — `utils.py` lines 366-371. Redacts phone/email patterns.

### Async/sync bridging

- `run_sync_in_thread_if_async(func, *args, **kwargs) -> T` — `utils.py` lines 43-66. Runs sync Django code in a thread pool when called from async; passes through when in sync context. Uses dedicated `_SYNC_EXECUTOR` (max 4 workers).

### Partial-report synthesis

- `is_recursion_limit_error(exc) -> bool` — `utils.py` lines 382-384. Checks against `langgraph.errors.GraphRecursionError` and `RecursionError`.
- `async synthesize_chatbot_partial_reply(user_message, messages_or_snippet, llm) -> str` — `utils.py` lines 422-477. Uses `CHATBOT_PARTIAL_REPLY_PROMPT`. Falls back to hardcoded message if LLM fails.
- `async synthesize_partial_report(query, findings_snippet, llm) -> str` — `utils.py` lines 480-499. Uses `PARTIAL_REPORT_PROMPT`.

### Call enrichment

- `_resolve_call_record(candidate_id, default_org_id, default_location_id) -> Tuple[Optional[str], Optional[str], Optional[Union[int, str]], str]` — `utils.py` lines 501-581. Resolves user input to canonical call/chat session row. Returns `(resolved_id, org_id, location_id, session_type)`.
- `enrich_investigation_request_from_call(req) -> InvestigationRequest` — `utils.py` lines 584-640. Fills `location_id`, `location_name`, `organization_name`, `caller_phone_number`, `retell_call_id` from the resolved `RetellAICall` row.

### Prompt-cache helpers

- `_human_message_with_cache(static_text, dynamic_text) -> HumanMessage` — `utils.py` lines 643-654. Builds an Anthropic prompt-cached message (cache_control: ephemeral on static; plain dynamic).

### State serializers for prompt injection

- `_gcp_logs_for_prompt(state, max_chars=14000) -> str` — `utils.py` lines 657-667.
- `_transcript_summary_for_prompt(state) -> str` — `utils.py` lines 670-680.

### Mode-switch and router context builders

- `_format_mode_switch_body_for_llm(raw_summary) -> str` — lines 687-693.
- `_summarize_transcript_for_mode_switch(transcript, *, target_mode, model_name) -> str` — lines 696-760. **LLM call** (Haiku, temp 0.15, max_tokens 6000).
- `build_mode_switch_context_for_llm(messages, target_mode, model_name, *, from_chatbot_to_agent=False) -> str` — lines 763-830.
- `_router_context_message_is_relevant(m) -> bool` — lines 833-843.
- `_format_router_transcript_lines(messages) -> str` — lines 846-866.
- `_summarize_text_for_mode_router(text, *, kind, model_name) -> str` — lines 869-917. **LLM call** (Haiku, temp 0.1, max_tokens 2500).
- `build_router_prior_context_for_llm(messages, *, model_name) -> Optional[str]` — lines 920-950.
- `build_router_supplemental_context_for_llm(supplemental_context, *, model_name) -> Optional[str]` — lines 953-977.

---

## H. BI Agent

### Class `BIAgent`
- **File:** `agents/bi_agent.py` (lines 92-1505)
- **Purpose:** Execute a multi-step BI investigation via LangGraph. Public entry: `investigate(...)`.
- **State schema:** `AgentState`.

**LangGraph nodes (defined as `async` methods, attached via `workflow.add_node(...)`):**

| Node | Method | Reads | Writes |
|---|---|---|---|
| `memory_load` | `_memory_load_node` | query, context, findings, session_id | mandatory_knowledge_loaded, current_intent, pending_intent, faq_hit, routing_reason, findings (FAQ short-circuit) |
| `knowledge_router` | `_knowledge_router_node` | query | knowledge_hit, knowledge_item |
| `knowledge_answer` | `_knowledge_answer_node` | knowledge_item, query | final_response (BIQueryResponse) |
| `plan_generation` | `_plan_generation_node` | query, bi_memory_context, skills_run, mandatory_knowledge | bi_investigation_plan, bi_plan_index |
| `skill_executor` | `_skill_executor_node` | bi_investigation_plan, bi_plan_index | current_intent, bi_investigation_plan (mutates current step → in_progress) |
| `discover` | `_discover_node` | query, context, location/org, findings, skills_run | findings (append), skills_run, pending_intent, resolved_* |
| `cross_validate` | `_cross_validate_node` | (same shape) | (same shape) |
| `contextualize` | `_contextualize_node` | (same shape) | (same shape) |
| `plan_update` | `_plan_update_node` | bi_investigation_plan, findings | bi_investigation_plan (current step → completed; optionally revises remainder), bi_plan_index |
| `remember` | `_remember_node` | skills_run, findings | conclusion_confidence |
| `report` | `_report_node` | full state | findings_report |

**Routing functions:**
- `_after_supervisor_decision(state) -> {"end" | "report" | "knowledge_router"}` — from `memory_load`.
- `_after_knowledge_router_decision(state) -> {"knowledge_answer" | "plan_generation"}`
- `_skill_executor_decision(state) -> {"discover" | "cross_validate" | "contextualize"}`
- `_after_plan_update_decision(state) -> {"skill_executor" | "remember"}`

**Per-event-loop graph compilation:** `_investigate_impl` caches compiled graphs by `id(asyncio.get_running_loop())` because the async Postgres checkpointer is loop-bound.

**Notable helper methods:**
- `_run_mandatory_checks(query) -> Dict[str, Any]` — FAQ check + 15-min cache fill of investigation_patterns/baselines/known_issues.
- `_revise_plan_bi(plan, next_index, latest_finding, query)` — LLM call for plan revision.
- `_build_structured_report(state)` — LLM call for final markdown report.
- `_render_finding_md(obj)` / `_render_findings_markdown(findings)` — markdown rendering of finding dicts.
- `_extract_confidence_from_findings(findings) -> str` — rollup of confidence labels.

**Class const:** `KNOWLEDGE_HIT_THRESHOLD = 0.75`.

**Module const:** `_KNOWLEDGE_CACHE: Dict[str, Any]`, `KNOWLEDGE_CACHE_TTL_SECONDS = 15 * 60`.

---

## I. SRE Agent

### Class `SREAgent`
- **File:** `agents/sre_agent.py` (lines 380-3279; ~1,300 lines are commented-out vestigial code)
- **Purpose:** Two execution paths:
  1. **Single-loop ReAct** (`run_agent`) — the public path called by `investigate()`. Up to 30 tool rounds, all tools available simultaneously.
  2. **LangGraph tier path** (`_investigate_impl`) — Tier 1 ReAct → optional Tier 2 ReAct → conclude. Has a compiled checkpointed graph.
- **State schema:** `SREAgentState`.

**LangGraph nodes (in `_build_workflow`):**

| Node | Method | Role |
|---|---|---|
| `route_entry` | `_route_entry_node` | No-op; entry point |
| `intake` | `_intake_node` | LLM resolves `call_id` via SQL → builds `InvestigationRequest` |
| `direct_investigation` | `_direct_investigation_node` | Used when `skip_trace_path=True`; primes state with no-trace defaults |
| `call_trace_fetch` | `_call_trace_fetch_node` | Parallel Langfuse + GCP fetch via `asyncio.gather(asyncio.to_thread(_sync_langfuse), asyncio.to_thread(_sync_gcp))` |
| `context_load` | `_context_load_node` | Loads `voice_call_debug.md`; sets empty `past_cases`, `component_tags`, `sre_memory_context` |
| `investigation_node` | `_tier1_investigation_node` → `_investigation_node(state, mode="tier1")` | Tier-1 ReAct with embedded transcript |
| `deep_investigation_node` | `_tier2_investigation_node` → `_investigation_node(state, mode="tier2")` | Tier-2 ReAct focused on tier-1's `unresolved_threads` |
| `conclude` | `_conclude_node` | Final markdown report via `SRE_CONCLUDE_PROMPT` |

**Edges:**
- `START → route_entry`
- `route_entry → intake` if not skip_trace; else `direct_investigation`
- `intake → call_trace_fetch → context_load → investigation_node`
- `direct_investigation → investigation_node`
- `investigation_node → conclude` if `tier1_decision.resolved`, else `deep_investigation_node → conclude`
- `conclude → END`

**Key constants (module-level):**
`MAX_ITERATIONS = 3`, `MAX_TIER_REACT_TURNS = 25`, `MAX_SRE_TOOL_ROUNDS = 30`, `SRE_MESSAGE_TRIM_WINDOW = 32`, `MAX_CODE_EXPLORATION_TOKENS = 180_000`, `MAX_TIER1_TRANSCRIPT_CHARS = 120_000`, `MAX_TIER2_GCP_LOG_CHARS = 30_000`, `MAX_TOOL_RESULT_CHARS = 50_000`.

**Tool builders:**
- `_build_sre_tools()` — module-level, cached in `_sre_tools_cache`. Builds the shared tool set (Langfuse, codebase, GitHub MCP, DB, GCP, Twilio).
- `_build_sre_loop_tools(state, todo_items, checked_items)` — per-state tools (adds `add_investigation_todo`, `list_investigation_todos`, `get_prefetched_trace_context`, `get_gcp_logs_from_state`, `get_prefetched_gcp_transcript`, `get_sre_investigation_skill`, `mark_checked`).
- `_get_tier_investigation_tools(state, include_trace_exception, include_state_gcp_tool, include_state_call_debug_tool, todo_items)` — used by `_investigation_node` (LangGraph path).

**Helpers:**
- `_route_after_entry(state) -> str` — `"intake"` or `"direct_investigation"`.
- `_route_after_tier1(state) -> str` — `"conclude"` if resolved, else `"deep_investigation_node"`.
- `_run_tier_investigation(state, step_name, prompt_text, ...)` — invokes `run_llm_with_tools` with `TierInvestigationDecision` schema.
- `_run_sre_no_tool_synthesis(messages, system_prompt, ...)` — synthesis call when ReAct loop exhausts.
- `_build_sre_runtime_user_message(state)` — structured "what to investigate" message.
- `_build_sre_invoke_config(...)` — merges parent `RunnableConfig`, adds LangSmith tags.
- `_investigation_request_for_conclude_prompt(req, fallback_query)` — formats request block for the conclude prompt.
- `_build_fallback_report(state)` — minimal partial report when `_conclude_node` raises.
- `_merge_state_updates(state, updates)` — sync state mutation (used in single-loop path, bypasses LangGraph state-merge).

**Dataclass `AgentResponse`** (lines 144-151): `final_text`, `tool_rounds`, `checked_items`, `inconclusive`, `error`.

---

## J. Chatbot

### Module `chatbot/entrypoint.py`

**Top-level constants:**
- `CHATBOT_RECURSION_LIMIT = 25`
- `CHATBOT_MESSAGE_TRIM_WINDOW = 32`
- `_chatbot_graph_cache: dict[str, Any]` — per-model graph cache (only when checkpointer is auto-fetched, not when passed in).
- `_chatbot_invocation_context: ContextVar[dict]` — holds per-turn todo list.

**Functions:**
- `_build_chatbot_resolved_system_prompt() -> str` (72-87) — Substitutes `{current_datetime_utc}`, `{table_list}`, `{row_sample_limit}`, `{accessible_tables}`, `{investigation_patterns_reference}` into `CHATBOT_SYSTEM_PROMPT`.
- `_trim_chatbot_messages_for_llm(messages, n) -> list` (89-109) — Keep last n, extend backward to avoid starting with orphan ToolMessages.
- `_normalize_tool_call_args(tc) -> dict` (112-125) — Defensive args coercion.
- `async _execute_one_chatbot_tool_async(tc, tools_by_name) -> ToolMessage` (150-173) — Async tool dispatch.
- `async _tool_messages_from_last_ai_async(state, tools_by_name) -> list[ToolMessage]` (195-219) — Parallelizes tool calls (semaphore cap 8).
- `_build_chatbot_graph(llm, all_tools, checkpointer) -> CompiledStateGraph` (222-259) — Custom explicit ReAct: `agent → tools → agent` loop with conditional exit on no `tool_calls`. **State schema:** LangGraph `MessagesState`.
- `_get_chatbot_todos()` (262-267), `set_chatbot_invocation_context()` (270-272), `_write_todos_impl(todos_json)` (275-304) — Per-turn investigation plan storage.
- `@tool write_todos(todos_json: str) -> str` (307-310) — Plan-setter tool exposed to the LLM.
- `@tool get_call_debug_context(max_chars=120_000) -> str` (323-328) — Voice debug skill loader tool.
- `async _chatbot_graph_with_async_checkpointer(model_name, checkpointer) -> Optional[CompiledStateGraph]` (331-372) — Build the graph for this event loop.
- `_make_chatbot_tools() -> Tuple[list, db_tool, knowledge_tool]` (375-407) — Assemble the chatbot tool set.
- `_chatbot_step_from_messages(messages, step_index) -> (step_id, message, detail)` (409-441) — Derive progress event from current message.
- `_checkpoint_has_messages(checkpoint) -> bool` (444-454) — Inspect `channel_values.messages` of a LangGraph Checkpoint.
- `_load_chatbot_prior_messages_from_db(thread_id, current_user_message) -> list[BaseMessage]` (457-485) — Bridge: load prior chatbot messages from `EvalAgentConversation.messages` (Django) into LangChain message list. Strips duplicate trailing HumanMessage.
- `async invoke_chatbot_with_progress(thread_id, user_message, context_summary, model_name, conversation_id, progress_callback, cancellation_check, checkpointer, routing_metadata) -> tuple[str, str, list[dict]]` (488-635) — Public entry. Returns `(response_text, thread_id, updated_messages_for_db)`. Handles cancellation and recursion-limit recovery (`is_recursion_limit_error` → `synthesize_chatbot_partial_reply`).

### Module `chatbot/utils.py`

**Constants:** `SOURCE_CHATBOT = "chatbot"`, `SOURCE_DEEP_SEARCH = "deep_search"`, `SKILL_REGISTRY = {"bi": BI_SKILL_PROMPT, "technical": TECHNICAL_SKILL_PROMPT}`.

**Functions:**
- `format_eval_message_timestamp_utc_z(dt=None) -> str` — ISO-8601 with Z suffix.
- `_parse_eval_message_timestamp(ts) -> Optional[datetime]`.
- `sort_eval_messages_by_timestamp(messages) -> list[dict]`.
- `ensure_sorted_eval_messages_with_timestamps(messages) -> list[dict]` — Forward-fills missing timestamps and sorts.
- `messages_to_dict(messages, skip_system=True, source="chatbot") -> list[dict]` — Converts LangChain messages to DB-storable dicts; tags `is_final`.
- `messages_for_chatbot_display(messages, display_final_only=False) -> list[dict]` — Filters for API output.
- `summarize_messages_for_context(messages, llm, max_keep) -> list[BaseMessage]` — Compresses old turns to a SystemMessage summary.
- `dict_to_messages(messages) -> list[BaseMessage]` — Inverse of `messages_to_dict`.
- `get_skill(skill_name) -> str` — Returns the skill prompt with substitutions filled.

---

## K. Skills

### Class `DiscoverSkill`
- **File:** `skills/discover.py`
- **Init:** `(llm, db_tool, knowledge_tool)` + `max_iterations=5`, `other_threshold=0.06`.
- **`async execute(query, context, location_id, organization_id, location_name, organization_name, skills_run, mandatory_knowledge) -> SkillResult`** — Loads `DISCOVER_PROMPT`, formats with table_list + row_sample_limit, prepends `format_mandatory_knowledge_for_prompt`, calls `run_llm_with_tools(max_tool_rounds=3, current_intent="discover", structured_output_schema=DiscoverNodeOutput)`.
- **Helpers:** `_resolve_location_from_query_with_name(query)`, `_resolve_organization_from_query_with_name(query)` — SQL-based name resolver.

### Class `CrossValidateSkill`
- **File:** `skills/cross_validate.py`
- Same shape; uses `CROSS_VALIDATE_PROMPT` and `CrossValidateNodeOutput`.

### Class `ContextualizeSkill`
- **File:** `skills/contextualize.py`
- Same shape; uses `CONTEXTUALIZE_PROMPT` and `ContextualizeNodeOutput`. Stores `default_baselines` (automation_rate=61, scheduling_rate=40, rep_requested_rate=28, negative_sentiment_on_failures=22).

### Class `RememberSkill`
- **File:** `skills/remember.py`
- **Init:** `(llm, knowledge_tool)`.
- **`async execute(query, context)`** — Uses `REMEMBER_PROMPT` and `make_remember_tools(knowledge_tool)`. **No structured output** — narrative.

### `skills/skill_utils.py` — shared infrastructure

- `ALLOWED_COLUMNS: Dict[str, set]` — strict allowlist of (table, column) pairs for `get_distinct_values` SQL injection prevention.
- `load_prompt(filename) -> str` — load by name (defers to `eval_agent.prompts.get_prompt` then disk).
- `make_db_and_knowledge_tools(db_tool, knowledge_tool) -> list[Tool]` — Factory; produces `list_tables`, `describe_table`, `run_query`, `get_distinct_values`, `search_knowledge`, `get_baselines`, `get_table_list`, `get_table_schema`, `search_tables`, `get_investigation_patterns`, `check_faq`, `get_file_content`.
- `make_remember_tools(knowledge_tool) -> list[Tool]` — `search_knowledge`, `get_file_content`, `update_knowledge`, `add_knowledge`, `update_knowledge_by_id`.
- `ensure_narrative_finding(text) -> str` — Returns a default narrative if input is JSON/HTML/empty.
- `extract_key_finding(full_response) -> Optional[str]` — Parses "### 1. Key Finding" markers.
- `parse_suggested_next_step(final_text) -> Optional[str]` — Extracts `NEXT_STEP:` line.
- `build_next_step_instruction(skills_run) -> str` — Builds the instruction suffix.
- `format_mandatory_knowledge_for_prompt(mandatory_knowledge) -> str` — Renders supervisor-loaded knowledge into prompt markdown.
- `async run_llm_with_tools(llm, system_prompt, user_message, tools, max_tool_rounds=3, current_intent=None, structured_output_schema=None, structured_output_instruction=None) -> Any` — **The async heart of skill execution.** Anthropic prompt-cached system message; ReAct loop; inline JSON parse first; structured-output fallback. Wraps each tool call in `asyncio.wait_for(timeout=TOOL_TIMEOUT=60)`.

---

## L. Tools

### `tools/db_client.py` — `class PostgresClient`
- **Methods:**
  - `execute_query(sql, params)` — Tenacity-retried; validates SQL & tables; applies row-limit guard; sets statement_timeout per query; returns `DatabaseQueryResult`.
  - `list_tables() -> List[str]`
  - `describe_table(table_name) -> Dict[str, Any]` — Parameterized `information_schema.columns` query.
  - `search_tables(pattern, limit=50) -> List[Dict[str, str]]` — ILIKE pattern match across allowlisted tables.
- **Helpers:** `_execute_sql`, `_get_read_connection`, `_resolve_read_alias`, `_normalize_env`.

### `tools/db_tools.py`
- `create_db_tools(db_client) -> List[Tool]` — Factory exposing `list_tables`, `describe_table`, `run_query`.

### `tools/validation_tool.py` — `class SQLValidationTool`
- `validate_query(query) -> Dict[str, Any]` with `is_valid`, `errors`, `warnings`, `safety_score`, `query_type`, `tables_accessed`, `estimated_complexity`.
- Internal checks: `_check_query_length` (max 10000), `_check_dangerous_patterns`, `_check_query_syntax` (single statement), `_check_statement_type` (SELECT only), `_check_table_access` (allowlist), `_check_query_complexity` (max 5 JOINs), `_check_injection_patterns`, `_calculate_safety_score`.
- Helpers: `suggest_query_improvements`, `sanitize_query`, `get_query_risk_assessment` (`risk_level` ∈ {low, medium, high}, `is_safe_to_execute = is_valid AND safety_score ≥ 60`).

### `tools/vector_knowledge_tool.py` — `class VectorKnowledgeTool`
- `search_knowledge(query, categories, metadata_filters) -> KnowledgeSearchResult` — Calls `store.search(query, k=8)`.
- `get_baselines() -> str` — Reads `BASELINES.yaml`.
- `get_table_schema(table_name) -> str` — Reads `SCHEMA_REFERENCE.yaml`.
- `get_table_list() -> str` — Reads `SCHEMA_REFERENCE.yaml` (returns table names + descriptions).
- `get_investigation_patterns(pattern_type=None) -> str` — Reads `INVESTIGATION_PATTERNS.yaml` via `load_investigation_patterns_text`.
- `get_known_issues() -> str` — Reads `KNOWN_ISSUES.yaml`.
- `check_faq(question) -> Optional[str]` — Vector search via `store.search(k=1, type_filter="faq")` (threshold 0.5).
- `get_file_content(filename) -> str` — Maps `.md` aliases to YAML files.
- `update_knowledge(category, content, section=None) -> None`, `add_knowledge(knowledge_type, title, content, metadata)`, `update_knowledge_by_id(item_id, new_content)`.
- Module-level: `_INVESTIGATION_PATTERNS_TEXT_CACHE` (TTL 900s), `load_investigation_patterns_text(force_reload=False)`.

### `tools/codebase_context_tool.py`
- `get_codebase_context_tool(*, env)` — `@tool search_codebase(query, limit=15)` — **DISABLED** (returns fixed-string disabled notice).
- `get_grep_codebase_tool(*, env)` — `@tool grep_codebase(pattern, file_glob, context_lines=5, literal=True)` — ripgrep wrapper with auto-expansion to context_lines=12 when matches contain `def `/`class `.
- `get_list_codebase_files_tool(*, env)` — `@tool list_codebase_files(prefix, max_results=2000)` — `rg --files`.
- `get_list_codebase_directories_tool(*, env)` — `@tool list_codebase_directories(prefix, max_results=500)`.
- `get_codebase_file_summary_tool(*, env)` — `@tool get_file_summary(file_path)` — Qdrant-backed; cached 1800s.
- `get_codebase_exception_trace_tool(*, env)` — `@tool trace_exception(exception_name)` — Qdrant-backed; cached 1800s.
- Helpers: `_classify_codebase_query` (heuristic + cached LLM classifier 3600s TTL), `_grep_codebase_impl`, `_parse_grep_context_output`, `_format_grep_for_llm` (rank by `def`/`class` first), `_get_indexer`, `_get_repo_root`.

### `tools/gcp_tools.py`
- `fetch_gcp_logs_bundle_for_call(call_ref, *, env)` — Main entry; resolves session row → window → phone-search variants → calls bundle fetcher.
- `fetch_gcp_logs_bundle_for_phone(phone_number, call_date, *, env)`.
- `fetch_gcp_logs_bundle_for_window(start, end, project_id, service_names, max_entries=800, max_chars=100000, *, text_search, search_terms, require_search_terms)`.
- Deep-engineer variants: `deep_engineer_gcp_logs_invoke`, `fetch_gcp_logs_bundle_for_phone_timestamp`, `_log_window_around_timestamp`.
- Resolution helpers: `resolve_retell_call_row`, `resolve_session_row`, `resolve_call_log_window`, `_normalize_caller_phone`, `_caller_phone_log_search_variants`.
- Lower-level: `build_cloud_run_filter`, `_iter_log_lines_with_transcript` (dedup by `(severity, service, msg_one)` fingerprint, separates `Transcript for twilio_` lines).
- Auth: `_get_cloud_logging_client()` — SA JSON via `EVALS_GCP_SA_KEY` or ADC.
- LangChain tools: `get_gcp_logs_tool(*, env)`, `get_gcp_logs_for_call_session_tool(*, env)`, `get_deep_engineer_gcp_logs_tool(*, env)`.

### `tools/github_mcp_client.py`
- `_get_github_token() -> str` — GitHub App installation token first, PAT fallback.
- `get_github_mcp_client()` — Lazy singleton; instantiates `MultiServerMCPClient`.
- `get_github_mcp_tools() -> list[BaseTool]` — Async-locked load; cached process-wide.
- Async wrappers around MCP tools: `github_mcp_search_code`, `github_mcp_get_file_contents`, `github_mcp_list_directory`, `github_mcp_list_commits`, `github_mcp_get_repo_metadata`, `github_mcp_list_files`.
- `parse_codebase_repo() -> Tuple[str, str]` — Parses `CODEBASE_REPO_URL` env.
- LangChain tools: `get_github_search_code_tool()`, `get_github_get_file_contents_tool()`, `get_github_list_directory_tool()`, `get_github_list_commits_tool()`, `get_github_get_repo_metdata_tool()` (note: typo retained), `get_github_list_files_tool()`.

### `tools/langfuse_tools.py`
- `fetch_all_traces_for_session(session_id, limit=100) -> List[dict]` — Paginated `GET /api/public/traces?sessionId=...`.
- `fetch_all_observations_v2_for_trace(trace_id, fields) -> List[dict]` — Cursor-paginated `GET /api/public/v2/observations?traceId=...&fields=core,basic,metrics,io`.
- `fetch_langfuse_session_call_logs_payload(session_id, *, enforce_call_age=True) -> dict` — Core logic; checks age via `sre_tools._is_call_old_enough_for_langfuse`.
- `build_latest_trace_observation_payload(latest_trace, latest_observation, session_fallback)` — Builds `{"call_logs": [...]}`.
- `format_langfuse_tool_response(payload) -> str` — JSON dumps.
- LangChain tool: `get_langfuse_session_call_logs_tool() -> @tool get_langfuse_session_call_logs(session_id)`.
- Helpers: `_b64_basic_auth`, `_langfuse_get`, `_strip_system_role`, `_is_system_role_message`, `_build_call_logs`, `_to_epoch`, `_trace_sort_key`, `_obs_sort_key`.

### `tools/sre_tools.py`
- `_is_call_old_enough_for_langfuse(session_id) -> (bool, str)` — Looks up `RetellAICall.id` or `ChatSession.id`; checks `created_at < now - 30min`.
- `format_traces_for_llm(session_id, limit=50)` — Full pipeline + Django cache (`eval_agent:langfuse_traces:<session_id>:<limit>`, 3600s TTL). Token budget `MAX_TRACE_OUTPUT_TOKENS = 180_000`.
- `get_langfuse_traces_structured(session_id, limit=50, skip_age_check=False) -> dict`.
- `_compact_event_payload(obs, seq)` — Drops `input` for LLM generation events; caps output at 4000 chars, input at 2000.
- Keeps: `agent_turn`, `user_turn`, `tts_request`, `llm_request`, `llm_response`, `llm_node`, `function_tool`. Drops: `tts_node`, `tts_request_run`, `llm_request_run`, `agent_speaking`, `user_speaking`, `drain_agent_activity`, `start_agent_activity`, `on_enter`, `on_exit`.
- LangChain tool: `get_langfuse_call_traces_tool() -> @tool get_langfuse_call_traces(session_id, limit=50)`.

### `tools/twilio_tools.py`
- Class `TwilioVoiceDebugTool`:
  - `investigate_call_sid(call_sid)` — Validates `CA...` prefix; calls `_fetch_call`, `_fetch_call_events`, `_maybe_fetch_call_conference_context`.
  - `investigate_conference_sid(conference_sid)` — Validates `CF...` prefix; fetches conference + participants + per-leg call+events.
  - Private fetchers + serializers: `_fetch_call`, `_fetch_call_events` (404-tolerant), `_fetch_conference`, `_fetch_conference_participants` (page_size=100, cap 500), `_build_participant_call_result`, `_serialize_twilio_resource`, `_resolve_participant_call_sid`.
- Module-level: `twilio_fetch_voice_call_debug(call_sid)`, `twilio_fetch_voice_conference_debug(conference_sid)` — return dicts.
- LangGraph-facing JSON wrappers: `twilio_fetch_voice_call_debug_tool(*, call_sid)`, `twilio_fetch_voice_conference_debug_tool(*, conference_sid)`.
- Dataclass `TwilioToolResult`.

---

## M. Knowledge

### `knowledge/store.py`
- `@dataclass KnowledgeItem` — `id`, `type` (KnowledgeType Literal), `title`, `content`, `metadata`.
- `class KnowledgeStore(ABC)` — `search`, `add`, `update`, `list_by_type`, `get_items_by_source`.
- `class LocalKnowledgeStore(KnowledgeStore)` — FAISS `IndexFlatIP` over normalized vectors. Persists to `index.faiss` + `items.pkl` + `version.json`. Methods: `_load`, `_get_embedding`, `_ensure_index`, `search`, `add`, `update`, `list_by_type`, `_persist`, `_rebuild`, `build_from_files(files_dir)`.
- `class DatabaseKnowledgeStore(KnowledgeStore)` — Django `KnowledgeEmbedding` (pgvector). `search` uses `from pgvector.django import CosineDistance; .annotate(similarity=1 - CosineDistance("embedding", query_vec)).order_by("-similarity")[:k]`. Calls wrapped in `run_sync_in_thread_if_async`. `add` uses `update_or_create(item_id=...)`.

### `knowledge/embedding.py`
- `EMBEDDING_MODEL = "text-embedding-3-large"` (3072-dim).
- `get_embedder()` — Singleton `OpenAIEmbeddings(model=EMBEDDING_MODEL)`.
- `embed(text) -> List[float]`, `embed_batch(texts) -> List[List[float]]`.

### `knowledge/build_index.py`
- CLI: `python -m admin_app.services.eval_agent.knowledge.build_index [--local]`.
- `build_db_from_files(files_dir)` — Loads via `load_all_from_directory`, calls `store.add(item)` per item.
- `main()` — argparse with `--local` flag.

### `knowledge/load_from_files.py`
Markdown chunkers, each returning `List[KnowledgeItem]`:
- `load_faq(path)` — Splits on `\n## Q:`; metadata `{source: "FAQ.md", type: "faq", name: <slug>}`.
- `load_baselines(path)` — Whole file → one item, `type: "baseline"`.
- `load_schema(path)` — Per-table / per-join-example / per-enum / per-issue chunks; tags `tables` from inline SQL.
- `load_known_issues(path)` — Splits on `\n###`; `type: "known_issue"`.
- `load_investigation_patterns(path)` — `##` major → `###` sub. SQL-bearing → `type: "sql_pattern"`; otherwise `type: "investigation_tip"`.
- `load_all_from_directory(files_dir)` — Aggregates all loaders.

### `knowledge/investigation_skills.py`
- `_SKILLS_DIR`, `_DEFAULT_MAX_CHARS = 120_000`, `_ALIAS_TO_STEM`.
- `@lru_cache list_investigation_skill_stems() -> Tuple[str, ...]`.
- `normalize_skill_id(skill_name) -> Optional[str]`.
- `get_sre_investigation_skill_payload(skill_name, max_chars=120000, *, voice_prefetch=None) -> str`.
- `load_investigation_skill_text(skill_name, max_chars=120000, *, use_cache=True) -> str`.
- `build_sre_investigation_skills_prompt_section() -> str` (and module-level `SRE_INVESTIGATION_SKILLS_PROMPT_SECTION`).
- `reload_skill_caches()`.

### `knowledge/call_debug_context.py`
- `load_call_debug_skill_markdown(force_reload=False) -> str`.
- `get_call_debug_markdown_for_tool(max_chars=120000) -> str`.
- `_expected_flows_from_call_debug_markdown(markdown_text) -> Dict[str, Any]` — Extracts YAML code fences containing `expected_flows`.
- `get_call_flows() -> Dict[str, Any]`.
- `get_call_flows_formatted(max_chars=8000) -> str`.

---

## N. Memory (currently disabled)

### Class `MemoryManager`
- **File:** `memory/manager.py` (lines 27-283)
- **Constructor:** `(collection_name, qdrant_url, qdrant_api_key, embedding_model="text-embedding-3-large")`. Lazy-initializes Mem0.
- **`_ensure_initialized()`** — Builds config dict `{vector_store: qdrant(url, api_key, collection, embedding_model_dims=1536), embedder: openai(text-embedding-3-large, OPENAI_API_KEY)}`; calls `Memory.from_config(config)`.
- **Methods:** `search(query, user_id, limit, filters)`, `add(content, user_id, metadata)`, `get_all(user_id, limit)`, `delete(memory_id)`.
- **Singletons:** `get_bi_memory()` (collection `bi_memory`), `get_sre_memory()` (`sre_memory`).
- **`format_memory_context(results) -> str`** — Formats search results as `## PRIOR KNOWLEDGE FROM PAST INVESTIGATIONS:` block. Differentiates `semantic` (PATTERN) vs `episodic` (HISTORY).

---

## O. API views — DRF surface (`admin_app/api/eval_agent/views.py`)

All views extend project `BaseAPI`. Token auth via `self.get_user()`. Response renderer wraps `{data: {success: True/False, ...}}` per project convention.

Detailed in section P. of `07_architecture.md`. Summary table:

| URL pattern | Methods | Class |
|---|---|---|
| `api/v1/eval-agent/query/` | POST | `EvalAgentQueryView` (multipart/JSON; cancel branch supported) |
| `api/v1/eval-agent/query-staging/` | POST | `EvalAgentQueryStagingView` |
| `api/v1/eval-agent/threads/` | POST | `EvalAgentCreateThreadView` |
| `api/v1/eval-agent/threads-staging/` | POST | `EvalAgentCreateThreadStagingView` |
| `api/v1/eval-agent/query/<job_id>/` | GET | `EvalAgentQueryStatusView` |
| `api/v1/eval-agent/deep-engineer/threads/<thread_id>/runs/` | POST | `DeepEngineerRunCreateView` |
| `api/v1/eval-agent/deep-engineer/threads-staging/<thread_id>/runs/` | POST | `DeepEngineerRunCreateStagingView` |
| `api/v1/eval-agent/deep-engineer/threads/<thread_id>/runs/<run_id>/stream/` | GET (SSE) | `DeepEngineerRunStreamView` |
| `api/v1/eval-agent/deep-engineer/threads-staging/<thread_id>/runs/<run_id>/stream/` | GET (SSE) | `DeepEngineerRunStreamStagingView` |
| `api/v1/eval-agent/deep-engineer/threads/<thread_id>/runs/<run_id>/cancel/` | POST | `DeepEngineerRunCancelView` |
| `api/v1/eval-agent/deep-engineer/threads-staging/.../cancel/` | POST | `DeepEngineerRunCancelStagingView` |
| `api/v1/eval-agent/artifacts/` | GET | `EvalAgentArtifactsView` |
| `api/v1/eval-agent/artifacts-staging/` | GET | `EvalAgentArtifactsStagingView` |
| `api/v1/eval-agent/sessions/<session_id>/export/` | POST | `EvalAgentExportReportView` — **disabled (returns 503)** |
| `api/v1/eval-agent/models/` | GET | `EvalAgentModelsView` |
| `api/v1/eval-agent/settings/` | GET | `EvaSettingsView` |
| `api/v1/eval-agent/file-content/` | GET | `EvaFileContentView` (with `?path=`) |
| `api/v1/eval-agent/conversations/` | GET | `EvalAgentConversationsView` (with `?time_range=`) |
| `api/v1/eval-agent/conversations-staging/` | GET | `EvalAgentConversationsStagingView` |
| `api/v1/eval-agent/conversations/<conversation_id>/` | GET | `EvalAgentConversationDetailView` |
| `api/v1/eval-agent/conversations-staging/<conversation_id>/` | GET | `EvalAgentConversationDetailStagingView` |

---

## P. Prefect runners (`prefect_app/eva_investigations/`)

### `flows.py`
- `@flow process_eva_investigation_mention_flow(payload, request_meta=None)` — Slack handler.
- `@flow process_eva_customer_feedback_flow(feedback_id, feedback_message_id=None, env=None)`.
- `@flow process_eva_technical_issue_flow(call_insight_id, call_id, env=None)`.
- `@flow process_eva_query_flow(query, context=None, thread_id=None, location_id=None, model=None, env=None, uploaded_artifacts=None)`.
- `@flow process_eva_brain_curator_flow(handoff_payload, model=None, debug=False, langsmith_*)`.

Helpers: `_rename_current_flow_run(*, flow_name, thread_id, run_name_kind)`, `_current_flow_run_id()`.

### `deployments.py`
Constants for flow names and deployment names. Submission helpers:
- `submit_eva_investigation_deployment(flow_name, deployment_name, parameters, ...)` — generic.
- `submit_eva_query_deployment(...)` — manual query.
- `submit_eva_customer_feedback_deployment(...)`.
- `submit_eva_technical_issue_deployment(...)`.
- `submit_eva_brain_curator_deployment(...)`.
- `submit_eva_investigation_mention_deployment(...)` — Slack.
- `eva_flow_run_name(*, kind, thread_id) -> str`.
- `deployment_full_name(*, flow_name, deployment_name) -> str`.

### `runners/eva.py`
End-to-end pipeline bodies called by each flow:
- `run_slack_app_mention(*, payload, request_meta, on_eval_thread_resolved)` — Slack flow body.
- `run_query_investigation(*, query, context, thread_id, location_id, model, env, uploaded_artifacts, flow_run_id)`.
- `run_customer_feedback_investigation(*, feedback_id, feedback_message_id, env)`.
- `run_technical_issue_investigation(*, call_insight_id, call_id, env)`.
- `_run_investigation_inline(*, query, eval_context, eval_thread_id, routing_metadata, effective_env) -> dict` — Branches on `EvalAgentConfig.USE_DEEP_ENGINEER_FOR_INVESTIGATION`.
- `_run_deep_engineer_inline(*, query, context, location_id, organization_id, thread_id, model, langsmith_metadata, effective_env, uploaded_artifacts, task_id)`.
- `_update_slack_with_result(*, eval_result, channel, message_ts, eval_thread_id, slack_user_query, slack_env, effective_env)`.
- `_prepare_conversation(*, conversation, title, query, write_alias)`.
- `_load_query_conversation(*, thread_id, write_alias)`.
- `_build_query_context(*, conversation, initial_context, model_name)`.

Locks (Django-cache mutex with TTL):
- `feedback_eva:lock:<feedback_id>` (TTL `FEEDBACK_EVA_LOCK_TTL`).
- `call_insight_eva:lock:<call_insight_id>` (TTL `CALL_INSIGHT_EVA_LOCK_TTL`).

---

## Q. Misc utilities

### `report_document.py` (currently unused)
- `compile_findings_report_to_pdf(markdown_report, title="Investigation Report") -> bytes` — Uses `xhtml2pdf.pisa.CreatePDF`.
- `_markdown_to_html(md) -> str` — Custom md→html (headings, bold, tables, lists, code fences, blockquotes, hr).
