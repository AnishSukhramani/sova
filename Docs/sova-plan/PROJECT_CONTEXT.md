# PROJECT_CONTEXT.md — Sova: What We Are Building and Why

## The Company

- **Product:** Voice AI agent for dental and medical practice front desks (USA market)
- **What it does:** Connects to a practice's phone number, stays active 24/7, handles inbound and after-hours calls in a human-like conversational manner
- **Capabilities:**
  - Book, reschedule, and cancel appointments
  - Answer patient queries
  - Capture insurance information
  - Transfer to staff when needed
  - Handle full scheduling workflows
- **Current scale:** ~200 active practice locations
- **Client acquisition so far:** Primarily through in-person seminars (e.g., HLTH) — a stall, live demos, word of mouth

---

## The Problem

The company has a product that works and real clients, but **no marketing program**.

- Online presence is very limited
- No inbound demand pipeline
- All growth has come from expensive, low-frequency in-person events
- The competitive landscape in 2026 is getting crowded fast (15+ competitors in dental voice AI)
- The window to build brand authority and organic inbound is now

---

## The Vision: Sova — The Marketing Brain

Sova is an automated marketing intelligence system. Think of it as a brain with many **fragments** — each fragment is an autonomous worker that performs one specific marketing or intelligence task.

The goal is to:
1. **Find** practices that are most likely to need the product right now (intent signals)
2. **Rank** those practices by how hot they are as leads (scoring)
3. **Understand** why they are hot (evidence)
4. **Act** on that intelligence — outreach, content generation, social publishing
5. **Learn** from what works (feedback loop)

This replaces the need for a large marketing team. The brain runs in the background, surfaces the right leads at the right time, and generates the right content to reach them.

---

## The Target Buyer

Dental and medical practice owners in the USA, specifically:
- Solo practice owners (single location)
- Small DSOs (2–10 locations)
- Practices actively hiring front desk staff (strong buy signal)
- Practices with legacy tech stacks (susceptible to disruption pitch)
- Practices with poor phone infrastructure / bad patient reviews about phones

---

## What a "Signal" Means

A signal is a data point that suggests a practice is likely to buy the product.

| Signal | What it means |
|---|---|
| Hiring for front desk (again) | They have front desk problems — our product solves this |
| Same front desk role posted 3+ times in 12 months | Chronic turnover — strong pain point |
| Negative reviews mentioning phones | Patients can't get through — our product solves this |
| Legacy PMS / old tech stack | Practice is behind on tech — receptive to modernization |
| No online booking / automation on website | Not automated — opportunity to pitch |
| New practice opening | Greenfield — building systems from scratch |

---

## What a "Fragment" Means

A fragment is one autonomous worker that:
- Has a single, well-defined job
- Reads from one data source
- Writes signals, practices, or opportunities to the database
- Can be run independently or as part of a pipeline

Examples:
- `jobs` fragment — scrapes DentalPost for front desk job postings
- `reviews` fragment — uses Google Places to find practices with phone friction reviews
- `score` fragment — reads all signals and computes ranked opportunity scores
- `outreach` fragment — (not yet built) takes a hot lead and drafts a personalized email
- `content` fragment — (not yet built) generates LinkedIn/blog posts from aggregate signal data

---

## Legacy System (Node.js) — What Exists Today

The legacy system (in the `jobportalscout` repo) already has:

**v0 Scout (CLI):**
- Scrapes job boards (DentalPost, Indeed, LinkedIn, iHireDental) via Hyperbrowser
- Scrapes Reddit for hiring discussions
- Enriches leads with Hunter.io (email, phone, social)
- Exports to Google Sheets

**v1 Brain (Next.js + Supabase):**
- Web dashboard (opportunities feed, detail view, classification panel)
- AI chat assistant (queries opportunities/signals via OpenAI)
- Background workers (jobs, reviews, nppes, website, tech_stack, ad_library, competitor_xray, score)
- Social publishing (Facebook, LinkedIn)
- OpenAI classification (actionable vs. content leads)

**What is missing from the legacy system:**
- Proper job queue (workers are manual CLI commands)
- Outreach execution (no email sending)
- Content generation (no automated drafting)
- Feedback loop (no conversion tracking)
- Clean architecture (v0 and v1 live together, ad-hoc design)

---

## Sova (Django) — What We Are Building

A clean, planned rebuild of the backend in Django. Goals:

- Replicate all existing fragment logic in Python
- Replace the ad-hoc Node.js workers with proper Django management commands
- Use local PostgreSQL instead of Supabase (free, already installed)
- Build toward a proper job queue (Celery) once the basics are stable
- Keep the Next.js frontend untouched (it will eventually point to the Django API)
- Add the missing execution layers (outreach, content, feedback) incrementally

---

## What Success Looks Like (End of Initial Phase)

A working Django backend that:
1. Connects to a local PostgreSQL database
2. Has Django ORM models for all core tables (practices, signals, opportunities, evidence)
3. Has REST API endpoints for all core resources
4. Has management commands that replicate every existing fragment
5. Runs entirely locally with a few simple commands
6. Is ready to be Dockerized in the next phase

---

## Key Constraints

- **Incremental:** Build one chunk at a time, Anish reviews each chunk
- **No Docker yet:** Local development only until the backend is stable
- **No GCP yet:** Deployment comes after Docker
- **No new fragments yet:** Replicate legacy fragments first, add new ones after
- **Learning-oriented:** Anish is learning Django — explain decisions as you go
