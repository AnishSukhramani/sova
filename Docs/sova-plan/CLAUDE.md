# CLAUDE.md — Working Rules for Sova

This file governs how Claude should behave when working on this project.
Read this before doing anything else in a new session.

---

## Who You Are Working With

- **Name:** Anish
- **Role:** Founder of a voice AI company targeting dental/medical practices in the USA
- **Experience level:** Junior developer — competent but learning Django for the first time
- **Style:** Hands-on supervisor. Wants to understand what is being built, not just receive finished code.

---

## How to Work

### Be Incremental
- Build in **sizable, digestible chunks** — one logical unit at a time
- Never build an entire feature end-to-end without pausing for Anish to review
- A "chunk" = one model, one endpoint, one fragment, one config block — not an entire layer
- After each chunk, **stop and explain what was just built and what comes next**

### Always Explain Before Writing
- Before writing any non-trivial code, briefly state:
  1. What you are about to write
  2. Why this approach was chosen
  3. What Anish needs to do after (run a command, check a file, etc.)

### Wait for Approval on Decisions
- If a decision has architectural weight (DB schema, new dependency, new pattern), **ask before implementing**
- Do not assume approval from a previous session carries forward

### Never Overbuild
- No speculative abstractions
- No helper utilities for things only used once
- No "future-proofing" unless explicitly asked
- No Docker, GCP, or deployment steps until explicitly told to proceed

### Supervise, Don't Replace
- Anish wants to edit and supervise code, not just receive it
- Keep files focused and short enough to read in one sitting
- Prefer clarity over cleverness

---

## Stack Decisions (Locked)

| Concern | Decision | Notes |
|---|---|---|
| Backend | Django + Django REST Framework | First time using Django — go slow |
| Database | Local PostgreSQL via pgAdmin 4 | Free, already installed locally |
| Task queue | Django management commands first, Celery later | Start primitive |
| Frontend | Next.js (legacy, kept as-is) | Not being touched in this phase |
| Deployment | Local only for now | Docker → GCP comes later |
| AI | OpenAI API (gpt-4o-mini) | Same as legacy system |
| ORM | Django ORM | No raw SQL unless necessary |

---

## Project Structure Convention

```
sova/                        ← Django project root
├── manage.py
├── sova/                    ← Django settings package
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                    ← Shared models, utilities
├── opportunities/           ← Opportunity + scoring app
├── signals_app/             ← Signal ingestion app (avoid naming conflict with Django signals)
├── practices/               ← Practice management app
├── fragments/               ← Worker/fragment management commands
│   └── management/
│       └── commands/        ← Each fragment = one management command
├── chat/                    ← Chat agent app
├── classifier/              ← OpenAI classification app
└── requirements.txt
```

---

## Fragment Convention

Each legacy worker fragment becomes a Django **management command**:

```bash
python manage.py run_fragment jobs
python manage.py run_fragment reviews
python manage.py run_fragment score
# etc.
```

Fragments are run manually for now. Celery scheduling comes in a later phase.

---

## Database Convention

- All tables use the `sova_` prefix (replacing the legacy `_athena` suffix)
- Example: `opportunities_athena` → `sova_opportunities`
- Use Django ORM models — no raw SQL
- Migrations are generated with `python manage.py makemigrations`

---

## Environment Variables

Store in `.env` at project root. Use `django-environ` or `python-dotenv` to load.

Required variables (replicated from legacy):
```
# Django
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (local PostgreSQL)
DB_NAME=sova
DB_USER=
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432

# OpenAI
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# Google
GOOGLE_MAPS_API_KEY=

# Hunter.io
HUNTER_API_KEY=

# Hyperbrowser
HYPERBROWSER_API_KEY=

# AWS S3 (optional)
AWS_REGION=
S3_BUCKET=

# Social
FACEBOOK_GRAPH_API_VERSION=
LINKEDIN_REST_VERSION=

# App config
OPPORTUNITY_DAILY_CAP=50
CHAT_AGENT_DEBUG=false
```

---

## Do Not Touch

- `/apps/brain-web/` — legacy Next.js frontend, leave it alone
- `/src/` — legacy v0 scout CLI, leave it alone
- `/workers/` — legacy Node.js workers, leave them alone
- The existing Supabase database (read-only reference only)

---

## When You Get Stuck

1. Read the error message carefully before trying a fix
2. Check `FRAGMENTS_INVENTORY.md` for the logic you are replicating
3. Check `ARCHITECTURE.md` for the decision rationale
4. If still stuck, describe the problem to Anish clearly — do not guess wildly

---

## Session Startup Checklist

At the start of every new session:
1. Read this file (`CLAUDE.md`)
2. Read `MIGRATION_PLAN.md` to know which phase is active
3. Ask Anish: "Where did we leave off? Which phase/chunk are we on?"
4. Do not start writing code until you know the current position in the plan
