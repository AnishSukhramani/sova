"""
Sova project package.

We import the Celery app here so it gets loaded whenever Django starts.
Without this, @shared_task decorators in our apps would never be registered
because Celery's app object wouldn't exist yet when the apps load.

`celery_app` is also re-exported under that name so tools (Flower, CLI commands)
that look for `<project>.celery_app` can find it.
"""

from .celery import app as celery_app

__all__ = ('celery_app',)
