# Learnings from Eva — Applied to Sova

> This document is a **forensic extraction** of every architectural pattern, technology choice, and engineering decision in Eva that is applicable to Sova. Eva is a production multi-agent investigation platform built on the same tech stack (Django, Postgres, Redis, Celery, LangGraph, Anthropic). It solves a different problem — root-cause analysis of voice call failures — but its structure is the closest available reference for how to build Sova correctly.
>
> Sova has four layers. This document is organized around those four layers. Every Eva pattern is mapped to the Sova layer it applies to, with an explanation of *why* it applies and *how* to implement it.

---

## Eva Overview (Quick Reference)

Eva's full architecture at a glance:

```
REST API / Slack / Prefect Trigger
        ↓
  Mode Router (LLM, Haiku, temp=0)
        ↓
  ┌─────────────────────────────┐
  │   Chatbot (LangGraph)       │  ← quick Q&A, tool-backed, Postgres-checkpointed
  │   BI Deep Search (LangGraph)│  ← multi-step data investigation
  │   SRE Deep Search (ReAct)   │  ← root-cause analysis
  │   Multi-agent (supervisor)  │  ← BI + SRE coordinated
  └─────────────────────────────┘
        ↓
  Tools: DB queries, Langfuse traces, GCP logs, GitHub MCP, Twilio debug
        ↓
  Postgres (results) + Redis (SSE stream) + EvalAgentConversation (messages)
```

Sova's equivalent:

```
REST API / CLI / Future Chatbot
        ↓
  Mode Router (same pattern — LLM decides: quick answer vs full analysis)
        ↓
  ┌─────────────────────────────┐
  │   Chatbot (LangGraph)       │  ← "Show me HOT leads in Texas"
  │   Deep Analysis (LangGraph) │  ← "Run full lead score refresh for NYC"
  └─────────────────────────────┘
        ↓
  Tools: Lead Score, Outreach Brief, Competitive Report, Revenue Rescue Planner, etc.
        ↓
  Postgres (all sub-fragment + tool output) + Redis (SSE) + SovaConversation (messages)
        ↑
  Celery Tasks (sub-fragments writing to Postgres, 24/7, autonomous)
```

---

## Layer 1 — Data Collector Fragments (Sub-fragments)

These are Sova's 110+ Celery tasks. Each one is autonomous, scheduled, and writes to its own DB table. Eva does not have "data collector fragments" per se — but the tool infrastructure Eva uses to *call* its data sources maps exactly onto how Sova should write its collectors.

---

### 1.1 Tenacity Retry on All External Calls

**Eva's implementation:**
```python
from tenacity import retry, stop_after_attempt, wait_fixed

@retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
def execute_query(self, sql):
    ...
```

Used in `tools/db_client.py::PostgresClient.execute_query` and `search_tables`. Any exception triggers a retry with a 1-second wait, up to 2 attempts.

**Apply to Sova:** Every sub-fragment making an external HTTP call (Google Places, Hunter.io, scraping targets, government APIs) or writing to the database should be wrapped with Tenacity. Build one shared decorator for the project:

```python
# sova/utils/retry.py
from tenacity import retry, stop_after_attempt, wait_exponential

sova_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=False
)
```

Apply it to every `fetch_*`, `scrape_*`, and `write_to_db` function in every sub-fragment. Network hiccups do not fail a Celery task permanently — they log a retry event and try again.

---

### 1.2 Django Cache as Distributed Mutex (Prevent Duplicate Runs)

**Eva's implementation:**
```python
lock_key = f"feedback_eva:lock:{feedback_id}"
acquired = cache.add(lock_key, "1", timeout=300)
if not acquired:
    logger.info("Already running for %s, skipping", feedback_id)
    return
```

`cache.add()` is atomic in Redis — it only sets the key if it does not already exist. This is a one-line distributed mutex.

**Apply to Sova:** When Celery Beat fires `google_places_collector` across 50,000 practices, two workers must never process the same practice simultaneously. Pattern for every sub-fragment:

```python
def run_collector(practice_npi: str):
    lock_key = f"sova:lock:google_places_collector:{practice_npi}"
    acquired = cache.add(lock_key, "1", timeout=300)
    if not acquired:
        return  # another worker is already on this practice
    try:
        # ... do the work ...
    finally:
        cache.delete(lock_key)
```

The `finally` block ensures the lock is always released even if the task raises an exception.

---

### 1.3 Last-Run Timestamp and Health Tracking Per Sub-fragment

**Eva's implementation:** Eva tracks `EvalAgentConversation.updated_at`, `deep_searches`, and per-run states explicitly. The orchestrator layer reads these to know what has and hasn't run.

**Apply to Sova:** Every sub-fragment should write a `last_run_at` timestamp and `last_run_status` (success/partial/failed) to a central `SubFragmentRunLog` model after each execution:

```python
class SubFragmentRunLog(models.Model):
    name = models.CharField(max_length=100)          # "google_places_collector"
    last_run_at = models.DateTimeField()
    last_run_status = models.CharField(max_length=20) # success / partial / failed
    records_written = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
```

The orchestrator uses this to detect stale collectors (last_run_at > 2× expected interval = alert) and collectors that succeeded but wrote zero records (silent failure = alert).

---

### 1.4 Per-Fragment Pydantic Output Schema

**Eva's implementation:** Every tool call returns a typed Pydantic model, never raw dicts. `DatabaseQueryResult`, `KnowledgeSearchResult`, `SkillResult` — every result has a defined schema.

**Apply to Sova:** Every sub-fragment writes to its own database table. Define a Pydantic model for what that table row looks like *before* writing any scraping code. This forces you to think about the data contract:

```python
class JobPostingRecord(BaseModel):
    practice_npi: str
    source: Literal["dentalpost", "indeed", "ihiredental"]
    job_title: str
    posted_at: datetime
    description_text: str
    pms_mentions: List[str]        # extracted by pms_signal_extractor
    is_chronic_repost: bool        # same role posted 3+ times in 12 months
    raw_url: str
    collected_at: datetime = Field(default_factory=datetime.utcnow)
```

The Django model mirrors this. The Pydantic model is used for validation before any DB write. Malformed records never make it to the database.

---

### 1.5 Sensitive Data Sanitization in Logs

**Eva's implementation:**
```python
def sanitize_query_for_logging(query: str) -> str:
    # Redacts phone number and email patterns before logging
    query = re.sub(r'\b\d{10,}\b', '[PHONE]', query)
    query = re.sub(r'[\w.+-]+@[\w-]+\.[a-z]{2,}', '[EMAIL]', query)
    return query
```

**Apply to Sova:** Sub-fragments handle practice phone numbers (from NPPES), email addresses (from Hunter.io), and NPI-linked personal data. Before any `logger.info(...)` call that contains query strings, URLs, or raw scraped data, sanitize it:

```python
# sova/utils/logging.py
def sanitize_for_log(text: str) -> str:
    text = re.sub(r'\b\d{10,}\b', '[PHONE]', text)
    text = re.sub(r'[\w.+-]+@[\w-]+\.[a-z]{2,}', '[EMAIL]', text)
    return text
```

---

### 1.6 Tool Timeout with asyncio.wait_for

**Eva's implementation:**
```python
TOOL_TIMEOUT = 60  # seconds

try:
    result = await asyncio.wait_for(tool.ainvoke(input), timeout=TOOL_TIMEOUT)
except asyncio.TimeoutError:
    return "Error: tool timed out after 60 seconds"
```

Tool timeouts never raise out of the ReAct loop — they return a string error that the LLM observes and handles.

**Apply to Sova:** Sub-fragments that make HTTP requests can hang indefinitely if a target server stops responding. Wrap every `httpx.get()` with a timeout:

```python
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(url, headers=headers)
```

For Celery tasks using the sync `requests` library:
```python
response = requests.get(url, timeout=30)
```

For async sub-fragments inside LangGraph tools, use `asyncio.wait_for(coro, timeout=60)`. Never let a network call block indefinitely.

---

### 1.7 Central Config Class (Single Source of Truth for All Knobs)

**Eva's implementation:**
```python
class EvalAgentConfig:
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"
    TEMPERATURE = 0.3
    MAX_TOKENS = 4096
    TOOL_TIMEOUT = 60
    API_RATE_LIMIT = 10
    HIGH_CONFIDENCE_THRESHOLD = 500
    MODERATE_CONFIDENCE_THRESHOLD = 100
    DANGEROUS_SQL_PATTERNS = [...]
    
    @classmethod
    def is_langsmith_enabled(cls) -> bool:
        return bool(settings.LANGSMITH_TRACING and settings.LANGSMITH_API_KEY)
```

Every configurable value is a class attribute on a single config class. No magic numbers scattered across files.

**Apply to Sova:** Create `sova/config.py`:

```python
class SovaConfig:
    # LLM
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"
    FAST_MODEL = "claude-haiku-4-5-20251001"      # routing, classification
    ANALYSIS_MODEL = "claude-sonnet-4-6"           # outreach briefs, reports
    TEMPERATURE = 0.3
    MAX_TOKENS = 4096
    
    # Scoring
    HOT_SCORE_THRESHOLD = 78
    HOT_FIT_THRESHOLD = 65
    HIGH_CONFIDENCE_THRESHOLD = 500
    MODERATE_CONFIDENCE_THRESHOLD = 100
    
    # Celery / Tasks
    TASK_TIMEOUT_SECONDS = 300
    HTTP_REQUEST_TIMEOUT = 30
    TOOL_TIMEOUT = 60
    
    # Rate limits
    CHATBOT_API_RATE_LIMIT = 10   # per minute per user
    
    # Chatbot
    CHATBOT_RECURSION_LIMIT = 25
    MAX_MESSAGES_BEFORE_SUMMARIZE = 15
    KEEP_RECENT_MESSAGES = 5
    
    # Observability
    @classmethod
    def is_langsmith_enabled(cls) -> bool:
        return bool(getattr(settings, 'LANGSMITH_TRACING', False) and 
                    getattr(settings, 'LANGSMITH_API_KEY', None))
```

---

### 1.8 Sentry SDK for Production Error Capture

**Eva's implementation:** `sentry-sdk[django]` installed and configured. Any unhandled exception in a Celery task, a LangGraph node, or a DRF view is captured automatically.

**Apply to Sova:** Add `sentry-sdk[django,celery]` to dependencies from day one. In `settings.py`:

```python
import sentry_sdk
sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)
```

The `celery` integration ensures Celery task failures are captured with the full task context (task name, args, kwargs). This is the difference between knowing about silent sub-fragment failures vs. discovering them when a lead score looks wrong.

---

## Layer 2 — Intelligence Tools

Tools read from the database tables written by sub-fragments and answer one specific business question. Eva's tool infrastructure is the closest reference for how to design these.

---

### 2.1 Pydantic Structured Output on Every LLM Call

**Eva's implementation:**
```python
# Every LLM call that needs structured data uses this pattern
llm = ChatAnthropic(model=EvalAgentConfig.DEFAULT_MODEL)
structured_llm = llm.with_structured_output(BIInvestigationPlanOutput)
result: BIInvestigationPlanOutput = await structured_llm.ainvoke([
    SystemMessage(content=system_prompt),
    HumanMessage(content=user_prompt)
])
```

Eva never parses raw LLM text. `with_structured_output()` forces JSON matching the Pydantic schema and retries on mismatch automatically.

**Apply to Sova:** Every LLM call in every tool must have a Pydantic output schema defined *before* writing the prompt. Examples:

```python
# For newsletter_classifier
class NewsletterClassification(BaseModel):
    signal_type: Literal["Opportunity", "Content", "Noise"]
    reason: str
    practice_name: Optional[str] = None
    practice_npi: Optional[str] = None
    confidence: Literal["High", "Moderate", "Low"]

# For competitor_product_monitor  
class ProductPageDiff(BaseModel):
    pricing_changed: bool
    new_features: List[str]
    removed_features: List[str]
    positioning_shift: Optional[str] = None
    urgency_for_sova: Literal["High", "Medium", "Low", "None"]

# For outreach_brief_tool
class OutreachBrief(BaseModel):
    practice_name: str
    why_hot: List[str]                    # evidence list
    owner_message: str                     # angle for the dentist
    office_manager_message: str            # angle for the OM
    recommended_opener: str
    best_contact_channel: Literal["email", "linkedin", "phone"]
    urgency_window_days: int
```

The schema comes first. The prompt is secondary. This is the discipline Eva enforces.

---

### 2.2 Prompt Caching (cache_control: ephemeral) on System Prompts

**Eva's implementation:**
```python
# Eva's prompt caching helper
def _human_message_with_cache(static_text: str, dynamic_text: str) -> HumanMessage:
    return HumanMessage(content=[
        {"type": "text", "text": static_text, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": dynamic_text}
    ])

# Used in multi_agent.py supervisor
system = [{"type": "text", "text": SUPERVISOR_PLANNING_PROMPT, "cache_control": {"type": "ephemeral"}}]
```

Anthropic caches prompt content marked with `cache_control: ephemeral` for 5 minutes. System prompts are identical across all calls in a batch — only the user input changes. This produces a 60–80% token reduction on the system prompt portion for batch LLM calls.

**Apply to Sova:** Every LLM call in every sub-fragment or tool that processes multiple records in a batch run (newsletter_classifier, staff_burnout_aggregator, competitor_product_monitor, reputation_shock_detector) must use prompt caching:

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

NEWSLETTER_SYSTEM_PROMPT = """You are a dental industry signal classifier..."""  # static

async def classify_newsletter_item(item_text: str, llm: ChatAnthropic) -> NewsletterClassification:
    structured_llm = llm.with_structured_output(NewsletterClassification)
    return await structured_llm.ainvoke([
        SystemMessage(content=[
            {"type": "text", "text": NEWSLETTER_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
        ]),
        HumanMessage(content=item_text)   # dynamic — different per item
    ])
```

In a batch of 50 newsletter items, only the first call pays for the full system prompt. The next 49 pay for the dynamic portion only. At $3/1M tokens for Sonnet, a 2,000-token system prompt across 50 calls = $0.15 vs $0.003 with caching.

---

### 2.3 Two-Level Knowledge Cache (In-Process Dict + Redis)

**Eva's implementation:**
```python
# Module-level in-process cache
_KNOWLEDGE_CACHE: Dict[str, Any] = {}
KNOWLEDGE_CACHE_TTL_SECONDS = 15 * 60  # 15 minutes

def _get_or_fill_knowledge_cache(key: str, fetch_fn) -> Any:
    entry = _KNOWLEDGE_CACHE.get(key)
    if entry and (time.time() - entry['ts']) < KNOWLEDGE_CACHE_TTL_SECONDS:
        return entry['data']
    data = fetch_fn()
    _KNOWLEDGE_CACHE[key] = {'data': data, 'ts': time.time()}
    return data
```

In-process dict cache for frequently-read, rarely-changing data. No Redis round-trip. 15-minute TTL. Used for investigation patterns, baselines, and known issues loaded from YAML.

**Apply to Sova:** Sova's tools will frequently read the same data per run — the ICP profile configuration, the scoring weights, the competitor list, the playbook content. Put slow-changing data in a module-level in-process cache with a 15-minute TTL. Put request-scoped data in the Django cache (Redis). Do not hit Postgres or Redis for data that won't change within a single Celery worker's lifetime.

---

### 2.4 Parallel Tool Execution with Semaphore Cap

**Eva's implementation:**
```python
semaphore = asyncio.Semaphore(8)

async def _execute_tool_with_semaphore(tool_call):
    async with semaphore:
        return await execute_one_tool(tool_call)

results = await asyncio.gather(*[
    _execute_tool_with_semaphore(tc) for tc in tool_calls
])
```

Eva's chatbot node parallelizes all tool calls from a single LLM response using `asyncio.gather`, capped at 8 concurrent executions. This prevents one slow tool from blocking others while avoiding thundering herd on the database.

**Apply to Sova's tools:** When the Lead Score tool computes a score for a practice, it needs to read from ~10 different sub-fragment tables (job postings, reviews, lifecycle events, technographic data, DSO proximity). These are independent reads — run them in parallel:

```python
TOOL_SEMAPHORE = asyncio.Semaphore(8)

async def compute_lead_score(practice_npi: str) -> LeadScore:
    async with TOOL_SEMAPHORE:
        # All these DB reads run concurrently
        job_signals, review_signals, lifecycle_signals, tech_signals = await asyncio.gather(
            fetch_job_signals(practice_npi),
            fetch_review_signals(practice_npi),
            fetch_lifecycle_events(practice_npi),
            fetch_technographic_signals(practice_npi),
        )
    return _score(job_signals, review_signals, lifecycle_signals, tech_signals)
```

---

### 2.5 Confidence Scoring with Sample Size Thresholds

**Eva's implementation:**
```python
HIGH_CONFIDENCE_THRESHOLD = 500
MODERATE_CONFIDENCE_THRESHOLD = 100

def _extract_confidence_from_findings(findings: List) -> str:
    # Rolls up individual finding confidences
    # HIGH requires n > 500, multiple independent sources
    # MODERATE requires n = 100-500, single reliable source
    # LOW requires n < 100, inference-based
```

Every BI finding has a confidence level derived from sample size and source diversity. The LLM is given this rubric in the prompt and must cite evidence counts.

**Apply to Sova:** Every signal that a sub-fragment produces should carry a confidence rating. The Lead Score tool should weight HIGH confidence signals more heavily than LOW confidence signals at the same nominal score value:

```python
class SignalConfidence(str, Enum):
    HIGH = "High"       # Direct evidence, n > threshold, multiple sources
    MODERATE = "Moderate"  # Single reliable source, reasonable n
    LOW = "Low"         # Inference, small n, single point of data

class CollectedSignal(BaseModel):
    signal_type: str
    raw_value: float
    confidence: SignalConfidence
    evidence_count: int
    source: str
    collected_at: datetime
```

The scoring formula then applies confidence as a weight modifier: `HIGH × 1.0`, `MODERATE × 0.75`, `LOW × 0.5`.

---

### 2.6 pgvector Knowledge Base for Semantic Retrieval

**Eva's implementation:**

Eva has a curated knowledge base embedded in pgvector:
- Source: YAML files (`knowledge/files_yaml/*.yaml`) — FAQ, BASELINES, KNOWN_ISSUES, INVESTIGATION_PATTERNS
- Embedding: `text-embedding-3-large` (3072 dimensions)
- Storage: `KnowledgeEmbedding` Django model with `VectorField(dimensions=3072)`
- Search: `CosineDistance` query, `KNOWLEDGE_HIT_THRESHOLD = 0.75`
- Cache: If cosine score ≥ 0.75, answer directly from knowledge base without running a full investigation

```python
class KnowledgeEmbedding(models.Model):
    content = models.TextField()
    embedding = VectorField(dimensions=3072)
    metadata = models.JSONField()

class DatabaseKnowledgeStore:
    def search(self, query: str, k: int = 1) -> List[KnowledgeSearchResult]:
        query_embedding = self.embedder.embed_query(query)
        results = KnowledgeEmbedding.objects.annotate(
            distance=CosineDistance('embedding', query_embedding)
        ).filter(distance__lt=0.25).order_by('distance')[:k]
        return [KnowledgeSearchResult(score=1-r.distance, ...) for r in results]
```

**Apply to Sova:** Build a `SovaKnowledge` table and populate it with:

1. **Outreach playbooks by ICP type** — authored YAML files describing the right pitch angle for each practice type (new practice owner, DSO executive, OM-led purchase, etc.)
2. **Objection handlers** — patterns from `lost_deal_reason_miner`, each embedded so the Revenue Rescue Planner can retrieve the right response to "too expensive" or "we already have a receptionist"
3. **Case study library** — each case study embedded with its practice type, specialty, geography, and pain profile so the Trust Vector tool can retrieve the most similar one to the current lead
4. **Competitor comparison sheets** — "How does Sova compare to Arini for an orthodontic practice on Dentrix?" embedded for instant retrieval

Use `text-embedding-3-small` (1536 dimensions, 5× cheaper) instead of `text-embedding-3-large`. For Sova's semantic retrieval use case (matching practice profiles to playbooks), 1536-dim is entirely sufficient.

Build script matches Eva: `python manage.py build_knowledge_index` loads all YAML/MD files, embeds them, writes to `SovaKnowledge`.

---

### 2.7 SQL Safety Layer

**Eva's implementation:**
```python
DANGEROUS_SQL_PATTERNS = [
    r'\bINSERT\b', r'\bUPDATE\b', r'\bDELETE\b', r'\bDROP\b',
    r'\bTRUNCATE\b', r'\bALTER\b', r'\bCREATE\b', r'\bGRANT\b',
    r'\bREVOKE\b', r'\bEXEC(UTE)?\b'
]

ALLOWED_TABLES: frozenset = frozenset({
    "nhapp_callinsight", "nhapp_location", ...  # 72 tables
})

# Statement timeout per query
SET LOCAL statement_timeout = '30000'  # 30s

def is_query_safe(query: str) -> bool:
    return not any(re.search(p, query, re.IGNORECASE) for p in DANGEROUS_SQL_PATTERNS)

def apply_row_sample_limit_guard(query: str, fallback_limit: int = 1000) -> str:
    if not outer_statement_has_limit(query):
        return f"{query.rstrip(';')} LIMIT {fallback_limit}"
    return query
```

**Apply to Sova's chatbot tool:** When the chatbot layer is built and users can ask "run a SQL query against the leads database," every LLM-generated SQL must pass through these guards before execution:

1. Pattern-match against dangerous SQL keywords — reject before even parsing
2. Validate all referenced tables are in an `ALLOWED_TABLES` allowlist
3. Wrap execution in `SET LOCAL statement_timeout = '30000'`
4. Auto-add `LIMIT 1000` if the query doesn't have one
5. Return `"Error: unsafe query"` as a string to the LLM — never raise an exception that crashes the tool loop

---

### 2.8 Tool Error Handling — Never Raise, Always Return

**Eva's implementation:**

In every ReAct loop, if a tool call throws an exception, it returns a `ToolMessage` with an error string rather than raising:

```python
try:
    result = await tool.ainvoke(tool_call.args)
except Exception as e:
    result = f"Error executing {tool_call.name}: {str(e)}"

# Returned to the LLM as a ToolMessage
messages.append(ToolMessage(content=str(result), tool_call_id=tool_call.id))
```

The LLM observes the error and decides whether to retry with different arguments, try a different approach, or acknowledge it cannot complete the task. The ReAct loop never crashes.

**Apply to Sova:** Every Sova tool that the chatbot can call must follow this contract: catch all exceptions internally and return a structured error response. Never let a tool exception propagate to the LangGraph graph engine:

```python
@tool
async def get_lead_score(practice_npi: str) -> str:
    try:
        score = await _compute_lead_score(practice_npi)
        return score.model_dump_json()
    except PracticeNotFoundError:
        return f"Practice NPI {practice_npi} not found in database"
    except Exception as e:
        logger.exception("lead_score tool failed for %s", practice_npi)
        return f"Error computing lead score: {str(e)}"
```

---

### 2.9 Partial Result Synthesis on Recursion Limit

**Eva's implementation:**
```python
def is_recursion_limit_error(exc) -> bool:
    return isinstance(exc, (langgraph.errors.GraphRecursionError, RecursionError))

async def synthesize_partial_report(query, findings_snippet, llm) -> str:
    """When the agent hits the recursion limit, synthesize what was found so far."""
    return await llm.ainvoke([
        SystemMessage(content=PARTIAL_REPORT_PROMPT),
        HumanMessage(content=f"Query: {query}\n\nPartial findings:\n{findings_snippet}")
    ])
```

Catch the recursion error, pass partial state to a synthesis LLM call, return a degraded-but-useful result. Never a raw error to the user.

**Apply to Sova's chatbot:** When the chatbot hits `CHATBOT_RECURSION_LIMIT = 25` mid-investigation:
1. Catch `GraphRecursionError`
2. Extract partial tool results from the message history so far
3. Call `synthesize_partial_reply(user_query, partial_results, llm)` — a lightweight Haiku call that wraps what was found into a coherent partial answer
4. Add a note: "Investigation reached its step limit. Here is what was found. For a complete analysis, use the Deep Analysis mode."

---

### 2.10 Token Caps and Context Truncation

**Eva's implementation:**

Eva has explicit caps on every injectable context string:
```python
MAX_SCHEMA_CHARS = 3000
MAX_KNOWLEDGE_PROMPT_CHARS = 12000
MAX_FINDINGS_MD_CHARS = 25000
MAX_FINDINGS_CHUNKS = 5
ROUTER_PRIOR_CONTEXT_FULL_MAX_CHARS = 38000
```

When context exceeds a cap, it's truncated or summarized via an LLM call before injection.

**Apply to Sova:** Every tool that injects context into an LLM prompt must respect a token budget. Define per-tool caps:

```python
class SovaConfig:
    MAX_OUTREACH_BRIEF_SIGNALS_CHARS = 8000    # evidence injected into outreach brief prompt
    MAX_COMPETITIVE_REPORT_CHANGES_CHARS = 12000
    MAX_REVENUE_RESCUE_EVIDENCE_CHARS = 6000
    MAX_CHATBOT_CONTEXT_CHARS = 48000
```

When sub-fragment data for a practice exceeds these caps (e.g., a practice with 500 job postings in history), truncate to the most recent N records before injection. Never let prompt size grow unbounded.

---

## Layer 3 — Orchestrator Brain

The orchestrator manages scheduling, health monitoring, and coordination between sub-fragments and tools. Eva's Prefect + Celery setup and its state management patterns are directly applicable.

---

### 3.1 Central Conversation/Session Model

**Eva's implementation:**
```python
class EvalAgentConversation(models.Model):
    conversation_id = models.UUIDField(default=uuid.uuid4, unique=True)
    thread_id = models.CharField(max_length=255, unique=True)    # LangGraph key
    messages = models.JSONField(default=list)                    # all turns
    mode = models.CharField(max_length=50)
    deep_searches = models.IntegerField(default=0)
    findings_report = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class EvalAgentReports(models.Model):
    conversation = models.ForeignKey(EvalAgentConversation, ...)
    state = models.JSONField()    # report_markdown, error, cancelled, etc.
    created_at = models.DateTimeField(auto_now_add=True)
```

Conversation history, run results, and LangGraph thread IDs are all stored in Postgres. Redis holds only transient streaming state (24h TTL).

**Apply to Sova:** Create two Django models:

```python
class SovaConversation(models.Model):
    conversation_id = models.UUIDField(default=uuid.uuid4, unique=True)
    thread_id = models.CharField(max_length=255, unique=True)    # LangGraph checkpoint key
    user_identifier = models.CharField(max_length=255)           # sales rep ID or API key
    messages = models.JSONField(default=list)
    mode = models.CharField(max_length=50, default="chatbot")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class SovaTaskRun(models.Model):
    run_id = models.UUIDField(default=uuid.uuid4, unique=True)
    conversation = models.ForeignKey(SovaConversation, ...)
    task_name = models.CharField(max_length=100)                  # "compute_lead_score"
    status = models.CharField(max_length=20, default="pending")  # pending/running/completed/failed/cancelled
    result = models.JSONField(null=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)
```

---

### 3.2 Job Submission and Status Polling Pattern

**Eva's implementation:**

The DRF query view returns HTTP 202 immediately with a `job_id`:

```
POST /api/v1/eval-agent/query/
→ HTTP 202 { "job_id": "<prefect_flow_run_id>" }

GET /api/v1/eval-agent/query/<job_id>/
→ { "status": "running|completed|failed|cancelled", "result": {...} }
```

The frontend polls this endpoint until `status` is terminal. No long-polling, no blocking.

**Apply to Sova:** The same pattern for any long-running tool invocation (full lead score computation, competitive intelligence report, outreach brief generation):

```
POST /api/v1/sova/tools/outreach-brief/
Body: { "practice_npi": "1234567890" }
→ HTTP 202 { "run_id": "<uuid>", "status_url": "/api/v1/sova/tasks/<run_id>/" }

GET /api/v1/sova/tasks/<run_id>/
→ { "status": "running", "progress": "Analyzing 47 signals...", "result": null }
→ { "status": "completed", "result": { ...outreach_brief... } }
```

The Celery task writes status updates to `SovaTaskRun.status`. The polling endpoint reads from that model.

---

### 3.3 Cancellation Pattern

**Eva's implementation:**
```python
# In every LangGraph node:
async def some_node(state, config):
    if await cancellation_check():
        raise InvestigationCancelled("Cancelled by user")
    # ... node logic ...

# In the API view:
class InvestigationCancelled(Exception):
    pass
```

Cancellation is implemented as a cooperative check at the start of every node. The `cancellation_check` callback returns True when a cancel API call has set a Redis key for this `job_id`.

**Apply to Sova:** When the chatbot is mid-computation of a large task (e.g., scoring 200 leads), the user should be able to cancel it:

```python
# Redis key: sova:cancel:<run_id>

class InvestigationCancelled(Exception):
    pass

async def check_cancellation(run_id: str) -> None:
    if cache.get(f"sova:cancel:{run_id}"):
        raise InvestigationCancelled(f"Run {run_id} cancelled by user")
```

Add a cancellation check at the entry of every LangGraph node in Sova's chatbot. Add a `POST /api/v1/sova/tasks/<run_id>/cancel/` endpoint that sets the Redis key. The Celery hard time limit (`900s`) serves as a backstop for tasks that ignore cancellation.

---

### 3.4 Celery Hard and Soft Time Limits

**Eva's implementation:**
```python
DEEP_ENGINEER_CELERY_TIME_LIMIT = 900      # hard: task is killed at 15 min
DEEP_ENGINEER_CELERY_SOFT_TIME_LIMIT = 840 # soft: SoftTimeLimitExceeded raised at 14 min
```

The soft limit allows the task to catch `SoftTimeLimitExceeded` and gracefully finalize (save partial results, update status to `failed_partial`) before the hard limit kills the process.

**Apply to Sova:** Every Celery task that runs a tool or a sub-fragment should have explicit time limits:

```python
@celery_app.task(
    bind=True,
    time_limit=900,         # hard kill at 15 min
    soft_time_limit=840,    # raise SoftTimeLimitExceeded at 14 min
    max_retries=3,
)
def run_outreach_brief_task(self, practice_npi: str, run_id: str):
    try:
        result = asyncio.run(compute_outreach_brief(practice_npi))
        SovaTaskRun.objects.filter(run_id=run_id).update(
            status="completed", result=result, completed_at=timezone.now()
        )
    except SoftTimeLimitExceeded:
        SovaTaskRun.objects.filter(run_id=run_id).update(status="failed_partial")
    except Exception as exc:
        self.retry(exc=exc, countdown=60)
```

---

### 3.5 Per-Event-Loop Async Resource Management

**Eva's implementation:**

Eva's LangGraph graphs and their async Postgres checkpointers are compiled **per asyncio event loop**:

```python
_async_checkpointers: Dict[int, AsyncPostgresSaver] = {}

async def get_async_postgres_checkpointer():
    loop_id = id(asyncio.get_running_loop())
    if loop_id not in _async_checkpointers:
        checkpointer = await AsyncPostgresSaver.from_conn_string(conn_str)
        await checkpointer.setup()
        _async_checkpointers[loop_id] = checkpointer
    return _async_checkpointers[loop_id]
```

Celery workers each have their own event loop. Sharing an async connection pool across loops causes race conditions. The solution: key all async resources on `id(asyncio.get_running_loop())`.

**Apply to Sova:** When Sova's chatbot layer uses `AsyncPostgresSaver` for conversation checkpointing, use this exact pattern. Do not share a single `AsyncPostgresSaver` instance across Celery workers. Create one per loop, cache by loop ID.

---

### 3.6 Django Connection Cleanup in Long-Running Tasks

**Eva's implementation:**
```python
# In every Prefect flow and Celery task
try:
    result = await run_investigation(...)
    return result
finally:
    from django.db import connections
    connections.close_all()
```

Long-running async tasks accumulate idle Django database connections. Explicitly closing all connections in the `finally` block of every Celery task prevents connection pool exhaustion, especially when Celery has many workers.

**Apply to Sova:** Add this `finally` block to every Celery task in Sova — both sub-fragment collectors and tool-execution tasks.

---

### 3.7 Sub-fragment Health Monitoring Schema

**Eva's implementation:** Eva has `EvalAgentConversation.deep_searches` (run counter) and `EvalAgentReports.state` (per-run result including `cancelled`, `error`). The Prefect UI shows per-flow-run states.

**Apply to Sova:** Build the `SubFragmentRunLog` model described in §1.3, and expose a health endpoint:

```
GET /api/v1/sova/health/collectors/
→ {
    "collectors": [
      {
        "name": "google_places_collector",
        "last_run_at": "2026-06-13T14:22:00Z",
        "status": "success",
        "records_written": 1247,
        "next_expected_run": "2026-06-14T14:22:00Z"
      },
      {
        "name": "nppes_collector",
        "last_run_at": "2026-05-01T00:00:00Z",
        "status": "success",
        "records_written": 187423,
        "next_expected_run": "2026-06-01T00:00:00Z"
      }
    ],
    "stale_collectors": ["business_license_monitor"],  # last_run > 2× interval
    "silent_fail_collectors": []                        # ran successfully but wrote 0 records
  }
```

The orchestrator's job is to keep all collectors healthy and alert when they aren't.

---

## Layer 4 — Chatbot Agent

This is the most direct parallel between Eva and Sova. Eva has a chatbot interface backed by LangGraph + Anthropic Claude that calls tools and maintains multi-turn conversation state. Sova will have the same.

---

### 4.1 LangGraph StateGraph with MessagesState

**Eva's implementation:**
```python
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import MessagesState

def _build_chatbot_graph(llm, tools, checkpointer):
    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        lambda state: "tools" if state["messages"][-1].tool_calls else END,
        {"tools": "tools", END: END}
    )
    workflow.add_edge("tools", "agent")
    return workflow.compile(checkpointer=checkpointer, recursion_limit=25)
```

The minimal chatbot graph: `agent` node calls the LLM → if tool calls, `tools` node executes them → loop back to `agent` → if no tool calls, END. This is Eva's chatbot verbatim, and it is exactly what Sova's chatbot should be.

**Apply to Sova:** Copy this graph structure wholesale. The only difference is the tools provided — instead of Eva's DB query + GCP log + GitHub tools, Sova binds its intelligence tools (lead_score, outreach_brief, competitive_report, market_intelligence, etc.):

```python
SOVA_CHATBOT_TOOLS = [
    get_lead_score,           # @tool — compute score for a practice
    get_outreach_brief,       # @tool — generate full outreach brief
    get_competitive_report,   # @tool — what did competitors do this week
    get_hot_leads,            # @tool — list HOT leads by filter
    get_client_health,        # @tool — health score for a client
    get_market_intelligence,  # @tool — weekly market briefing
    search_knowledge,         # @tool — pgvector knowledge base lookup
]
```

---

### 4.2 AsyncPostgresSaver — Conversation State Persistence

**Eva's implementation:**
```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async def get_async_checkpointer_context():
    conn_str = _make_conn_string()
    async with AsyncPostgresSaver.from_conn_string(conn_str) as checkpointer:
        await checkpointer.setup()  # creates checkpoint tables if not exist
        yield checkpointer
```

**Tables created by `checkpointer.setup()`:**
- `checkpoints` — per-thread, per-step state snapshot
- `checkpoint_blobs` — serialized state data
- `checkpoint_writes` — pending state updates before checkpoint commit

The same `thread_id` passed to `graph.ainvoke(input, config={"configurable": {"thread_id": thread_id}})` resumes the exact state from the last checkpoint. Conversation history is fully durable across Celery worker restarts.

**Apply to Sova:** Use `AsyncPostgresSaver` from day one in the chatbot layer. Every conversation gets a `thread_id` (stored in `SovaConversation.thread_id`). When a sales rep continues a conversation from yesterday, LangGraph resumes from the exact last checkpoint. The sales rep does not need to re-explain context.

```python
async def invoke_chatbot(query: str, thread_id: str) -> str:
    async with get_async_checkpointer_context() as checkpointer:
        graph = build_sova_chatbot_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id}}
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=query)]},
            config=config
        )
    return result["messages"][-1].content
```

---

### 4.3 Mode Router — Query Classification

**Eva's implementation:**
```python
class ModeRoutingDecision(BaseModel):
    route: Literal["chatbot", "deep_search_bi", "deep_search_sre", "deep_search_multi"]
    reason: str
    confidence: str
    signals: List[str]

async def plan_eval_agent_dispatch(query, auto_route=True, ...) -> EvalAgentDispatchPlan:
    if not auto_route:
        return EvalAgentDispatchPlan(use_deep_search=deep_search, ...)
    
    # LLM route: use lightest model (Haiku), temp=0, max_tokens=1024
    llm = ChatAnthropic(model=ROUTING_MODEL, temperature=0, max_tokens=1024, timeout=60)
    decision = await llm.with_structured_output(ModeRoutingDecision).ainvoke([
        SystemMessage(content=QUERY_MODE_ROUTING_PROMPT),
        HumanMessage(content=f"Query: {query}\n\nThread: {thread_context}")
    ])
    return _build_dispatch_plan(decision)
    
    # Fallback: always chatbot if routing fails
```

Key design decisions:
- Use the lightest model for routing (Haiku, 1024 tokens, temp=0) — this call is classification, not reasoning
- `auto_route=True` by default, but users can bypass with explicit flags
- Always fall back to chatbot on any routing failure
- Routing decision is a typed Pydantic object, not a string

**Apply to Sova:** When a sales rep sends a message, classify it:

```python
class SovaRoutingDecision(BaseModel):
    route: Literal["chatbot", "deep_analysis", "report_generation"]
    reason: str

# "What are the hottest leads in Texas?" → chatbot (quick tool call)
# "Run a full competitive analysis for this week" → report_generation (async, SSE)
# "Score every practice in NYC that posted a front desk job this month" → deep_analysis (async batch)
```

Use `claude-haiku-*` (cheapest, fastest) for routing. Always fall back to `chatbot` on failure. The router call costs a fraction of a cent — do not skip it to "save money." The wrong mode costs far more.

---

### 4.4 Context Auto-Summarization When Window Grows

**Eva's implementation:**
```python
MAX_MESSAGES_BEFORE_SUMMARIZE = 15
KEEP_RECENT_MESSAGES = 5

async def _summarize_old_messages(messages, llm) -> str:
    """Summarize the oldest messages to keep context manageable."""
    to_summarize = messages[:-KEEP_RECENT_MESSAGES]
    summary = await llm.ainvoke([
        SystemMessage(content="Summarize this conversation preserving all key facts, identifiers, and open questions."),
        HumanMessage(content=format_messages(to_summarize))
    ])
    return summary.content

async def trim_messages_for_llm(messages, llm):
    if len(messages) > MAX_MESSAGES_BEFORE_SUMMARIZE:
        summary = await _summarize_old_messages(messages, llm)
        return [SystemMessage(content=f"Summary of earlier conversation:\n{summary}")] + messages[-KEEP_RECENT_MESSAGES:]
    return messages
```

**Apply to Sova:** A sales rep investigating a single dental practice over multiple turns will accumulate substantial context (lead scores, signal explanations, competitor reports). At 15+ messages, summarize the older portion before the next LLM call. Keep the 5 most recent messages verbatim. This keeps token costs bounded while preserving continuity across long sessions.

---

### 4.5 Redis SSE Streaming with Cursor-Based Replay

**Eva's implementation:**

Events published to Redis:
```python
# publish_stream_event in deep_agent_stream.py
def publish_stream_event(job_id: str, *, event: str, data: dict) -> dict:
    event_id = redis.incr(f"eval_agent:deep_stream:counter:{job_id}")
    event_payload = json.dumps({"id": event_id, "event": event, "data": data})
    
    redis.pipeline()
        .rpush(f"eval_agent:deep_stream:events:{job_id}", event_payload)  # buffered list
        .expire(f"eval_agent:deep_stream:events:{job_id}", 86400)         # 24h TTL
        .setex(f"eval_agent:deep_stream:status:{job_id}", 86400, "running")
        .publish(f"eval_agent:deep_stream:channel:{job_id}", event_payload)
        .execute()
```

SSE endpoint format:
```
id: 42
event: tool_result
data: {"tool": "get_lead_score", "result": {"score": 84, "tier": "HOT"}}

id: 43
event: partial_text
data: {"text": "Based on the lead score analysis..."}

id: 99
event: final_text
data: {"text": "Here are the 10 hottest leads in Texas..."}
```

Resume: SSE client sends `Last-Event-ID: 42` header on reconnect. The endpoint replays all events with `id > 42` from the Redis list.

**Apply to Sova:** For the chatbot's streaming output (tool calls visible in real-time, partial text as the LLM types), implement the exact same Redis pub/sub + list buffer pattern. Key insight: **the list buffer is the resume mechanism**. If the SSE connection drops at event 42, the client reconnects and gets events 43–N replayed instantly from the list. The live channel is for real-time delivery; the list is for replay. Both are always written.

Event types for Sova's chatbot:
- `run_started` — job began
- `thinking` — LLM is reasoning (no tool call yet)
- `tool_call` — LLM decided to call a tool (show which tool + args)
- `tool_result` — tool returned a result (show summary)
- `partial_text` — streaming LLM response text
- `final_text` — complete response
- `run_completed` — terminal event, client closes connection
- `run_failed` — error, client shows error state
- keepalive (10s interval) — prevents proxy timeout

---

### 4.6 DRF API Surface — Five Endpoints

**Eva's implementation:**

Eva's complete API surface for the chatbot and deep search:

```
POST   /threads/                           → create new conversation, get thread_id
POST   /query/                             → submit query (HTTP 202 + job_id)
GET    /query/<job_id>/                    → poll status
GET    /threads/<thread_id>/runs/<run_id>/stream/   → SSE event stream
POST   /threads/<thread_id>/runs/<run_id>/cancel/   → cancel a running job
```

**Apply to Sova:** Same five endpoints, same HTTP semantics:

```
POST   /api/v1/sova/conversations/                  → create thread
POST   /api/v1/sova/conversations/<thread_id>/query/ → submit (202 + run_id)
GET    /api/v1/sova/tasks/<run_id>/                  → poll status
GET    /api/v1/sova/tasks/<run_id>/stream/           → SSE stream
POST   /api/v1/sova/tasks/<run_id>/cancel/           → cancel
```

Input serializer fields for the query endpoint:

```python
class SovaQueryInputSerializer(serializers.Serializer):
    query = serializers.CharField()
    context = serializers.CharField(required=False)  # supplemental context
    thread_id = serializers.CharField(required=False)  # attach to existing conversation
    auto_route = serializers.BooleanField(default=True)
    mode = serializers.ChoiceField(
        choices=["chatbot", "deep_analysis", "report_generation"],
        required=False
    )
```

---

### 4.7 Tool Registry and LangChain @tool Decorator

**Eva's implementation:**
```python
from langchain_core.tools import tool, BaseTool

@tool
async def run_query(sql: str) -> str:
    """Execute a SQL query against the analytics database. Read-only."""
    return await db_client.execute_query(sql)

@tool
async def search_knowledge(query: str) -> str:
    """Search the curated knowledge base for relevant facts."""
    results = knowledge_store.search(query, k=3)
    return format_knowledge_results(results)

# Complex tools use BaseTool for custom invocation
class GetGCPLogsTool(BaseTool):
    name = "get_gcp_logs_tool"
    description = "Fetch GCP Cloud Run logs for a specific call session."
    
    async def _arun(self, session_id: str, ...) -> str:
        # ... implementation
```

Tools are bound to the LLM once per chatbot session:
```python
llm_with_tools = llm.bind_tools(all_tools)
```

**Apply to Sova:** Define all Sova tools using `@tool` for simple cases and `BaseTool` for complex ones. Docstrings matter — the LLM reads the docstring to decide when to use the tool:

```python
@tool
async def get_hot_leads(
    state: Optional[str] = None,
    specialty: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Get the current HOT leads from the Sova database.
    Use this when the user asks for lead lists, top prospects, or hot practices.
    
    Args:
        state: Two-letter US state code to filter by (e.g. 'TX', 'CA')
        specialty: Dental specialty filter (e.g. 'general', 'orthodontic', 'pediatric')
        limit: Maximum number of leads to return (default 10, max 50)
    
    Returns:
        JSON list of HOT leads with name, score, location, and top signal
    """
    leads = await Lead.objects.filter(
        tier="HOT",
        **({'state': state} if state else {}),
        **({'specialty': specialty} if specialty else {}),
    ).select_related('practice').order_by('-composite_score')[:limit]
    return json.dumps([lead.to_brief_dict() for lead in leads])
```

The docstring is the tool's interface to the LLM. Write it like API documentation, not a comment.

---

### 4.8 asgiref sync_to_async Bridge

**Eva's implementation:**
```python
from asgiref.sync import sync_to_async

# Django ORM is synchronous. LangGraph runs asynchronously.
# Bridge them with sync_to_async.

async def _load_chatbot_prior_messages_from_db(thread_id: str):
    conversation = await sync_to_async(
        EvalAgentConversation.objects.get
    )(thread_id=thread_id)
    return conversation.messages
```

**Apply to Sova:** Every Django ORM query inside an async LangGraph node, an async tool, or an async chatbot function must be wrapped with `sync_to_async`. Django's ORM is synchronous and will block the event loop if called directly from async code:

```python
from asgiref.sync import sync_to_async

async def get_practice_data(npi: str) -> dict:
    practice = await sync_to_async(Practice.objects.get)(npi=npi)
    signals = await sync_to_async(list)(
        Signal.objects.filter(practice=practice).order_by('-collected_at')[:50]
    )
    return {"practice": practice, "signals": signals}
```

Alternatively, use `database_sync_to_async` from `channels` for Django ORM calls that are part of a larger async workflow.

---

### 4.9 Multi-Turn State Management in `SovaConversation.messages`

**Eva's implementation:**
```python
class EvalAgentConversation(models.Model):
    messages = models.JSONField(default=list)
    # Stored as: [{"role": "user", "content": "...", "timestamp": "...", "source": "api"}]

# On each turn, append to messages:
def append_message(conversation, role, content, source="api"):
    conversation.messages.append({
        "role": role,
        "content": content,
        "timestamp": format_timestamp(timezone.now()),
        "source": source,
        "is_final": True
    })
    conversation.save(update_fields=["messages", "updated_at"])
```

Conversation history is stored in the Django model (durable, queryable) as a complement to the LangGraph checkpoint (which stores full state including intermediate tool calls).

**Apply to Sova:** The LangGraph checkpoint stores the complete technical state. The `SovaConversation.messages` JSONField stores the *user-visible* conversation history — the cleaned, final turns that a UI would display. Keep both. The LangGraph checkpoint is for resuming the agent. The messages field is for rendering the conversation to the user.

---

### 4.10 Rate Limiting at the API Layer

**Eva's implementation:**
```python
API_RATE_LIMIT = 10  # queries per minute per user
```

Enforced upstream of the DRF view. Any request beyond 10/minute gets HTTP 429.

**Apply to Sova:** Use `django-ratelimit` or a Redis-based counter on the query endpoint. The chatbot is backed by Anthropic API calls — unbounded usage is a cost risk:

```python
from django_ratelimit.decorators import ratelimit

class SovaChatbotQueryView(APIView):
    @ratelimit(key='user', rate='10/m', method='POST', block=True)
    def post(self, request):
        ...
```

---

## Technology Checklist — Everything Sova Needs from Eva's Stack

| Technology | Eva's use | Sova's use | Priority |
|---|---|---|---|
| `langgraph` | StateGraph, MessagesState, conditional edges | Chatbot graph, future deep analysis graphs | When chatbot is built |
| `langgraph-checkpoint-postgres` | AsyncPostgresSaver — durable conversation state | Same — conversation checkpointing | When chatbot is built |
| `langchain-anthropic` | ChatAnthropic — all LLM calls | Same | Day 1 (first LLM sub-fragment) |
| `langchain-openai` | OpenAIEmbeddings — knowledge base | Same — pgvector knowledge base | When knowledge base is built |
| `langchain-core` | @tool, BaseTool, message types | Same | When chatbot is built |
| `langsmith` | LLM call tracing | Same | When first LLM sub-fragment ships |
| `pydantic` v2 | All state, request, response schemas | Same — every LLM output, every DB record | Day 1 |
| `tenacity` | Retry on DB calls | Retry on all external HTTP calls + DB writes | Day 1 |
| `pgvector` | Knowledge base vector search | Outreach playbooks, case study matching, objection handling | When knowledge base is built |
| `django-redis` | Cache backend for mutex locks + in-memory cache | Same | Day 1 (Redis already required for Celery) |
| `redis` client | SSE pub/sub for streaming | Same | When chatbot SSE is built |
| `asgiref.sync_to_async` | Django ORM bridge in async LangGraph | Same | When chatbot is built |
| `sentry-sdk[django,celery]` | Exception capture | Same | Day 1 |
| `psycopg_pool` | Async connection pool for LangGraph checkpointer | Same | When chatbot is built |
| `sqlparse` | SQL safety validation | Same — when LLM can generate SQL | When chatbot SQL tool is built |

---

## What NOT to Take from Eva

| Eva Component | Why Not |
|---|---|
| Prefect | Sova uses Celery Beat. Prefect solves workflow DAGs with UI. Add later only if multi-step pipeline dependencies become unmanageable. |
| GitHub MCP | Eva debugs production code. Sova has no analogous use case. |
| Langfuse trace inspection | Eva inspects voice agent call traces. Sova does not. |
| GCP Cloud Logging integration | Eva debugs cloud infrastructure. Sova does not. |
| Twilio voice debug | Eva inspects call SIDs. Sova's Twilio usage (outbound test calls) is entirely different. |
| `text-embedding-3-large` (3072-dim) | Use `text-embedding-3-small` (1536-dim). 5× cheaper, 90%+ quality for Sova's retrieval tasks. |
| `mem0ai` + Qdrant | Disabled in Eva. Too immature. Not needed for v1. |
| Multi-agent supervisor pattern | Eva coordinates BI + SRE agents. Sova's chatbot is single-agent. Add multi-agent routing only if different analysis modes (quick vs deep) warrant separate specialized agents. |
| FAISS LocalKnowledgeStore | Eva uses this as a local dev fallback for pgvector. pgvector is already required for Sova's main DB. Use pgvector everywhere. |
| xhtml2pdf / PDF export | Not needed now. |

---

## Build Order Recommendation

Based on Eva's architecture and Sova's four layers:

**Phase 0 — Foundation (do first, everything depends on this)**
1. `sova/config.py` — `SovaConfig` class with all knobs
2. `sova/utils/retry.py` — shared Tenacity decorator
3. `SubFragmentRunLog` model
4. Sentry SDK integration
5. Django cache mutex pattern
6. Docker Compose with Django + Postgres + Redis + Celery worker + Celery Beat + Flower

**Phase 1 — First sub-fragments**
7. `nppes_collector` — master practice table
8. `google_places_collector` — reviews and phone friction
9. `dentalpost_collector` + `indeed_collector` — job signals
10. All sub-fragments use Phase 0 patterns from day one

**Phase 2 — First tools (after data is flowing)**
11. Pydantic output schemas for all LLM tools
12. pgvector knowledge base setup + `build_knowledge_index` command
13. `Lead Score` tool (reads from Phase 1 tables)
14. `Outreach Brief` tool (reads from Lead Score + sub-fragment tables)
15. LangSmith instrumented on all LLM calls

**Phase 3 — Chatbot (after tools are stable)**
16. LangGraph chatbot graph (2 nodes: agent + tools)
17. `AsyncPostgresSaver` checkpointer setup
18. DRF API surface (5 endpoints)
19. Redis SSE streaming
20. Mode router (LLM classification of query type)
21. All Sova tools bound as LangGraph tools with proper docstrings
