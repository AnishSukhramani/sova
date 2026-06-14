"""
Shared utilities for collectors, tools, and the orchestrator.

Each module here is single-purpose:
    retry.py    — exponential backoff decorator
    logging.py  — PII sanitization for log messages
    cache.py    — distributed locks + two-level knowledge cache
    tasks.py    — SovaBaseTask, the Celery task base class
"""
