"""
PII (personally identifiable information) redaction for log messages.

When something fails in a collector, we want to log enough context to debug —
but log files often end up in third-party tools (Sentry, CloudWatch). Phone
numbers and emails of dental practice owners should never reach those tools
in raw form.

Call `sanitize_for_log` on any string before passing it to a logger or to
Sentry's `extra` payload.

Examples:
    >>> sanitize_for_log("Failed to call 5551234567")
    'Failed to call [PHONE]'

    >>> sanitize_for_log("Bounced email: owner@example.com")
    'Bounced email: [EMAIL]'

    >>> sanitize_for_log("Practice contact: owner@dental.com / 5551234567")
    'Practice contact: [EMAIL] / [PHONE]'

Note: the phone regex matches any 10+ consecutive digits. NPIs (also 10 digits)
will be redacted as [PHONE] — acceptable trade-off since NPIs are public anyway.
"""

import re

_EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
_PHONE_PATTERN = re.compile(r'\b\d{10,}\b')


def sanitize_for_log(text: str) -> str:
    """Replace emails and phone numbers in `text` with [EMAIL] / [PHONE] tokens."""
    text = _EMAIL_PATTERN.sub('[EMAIL]', text)
    text = _PHONE_PATTERN.sub('[PHONE]', text)
    return text
