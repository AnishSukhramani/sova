"""Core API views — health, practice list/detail."""

from django.core.cache import cache
from django.db import connection
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Practice
from .serializers import PracticeDetailSerializer, PracticeListSerializer


class SystemHealthView(APIView):
    """GET /api/v1/health/ — service liveness probe.

    Unauthenticated by design (used by load balancers / uptime monitors).
    Returns 200 with a status JSON whether the dependencies are healthy or not —
    callers grep the body fields, not the status code.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request):
        statuses = {
            'db': self._check_db(),
            'redis': self._check_redis(),
            'celery': self._check_celery(),
        }
        overall = 'healthy' if all(v == 'ok' for v in statuses.values()) else 'degraded'
        return Response({'status': overall, **statuses})

    def _check_db(self) -> str:
        try:
            connection.ensure_connection()
            return 'ok'
        except Exception:  # noqa: BLE001 — health check; we want to never raise
            return 'error'

    def _check_redis(self) -> str:
        try:
            cache.set('health:probe', 'ok', timeout=5)
            return 'ok' if cache.get('health:probe') == 'ok' else 'error'
        except Exception:  # noqa: BLE001
            return 'error'

    def _check_celery(self) -> str:
        try:
            from sova.celery import app as celery_app
            replies = celery_app.control.ping(timeout=2)
            return 'ok' if replies else 'no_workers'
        except Exception:  # noqa: BLE001
            return 'error'


class PracticeListView(generics.ListAPIView):
    """GET /api/v1/practices/ — list with optional filters."""

    serializer_class = PracticeListSerializer

    def get_queryset(self):
        qs = Practice.objects.all()
        state = self.request.query_params.get('state')
        specialty = self.request.query_params.get('specialty')
        is_active = self.request.query_params.get('is_active')
        if state:
            qs = qs.filter(state=state.upper())
        if specialty:
            qs = qs.filter(specialty_taxonomy_code=specialty)
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ('true', '1', 'yes'))
        return qs.order_by('npi')


class PracticeDetailView(generics.RetrieveAPIView):
    """GET /api/v1/practices/<npi>/ — single practice with all fields."""

    queryset = Practice.objects.all()
    serializer_class = PracticeDetailSerializer
    lookup_field = 'npi'
