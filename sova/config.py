"""
Central configuration constants for Sova.

Every tunable value in the system lives here — thresholds, timeouts, model
names, rate limits, character caps, signal decay half-lives. Code throughout
the project imports from this class instead of hardcoding magic numbers.

The "no magic numbers" rule:
    BAD:  if score >= 78:  ...
    GOOD: if score >= SovaConfig.HOT_SCORE_THRESHOLD:  ...

When a threshold needs tuning, you change it in one place and the whole
system picks it up. Don't grep the codebase for "78."
"""

from django.conf import settings


class SovaConfig:
    # ---------- LLM Models ----------
    # Models are referenced by string ID. Anthropic and OpenAI version their
    # models — pinning the version here keeps behavior reproducible.
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"
    FAST_MODEL = "claude-haiku-4-5-20251001"          # routing, classification
    ANALYSIS_MODEL = "claude-sonnet-4-6"              # outreach briefs, reports
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS = 1536
    TEMPERATURE = 0.3
    MAX_TOKENS = 4096

    # ---------- Scoring Thresholds ----------
    # A practice scores HOT only if composite_score >= 78 AND fit_score >= 65.
    # See tools/lead_score.py (Phase 5) for the full scoring rules.
    HOT_SCORE_THRESHOLD = 78
    HOT_FIT_THRESHOLD = 65

    # Confidence buckets — used to weight signals during scoring.
    # n >= 500 evidence points => HIGH confidence (full weight, 1.0x)
    # 100 <= n < 500           => MODERATE (0.75x)
    # n < 100                  => LOW (0.5x)
    HIGH_CONFIDENCE_THRESHOLD = 500
    MODERATE_CONFIDENCE_THRESHOLD = 100

    # ---------- Celery / Tasks ----------
    TASK_TIMEOUT_SECONDS = 300          # generic task budget
    HTTP_REQUEST_TIMEOUT = 30           # sync httpx calls
    TOOL_TIMEOUT = 60                   # intelligence tool execution
    # Celery hard/soft limits: at SOFT, the task gets a SoftTimeLimitExceeded
    # exception (chance to clean up). At HARD, the worker kills the process.
    CELERY_HARD_TIME_LIMIT = 900        # 15 minutes
    CELERY_SOFT_TIME_LIMIT = 840        # 14 minutes

    # ---------- Rate Limits ----------
    CHATBOT_API_RATE_LIMIT = 10         # requests per minute per user

    # ---------- Chatbot (v2 — Phase 10) ----------
    CHATBOT_RECURSION_LIMIT = 25        # max LangGraph node steps per query
    MAX_MESSAGES_BEFORE_SUMMARIZE = 15  # trigger context auto-summarization
    KEEP_RECENT_MESSAGES = 5            # keep verbatim, summarize the rest

    # ---------- Knowledge Base (pgvector) ----------
    KNOWLEDGE_HIT_THRESHOLD = 0.75      # cosine similarity to count as a hit
    KNOWLEDGE_CACHE_TTL_SECONDS = 900   # 15-minute in-process cache for slow-changing data

    # ---------- Token / Context Caps ----------
    # Hard ceilings on how much data we shove into an LLM prompt.
    # When data exceeds the cap, truncate to the most recent N records.
    MAX_OUTREACH_BRIEF_SIGNALS_CHARS = 8000
    MAX_COMPETITIVE_REPORT_CHANGES_CHARS = 12000
    MAX_REVENUE_RESCUE_EVIDENCE_CHARS = 6000
    MAX_CHATBOT_CONTEXT_CHARS = 48000
    MAX_SCHEMA_CHARS = 3000

    # ---------- SQL Safety (chatbot LLM-generated queries) ----------
    # Any SQL the LLM produces is regex-matched against these patterns. A match
    # means we refuse to execute — chatbot can read, never write.
    DANGEROUS_SQL_PATTERNS = [
        r'\bINSERT\b', r'\bUPDATE\b', r'\bDELETE\b', r'\bDROP\b',
        r'\bTRUNCATE\b', r'\bALTER\b', r'\bCREATE\b', r'\bGRANT\b',
        r'\bREVOKE\b', r'\bEXEC(UTE)?\b',
    ]
    SQL_STATEMENT_TIMEOUT_MS = 30000    # statement_timeout for LLM-generated SQL
    SQL_FALLBACK_LIMIT = 1000           # auto-appended LIMIT if missing

    # ---------- Signal Decay Half-Lives (days) ----------
    # Signals lose value exponentially over time. A 7-day half-life means a
    # signal collected 7 days ago contributes half its raw_value to the score.
    # Decay formula: raw × exp(-ln(2) × age_days / half_life).
    HALF_LIFE_DEMO_CALL = 7
    HALF_LIFE_JOB_POSTING = 14
    HALF_LIFE_REVIEW_COMPLAINT = 21
    HALF_LIFE_OWNERSHIP_TRANSFER = 60
    HALF_LIFE_NEW_NPI = 90
    HALF_LIFE_TECHNOGRAPHIC_GAP = 180

    @classmethod
    def is_langsmith_enabled(cls) -> bool:
        """True only if BOTH tracing is on AND an API key is configured.

        Reading both flags before phoning home to LangSmith prevents wasted
        network calls when the key is missing.
        """
        return bool(
            getattr(settings, 'LANGSMITH_TRACING', False)
            and getattr(settings, 'LANGSMITH_API_KEY', None)
        )
