# Docker Compose for Multi-Service Backends

> Notes from setting up Phase 0 of Sova — a 7-service Docker Compose topology covering Django, Celery workers, Celery Beat, Flower, PostgreSQL with pgvector, and Redis.

## Key Points

- **Docker Compose is the right tool when one app spans multiple long-running services** — database, cache, web server, background workers. Plain `docker run` works for one container; Compose works for many. [Compose file reference](https://docs.docker.com/reference/compose-file/services/)
- **One image, many roles** — the Sova app image runs Gunicorn in one container, Celery workers in others, Flower in another. The Dockerfile has no `CMD`; each service in compose declares its own `command:`.
- **Layer caching is decided by file copy order** — copy `requirements.txt` and run `pip install` *before* copying source code. Otherwise every code change forces a full reinstall. [Docker best practices for Python](https://testdriven.io/blog/docker-best-practices/)
- **`pip install --no-cache-dir`** shrinks image size by not storing pip's download cache inside the layer. [Why --no-cache-dir](https://protsenko.dev/infrastructure-security/using-pip-install-without-no-cache-dir/)
- **Compose auto-creates a private network** — services reach each other by service name (`db`, `redis`), not IP or localhost. No `networks:` block required.
- **`ports:` is only for host-to-container exposure**, not inter-service traffic. Workers don't need ports because nothing outside Compose ever talks to them directly.
- **Named volumes preserve database state**, bind mounts sync code live in dev. Both used together. [Volumes guide](https://docs.docker.com/storage/volumes/)
- **`depends_on` alone is not enough** — it only waits for the container to start, not for the service inside to be ready. Combine with `condition: service_healthy` + a `healthcheck:` on the dependency. [Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/)
- **Two-file env pattern**: `.env` (real secrets, git-ignored) + `.env.example` (placeholder template, committed). Compose substitutes `${VAR}` automatically from `.env`. [Compose env vars](https://docs.docker.com/compose/environment-variables/set-environment-variables/)
- **Modern Compose doesn't need `version:`** — it's deprecated. Just start with `services:`.

## How We Used It / Why It Matters

- Phase 0 of Sova needed Postgres 16 + pgvector, Redis 7, and a Python app running 5 different processes — installing all of that on the host directly was a non-starter
- Layer caching cut rebuild times from minutes to seconds once requirements stabilized
- Service-name DNS meant `DATABASE_URL=postgresql://...@db:5432/sova` works identically across dev machines
- Splitting Celery into two worker pools (`collectors` queue at concurrency 8, `tools`/`llm` queue at concurrency 4) caps LLM API spend and prevents head-of-line blocking
- Named volume `postgres_data` survives `docker compose down`, so database state isn't wiped on every restart
- Bind mount `.:/app` means code edits on the Mac are visible inside the container instantly — no rebuild loop during development
- Healthcheck-gated startup eliminated the "web container crashes because Postgres wasn't ready yet" class of bug

## Key Terminology

- **Image:** read-only blueprint. Built from a Dockerfile or pulled from a registry.
- **Container:** a running instance of an image. Ephemeral by default.
- **Volume:** persistent disk storage that outlives container restarts.
- **Bind mount:** maps a host directory into a container — live-syncs files in both directions.
- **Named volume:** Docker-managed persistent storage, referenced by name (e.g. `postgres_data`).
- **Layer:** each Dockerfile instruction produces a cached layer. Reused on rebuild if inputs are unchanged.
- **Healthcheck:** a command Docker runs inside a container periodically to confirm the service is responsive.
- **Service:** one entry under `services:` in `docker-compose.yml` — defines one container's image, command, env, ports, volumes.
- **`--prefetch-multiplier 1`** (Celery): tell each worker to pull one task at a time instead of batching. Prevents one slow task from blocking others queued behind it.

## Explore Further

- [Docker Compose official docs — services reference](https://docs.docker.com/reference/compose-file/services/) — the authoritative reference for every field in `docker-compose.yml`
- [Docker best practices for Python — TestDriven.io](https://testdriven.io/blog/docker-best-practices/) — the most thorough article on Dockerfile patterns for Python apps; covers layer caching, multi-stage builds, and image size
- [Speed up pip downloads in Docker — Python Speed](https://pythonspeed.com/articles/docker-cache-pip-downloads/) — explains BuildKit cache mounts (next-level beyond simple layer caching)
- [Compose startup order — Docker docs](https://docs.docker.com/compose/how-tos/startup-order/) — official explanation of `depends_on` semantics
- [Setting up Django with Docker, Postgres, Redis, and Celery — Glinteco](https://glinteco.com/en/post/how-to-set-up-django-with-docker-postgres-redis-cache-redis-message-queue-and-celery/) — concrete walkthrough of the exact stack Sova uses
- [Docker Compose Tutorial: Django with Celery, Redis, Postgres (YouTube, 2025)](https://www.youtube.com/watch?v=K4T-5xZVhUs) — beginner-friendly video walkthrough of the same architecture
- [Saasitive — Django + Celery + Redis + Postgres docker-compose tutorial](https://saasitive.com/tutorial/django-celery-redis-postgres-docker-compose/) — written guide with line-by-line config

## FAQs

**Q: Why is there no `CMD` at the end of the Dockerfile?**
A: Because the same image runs 5 different commands (Gunicorn, two Celery workers, Celery Beat, Flower). Each service in compose specifies its own `command:`. A `CMD` would just set a default that gets overridden every time anyway.

**Q: Do I have to use `${VAR}` syntax in `environment:` blocks?**
A: No. You can hardcode values, but that puts secrets in the YAML which gets committed. The `${VAR}` form pulls from `.env` at parse time, keeping secrets out of git. [Compose env interpolation](https://docs.docker.com/compose/environment-variables/env-file/)

**Q: What's the difference between `environment:` and `env_file:` in a service?**
A: `environment:` lets you set specific vars inline (good when a service only needs a few). `env_file:` loads an entire file's worth of vars at once (good when a service needs many). Sova uses `environment:` for `db` (3 vars) and `env_file:` for app services (20+ vars).

**Q: Will `docker compose down` delete my database?**
A: No — not by default. Named volumes (`postgres_data`) persist across `down`. They only get wiped if you run `docker compose down -v` (the `-v` flag is destructive — be careful).

**Q: Why does the database use `@db:5432` in the URL, not `localhost:5432`?**
A: Inside the Compose network, `db` is the hostname that resolves to the database container. `localhost` from inside the web container points to *itself*, not to the host machine. Only when connecting from outside Compose (PGAdmin on your Mac) do you use `localhost:5432`.

**Q: Why split Celery into two worker pools instead of one?**
A: Cost containment (LLM workers capped at concurrency 4) and isolation (a flood of collector tasks won't starve a high-priority tool invocation). Same Celery binary, different queues, different worker pools.

**Q: How do I check Compose parses my file correctly without actually starting anything?**
A: `docker compose config` — prints the resolved YAML with all `${VAR}` substituted. Errors here are way faster to diagnose than `docker compose up` failures.

**Q: Why `restart: unless-stopped` instead of `always`?**
A: `unless-stopped` restarts the container after crashes but respects manual `docker compose stop`. `always` ignores manual stops too, which is annoying during development.

Sources for further reading are inline above.
