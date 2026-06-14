"""
Orchestrator background tasks.

Stubs for now — real implementations come in later phases. These exist so the
Celery Beat schedule has real task names to reference from day one.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='orchestrator.tasks.smoke_test')
def smoke_test() -> str:
    """Sanity check — confirms Celery is dispatching and workers are running."""
    return 'Celery is working'


@shared_task(name='orchestrator.tasks.check_collector_health')
def check_collector_health() -> dict:
    """Hourly: scan SubFragmentRunLog and log any stale/silent-fail collectors.

    Real reporting (Slack alerts, etc.) comes later — for now this just emits
    a log line so we can verify Beat is firing it.
    """
    from datetime import timedelta

    from django.utils import timezone

    from core.models import SubFragmentRunLog

    now = timezone.now()
    stale, silent_fail = [], []
    for log in SubFragmentRunLog.objects.all():
        if log.last_run_at and (now - log.last_run_at) > timedelta(hours=2 * log.expected_interval_hours):
            stale.append(log.name)
        if log.last_run_status == 'success' and log.records_written == 0:
            silent_fail.append(log.name)
    logger.info('Collector health: stale=%s silent_fail=%s', stale, silent_fail)
    return {'stale': stale, 'silent_fail': silent_fail}


@shared_task(name='orchestrator.tasks.recompute_all_lead_scores')
def recompute_all_lead_scores() -> str:
    """Daily 2 AM UTC: recompute lead scores for all practices with recent signals.

    Stub — real implementation in Phase 5 once the lead-score engine exists.
    """
    logger.info('Lead score recomputation not yet implemented (Phase 5).')
    return 'not_implemented'
