# Pre-Deployment Checklist

> Things we deliberately deferred while building locally. Each item has a clear "do this before deploying / when X happens" trigger. Add to this file whenever we make a "park this for later" decision.

## How to use this doc
- Read top to bottom before any production deployment.
- Each entry: **what**, **why deferred**, **when to act**, **how**.
- When you complete an item, move it to the **Done** section at the bottom (don't delete — having the history is useful).

---

## Secrets & API keys

### Restrict Google Maps API key by IP
- **What:** Lock the key to specific server IPs in Google Cloud Console.
- **Why deferred (2026-06-27):** No public IP yet — local dev runs on dynamic home IP.
- **When:** Before the app runs on any server with a stable public IP (deploy day).
- **How:** Google Cloud Console → APIs & Services → Credentials → key → Application restrictions → IP addresses → add server IP(s). Currently restricted by API only (Places API).

### Set spending limits on Anthropic, OpenAI, RapidAPI keys
- **What:** Cap monthly spend per provider so a leaked key has bounded blast radius.
- **Why deferred:** Not yet making real LLM calls; defaults are fine for dev.
- **When:** Before Phase 5 (lead-scoring tool starts hitting Claude regularly) and before any production traffic.
- **How:** Each provider dashboard has a "Usage limits" / "Spending caps" section. Suggested dev limits: Anthropic $50/mo, OpenAI $20/mo. Production: whatever your CFO signs off on.

### Use separate dev and prod keys
- **What:** Different API keys per environment.
- **Why deferred:** Single dev env right now.
- **When:** First time you have a staging or prod environment.
- **How:** Generate new keys per env. Store via env-specific secret manager (see below). Restrict each by IP/origin to its own environment.

### Migrate secrets out of `.env` to a secret manager
- **What:** Replace `.env` file with GCP Secret Manager (or Doppler / HashiCorp Vault).
- **Why deferred:** `.env` works perfectly for local single-developer dev.
- **When:** First production deploy. Don't ship `.env` files to a server.
- **How:** GCP Secret Manager → store each key → grant service account read access → fetch at app startup, populate `os.environ`. Alternatives: Doppler (simpler UX), Vault (more powerful, more setup).

### Rotate the dev superuser password
- **What:** Replace the bypassed-validation password (set during Phase 0.9).
- **Why deferred:** Local-only access right now.
- **When:** Before exposing Django admin to anything network-reachable.
- **How:** `docker compose exec web python manage.py changepassword <username>`.

### Replace placeholder Postgres password
- **What:** `POSTGRES_PASSWORD=changeme_in_production` → strong random password.
- **Why deferred:** Postgres only accessible from inside docker network locally.
- **When:** First prod deploy.
- **How:** Generate via `openssl rand -base64 32`. Update `.env` (or secret manager). Recreate db container with new password.

### Strong `DJANGO_SECRET_KEY` for production
- **What:** The dev fallback is fine locally, NOT for prod.
- **Why deferred:** Dev only, no real session security needed.
- **When:** First prod deploy.
- **How:** `python -c "import secrets; print(secrets.token_urlsafe(64))"` → put in prod secret manager.

### Strong `SOVA_API_KEY` for production
- **What:** Dev value `sova-dev-key-change-in-production` is a marker, not a real secret.
- **Why deferred:** Same as above.
- **When:** First prod deploy / first time an external service calls our API.
- **How:** Same generation pattern as `DJANGO_SECRET_KEY`. Distribute to legitimate clients out-of-band.

---

## Configuration

### `DEBUG=False` in production
- **What:** `DJANGO_DEBUG=False` in prod `.env` / secret manager.
- **Why deferred:** Already env-driven; just hasn't been set.
- **When:** Prod deploy.
- **How:** Set `DJANGO_DEBUG=False` in prod environment. Django will require `ALLOWED_HOSTS` to be set correctly when DEBUG is off.

### Tighten `CORS_ALLOW_ALL_ORIGINS`
- **What:** Replace `True` with an explicit list of allowed origins.
- **Why deferred:** Dev convenience.
- **When:** Before any prod or staging deploy.
- **How:** In `settings.py`: `CORS_ALLOW_ALL_ORIGINS = False` + `CORS_ALLOWED_ORIGINS = ['https://app.example.com']`.

### Real `ALLOWED_HOSTS`
- **What:** Lock down which hostnames Django responds to.
- **Why deferred:** Defaults to localhost which is correct for dev.
- **When:** Prod deploy.
- **How:** Set `DJANGO_ALLOWED_HOSTS=api.sova.example.com,...` in prod env.

### Remove `--reload` from prod gunicorn command
- **What:** `gunicorn ... --reload` watches files. Useful in dev, wasteful in prod.
- **Why deferred:** Dev convenience.
- **When:** Building the prod compose / k8s manifest.
- **How:** Drop the `--reload` flag in the production deployment spec.

---

## Observability

### Sentry data scrubbing
- **What:** Filter API keys and PII from Sentry payloads before they're sent.
- **Why deferred:** Sentry not wired up yet (`SENTRY_DSN` empty).
- **When:** Same time as wiring up Sentry (first prod-like environment).
- **How:** Set `before_send` and `before_send_transaction` callbacks in `sentry_sdk.init(...)` that strip `key=`, `token=`, `api_key=`, `secret=` from URL query strings. Code snippet in the [Security Convo blog](../case-study/blog4_2026-06-15.md) and the architecture mentor session.

### Structured (JSON) logging
- **What:** Switch log format to JSON for prod log aggregators.
- **Why deferred:** Plain text logs are easier to read in dev.
- **When:** When wiring up CloudWatch / Cloud Logging / Datadog.
- **How:** Configure Django `LOGGING` dict with `python-json-logger` formatter.

### Real liveness/readiness probes
- **What:** k8s/load-balancer health probes that differ from `/api/v1/health/`.
- **Why deferred:** Single-host docker compose right now.
- **When:** First k8s/managed-cluster deploy.
- **How:** Add a lightweight `/livez` endpoint (no DB check) and use the existing `/api/v1/health/` as `/readyz`.

---

## Repository & access

### Switch repo to private
- **What:** Move the GitHub repo from public to private.
- **Why deferred (2026-06-14):** Paid GitHub features not justified yet. Public docs are not sensitive.
- **When:** When repo accumulates anything that shouldn't be public (proprietary algorithms, paid integrations), OR when paying for GitHub becomes worthwhile.
- **How:** GitHub repo → Settings → Danger Zone → "Change visibility" → Private. History stays; visibility flips.

### Per-developer keys when teammates join
- **What:** Each developer gets their own dev API keys, not shared ones.
- **Why deferred:** Solo developer right now.
- **When:** Second person commits to the repo.
- **How:** Onboarding doc with "go to provider X, get your own key, paste into local `.env`." No shared dev key.

### Emergency rotate runbook
- **What:** A checklist for "we think a key leaked, rotate everything now."
- **Why deferred:** Solo developer, low exposure.
- **When:** Before any other person has access to the repo or production.
- **How:** Document in `.docs/runbooks/key-rotation.md` (folder to be created). Should cover: order to rotate keys, services to restart, audit log to check, communication to send.

---

## Operations

### Postgres backup strategy
- **What:** Automated, tested backups of the `postgres_data` volume.
- **Why deferred:** Local dev only — losing the volume means rerunning NPPES import.
- **When:** First time any real (non-rerunnable) data lives in Postgres.
- **How:** GCP Cloud SQL has managed backups. Self-hosted: `pg_dump` + cron + S3/GCS upload.

### Connection pooling tuning
- **What:** `CONN_MAX_AGE=60` is fine for dev. Production at scale needs more thought.
- **Why deferred:** Single-worker dev environment.
- **When:** When traffic justifies it (hundreds of concurrent requests).
- **How:** Consider PgBouncer in front of Postgres. Tune `CONN_MAX_AGE`, `CONN_HEALTH_CHECKS`, `max_connections` on the DB side.

### Static files in production
- **What:** Run `collectstatic`, serve via WhiteNoise or CDN.
- **Why deferred:** Django dev server handles static files in dev.
- **When:** Prod deploy.
- **How:** Add WhiteNoise to `requirements.txt`, add `WhiteNoiseMiddleware` to `MIDDLEWARE`, run `python manage.py collectstatic` in the prod Dockerfile.

### Migrations in production
- **What:** Migrations run automatically on deploy, NOT manually.
- **Why deferred:** Manual `migrate` is fine for solo dev.
- **When:** Prod deploy.
- **How:** Add `python manage.py migrate --noinput` to the prod entrypoint or as a pre-deploy job.

---

## Done

(Move items here as they're completed. Add the date.)

- *(none yet)*
