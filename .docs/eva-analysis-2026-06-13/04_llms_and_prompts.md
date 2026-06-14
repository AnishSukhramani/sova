# 04 — LLMs and Prompts

Every LLM call site in Eva, with provider, model string, role, prompt source, inference parameters, structured output schema, and response parsing. Prompt bodies are in `admin_app/services/eval_agent/prompts.py` (2,398 lines) and `chatbot/prompts.py`.

---

## Models in use (verbatim strings sent to the SDK)

From `EvalAgentConfig` (`config.py`):

```python
AVAILABLE_MODELS = [
    {"id": "claude-opus-4-5-20251101",   "name": "Claude Opus 4.5",  "is_default": False},
    {"id": "claude-haiku-4-5-20251001",  "name": "Claude Haiku 4.5", "is_default": True},
    {"id": "claude-sonnet-4-5-20250929", "name": "Claude Sonnet 4.5","is_default": False},
    {"id": "claude-sonnet-4-6",          "name": "Claude Sonnet 4.6","is_default": False},
]
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
ROUTING_MODEL = "claude-haiku-4-5-20251001"
DEEP_ENGINEER_MODEL = "claude-sonnet-4-6"
DEEP_ENGINEER_OPENAI_MODEL = "gpt-5.4"           # fallback provider; not used by default
DEEP_ENGINEER_RUBRIC_MODEL = "claude-haiku-4-5-20251001"
SLACK_DEFAULT_MODEL = "claude-sonnet-4-6"        # (constant in runners/eva.py)
```

The model strings are passed verbatim to `ChatAnthropic(model=...)`. They appear to be internal-codename identifiers; Anthropic SDK accepts arbitrary model strings and the system mapping resolves them.

---

## Common parameters

| Setting | Default value | Source |
|---|---|---|
| Temperature | 0.3 | `EvalAgentConfig.TEMPERATURE` |
| Max tokens | 4096 | `EvalAgentConfig.MAX_TOKENS` |
| Tool timeout | 60s | `EvalAgentConfig.TOOL_TIMEOUT` |
| Query timeout (DB) | 30s | `EvalAgentConfig.QUERY_TIMEOUT` |
| MAX_MESSAGES_BEFORE_SUMMARIZE | 15 | chatbot turn cap |
| KEEP_RECENT_MESSAGES | 5 | chatbot summary keeps last N |
| MAX_FINDINGS_SUMMARIES | 10 | BI deep-search cap |
| MAX_SCHEMA_CHARS | 3000 | prompt schema-truncate cap |
| MAX_KNOWLEDGE_PROMPT_CHARS | 12000 | mandatory_knowledge cap |
| MAX_FINDINGS_MD_CHARS | 25000 | findings markdown cap for report LLM |
| MAX_FINDINGS_CHUNKS | 5 | findings chunks cap before report |
| ROUTER_PRIOR_CONTEXT_FULL_MAX_CHARS | 38000 | router thread context cap |
| ROUTER_PRIOR_SUMMARY_INPUT_MAX_CHARS | 150000 | router summarizer input cap |
| MODE_SWITCH_CONTEXT_FULL_MAX_CHARS | 48000 | mode-switch context cap |
| MODE_SWITCH_SUMMARY_INPUT_MAX_CHARS | 150000 | mode-switch summarizer input cap |
| Chatbot recursion limit | 25 | `CHATBOT_RECURSION_LIMIT` |
| Chatbot message trim window | 32 | `CHATBOT_MESSAGE_TRIM_WINDOW` |
| Deep-engineer recursion limit | 1000 | `DEEP_ENGINEER_RECURSION_LIMIT` |
| Deep-engineer model call limit | 50 | `DEEP_ENGINEER_MODEL_CALL_RUN_LIMIT` |
| Deep-engineer tool call limit | 200 | `DEEP_ENGINEER_TOOL_CALL_RUN_LIMIT` |
| Deep-engineer Celery time limit | 900s (15 min) hard / 840s (14 min) soft | `DEEP_ENGINEER_CELERY_*` |
| SRE single-loop max rounds | 30 | `MAX_SRE_TOOL_ROUNDS` |
| SRE tier ReAct turns | 25 | `MAX_TIER_REACT_TURNS` |
| SRE code exploration tokens | 180000 | `MAX_CODE_EXPLORATION_TOKENS` |
| SRE message trim window | 32 | `SRE_MESSAGE_TRIM_WINDOW` |
| Multi-agent max handoffs | 3 | `MAX_HANDOFFS` (multi_agent.py) |
| Confidence thresholds | High≥500, Moderate≥100, Low<100 | `HIGH_CONFIDENCE_THRESHOLD`, `MODERATE_CONFIDENCE_THRESHOLD` |
| API rate limit | 10/min/user | `API_RATE_LIMIT` |
| Async task timeout | 300s (5 min) | `ASYNC_TASK_TIMEOUT` |

---

## Call sites — one row per location

### A. Mode routing (entry point classifier)

| Field | Value |
|---|---|
| File | `mode_router.py::plan_eval_agent_dispatch` |
| Model | `ROUTING_MODEL = claude-haiku-4-5-20251001` |
| Temperature | 0 |
| Max tokens | 1024 |
| Timeout | 60s |
| Structured output | `ModeRoutingDecision` (Pydantic: `route` ∈ {chatbot, deep_search_bi, deep_search_sre, deep_search_multi}, `reason`, `confidence`, `signals`) |
| Prompt | `QUERY_MODE_ROUTING_PROMPT` (in `prompts.py`) — a long instruction asking the LLM to classify the user's query as chatbot / deep_search_{bi,sre,multi} based on call-id presence, codebase intent, BI vs SRE shape, etc. |
| Response parsing | Returns `decision.route` → maps to `EvalAgentDispatchPlan(use_deep_search, BI, SRE, routed_mode, routing_reason, router_model)`. Falls back to `chatbot` if LLM fails. |
| Notes | Receives prior conversation context via `build_mode_router_conversation_block` (full verbatim if under 38k chars, else LLM-summarized). |

### B. Mode-switch summarization

| Field | Value |
|---|---|
| File | `utils.py::_summarize_transcript_for_mode_switch` |
| Model | `EvalAgentConfig.DEFAULT_MODEL` (Haiku) |
| Temperature | 0.15 |
| Max tokens | 6000 |
| Structured output | None |
| Prompt | Inline — instructs the LLM to summarize the full thread preserving chronology, every user goal, investigation sections, identifiers (call ids with `@`, UUIDs, URLs, error strings), and open threads. Target 700-1800 words. |
| Trigger | Mode-switch context exceeds `MODE_SWITCH_CONTEXT_FULL_MAX_CHARS = 48000`. |
| Notes | Called by `build_mode_switch_context_for_llm`. |

### C. Router context summarization

| Field | Value |
|---|---|
| File | `utils.py::_summarize_text_for_mode_router` |
| Model | `EvalAgentConfig.ROUTING_MODEL` (Haiku) |
| Temperature | 0.1 |
| Max tokens | 2500 |
| Structured output | None |
| Prompt | Inline — preserves call ids (including `@`-style), UUIDs, error strings, metric names. Targets 400-900 words. |
| Trigger | Thread or supplemental context exceeds `ROUTER_PRIOR_CONTEXT_FULL_MAX_CHARS = 38000`. |

### D. Partial-report synthesis (recursion-limit recovery)

| Field | Value |
|---|---|
| File | `utils.py::synthesize_partial_report` (called by BI agent and SRE agent on `GraphRecursionError`) |
| Model | Agent's own LLM (`self.llm`) |
| Prompt | `PARTIAL_REPORT_PROMPT` — Markdown report acknowledging step-limit truncation. SRE variant adopts the "INVESTIGATION REPORT (Partial)" shape with Header table, TL;DR, Evidence. |
| Structured output | None |

### E. Chatbot partial reply

| Field | Value |
|---|---|
| File | `utils.py::synthesize_chatbot_partial_reply` (called by `chatbot/entrypoint.py` on `GraphRecursionError`) |
| Model | `EvalAgentConfig.DEFAULT_MODEL` |
| Temperature | 0.3 (`EvalAgentConfig.TEMPERATURE`) |
| Max tokens | 1024 |
| Timeout | 60s |
| Prompt | `CHATBOT_PARTIAL_REPLY_PROMPT` — explains truncation and suggests switching to Deep Search BI or SRE based on detected skill hint. |

### F. Multi-Agent Supervisor (coordinator)

| Field | Value |
|---|---|
| File | `multi_agent.py::_supervisor_llm_route_async` |
| Model | `ROUTING_MODEL` (Haiku) |
| Temperature | 0 |
| Max tokens | 20 |
| Timeout | 30s |
| Structured output | None — returns one of `{bi, sre, sre_skip_trace, finish}` as raw text |
| Prompt | `SUPERVISOR_PLANNING_PROMPT` (with prompt caching: `cache_control: ephemeral` on system) — full decision tree: handoff count, BI vs SRE shape, last_agent_called. |
| Anti-loop guard | If `handoff_count == 0` and LLM says `finish`, force `bi` instead. Cap at `MAX_HANDOFFS = 3`. |

### G. Multi-Agent Report Merge

| Field | Value |
|---|---|
| File | `multi_agent.py::_merge_reports` |
| Model | Coordinator's `_report_llm` (default model) |
| Temperature | 0.3 |
| Max tokens | 4096 |
| Timeout | 120s |
| Structured output | None |
| Prompt | `MULTI_AGENT_REPORT_PROMPT` (cached via `cache_control: ephemeral`) — merges BI and SRE findings into a unified markdown report. |

### H. BI Agent — `memory_load_node` routing decision

| Field | Value |
|---|---|
| File | `agents/bi_agent.py::_memory_load_node` |
| Model | Agent's `self.llm` (default `DEFAULT_MODEL`) |
| Structured output | `_BIRoutingDecision` (Pydantic: `intent` ∈ {discover, contextualize, cross_validate, clarify}, `reason`) |
| Prompt | `ROUTING_PROMPT` — short intent classifier ("discover" for causes/patterns, "cross_validate" for compare/before-vs-after, "contextualize" for interpret-vs-baseline). |
| Fallback | `self.llm.bind(max_tokens=80).ainvoke(...)` and substring-match the response. |
| Notes | `clarify` is coerced to `discover` (line ~557). |

### I. BI Agent — knowledge answer

| Field | Value |
|---|---|
| File | `agents/bi_agent.py::_knowledge_answer_node` |
| Model | Agent's `self.llm` |
| Structured output | None |
| Prompt | Inline: "Answer the user's question using ONLY the information below. Source type / Title / Content / ..." |
| Trigger | Semantic search hit (cosine similarity ≥ `KNOWLEDGE_HIT_THRESHOLD = 0.75`) against `DatabaseKnowledgeStore`. |

### J. BI Agent — plan generation

| Field | Value |
|---|---|
| File | `agents/bi_agent.py::_plan_generation_node` |
| Model | Agent's `self.llm` |
| Structured output | `BIInvestigationPlanOutput` (`plan: List[InvestigationPlanStep]`) |
| Prompt | `BI_PLAN_GENERATION_PROMPT` + appended task description + memory context + mandatory-knowledge boolean summary + skills_run list. Skills allowed: `{discover, contextualize, cross_validate}`. |

### K. BI Agent — plan revision

| Field | Value |
|---|---|
| File | `agents/bi_agent.py::_revise_plan_bi` |
| Model | Agent's `self.llm` |
| Structured output | `BIInvestigationPlanOutput` |
| Prompt | `BI_PLAN_REVISION_PROMPT.format(plan_summary, latest_finding, query)`. Strict one-direction state machine: completed steps are TERMINAL; never re-add them as pending. |

### L. BI Agent — structured report

| Field | Value |
|---|---|
| File | `agents/bi_agent.py::_build_structured_report` |
| Model | Agent's `self.llm` |
| Structured output | None |
| Prompt | `FINDINGS_REPORT_FORMAT` as system + Human "**Original question:** ... **Investigation findings:** ... Transform the above into a comprehensive markdown report following the Findings Report Format specified in your instructions." |
| Notes | Caps findings to `MAX_FINDINGS_CHUNKS = 5` and `MAX_FINDINGS_MD_CHARS = 25000`. |

### M. BI Skills (Discover, CrossValidate, Contextualize)

Each skill calls `run_llm_with_tools` (in `skills/skill_utils.py`).

| Skill | Prompt | Structured output | Tools available |
|---|---|---|---|
| `DiscoverSkill` | `DISCOVER_PROMPT` (Sample-Pattern-Quantify methodology) | `DiscoverNodeOutput` | DB tools (`list_tables`, `describe_table`, `run_query`, `search_tables`, `get_distinct_values`, `get_table_schema`, `get_table_list`); knowledge tools (`search_knowledge`, `check_faq`, `get_baselines`, `get_investigation_patterns`, `get_file_content`) |
| `CrossValidateSkill` | `CROSS_VALIDATE_PROMPT` (two-source comparison) | `CrossValidateNodeOutput` | Same as Discover |
| `ContextualizeSkill` | `CONTEXTUALIZE_PROMPT` (baseline comparison) | `ContextualizeNodeOutput` | Same as Discover |
| `RememberSkill` | `REMEMBER_PROMPT` (FAQ/BASELINES/KNOWN_ISSUES/INVESTIGATION_PATTERNS update) | None — free-form narrative | `search_knowledge`, `get_file_content`, `update_knowledge`, `add_knowledge`, `update_knowledge_by_id` |

`run_llm_with_tools` parameters:
- `system_prompt` (cached via `cache_control: ephemeral`)
- `max_tool_rounds=3` (BI skills); `max_tool_rounds=5` for `_intake_node`; `max_tool_rounds=25` for tier investigations
- Inline JSON parse first (strip ` ```json ` fences), fallback to `llm.with_structured_output(schema)` for a second pass
- Per-tool execution wrapped in `asyncio.wait_for(timeout=TOOL_TIMEOUT=60s)`

### N. SRE Agent — `_intake_node` (parse call_id + complaint)

| Field | Value |
|---|---|
| File | `agents/sre_agent.py::_intake_node` |
| Model | Agent's `self.llm` (Sonnet default for SRE) |
| Structured output | `InvestigationRequest` |
| Prompt | `SRE_INTAKE_PROMPT.format(query=..., context=...)` — mandates resolving `call_id` (nhapp_retellaicall.id UUID) first via SQL. |
| Tools | `list_tables`, `describe_table`, `run_query` |
| Max tool rounds | 5 |

### O. SRE Agent — Tier 1 & Tier 2 ReAct investigation (LangGraph path)

| Field | Value |
|---|---|
| File | `agents/sre_agent.py::_investigation_node` (mode="tier1" or "tier2") |
| Model | Agent's `self.llm` (`max_tokens=min(4096, EvalAgentConfig.MAX_TOKENS)`) |
| Structured output | `TierInvestigationDecision` (`resolved: bool`, `confidence ∈ {high, medium, low}`, `root_cause: str`, `evidence: List[str]`, `unresolved_threads: List[str]`) |
| Prompt | `SRE_TIER_INVESTIGATION_PROMPT` — different fill for tier1 vs tier2. Tier1 reads the embedded GCP transcript log directly (cap 120k chars); Tier2 receives Tier1's structured decision + notes + unresolved threads. |
| Max tool rounds | 25 (`MAX_TIER_REACT_TURNS`) |
| Tool set | DB (`list_tables`, `describe_table`, `run_query`), codebase (`grep_codebase`, `list_codebase_directories`, `list_codebase_files`), GitHub MCP (`search_code`, `get_file_contents`, `list_commits`, `list_directory`, `list_files`), GCP (`get_gcp_logs_for_call_session`, `get_gcp_logs`, `get_gcp_logs_from_state` (tier1 only)), Twilio (`twilio_fetch_voice_call_debug_tool`, `twilio_fetch_voice_conference_debug_tool`), Inline (`add_investigation_todo`, `list_investigation_todos`, `get_sre_investigation_skill`). Tier 2 also has `trace_exception`. |
| Routing | `_route_after_tier1`: returns `conclude` if `tier1_decision.resolved` else `deep_investigation_node`. |

### P. SRE Agent — single-loop ReAct (the actual public path)

| Field | Value |
|---|---|
| File | `agents/sre_agent.py::run_agent` |
| Model | `self.llm` |
| Structured output | None (free-form final text) |
| Prompt | `SRE_SINGLE_LOOP_SYSTEM_PROMPT` (cached via `cache_control: ephemeral`) + appended `voice_call_debug.md` section when `state.call_debug_skill_markdown` is set + user message from `_build_sre_runtime_user_message` (parsed investigation request, GCP/Langfuse correlation block, prefetched trace, prefetched GCP transcript, non-transcript GCP logs, shared findings). |
| Max tool rounds | 30 (`MAX_SRE_TOOL_ROUNDS`) |
| Tool set | Cached `_build_sre_tools()` + per-state `_build_sre_loop_tools()` (adds `get_prefetched_trace_context`, `get_gcp_logs_from_state`, `get_prefetched_gcp_transcript`, `get_sre_investigation_skill`, `mark_checked`, `add_investigation_todo`, `list_investigation_todos`). |
| Trim window | 32 messages, never starting with orphan ToolMessage. |
| When loop exhausts | `_run_sre_no_tool_synthesis` — final non-tool call instructing the LLM to declare inconclusive with Evidence checked / Remaining unknowns / Next missing evidence. |

### Q. SRE Agent — conclude (LangGraph path)

| Field | Value |
|---|---|
| File | `agents/sre_agent.py::_conclude_node` |
| Model | `self.llm` |
| Structured output | None |
| Prompt | `SRE_CONCLUDE_PROMPT.format(confirmed_root_cause, investigation_request, fetch_history, correlation_history)` — prompt-cached split via `_human_message_with_cache` when the static prefix contains the cache marker placeholder. |
| Notes | Picks `confirmed_root_cause` by precedence: tier1 → tier2 → `plan_update_decision.confirmed_root_cause` → first `CONFIRMED` in `correlation_history` → "No confirmed root cause — investigation inconclusive." |

### R. SRE Agent — hypothesis revision (vestigial code path)

| Field | Value |
|---|---|
| File | `agents/sre_agent.py::_revise_hypotheses_sre` |
| Model | `self.llm` |
| Structured output | inline `HypothesisSet(BaseModel)` with `hypotheses: List[Hypothesis]` |
| Prompt | `SRE_HYPOTHESIS_REVISION_PROMPT.format(complaint_text, hypotheses, evidence_summary, correlation_result)` |
| Status | Called from the commented-out `_correlate_node` — not on the active path. |

### S. Chatbot — every turn

| Field | Value |
|---|---|
| File | `chatbot/entrypoint.py::agent_node` |
| Model | Caller's choice (default `DEFAULT_MODEL` Haiku) |
| Temperature | 0.3 |
| Max tokens | `min(4096, MAX_TOKENS)` |
| Timeout | 90s |
| Structured output | None |
| Prompt | `CHATBOT_SYSTEM_PROMPT` with substitutions: `{current_datetime_utc}`, `{table_list}`, `{row_sample_limit}` (1000 chars), `{accessible_tables}` (`ACCESSIBLE_TABLES_AND_LIMITS_PROMPT`), `{investigation_patterns_reference}` (loaded from `INVESTIGATION_PATTERNS.yaml`, 15-min cache). |
| Tools | DB tools, knowledge tools (without `search_tables`), Langfuse `get_langfuse_session_call_logs_tool`, GCP `get_gcp_logs_tool`, GitHub MCP (`search_code`, `get_file_contents`, `list_directory`, `list_commits`), `grep_codebase`, `get_call_debug_context` (voice_call_debug.md), and `write_todos`. |
| Recursion limit | 25 |
| Message trim | 32 (`CHATBOT_MESSAGE_TRIM_WINDOW`), never starting with orphan ToolMessage |
| Persistence | AsyncPostgresSaver keyed on `thread_id` |

---

## Prompt files — what each one is

The prompts are defined in two files. Below is a one-line summary of each named prompt constant.

### `admin_app/services/eval_agent/prompts.py`

- `DATABASE_TOOLS` — text block describing read-only DB tools (`list_tables`, `describe_table`, `run_query`); injected into many skill prompts.
- `KNOWLEDGE_TOOLS` — text block describing knowledge tools (`get_table_schema`, `get_baselines`, `get_investigation_patterns`, `search_knowledge`, `check_faq`).
- `CONFIDENCE_LEVELS` — text block defining High/Moderate/Low confidence thresholds (n>500, 100-500, <100).
- `CRITICAL_STEPS` — "MANDATORY: follow steps exactly, in order. Use tools only. Never fabricate or assume data."
- `ROUTING_PROMPT` — BI intent classifier (discover | contextualize | cross_validate).
- `DISCOVER_PROMPT` — Sample-Pattern-Quantify methodology with strict JSON output schema (`DiscoverNodeOutput`).
- `CROSS_VALIDATE_PROMPT` — two-method comparison with discrepancy interpretation.
- `CONTEXTUALIZE_PROMPT` — baseline comparison cheat sheet (22% negative on failures, 61% l1_pass, etc.).
- `REMEMBER_PROMPT` — knowledge base updater (classify → check coverage → update/append/add new).
- `FINDINGS_REPORT_FORMAT` — executive summary, key finding, confidence, methodology, supporting data, caveats.
- `CALL_TRACES_PROMPT` — instruction for `get_langfuse_session_call_logs`: when to use, when not to, age constraint (≥30 min).
- `COORDINATOR_ROUTING_PROMPT` — single-word classifier "bi | sre | both" (legacy, not currently in use).
- `MULTI_AGENT_REPORT_PROMPT` — BI + SRE findings merge instructions.
- `QUERY_MODE_ROUTING_PROMPT` — top-level mode router (chatbot | deep_search_{bi,sre,multi}) with strict JSON output (`ModeRoutingDecision`).
- `SUPERVISOR_PLANNING_PROMPT` — coordinator decision tree (bi | sre | sre_skip_trace | finish).
- `BI_PLAN_GENERATION_PROMPT` — BI investigation plan (which skills, in what order).
- `BI_PLAN_REVISION_PROMPT` — strict state machine (completed → terminal).
- `SRE_INTAKE_PROMPT` — resolves call_id via SQL first, then extracts rest.
- `SRE_FETCH_DB_PROMPT` — fetch DB evidence for a hypothesis (vestigial).
- `SRE_TRANSCRIPT_READ_PROMPT` — analyze the full call transcript log (vestigial).
- `SRE_TRACE_READ_PROMPT` — observability analysis combining Langfuse + GCP (vestigial).
- `SRE_HYPOTHESIZE_PROMPT` — generate 2-3 falsifiable hypotheses (vestigial).
- `SRE_PLAN_PROMPT` — translate hypotheses into FetchPlan (db/langfuse/code tasks) (vestigial).
- `SRE_CORRELATE_PROMPT` — belief updater (CONFIRMED/REFUTED/INSUFFICIENT verdicts) (vestigial).
- `SRE_PLAN_UPDATE_PROMPT` — CONCLUDE/FETCH_MORE/PIVOT/ESCALATE decision (vestigial).
- `SRE_CONCLUDE_PROMPT` — final investigation report with Header, TL;DR, What Happened, What Went Wrong (Step by Step), Evidence, Suggested Fixes.
- `SRE_CODE_EXPLORER_PROMPT` — code-exploration helper.
- `SRE_TIER_INVESTIGATION_PROMPT` — tier-1 and tier-2 ReAct system prompt with strict JSON output (`TierInvestigationDecision`).
- `SRE_SINGLE_LOOP_SYSTEM_PROMPT` — single-loop ReAct system prompt (the live SRE path).
- `SRE_HYPOTHESIS_REVISION_PROMPT` — refine hypothesis set after correlation (vestigial).

(The SRE_TIER and SRE_SINGLE_LOOP prompts are post-processed to inject `SRE_INVESTIGATION_SKILLS_PROMPT_SECTION` — a dynamic block describing the available investigation playbooks (`general_skill`, `voice_call_debug`, `sms_chat_debug`, `web_scheduler`).)

### `admin_app/services/eval_agent/chatbot/prompts.py`

- `CHATBOT_SYSTEM_PROMPT` — chatbot system instructions (skills BI vs technical, tool guidance, mode-switch hint to suggest Deep Search when appropriate).
- `ACCESSIBLE_TABLES_AND_LIMITS_PROMPT` — DB table list + SQL LIMIT rules.
- `BI_SKILL_PROMPT` — BI skill instructions for chatbot (when to do simple count vs suggest deep search).
- `TECHNICAL_SKILL_PROMPT` — technical/SRE skill instructions for chatbot.
- (Helper file `chatbot/utils.py` defines `SKILL_REGISTRY = {"bi": BI_SKILL_PROMPT, "technical": TECHNICAL_SKILL_PROMPT}` and `get_skill(name)`.)

### `admin_app/services/eval_agent/utils.py`

- `CHATBOT_PARTIAL_REPLY_PROMPT` — used when chatbot hits recursion limit; instructs LLM to acknowledge truncation and suggest Deep Search.
- `PARTIAL_REPORT_PROMPT` — used when BI or SRE hit recursion limit; renders a partial markdown report.

### Inline prompts (defined in agent code)

- `_summarize_transcript_for_mode_switch` — long handoff-summary instruction (700-1800 words).
- `_summarize_text_for_mode_router` — short summarization instruction (400-900 words) for router.
- `_BIRoutingDecision`, `_BIClarifyResponse` — Pydantic schemas used as structured outputs at routing time (not prompts).
- `_run_sre_no_tool_synthesis` — final-round synthesis prompt forcing no-tool inconclusive answer.

---

## Anthropic prompt caching usage

Eva uses `cache_control: {"type": "ephemeral"}` on prompt blocks in these places (saves ~90% cost on repeated multi-round calls):

1. `multi_agent.py::_supervisor_llm_route_async` — system message wraps `SUPERVISOR_PLANNING_PROMPT`.
2. `multi_agent.py::_merge_reports` — system message wraps `MULTI_AGENT_REPORT_PROMPT`.
3. `agents/sre_agent.py::run_agent` — system message wraps `SRE_SINGLE_LOOP_SYSTEM_PROMPT` + appended skill markdown.
4. `agents/sre_agent.py::_conclude_node` — split via `_human_message_with_cache(static_text, dynamic_text)` when the static prefix contains the cache marker.
5. `skills/skill_utils.py::run_llm_with_tools` — system prompt block in the ReAct loop.

BI agent does **not** appear to use prompt caching.

---

## Response parsing patterns

- **JSON inline first.** `run_llm_with_tools` strips ` ```json ` fences from the final assistant message and tries `json.loads`. If valid, validates against `structured_output_schema`. Saves a round trip vs `with_structured_output`.
- **`with_structured_output` fallback.** If inline JSON parse fails or LLM didn't return JSON, makes a second LLM call with structured-output binding.
- **Free-form text.** Used for reports (BI report, SRE conclude, multi-agent merge) — returned as markdown directly.
- **Single-word.** Supervisor returns one of `{bi, sre, sre_skip_trace, finish}` as plain text; coerced via substring match.
- **Tool-call-bearing AIMessage.** All ReAct loops detect `last_message.tool_calls` and dispatch.
