"""
SovaBaseTask — the Celery base class every collector inherits from.

Why have a base class at all? Three cross-cutting concerns every collector
needs to handle, where forgetting any one of them causes real problems:

1. Health tracking — every run (success or failure) updates SubFragmentRunLog
   so the /api/v1/health/collectors/ endpoint can report which collectors are
   stale or silently failing.

2. DB connection cleanup — Django's ORM opens a connection per-thread. Celery
   workers run many tasks; without explicit cleanup, the connection pool gets
   exhausted within hours of operation.

3. Consistent error truncation — exception messages can be huge (full HTML
   responses, stack traces). We cap them at 2000 chars so the run-log row
   doesn't bloat the database.

Every collector task should declare it like:

    @shared_task(bind=True, base=SovaBaseTask, name='collectors.tasks.foo')
    def foo_collector(self):
        ...

The four lifecycle hooks below are called by Celery automatically:
    before_start  → before the task body runs
    on_success    → after the task body returns normally
    on_failure    → after the task body raises
    after_return  → always, after success OR failure
"""

from celery import Task
from django.db import connections
from django.utils import timezone


class SovaBaseTask(Task):
    """Abstract base — set as the `base=` for every @shared_task in the project."""

    abstract = True  # Don't register this as a runnable task itself.

    # ---------- Lifecycle hooks ----------

    def before_start(self, task_id, args, kwargs):
        """Called immediately before the task body executes.

        Currently a no-op kept here as an obvious hook for future cross-cutting
        concerns (request-scoped logging, tracing spans, etc.).
        """
        return super().before_start(task_id, args, kwargs)

    def on_success(self, retval, task_id, args, kwargs):
        """Record a successful run.

        Convention: tasks return an integer = number of records written.
        Anything else (None, dict, etc.) is recorded as 0 records.
        """
        records_written = retval if isinstance(retval, int) else 0
        self._record_run(
            status='success',
            records_written=records_written,
            error_message='',
        )

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Record a failed run, with the exception message truncated."""
        self._record_run(
            status='failed',
            records_written=0,
            error_message=str(exc)[:2000],
        )

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Runs after success OR failure. Last chance for cleanup.

        We close all DB connections held by this worker thread. Without this,
        Django's connection pool fills up over time and eventually rejects new
        connections — a common failure mode in long-running Celery deployments.
        """
        connections.close_all()
        return super().after_return(status, retval, task_id, args, kwargs, einfo)

    # ---------- Internal ----------

    def _record_run(self, status: str, records_written: int, error_message: str) -> None:
        """Upsert a row in SubFragmentRunLog keyed on this task's name.

        Lazy import inside the method: SubFragmentRunLog is in core.models, which
        Django can't load until app registry is ready. By the time on_success /
        on_failure runs (inside a running task), the registry is always ready.
        """
        from core.models import SubFragmentRunLog  # noqa: PLC0415

        SubFragmentRunLog.objects.update_or_create(
            name=self.collector_name,
            defaults={
                'last_run_at': timezone.now(),
                'last_run_status': status,
                'records_written': records_written,
                'error_message': error_message,
            },
        )

    @property
    def collector_name(self) -> str:
        """The trailing segment of the task's dotted name.

        e.g. 'collectors.tasks.practice_data.nppes_collector' → 'nppes_collector'
        Matches the 'name' column in SubFragmentRunLog.
        """
        return (self.name or 'unknown').rsplit('.', 1)[-1]
