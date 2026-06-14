"""
Simple shared-secret API key authentication.

Clients send `X-API-Key: <key>`. We compare against the SOVA_API_KEY env var.
This is a minimal auth scheme suitable for an internal backend — fine for
dev and early production, replace with per-user tokens when we need scoped
access.
"""

from django.conf import settings
from rest_framework import authentication, exceptions


class APIKeyUser:
    """Stand-in user for shared-secret API key auth.

    DRF's IsAuthenticated permission checks `request.user.is_authenticated`,
    which is False on Django's AnonymousUser. We're not tying API keys to
    real database users (no per-user keys yet), so we use this minimal
    stand-in that satisfies the permission check.
    """

    is_authenticated = True
    is_anonymous = False
    is_active = True
    is_staff = False
    is_superuser = False
    pk = None
    username = 'api-key-user'

    def __str__(self) -> str:
        return self.username


class SovaAPIKeyAuthentication(authentication.BaseAuthentication):
    """Authenticate any request that presents the correct X-API-Key header."""

    def authenticate(self, request):
        provided = request.META.get('HTTP_X_API_KEY')
        if not provided:
            return None  # Returning None lets DRF try the next auth class.

        expected = getattr(settings, 'SOVA_API_KEY', '')
        if not expected or provided != expected:
            raise exceptions.AuthenticationFailed('Invalid or missing API key.')

        return (APIKeyUser(), provided)
