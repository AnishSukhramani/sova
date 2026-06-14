# 08 — Data Schemas and Models

Every data model, schema, type, and interface in Eva.

---

## A. Pydantic state schemas (`admin_app/services/eval_agent/models.py`)

### `ConfidenceLevel(str, Enum)`
- Values: `HIGH = "High"`, `MODERATE = "Moderate"`, `LOW = "Low"`.

### `BIQueryRequest(BaseModel)`
| Field | Type | Required | Description |
|---|---|---|---|
| `query` | `str` | ✓ | The BI question |
| `context` | `Optional[str]` | — | Additional context |
| `location_id` | `Optional[Union[int, str]]` | — | Specific location |
| `time_window` | `Optional[str]` | — | Default `"30 days"` |

Validator: `_coerce_location_id` accepts int/str/UUID.

### `BIQueryResponse(BaseModel)`
| Field | Type | Description |
|---|---|---|
| `finding` | `str` | Main finding/insight |
| `confidence` | `ConfidenceLevel` | High/Moderate/Low |
| `methods` | `str` | Methods used |
| `supporting_data` | `Dict[str, Any]` | Tables/metrics |
| `validation_approaches` | `List[str]` | Suggested validations |
| `caveats` | `List[str]` | Limitations |
| `sample_size` | `Optional[int]` | n |
| `time_period` | `Optional[str]` | Time period analyzed |

### `MandatoryKnowledge(BaseModel)`
| Field | Type | Description |
|---|---|---|
| `faq_checked` | `bool` | Default True |
| `investigation_patterns` | `str` | YAML content (formatted) |
| `baselines` | `str` | Metric benchmarks |
| `known_issues` | `str` | Known data issues |

Note: `schema_content` is commented out — agents now call `get_table_schema()` on demand.

### `FindingSummary(BaseModel)`
| Field | Type | Description |
|---|---|---|
| `node_name` | `str` | discover/cross_validate/contextualize |
| `key_insights` | `List[str]` | max_length=10 |
| `confidence` | `str` | High/Moderate/Low |

### `RoutingPlanStep(BaseModel)`
| Field | Type | Description |
|---|---|---|
| `agent` | `Literal["bi", "sre"]` | Which agent |
| `task` | `str` | Task assigned |
| `status` | `Literal["pending", "in_progress", "completed"]` | |
| `findings` | `Optional[str]` | Result |

### `InvestigationPlanStep(BaseModel)`
| Field | Type | Description |
|---|---|---|
| `skill` | `str` | discover/contextualize/cross_validate/etc. |
| `goal` | `str` | What this should accomplish |
| `status` | `Literal["pending", "in_progress", "completed"]` | |
| `finding` | `Optional[str]` | Skill output summary |

### `BIInvestigationPlanOutput(BaseModel)` (structured LLM output)
- `plan: List[InvestigationPlanStep]` (min_length=1).

### `TriageOutput(BaseModel)`
| Field | Type | Description |
|---|---|---|
| `location_id` | `Optional[str]` | |
| `component` | `Optional[str]` | |
| `symptom` | `Optional[str]` | |
| `needs_bi` | `bool` | Default False |

### `SRETriageOutput(BaseModel)` (legacy structured output)
- `triage: TriageOutput`
- `plan: List[InvestigationPlanStep]` (min_length=1; final step should be "correlate")

### `AgentState(BaseModel)` — **BI agent state**
| Field | Type | Description |
|---|---|---|
| `session_id` | `Optional[str]` | UUID |
| `query` | `str` | |
| `context` | `Optional[str]` | |
| `location_id` | `Optional[Union[int, str]]` | |
| `location_name` | `Optional[str]` | |
| `organization_id` | `Optional[Union[int, str]]` | |
| `organization_name` | `Optional[str]` | |
| `time_window` | `str` | Default `"30 days"` |
| `findings` | `List[Any]` | Append-only |
| `final_response` | `Optional[BIQueryResponse]` | Early-exit FAQ/knowledge response |
| `findings_report` | `Optional[str]` | Markdown report |
| `knowledge_hit` | `bool` | |
| `knowledge_item` | `Optional[Dict[str, Any]]` | KnowledgeItem as dict |
| `mandatory_knowledge_loaded` | `bool` | |
| `faq_hit` | `bool` | |
| `current_intent` | `Optional[str]` | discover/cross_validate/contextualize/clarify |
| `pending_intent` | `Optional[str]` | |
| `routing_reason` | `Optional[str]` | LLM's explanation |
| `skills_run` | `List[str]` | Append-only |
| `bi_memory_context` | `Optional[str]` | (Mem0; currently empty) |
| `bi_investigation_plan` | `List[InvestigationPlanStep]` | |
| `bi_plan_index` | `int` | Default 0 |
| `conclusion_confidence` | `Optional[str]` | High/Moderate/Low |

### `DatabaseQueryResult(BaseModel)`
- `query`, `results: List[Dict[str, Any]]`, `row_count: int`, `execution_time: float`, `columns: List[str]`.

### `KnowledgeSearchResult(BaseModel)`
- `query`, `results: List[Dict[str, str]]`, `relevance_scores: List[float]`.

### `SkillResult(BaseModel)`
- `skill_name`, `input_query`, `findings: List[str]`, `data: Dict[str, Any]`, `confidence: ConfidenceLevel`, `next_steps: List[str]`, `suggested_next_skill: Optional[str]`.

### `DiscoverCategory(BaseModel)`
- `name`, `keywords: List[str]`, `count: Union[int, float]`, `pct: Union[int, float]`, `type: Literal["actionable", "structural", "unclear"]`.

### `DiscoverData(BaseModel)`
- `categories: List[DiscoverCategory]`.

### `DiscoverNodeOutput(BaseModel)` (structured LLM output)
- `node: Literal["discover"] = "discover"`
- `summary: Dict[str, str]` (must include `key_finding`)
- `metrics: Dict[str, Optional[Union[int, float]]]` (population_size, sample_size, iterations, other_unclear_pct)
- `methods: Dict[str, str]` (population_filter, time_window, pattern_strategy)
- `data: DiscoverData`
- `insights: List[str]`, `alternative_validations: List[str]`, `confidence: Literal["High","Moderate","Low"]`, `caveats: List[str]`
- `suggested_next_skill: Optional[str]`
- `resolved_location_id`, `resolved_location_name`, `resolved_organization_id`, `resolved_organization_name`.

### `CrossValidateMethod(BaseModel)`
- `name` ("Method A" / "Method B"), `approach: Literal["structured_field", "transcript", "alternative"]`, `description`, `count`, `rate`.

### `CrossValidateNodeOutput(BaseModel)` (structured LLM output)
- Same shape as DiscoverNodeOutput but: `node: "cross_validate"`, `metric_definition: str`, `methods: List[CrossValidateMethod]`, metrics include `discrepancy_ratio`, `difference_pct`, `sample_size_a`, `sample_size_b`.

### `ContextualizeNodeOutput(BaseModel)` (structured LLM output)
- `node: "contextualize"`, `metric_name`, metrics include `value`, `baseline`, `delta`, `ratio`, `sample_size`, `interpretation: Literal["better", "worse", "typical"]`.

### `SREFindings(BaseModel)`
- `langfuse_samples: List[Dict[str, Any]]`, `code_patterns: List[Dict[str, Any]]`, `summary: str`.

### `InvestigationRequest(BaseModel)` (structured LLM output, SRE intake)
| Field | Type | Description |
|---|---|---|
| `call_id` | `str` | UUID (nhapp_retellaicall.id) or empty string |
| `caller_phone_number` | `Optional[str]` | E.164, enrichment-set |
| `retell_call_id` | `Optional[str]` | External Retell id |
| `org_id` | `Optional[str]` | |
| `location_id` | `Optional[str]` | |
| `location_name` | `Optional[str]` | |
| `organization_name` | `Optional[str]` | |
| `complaint_text` | `str` | Core complaint |
| `patient_details` | `Optional[str]` | |

### `TurnNode(BaseModel)` (call turn analysis)
- `turn_index: int`, `role: str`, `content: str`, `tool_calls: List[Dict[str, Any]]`, `latency_ms: Optional[float]`, `anomalies: List[str]`.

### `CallBehavior(BaseModel)`
- `tool_sequences`, `tool_params`, `tool_results`, `loops_detected`, `gave_up_turns`.

### `FlowViolation(BaseModel)`
- `flow_name`, `violation_type: str` (missing_tool/wrong_order/missing_param/unexpected_continuation), `description`, `turn_index`, `severity: str` (low/medium/high).

### `Hypothesis(BaseModel)`
- `id` (e.g. H1), `statement` (technical), `issue_layer: str` (data/logic/infra/llm), `confirmed_by`, `refuted_by`, `requires: str` (db/langfuse/code), `confidence: float (0-1)`.

### `FetchTask(BaseModel)`
- `hypothesis_id`, `task_type: str` (db/langfuse/code), `task_id: Optional[str]`, `description`, `tables_hint`, `query_intent`, `span_names`, `filter_criteria`, `symbol_hint`, `reason`, `exception_class`, `depends_on`.

### `FetchPlan(BaseModel)`
- `db_queries: List[FetchTask]`, `langfuse_tasks: List[FetchTask]`, `code_tasks: List[FetchTask]`.

### `HypothesisEvaluation(BaseModel)`
- `hypothesis_id`, `verdict: str` (CONFIRMED/REFUTED/INSUFFICIENT), `evidence_citation`, `causal_explanation`, `new_hypothesis: Optional[str]`.

### `CorrelationResult(BaseModel)` (structured LLM output)
- `evaluations: List[HypothesisEvaluation]`, `unexpected_findings: List[str]`, `emerging_signal: Optional[str]`, `updated_hypotheses: Optional[List[Hypothesis]]`.
- Validators coerce stringified JSON lists into Python lists.

### `PlanUpdateDecision(BaseModel)` (structured LLM output)
- `decision: str` (CONCLUDE/FETCH_MORE/PIVOT/ESCALATE), `confirmed_root_cause`, `open_questions`, `new_hypotheses`, `escalation_reason`, `iteration_summary`.

### `TranscriptReadSummary(BaseModel)` (structured LLM output, vestigial)
- `action_timeline: str`, `notable_errors_or_warnings: str`, `caller_intent_and_outcome: str`.

### `TraceFailureAnalysis(BaseModel)` (structured LLM output, vestigial)
- `failure_turn_index`, `failure_node`, `failure_type`, `failure_evidence`, `failure_input`, `failure_output`, `primary_violation`, `preceding_nodes`, `secondary_anomalies`.

### `TierInvestigationDecision(BaseModel)` (the **live** SRE structured output)
| Field | Type | Description |
|---|---|---|
| `resolved` | `bool` | Default False |
| `confidence` | `Literal["high", "medium", "low"]` | |
| `root_cause` | `str` | |
| `evidence` | `List[str]` | Each entry follows format `Transcript:`, `Code:`, or `Log:` |
| `unresolved_threads` | `List[str]` | Each entry: `<question> | Missing: <evidence> | Next step: <action>` |

### `MultiAgentState(BaseModel)` — **multi-agent coordinator state**
| Field | Type | Description |
|---|---|---|
| `session_id` | `Optional[str]` | |
| `query` | `str` | |
| `context` | `Optional[str]` | |
| `location_id` | `Optional[Union[int, str]]` | |
| `location_name` | `Optional[str]` | |
| `organization_id` | `Optional[Union[int, str]]` | |
| `organization_name` | `Optional[str]` | |
| `time_window` | `str` | Default `"30 days"` |
| `shared_findings` | `List[str]` | Append-only blackboard, each entry tagged `[BI]\n...` or `[SRE]\n...` |
| `active_agent` | `Optional[str]` | `"bi"` / `"sre"` / None |
| `last_agent_called` | `Optional[str]` | |
| `handoff_count` | `int` | Default 0; cap `MAX_HANDOFFS = 3` |
| `handoff_reason` | `Optional[str]` | |
| `bi_only` | `bool` | API override |
| `sre_only` | `bool` | API override |
| `sre_skip_trace` | `bool` | Direct hypothesize path |
| `bi_findings` | `Optional[str]` | Last BI report |
| `sre_findings` | `Optional[str]` | Last SRE report |
| `final_report` | `Optional[str]` | Merged result |
| `mem0_bi_context` | `Optional[str]` | Disabled |
| `mem0_sre_context` | `Optional[str]` | Disabled |
| `routing_plan` | `List[RoutingPlanStep]` | |
| `routing_index` | `int` | Default 0 |

### `SREAgentState(BaseModel)` — **SRE agent state**
Massive struct. Key fields:

| Section | Field | Type | Description |
|---|---|---|---|
| **Base** | `session_id` | `Optional[str]` | |
| | `query` | `str` | |
| | `context` | `Optional[str]` | |
| | `location_id` | `Optional[Union[int, str]]` | |
| | `time_window` | `str` | Default `"30 days"` |
| | `shared_findings` | `List[str]` | |
| | `skip_trace_path` | `bool` | If True, skip intake→call_trace→trace_read |
| **Intake** | `investigation_request` | `Optional[InvestigationRequest]` | |
| **Trace** | `turn_tree` | `List[TurnNode]` | |
| | `call_behavior` | `Optional[CallBehavior]` | |
| | `formatted_trace` | `str` | ~800-token timeline |
| | `raw_observation_count` | `int` | |
| | `cached_trace_call_id` | `Optional[str]` | |
| | `cached_trace_formatted` | `Optional[str]` | |
| **GCP** | `formatted_gcp_logs` | `str` | LiveKit Cloud Run logs |
| | `gcp_transcript_log` | `str` | Full textPayload of Transcript line (not truncated) |
| **Context** | `call_debug_skill_markdown` | `str` | voice_call_debug.md prefetch |
| | `past_cases` | `List[Dict[str, Any]]` | (Mem0; disabled) |
| | `component_tags` | `List[str]` | |
| | `investigation_start` | `str` | db/langfuse/code |
| **Vestigial** | `transcript_read_summary` | `Optional[TranscriptReadSummary]` | |
| | `trace_failure_analysis` | `Optional[TraceFailureAnalysis]` | |
| | `code_context` | `str` | |
| **Tiered (live)** | `tier1_decision` | `Optional[TierInvestigationDecision]` | |
| | `tier2_decision` | `Optional[TierInvestigationDecision]` | |
| | `tier1_notes` | `str` | |
| | `tier2_notes` | `str` | |
| | `tier1_todos` | `List[str]` | |
| | `tier2_todos` | `List[str]` | |
| **Hypotheses (vestigial)** | `hypotheses` | `List[Hypothesis]` | |
| | `iteration` | `int` | Default 0 |
| | `fetch_plan` | `Optional[FetchPlan]` | |
| | `fetch_results` | `Dict[str, Any]` | |
| | `fetch_history` | `List[Dict[str, Any]]` | |
| | `correlation_result` | `Optional[CorrelationResult]` | |
| | `correlation_history` | `List[CorrelationResult]` | |
| | `plan_update_decision` | `Optional[PlanUpdateDecision]` | |
| **Output** | `final_package` | `Optional[str]` | Final SRE report |
| | `conclusion_confidence` | `Optional[str]` | HIGH/MEDIUM/LOW |
| **Memory** | `sre_memory_context` | `Optional[str]` | Disabled |
| **Compat** | `triage_output` | `Optional[TriageOutput]` | Legacy |

---

## B. Pydantic schemas (other files)

### `mode_router.py`

#### `ModeRoutingDecision(BaseModel)` (structured LLM output)
- `route: Literal["chatbot", "deep_search_bi", "deep_search_sre", "deep_search_multi"]`
- `reason: str` (min_length=10)
- `confidence: float` (0..1, default 0.8)
- `signals: List[str]`

#### `@dataclass EvalAgentDispatchPlan` (frozen)
- `use_deep_search: bool`
- `BI: bool`
- `SRE: bool`
- `routed_mode: str`
- `routing_reason: str`
- `router_model: str`
- Method: `routing_metadata() -> dict[str, Any]`

### `agents/bi_agent.py`

#### `_BIRoutingDecision(BaseModel)` (structured LLM output)
- `intent: str` ("discover" / "contextualize" / "cross_validate" / "clarify")
- `reason: str`

#### `_BIClarifyResponse(BaseModel)` (currently unused; clarify is coerced to discover)
- `best_effort_answer: str`
- `missing_info: List[str]`
- `follow_up_questions: List[str]`

### `agents/sre_agent.py`

#### `@dataclass AgentResponse`
- `final_text: str`
- `tool_rounds: int`
- `checked_items: List[str]`
- `inconclusive: bool`
- `error: Optional[str]`

#### Inline `HypothesisSet(BaseModel)` (structured output for `_revise_hypotheses_sre`, vestigial)
- `hypotheses: List[Hypothesis]` (min_length=1)

### `tools/twilio_tools.py`

#### `@dataclass TwilioToolResult`
- `ok: bool`
- `input_sid: str`
- `input_type: Literal["call", "conference", "unknown"]`
- `data: dict[str, Any]`
- `error: Optional[str]`

### `knowledge/store.py`

#### `KnowledgeType = Literal["faq", "db_schema", "known_issue", "investigation_pattern", "baseline"]`

#### `@dataclass KnowledgeItem`
- `id: str`
- `type: KnowledgeType`
- `title: str`
- `content: str`
- `metadata: Dict[str, Any]`
- Methods: `to_dict()`, `classmethod from_dict(d)`

#### `KnowledgeStore(ABC)`
- `search(query, k=5, type_filter=None, metadata_filters=None) -> List[Tuple[KnowledgeItem, float]]`
- `add(item)`, `update(item_id, new_content)`, `list_by_type(knowledge_type)`, `get_items_by_source(source_filename)`

---

## C. Django models (`admin_app/models/admin_evals.py`)

All three extend `TimestampBase` (which provides `created_at`, `updated_at`) and use `managed = False` (schema owned by another migration).

### `EvalAgentConversation(TimestampBase)`
**Table:** `nhapp_evalagentconversation`

| Field | Type | Notes |
|---|---|---|
| `conversation_id` | `UUIDField(default=uuid4, unique=True, editable=False)` | Public id surfaced via API |
| `thread_id` | `CharField(max_length=128, unique=True, db_index=True)` | LangGraph checkpointer key; Slack thread anchor |
| `user_id` | `ForeignKey(User, on_delete=CASCADE, null=True, blank=True, related_name="eval_agent_conversations")` | Nullable |
| `title` | `CharField(max_length=255, blank=True)` | |
| `mode` | `CharField(max_length=32, default="chatbot")` | `"chatbot"` / `"deep_search"` / `"deep_engineer"` |
| `last_query` | `TextField(blank=True)` | Truncated `[:500]` at write |
| `messages` | `JSONField(default=list)` | Full conversation message list |
| `findings_compressed` | `JSONField(default=list)` | Reserved for future use |
| `message_count` | `IntegerField(default=0)` | |
| `deep_searches` | `IntegerField(default=0)` | Incremented per deep-search submission |
| `findings_report` | `TextField(blank=True)` | Mirror of latest report markdown |

**Indexes:** `Index(fields=["thread_id"]), Index(fields=["user_id"])`. **Ordering:** `("-updated_at",)`.

### `EvalAgentReports(TimestampBase)`
**Table:** `nhapp_evalagentreports`

| Field | Type | Notes |
|---|---|---|
| `conversation` | `ForeignKey(EvalAgentConversation, on_delete=CASCADE, null=True, blank=True, related_name="sessions")` | Reverse: `conv.sessions` |
| `query` | `TextField()` | |
| `document_url` | `URLField(max_length=500, blank=True, null=True)` | GCS URL placeholder |
| `state` | `JSONField(default=dict, blank=True)` | Holds `report_markdown`, `user_visible_final_response`, `artifact_files`, `error`, `details`, `document_error`, `cancelled`, `report_format` |

**Ordering:** `("-created_at",)`.

### `KnowledgeEmbedding(TimestampBase)`
**Table:** `nhapp_knowledgeembedding` (pgvector)

| Field | Type | Notes |
|---|---|---|
| `item_id` | `CharField(max_length=255, unique=True)` | Stable id (`faq_5_...`, `sql_pattern_...`) |
| `knowledge_type` | `CharField(max_length=64)` | Literal: faq/db_schema/known_issue/investigation_pattern/baseline |
| `title` | `CharField(max_length=500)` | |
| `content` | `TextField()` | |
| `embedding` | `VectorField(dimensions=3072)` | **pgvector, 3072 dims** matches OpenAI text-embedding-3-large |
| `metadata` | `JSONField(default=dict, blank=True)` | `{source, type, name, tags, tables}` per loader |
| `source` | `CharField(max_length=255, blank=True)` | e.g. `"FAQ.md"`, `"INVESTIGATION_PATTERNS.md"` |

**Ordering:** `("knowledge_type", "item_id")`.

---

## D. LangGraph checkpoint tables

The async Postgres checkpointer (`langgraph-checkpoint-postgres`) auto-creates three tables on `setup()`:
- `checkpoints` — main checkpoint metadata.
- `checkpoint_blobs` — large state values.
- `checkpoint_writes` — pending writes.

These are managed by the library; Eva does not declare them. They live in the same Postgres database as `EvalAgentConversation` (`default` alias) and are keyed by `thread_id`.

---

## E. Redis schema (stream events)

For each `job_id`, four Redis keys (TTL 24h):
- `eval_agent:deep_stream:counter:<job_id>` — INTEGER (event sequence counter; INCR).
- `eval_agent:deep_stream:events:<job_id>` — LIST of JSON event payloads (RPUSH).
- `eval_agent:deep_stream:status:<job_id>` — STRING (`"running"` or terminal event name).
- `eval_agent:deep_stream:channel:<job_id>` — pub/sub channel for live subscribers.

Event payload shape:
```json
{
  "id": <int sequence>,
  "event": "<event_name>",
  "data": {...arbitrary},
  "timestamp": "2026-06-13T12:34:56.789Z"
}
```

Terminal events: `completed`, `failed`, `cancelled`.

---

## F. Knowledge YAML schemas

### `INVESTIGATION_PATTERNS.yaml`
Top-level sections (read by `format_investigation_patterns_yaml_data`):
- `agent_guidelines` — array
- `data_model_reference` — keyed object
- `investigation_patterns.critical_caveats` — array
- `investigation_patterns.queries` — list of named SQL patterns
- `investigation_patterns.tips` — array

### `BASELINES.yaml`
- `metrics` — keyed object of `metric_name → value` pairs (e.g. `negative_sentiment_on_failures: 22.0`).

### `KNOWN_ISSUES.yaml`
- `issues` — array of `{title, description}` dicts.

### `SCHEMA_REFERENCE.yaml`
- `tables` — array of `{name, description, columns, common_joins, related_enums}`.
- `columns` — `[{name, type, description, enum?}]`.

### `FAQ.yaml`
- Currently loaded via vector search; the curated FAQ markdown is the source of truth, indexed by `load_faq()`.

---

## G. Knowledge skills markdown frontmatter

`knowledge/skills/*.md` files may include YAML frontmatter:
```yaml
---
description: One-line description shown in the agent prompt.
---
```

Parsed by `investigation_skills.py::_frontmatter_description(path)`.

---

## H. Request/response shapes (DRF)

### `EvalAgentQueryView` input (multipart/JSON):

```json
{
  "env": "prod" | "staging",
  "cancel": false,
  "job_id": "<uuid>" (if cancel=true),
  "query": "<text>",
  "context": "<text>",
  "location_id": <int>,
  "time_window": "30 days",
  "model": "claude-haiku-4-5-20251001",
  "deep_search": false,
  "auto_route": true,
  "thread_id": "<uuid>",
  "BI": false,
  "SRE": false,
  "files": [<multipart files>]
}
```

### `EvalAgentQueryView` response (HTTP 202):

```json
{
  "data": {
    "success": true,
    "job_id": "<prefect_flow_run_id>",
    "thread_id": "<uuid>",
    "conversation_id": "<uuid>",
    "routing": {
      "eval_agent_route": "deep_search_sre",
      "eval_agent_route_reason": "...",
      "eval_agent_router_model": "claude-haiku-4-5-20251001"
    },
    "stream_url": "/api/v1/eval-agent/deep-engineer/threads/<id>/runs/<id>/stream/",
    "cancel_url": "/api/v1/eval-agent/deep-engineer/threads/<id>/runs/<id>/cancel/"
  }
}
```

### `EvalAgentQueryStatusView` response:

```json
{
  "data": {
    "success": true,
    "status": "running" | "completed" | "failed" | "cancelled" | "pending",
    "prefect_state": "<Prefect StateType>",
    "result": {
      "report_markdown": "...",
      "user_visible_final_response": "...",
      "artifact_files": [...]
    } | null,
    "progress": {
      "steps": [...],
      "current": {...}
    },
    "stream_url": "...",
    "cancel_url": "..."
  }
}
```

### `EvalAgentConversationDetailView` response:

```json
{
  "data": {
    "success": true,
    "conversation_id": "<uuid>",
    "thread_id": "<uuid>",
    "title": "...",
    "mode": "chatbot" | "deep_search",
    "last_query": "...",
    "message_count": N,
    "deep_searches": N,
    "messages": [
      {"role": "user" | "assistant", "content": "...", "source": "chatbot" | "deep_search", "is_final": true, "timestamp": "...", "report_url": "...", "session_id": "..."}
    ],
    "reports": [
      {"session_id": "<uuid>", "query": "...", "document_url": "https://..."(signed, 7-day), "created_at": "..."}
    ],
    "created_at": "...",
    "updated_at": "..."
  }
}
```

### `EvaSettingsView` response (abbreviated):

```json
{
  "data": {
    "success": true,
    "provider": "anthropic",
    "model_id": "claude-sonnet-4-6",
    "temperature": 0.3,
    "max_tokens": 4096,
    "harness_profile": "anthropic:claude-sonnet-4-6",
    "system_prompt_suffix": "...",
    "subagent_catalog": [...],
    "limits": {
      "recursion_limit": 1000,
      "model_call_run_limit": 50,
      "tool_call_run_limit": 200
    },
    "learning_memories": {...},
    "playbooks": {...},
    "issue_ledger": [...]
  }
}
```

---

## I. Example finding shapes (BI agent)

A typical `finding` appended to `state.findings` is a stringified JSON (or dict) matching `DiscoverNodeOutput` / `CrossValidateNodeOutput` / `ContextualizeNodeOutput`. The `_render_finding_md` helper converts these to markdown for the report node.

Example discover finding (JSON):
```json
{
  "node": "discover",
  "summary": {"key_finding": "73% of failed L1 calls are callback/voicemail requests"},
  "metrics": {"population_size": 2341, "sample_size": 200, "iterations": 3, "other_unclear_pct": 5.2},
  "methods": {"population_filter": "l1_pass=false", "time_window": "30 days", "pattern_strategy": "transcript ILIKE patterns"},
  "data": {
    "categories": [
      {"name": "Callback/Voicemail", "keywords": ["%callback%", "%voicemail%"], "count": 1709, "pct": 73.0, "type": "actionable"},
      {"name": "Insurance Question", "keywords": ["%insurance%"], "count": 388, "pct": 16.6, "type": "actionable"},
      {"name": "Other/Unclear", "keywords": [], "count": 122, "pct": 5.2, "type": "unclear"}
    ]
  },
  "insights": ["..."],
  "alternative_validations": ["..."],
  "confidence": "High",
  "caveats": ["..."],
  "suggested_next_skill": "contextualize",
  "resolved_location_id": null,
  "resolved_location_name": null,
  "resolved_organization_id": null,
  "resolved_organization_name": null
}
```

## J. Example output shape (SRE report)

The SRE conclude returns a markdown string roughly following:

```markdown
# INVESTIGATION REPORT

## Header
| Field | Value |
|-------|-------|
| **Call ID** | <uuid> |
| **Location** | Main Street Dental (location_id=42) |
| **Confidence** | HIGH |
| **Confidence Reason** | Failure point confirmed by both Langfuse trace span "schedule_appointment" returning empty AND code analysis showing pms_sync_enabled=false. |

## TL;DR
| | |
|---|---|
| **What broke** | check_availability returned empty because PMS sync was disabled |
| **Patient impact** | Appointment not booked; patient transferred |
| **Root cause** | location.pms_sync_enabled = false |
| **Engineering action** | Add fallback when PMS sync is disabled |

## What Happened
[3-5 sentences in plain English]

## What Went Wrong (Step by Step)
**Step 1 — ...**
What happened: ...
Evidence: Turn 4, span "check_availability", output: `[]`

## Evidence
### Trace Evidence
### Code Evidence
### Database Evidence
### GCP Log Evidence

## Suggested Fixes
### Immediate Fix
**File:** `path/to/file.py`
**Function:** `function_name`
[code snippets]
### Additional Improvements
### Monitoring
```
