"""
Celery application for Sova.

Celery is a separate process (or pool of processes) that runs background tasks.
Django itself doesn't know about Celery — we have to wire it in. This module:

1. Creates the Celery app instance.
2. Tells it to read its config from Django settings (the CELERY_* keys in settings.py).
3. Tells it which Django apps to scan for @shared_task functions.

The app instance is then imported in sova/__init__.py so Django sees it on startup.
"""

import os

from celery import Celery

# Point Celery at our Django settings module before creating the app.
# Workers run as standalone processes — without this, they wouldn't know which
# Django settings to use.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sova.settings')

# Create the Celery app. The string 'sova' is the app's name — shown in logs
# and used as a namespace for default queue names.
app = Celery('sova')

# Pull configuration from Django settings, but only the keys prefixed with CELERY_.
# So CELERY_BROKER_URL in settings.py becomes app.conf.broker_url here.
# The namespace stripping is what lets Django and Celery share one settings file
# without their keys colliding.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks across our apps. For each installed app, Celery will look
# for a `tasks.py` file or a `tasks/` package and register every @shared_task
# inside. This is how we avoid hand-registering all 110+ collector tasks.
app.autodiscover_tasks(['collectors', 'orchestrator', 'tools'])


@app.task(bind=True)
def debug_task(self):
    """Sanity-check task — useful for confirming Celery wiring works.

    Usage from a Django shell:
        from sova.celery import debug_task
        debug_task.delay()
    Then watch the Celery worker logs.
    """
    print(f'Request: {self.request!r}')
