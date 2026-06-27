"""
Collector tasks package.

Celery's autodiscover_tasks imports `<app>.tasks` — for a package (this folder)
that means it runs THIS __init__.py and nothing else. The submodules below
must be explicitly imported here, otherwise their @shared_task decorators
never run and the tasks aren't registered with Celery.

Every new collector task module added under collectors/tasks/ should get an
import line below.
"""

from . import practice_data  # noqa: F401
