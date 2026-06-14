"""Orchestrator API views — task status, cancellation, collector health."""

from datetime import timedelta

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import SubFragmentRunLog
from core.serializers import SubFragmentRunLogSerializer

from .models import SovaTaskRun
from .serializers import TaskStatusSerializer


class TaskStatusView(generics.RetrieveAPIView):
    """GET /api/v1/tasks/<run_id>/ — poll a task's current state."""

    queryset = SovaTaskRun.objects.all()
    serializer_class = TaskStatusSerializer
    lookup_field = 'run_id'


class TaskCancelView(APIView):
    """POST /api/v1/tasks/<run_id>/cancel/ — request cooperative cancellation.

    Sets a Redis key the running task can poll. The task itself decides when
    (and whether) to honor the cancellation — Celery's hard time limit is the
    backstop if the task ignores it.
    """

    def post(self, request, run_id):
        task = get_object_or_404(SovaTaskRun, run_id=run_id)
        cache.set(f'sova:cancel:{task.run_id}', '1', timeout=3600)
        return Response({'cancelled': True, 'run_id': str(task.run_id)})


class CollectorHealthView(APIView):
    """GET /api/v1/health/collectors/ — aggregate collector health.

    Reports stale collectors (haven't run in 2x their expected interval) and
    silent-fail collectors (last status=success but 0 records written).
    """

    def get(self, request):
        logs = list(SubFragmentRunLog.objects.all())
        now = timezone.now()

        stale = []
        silent_fail = []
        healthy = 0

        for log in logs:
            if log.last_run_at:
                age = now - log.last_run_at
                if age > timedelta(hours=2 * log.expected_interval_hours):
                    stale.append(log.name)
            if log.last_run_status == 'success' and log.records_written == 0:
                silent_fail.append(log.name)
            if (
                log.last_run_status == 'success'
                and log.records_written > 0
                and log.name not in stale
            ):
                healthy += 1

        return Response({
            'collectors': SubFragmentRunLogSerializer(logs, many=True).data,
            'stale_collectors': stale,
            'silent_fail_collectors': silent_fail,
            'total_collectors': len(logs),
            'healthy_collectors': healthy,
        })
