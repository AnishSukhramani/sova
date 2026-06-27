# Sova Architecture Mental Model

> How the Docker services, Django apps, Celery integration, and Postgres-as-bus pattern fit together in this project.

## Key Points

- **Docker services ≠ Django apps.** Services are separate processes (web, celery worker, beat, etc.). Django apps are code modules (`core`, `collectors`, ...). One image runs 5 services; all 6 apps live inside that image.
- **Five sova-image containers, one codebase.** Same Dockerfile, different commands — `gunicorn ...`, `celery -A sova worker ...`, `celery -A sova beat ...`, etc.
- **A Django "project" is the config** (`sova/settings.py`, `sova/urls.py`). A Django "app" is a self-contained feature module ([learndjango](https://learndjango.com/tutorials/django-best-practices-projects-vs-apps)).
- **Celery is glued to Django via two files:** `sova/celery.py` (creates the app) and `sova/__init__.py` (imports it so Django sees it on boot) — the canonical pattern from the [Celery docs](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html).
- **The `CELERY_` namespace trick** in settings (`app.config_from_object('django.conf:settings', namespace='CELERY')`) lets Django and Celery share one settings file.
- **`autodiscover_tasks` finds every `@shared_task`** in each app's `tasks.py` or `tasks/` package — no manual registration of the 110+ collector tasks.
- **Database-as-bus rule:** collectors never call each other; tools never call collectors; Postgres is the only shared state. Standard microservices teaching says shared DBs are an anti-pattern ([Medium — Alberto De Natale](https://thegreenerman.medium.com/why-having-a-shared-database-is-considered-an-anti-pattern-in-the-microservice-architecture-392aee75ff7d)) — but Sova is a monorepo, not microservices. Same-process apps sharing a DB is fine.
- **Volume mount maps host project root to `/app` inside every container.** Code edits on the Mac appear live in containers — no rebuild needed.

## How We Used It / Why It Matters

- Lets us scale Celery workers independently (collectors queue = 8 concurrent, tools queue = 4) without touching the web tier.
- Lets us run any Django management command from any of the 5 sova-image containers — they all have the same code.
- Makes the system inspectable — "why does this practice have this score?" is always a Postgres query, never a runtime trace.
- Each collector can fail without taking down the others. Failure blast radius is one task, not the system.
- Tunable values (`HOT_SCORE_THRESHOLD = 78` etc.) live in `sova/config.py` — single place to change, no grep-replace across files.

## Key Terminology

- **Container:** a single running process (isolated Linux env on macOS via Docker Desktop).
- **Image:** the read-only template a container is built from.
- **Service (Docker Compose):** one named recipe for a long-running container.
- **Django project:** top-level configuration package — settings, URLs, WSGI/ASGI entry.
- **Django app:** a feature module — folder containing models/views/admin/migrations for one slice of functionality.
- **WSGI:** Web Server Gateway Interface — sync entry point Gunicorn uses to call Django.
- **ASGI:** Async Server Gateway Interface — for async views and websockets (not used until Phase 10).
- **Celery broker:** the message queue tasks pass through (Redis for us).
- **Celery beat:** the scheduler that periodically dispatches tasks (cron-like).
- **Bind mount:** Docker volume that points to a host folder — changes sync both ways.
- **Database-as-bus:** architecture rule where Postgres is the only thing components share state through.

## Explore Further

- [Django docs — Apps reference](https://docs.djangoproject.com/en/5.0/ref/applications/) — the authoritative spec on how Django's "app" concept works.
- [Celery — First Steps with Django](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html) — the canonical celery.py + __init__.py wiring; matches what we did exactly.
- [LearnDjango — Projects vs Apps](https://learndjango.com/tutorials/django-best-practices-projects-vs-apps) — short, opinionated, correct.
- [TestDriven.io — The Definitive Guide to Celery and Django](https://testdriven.io/blog/django-and-celery/) — production-grade walkthrough that mirrors our stack closely.
- [SaaSitive — Django, Celery, Redis, Postgres with Docker Compose](https://saasitive.com/tutorial/django-celery-redis-postgres-docker-compose/) — the multi-service pattern, almost the same shape as our `docker-compose.yml`.
- [YouTube — Docker Compose Tutorial: Django + Celery + Redis + Postgres](https://www.youtube.com/watch?v=K4T-5xZVhUs) — January 2025, visual end-to-end walkthrough.
- [YouTube — Monitor Celery Tasks With Flower](https://www.youtube.com/watch?v=5oznWhK3pGs) — short Flower-specific clip; matches our flower service.
- [REVSYS — Celery and Django and Docker: Oh My!](https://www.revsys.com/tidbits/celery-and-django-and-docker-oh-my/) — a senior engineer's working notes; good for absorbing instincts.

## FAQs

**Q: Does each Django app run in its own container?**
A: No. All 6 apps live in the same codebase. Every sova-image container (web, celery worker, beat, flower) loads all of them. Apps are code organization; services are process organization.

**Q: Why do we have 2 Celery worker services instead of 1?**
A: Different queues for different work shapes. `celery-worker-collectors` handles I/O-bound HTTP scrapes (8 concurrent processes). `celery-worker-tools` handles LLM-bound work where over-subscription hits external rate limits (4 concurrent). Splitting them lets each scale independently.

**Q: Why is sharing one Postgres considered fine here when articles call it an anti-pattern?**
A: That anti-pattern applies to **independently deployed microservices** — different teams, different release cycles. Sova is a monorepo with one deployment. Same-process apps sharing one DB is the normal Django pattern. The architectural rule we DO enforce ("collectors don't call each other") gives us most of the decoupling benefit without the operational cost of N databases. [Source](https://thegreenerman.medium.com/why-having-a-shared-database-is-considered-an-anti-pattern-in-the-microservice-architecture-392aee75ff7d)

**Q: Why does `sova/__init__.py` import the Celery app?**
A: Because `@shared_task` decorators register with whatever Celery app is "current" at import time. If `sova/__init__.py` doesn't trigger Celery app creation, Celery falls back to its default app with default config (RabbitMQ broker on localhost — which isn't running) and tasks silently fail to register. [Celery docs](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html#using-celery-with-django).

**Q: Can I run `python -c "from orchestrator.tasks import smoke_test; smoke_test.delay()"` to test a task?**
A: No — that bypasses `django.setup()`, so `sova/__init__.py` never runs, so the configured Celery app never exists. Use `python manage.py shell -c "..."` instead. (We hit this exact bug during Phase 0.8.)

**Q: Why doesn't Gunicorn auto-reload on file changes by default?**
A: Production performance. Reloading watches the filesystem and reimports modules — useful in dev, wasteful in prod. We added `--reload` to the compose command for the dev workflow. Celery workers do NOT auto-reload — restart them manually after editing task code.

**Q: What's the order of containers booting?**
A: `db` and `redis` start first (they have healthchecks). Once both report healthy, `web`, `celery-worker-collectors`, `celery-worker-tools`, `celery-beat`, and `flower` start. The `depends_on: condition: service_healthy` lines in `docker-compose.yml` enforce this.
