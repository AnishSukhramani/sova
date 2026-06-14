"""
Retry decorator for unreliable external calls.

Use `sova_retry` on any function that talks to the outside world: HTTP requests,
third-party API calls, web scraping. Don't use it on internal logic — failures
there are bugs, not transient errors.

Behavior:
    - Up to 3 attempts total (1 original + 2 retries)
    - Exponential backoff between attempts: 1s, 2s, 4s, ... capped at 10s
    - On final failure, the original exception is re-raised

Example:
    from core.utils.retry import sova_retry

    @sova_retry
    def fetch_nppes_page(url: str) -> str:
        return httpx.get(url, timeout=30).text
"""

from tenacity import retry, stop_after_attempt, wait_exponential

sova_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
