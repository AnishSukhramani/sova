# Sova — Full Project Context for AI Agent

> This document is written for an AI agent (Claude Workbench, Claude Code, or similar) that will be helping build Sova. Read this entirely before writing any code or architecture. This is your source of truth.

---

## 1. Who We Are

**Company:** Neurality Health  
**Product:** An AI voice receptionist for dental and medical practices. The AI answers every inbound call, schedules appointments, handles after-hours inquiries, and integrates with the practice's practice management software (PMS). The AI sounds human, handles complex patient interactions, and never goes to voicemail.  
**Current state:** ~200 active client locations across multiple dental practice clients in the US.  
**Goal:** 2,000 active client locations by end of 2027.

---

## 2. What We Are Building (Sova)

Sova is a **marketing intelligence brain** — an autonomous backend system that finds, qualifies, and understands dental and medical practice leads so we know exactly who to pitch, when to pitch them, and what to say.

Sova is **not** the AI receptionist product itself. It is the system that feeds our sales and marketing operation with high-quality, signal-rich intelligence about potential clients.

### The Core Problem

Finding and qualifying dental practices at scale is hard. There are ~200,000 dental practices in the US. We need 1,800 more clients. Generic outreach at that volume is wasteful and slow. The practices most likely to buy are showing specific, time-sensitive signals right now — a front desk job posting, a practice just sold, a new DSO opening nearby, a live-answer failure on a test call. Sova finds those signals before any human could.

### What Sova Does

1. **Collects data** from dozens of public and semi-public internet sources, 24/7, autonomously
2. **Writes structured records** into a PostgreSQL database
3. **Exposes tools** that read from the database and compute intelligence (lead scores, outreach briefs, competitive reports)
4. **Orchestrates everything** via a scheduling and coordination layer that keeps all collectors running on their correct cadences

---

## 3. Architecture Direction

> **Note to agent:** We are providing direction here, not a final spec. We want you to design the actual architecture. The hierarchy below is our current thinking — you should challenge it, refine it, and propose the best implementation.

### Current Thinking

We originally thought in three layers: sub-fragments → fragments → brain. We are rethinking this into something simpler and more practical:

**Layer 1 — Data Collectors (sub-fragments)**
- Each sub-fragment is one autonomous data collector
- It monitors one specific data source
- It writes raw structured data into its own database table
- It does NOT interpret, score, or act on data
- It runs on a schedule (every N hours/days depending on the source)
- Sub-fragments are fully independent of each other — they share no state except the database

**Layer 2 — Tools**
- Tools replace what we called "fragments"
- A tool reads from one or more sub-fragment database tables
- It processes, scores, correlates, or summarises the data to answer one business question
- Tools are called on demand (by the orchestrator, by an API, or eventually by a chatbot)
- Example: a "Lead Score" tool reads hiring data, review data, and lifecycle event data for a given practice and returns a composite score

**Layer 3 — Orchestrator**
- Manages scheduling: ensuring every sub-fragment runs at the right cadence
- Monitors health: alerts when a sub-fragment fails or produces no data
- Coordinates tool execution: runs scoring and briefing tools after relevant sub-fragments complete
- Does NOT contain business logic — that lives in the tools

**Future Layer — Chatbot Interface**
- Eventually, a conversational interface (likely Claude-powered) will sit on top of the tools
- A sales rep will be able to ask: "Give me the 10 hottest leads in Texas this week" or "What has Arini done in the last 30 days?"
- The chatbot calls tools, which read from the database, and returns structured answers
- This is not v1 — design the system so this is possible later, but do not build it now
- **Planned framework: DeepAgents + LangGraph (both open-source, free).** DeepAgents is LangChain's agent orchestration harness — it handles multi-step planning, parallel subtask execution, and tool-calling loops. LangGraph is the underlying state machine it runs on. When the chatbot layer is built, each intelligence tool becomes a LangGraph node, and the chatbot becomes the graph that decides which tools to invoke and in what order. Design the tools layer now with clean, callable interfaces so this migration is natural — not a rewrite.

### Technology Preferences

We are building with:
- **Python / Django** — backend framework
- **PostgreSQL** — primary database (local for now, cloud-ready later)
- **Celery + Redis** — task scheduling and async execution for sub-fragments
- **Docker Compose** — local development environment (required from day one since Celery + Redis need it)
- **OpenAI API (gpt-4o-mini)** — for LLM-based classification tasks within sub-fragments and tools
- **LangSmith** — observability for all LLM calls. Traces every input, output, latency, and token count for every OpenAI call in the system. Free tier covers 5,000 traces/month — sufficient for all of development and early production. Use the standalone `langsmith` Python SDK (not LangChain wrappers) to avoid framework lock-in. Instrument every sub-fragment that calls OpenAI. When a classifier starts misfiring or token costs spike, this is how you find out. If the free tier becomes a bottleneck at scale, Langfuse is an open-source self-hostable alternative with identical features.

The developer is learning Django while building this. Code should be idiomatic Django, well-structured, and explained where non-obvious patterns are used.

---

## 4. The Sub-fragment Inventory

These are all the data collectors Sova needs to build. Each one is a Celery task that runs on a schedule, fetches data from a specific source, and writes to a database table.

The agent's job is to design the database schema, the Django app structure, and the Celery task architecture that supports all of these.

| # | Sub-fragment | What it collects | Source |
|---|---|---|---|
| 1 | `dentalpost_collector` | Front desk job postings at dental practices; detects chronic re-posting | DentalPost (public, HTTP scrape) |
| 2 | `indeed_collector` | Dental/medical front desk openings on Indeed | Indeed (HTTP scrape) |
| 3 | `linkedin_jobs_collector` | Front desk openings on LinkedIn Jobs; extracts PMS software mentions | LinkedIn Jobs (public HTML + Hyperbrowser fallback) |
| 4 | `ihiredental_collector` | Specialty dental job board postings | iHireDental (HTTP scrape) |
| 5 | `ziprecruiter_collector` | Dental/medical front desk roles on ZipRecruiter | ZipRecruiter (HTTP scrape) |
| 6 | `glassdoor_collector` | Employee reviews at dental practices for turnover/chaos language | Glassdoor (partial public, HTTP scrape) |
| 7 | `facebook_api_collector` | Practice Facebook page metrics: follower count, post frequency, engagement | Facebook Graph API (official) |
| 8 | `linkedin_api_collector` | Competitor + practice LinkedIn company page data | LinkedIn Company Pages API (official) |
| 9 | `facebook_hyperbrowser_agent` | Richer Facebook data — group posts, comment threads (API fallback) | Hyperbrowser SDK |
| 10 | `linkedin_hyperbrowser_agent` | LinkedIn commenter profiles on competitor posts, dental group discussions | Hyperbrowser SDK |
| 11 | `youtube_competitor_monitor` | Competitor YouTube channels; category keyword search rankings | YouTube Data API v3 (official) |
| 12 | `tiktok_industry_monitor` | Dental practice owner content and AI receptionist mentions on TikTok | TikTok Research API |
| 13 | `conference_website_monitor` | Speaker lists, sponsor lists, session topics at major dental conferences | HTTP scrape (ADA, HLTH, Dentsply Sirona World, etc.) |
| 14 | `conference_social_tracker` | Who is commenting on dental conference Facebook/LinkedIn posts | Facebook Graph API + LinkedIn API |
| 15 | `email_inbox_reader` | Dental/healthcare newsletters from a dedicated Gmail inbox | Gmail API (official, OAuth) |
| 16 | `newsletter_classifier` | Classifies newsletter content as Opportunity / Content / Noise | OpenAI API (runs on `email_inbox_reader` output) |
| 17 | `reddit_scout` | Dental subreddits: front desk problems, hiring pain, phone management posts | Reddit API (official, free) |
| 18 | `quora_scout` | Quora dental practice management questions | Quora (HTTP scrape, public) |
| 19 | `dentaltown_forum_scout` | Dentaltown forums: operational pain, vendor complaints, tech questions | HTTP scrape (public forums) |
| 20 | `facebook_groups_scout` | Public dental Facebook group posts for hiring complaints and tech frustrations | Facebook Graph API (public groups) |
| 21 | `nppes_collector` | Full US government NPI registry — master list of all dental/medical practices | NPPES monthly CSV download (~7GB) |
| 22 | `google_places_collector` | Review count, star rating, and phone friction keywords per practice | Google Places API (paid) |
| 23 | `clinic_hours_change_monitor` | Changes to practice opening hours on Google Business Profile | Google Places API |
| 24 | `website_crawler` | Practice homepages: missing booking widgets, patient comms tools | httpx + BeautifulSoup |
| 25 | `rss_feed_monitor` | Industry RSS feeds: ADA News, Dental Economics, HIPAA Journal, CMS.gov | Python feedparser |
| 26 | `competitor_website_monitor` | Competitor homepage/pricing page change detection | HTTP fetch + hash comparison |
| 27 | `facebook_ads_library_collector` | Every active competitor Meta ad: copy, format, run duration, targeting | Meta Ad Library API (official, free) |
| 28 | `competitor_client_scout` | Named clients from competitor case studies and testimonials | HTTP scrape (competitor websites) |
| 29 | `competitor_jobs_tracker` | Competitor hiring patterns: role type reveals what they are building | HTTP scrape (competitor careers pages + DentalPost/Indeed by company) |
| 30 | `crunchbase_monitor` | Competitor funding rounds, acquisitions, executive hires | Crunchbase API (limited free tier) |
| 31 | `competitor_pr_monitor` | Competitor press mentions and product announcements | Google News RSS + keyword alerts |
| 32 | `google_ads_intelligence_collector` | Competitor Google search ads and keywords via Ads Transparency Center | Google Ads Transparency Center (public, HTTP scrape) + SEMrush/SpyFu API |
| 33 | `linkedin_ads_library_collector` | Competitor LinkedIn ads: creative, copy, targeting from public ad library | LinkedIn Ad Library (HTTP scrape) |
| 34 | `weave_truelark_displacement_monitor` | TrueLark clients showing churn signals post-Weave acquisition (time-bounded window) | NLP on reviews + job boards filtered by known TrueLark client names |
| 35 | `competitor_churn_poison_monitor` | Competitor reputation decay in G2/Capterra reviews and forums | HTTP scrape + NLP on review platforms |
| 36 | `competitor_product_monitor` | Competitor feature pages, pricing, changelogs — structured diff on every change | HTTP fetch + hash comparison + LLM extraction |
| 37 | `google_news_collector` | Dental, healthcare, and voice AI news | Google News RSS |
| 38 | `google_trends_monitor` | Search trend volume for category keywords | pytrends (Google Trends unofficial API) |
| 39 | `yelp_collector` | Yelp reviews and ratings for dental practices | Yelp Fusion API (official) |
| 40 | `healthgrades_collector` | Healthgrades patient reviews; detects unclaimed profiles | HTTP scrape (public listings) |
| 41 | `zocdoc_listing_detector` | Whether a practice is listed on Zocdoc — gaps indicate no booking automation | HTTP scrape |
| 42 | `review_response_rate_tracker` | How consistently practices respond to reviews — zero response = low engagement | Computation on `google_places_collector` + `yelp_collector` output |
| 43 | `reputation_shock_detector` | Sudden spike in phone/access complaint reviews within a 30-day window | Time-series on existing review output + LLM classification |
| 44 | `business_license_monitor` | New dental LLC filings from county public records | County portal HTTP scrapes (varies by state) |
| 45 | `commercial_real_estate_scout` | New dental office leases on LoopNet | HTTP scrape (LoopNet public listings) |
| 46 | `dental_supplier_monitor` | Henry Schein / Patterson tech partner changes and affiliated practice listings | HTTP scrape (public partner pages) |
| 47 | `insurance_network_collector` | Dentist directories from Delta Dental, MetLife, and other major insurers | HTTP scrape (public provider directories) |
| 48 | `insurance_plan_change_monitor` | Practices joining or leaving major insurance networks | Periodic scrape diff against stored snapshots |
| 49 | `dental_insurer_credentialing_monitor` | Practices in payer credentialing limbo — maximum phone chaos, zero booking conversion | HTTP fetch + NLP on practice websites and Google Business posts |
| 50 | `insurance_ppo_density_monitor` | How many PPO networks a practice participates in | Computation on `insurance_network_collector` output per NPI |
| 51 | `hunter_enricher` | Decision-maker email address from practice domain | Hunter.io API (paid, run on high-score leads only) |
| 52 | `linkedin_profile_enricher` | Practice owner / office manager LinkedIn profile | Proxycurl API (licensed LinkedIn proxy) |
| 53 | `phone_validator` | Validates and cleans practice phone numbers; flags disconnected lines | Twilio Lookup API |
| 54 | `champion_job_change_tracker` | Ex-client staff who moved to a new practice — warmest possible lead | Proxycurl API (weekly polling against seed list of known contacts) |
| 55 | `npi_new_registration_monitor` | New dental NPI registrations each month — new practice openings | Monthly NPPES CSV diff |
| 56 | `dental_broker_listing_monitor` | Practices listed for sale or sold — new owner rebuilding vendor stack | HTTP scrape (AFTCO, Omni, Henry Schein Transitions, etc.) |
| 57 | `dental_school_new_licensee_monitor` | Newly licensed dentists from state dental boards | HTTP scrape (50 state dental board sites) |
| 58 | `building_permit_monitor` | Dental office renovation/buildout permits from county databases | HTTP scrape (county permit portals, top 20 metros) |
| 59 | `multi_location_expansion_detector` | Existing practices adding a second NPI or address under same tax ID | NPPES monthly delta + entity resolution |
| 60 | `cms_enrollment_collector` | Medicare provider enrollment dates and locations | CMS Open Data Portal API (free) |
| 61 | `sba_loan_monitor` | New SBA loans to dental practices (NAICS 621210) | SBA FOIA data releases |
| 62 | `dea_registration_checker` | Validates practice is active via DEA registration; lapsed = likely closed | DEA Diversion Control (rate-limited HTTP) |
| 63 | `state_medicaid_provider_monitor` | State Medicaid dental provider directories | HTTP scrape (state Medicaid agency pages) |
| 64 | `ucc_loan_filings_monitor` | Equipment financing filings at Secretary of State offices | HTTP scrape (state SoS UCC portals) |
| 65 | `oig_exclusion_checker` | Checks providers against HHS OIG exclusion list — immediate lead disqualifier | HHS OIG LEIE monthly download (free) |
| 66 | `hrsa_hpsa_monitor` | HRSA dental shortage area designations — highest automation urgency | HRSA data warehouse API (free) |
| 67 | `osha_fda_recall_monitor` | OSHA safety alerts + FDA dental device recalls | FDA MedWatch RSS + OSHA news RSS |
| 68 | `bls_staffing_heatmap` | BLS metro-level dental employment and wage data | BLS API (free) |
| 69 | `ada_member_finder_scraper` | ADA member directory — engaged dentists, better signal than cold NPPES | HTTP scrape (findadentist.ada.org) |
| 70 | `dental_specialty_association_scraper` | AAO, AAOMS, AAP, AAPD member directories — specialty practices | HTTP scrape (per-association directories) |
| 71 | `aadom_member_intelligence_collector` | AADOM office manager members — buying committee pre-qualified | HTTP scrape (aadom.net public pages) |
| 72 | `beckers_dental_review_scraper` | Becker's Dental Review: DSO deals, acquisitions, tech adoption stories | HTTP scrape + RSS |
| 73 | `pms_signal_extractor` | PMS software mentions from job postings already collected | NLP/regex on existing job collector DB output |
| 74 | `booking_tech_detector` | Which booking/comms tool is embedded on each practice site | httpx + BeautifulSoup (runs on existing crawl pass) |
| 75 | `bilingual_demand_detector` | Multilingual service pages + bilingual hiring — complex call routing signal | HTTP fetch + NLP on job collector output |
| 76 | `g2_intent_monitor` | Practices actively browsing G2 for AI receptionist alternatives | G2 Buyer Intent API (paid) |
| 77 | `pms_migration_detector` | PMS migration language in job postings — entire tech stack in re-evaluation | NLP/regex on existing job collector output |
| 78 | `patient_financing_badge_detector` | CareCredit/Cherry/Sunbit badges on practice sites — elective revenue signal | httpx + BeautifulSoup (runs on existing crawl pass) |
| 79 | `bombora_b2b_intent_integration` | Practices consuming AI/dental automation content on third-party sites before visiting Sova | Bombora Company Surge API (paid) |
| 80 | `website_visitor_deanonymizer` | Identifies dental practices visiting Sova's own website | RB2B API or Clearbit Reveal (tracking pixel) |
| 81 | `dso_expansion_monitor` | New DSO locations opening near independent practices | Google Places API + commercial real estate |
| 82 | `saturation_zip_analyzer` | DSO market share % per ZIP code | Computation on `dso_expansion_monitor` + NPPES output |
| 83 | `branded_search_spike_monitor` | Sova branded search spikes with no paid campaign = dark social sharing | Google Search Console API |
| 84 | `dental_community_mention_tracker` | Sova and competitor mentions in public dental communities | Facebook Graph API + Reddit API + LinkedIn API |
| 85 | `practice_advisor_network_mapper` | CPAs, brokers, and transition attorneys who appear around dental practice deals | HTTP scrape (advisory firm sites, conference sponsors, broker listings) |
| 86 | `peer_influence_mapper` | Community influencers in Dentaltown/Reddit — whose recommendations others act on | Graph analysis on existing opinion platform output |
| 87 | `referral_network_mapper` | Clinical referral and supply chain network graph for warm introduction paths | HTTP scrape (practice referral pages, conference sponsors, podcast notes) |
| 88 | `uspto_trademark_monitor` | Competitor trademark filings | USPTO TESS (free, weekly polling) |
| 89 | `patent_filing_monitor` | Competitor patent applications in voice AI and scheduling | Google Patents RSS + USPTO bulk data |
| 90 | `dental_podcast_monitor` | Dental business podcast topics and guest names — opinion leader IDs | RSS feed scraping |
| 91 | `dental_webinar_calendar_scraper` | Upcoming dental webinar topics — ICP learning and sponsorship signals | HTTP scrape (Patterson, Henry Schein, ADA CE Online) |
| 92 | `pms_vendor_support_forum_sentinel` | PMS vendor support forums for "looking for alternative" complaint threads | HTTP scrape (Open Dental forums, etc.) |
| 93 | `weather_disruption_monitor` | NOAA severe weather alerts cross-referenced with practice ZIP codes | NOAA Weather API (free, official) |
| 94 | `ce_enrollment_monitor` | CE course calendars for operations/technology topics — growth-minded contacts | HTTP scrape + RSS (ADA CE Online, dental society event pages) |
| 95 | `local_biz_journal_monitor` | Regional biz journals + chamber feeds for dental openings and ownership changes | BizJournals.com RSS + chamber HTTP scrapes |
| 96 | `dental_staffing_agency_monitor` | Dental temp agency demand spikes per metro — entire local market in structural pain | HTTP scrape (Dental Temps of America, DentalPost Temp, regional agencies) |
| 97 | `staff_burnout_aggregator` | NLP across all job/review data for burnout language per practice | NLP on existing job collector + review collector DB output |
| 98 | `patient_access_complaint_velocity` | Review complaint spikes for phone/scheduling friction within 30 days | Time-series on existing review collector output |
| 99 | `live_answer_audit` | Automated test calls to practices during business hours — measures pickup rate | Twilio Programmable Voice |
| 100 | `after_hours_coverage_audit` | Test calls on evenings/weekends — detects practices with zero after-hours coverage | Twilio Programmable Voice (separate schedule) |
| 101 | `same_day_availability_scanner` | Scans online booking for unused near-term appointment slots | httpx + BeautifulSoup (scheduling widget APIs + Zocdoc) |
| 102 | `new_patient_promo_detector` | "New patient special" banners on practice homepages — demand softness signal | httpx + BeautifulSoup |
| 103 | `contact_friction_scorer` | Scores total contact accessibility: click-to-call, hours listed, booking CTA | httpx + BeautifulSoup (desktop + mobile) |
| 104 | `mobile_conversion_friction_scanner` | Mobile site performance (Lighthouse score) + click-to-call detection | Lighthouse API + mobile BeautifulSoup crawl |
| 105 | `office_manager_turnover_detector` | Detects OM departures from staff pages and LinkedIn | Staff page HTML diff + Proxycurl API |
| 106 | `associate_arrival_detector` | New clinicians joining a practice — volume pressure on phones immediately | Provider bio page HTML diff + state board data |
| 107 | `answering_service_vendor_loss_monitor` | Practices leaving legacy answering services — active switching window | NLP on job descriptions + periodic test calls detecting greeting changes |
| 108 | `first_party_voice_demo_tracker` | Tracks calls to Sova's public AI demo line — self-persuading prospect | Twilio + reverse NPPES phone lookup |
| 109 | `lost_deal_reason_miner` | Mines CRM/Gong notes for objection patterns — trains the outreach engine | CRM data export + LLM classification |
| 110 | `direct_mail_response_tracker` | QR/vanity URL tracking on physical mail to HOT practices | QR generation + UTM-tagged vanity URLs |
| 111 | `x_competitor_tracker` | *(v2 — future)* Competitor X/Twitter posts and engagement | X API v2 (paid Basic tier) |
| 112 | `x_industry_monitor` | *(v2 — future)* Live dental practice owner pain posts on X | X API v2 |

---

## 5. The Intelligence Tools

Tools are the processing layer. They read from the database tables written by sub-fragments and answer one specific business question. They do not collect data — they interpret it.

The following tools need to be designed and built:

| Tool | Business Question |
|---|---|
| **Fit Score** | Does this practice match our ICP (size, specialty, location, tech posture)? |
| **Intent Score** | Is this practice experiencing active operational pain right now? |
| **Lead Score** | Composite score combining Fit, Pain, Timing, First-Party Intent, Technographic, Human Route, Geography |
| **Transition Window Detector** | Is this practice in a 30–90 day system reconfiguration period? |
| **Access Failure Index** | How badly is this practice leaking patient demand at the front door? |
| **Outreach Intelligence Brief** | Given a HOT lead, what is everything we know and what should the outreach say? |
| **Competitive Leaderboard** | Where does Sova rank vs. every competitor across measurable dimensions? |
| **Competitive Intelligence Report** | What did each competitor do this week? |
| **Market Intelligence Report** | What is happening in the dental/voice AI market this week? |
| **Client Health Monitor** | How are existing client locations doing — churn risk or upsell? |
| **Churn Early Warning System** | Which clients are in the 30–60 day pre-churn window? |
| **Practice Growth Predictor** | Which practices are in active growth and likely to have budget? |
| **Displacement Intelligence Engine** | Which practices using a competitor tool are most vulnerable to switching? |
| **Revenue Rescue Planner** | What exact revenue-leak story should we tell this specific practice? |
| **Buying Committee Intelligence** | Who is the economic buyer vs. daily champion at this practice, and what do we say to each? |
| **Trust Vector** | What proof asset will most reduce resistance for this specific lead? |
| **Influence & Network Map** | Who can credibly introduce us to this account? |
| **Local Pressure Index** | How much competitive pressure is this practice under from its geography? |
| **ICP Accuracy & Signal Calibration Monitor** | Is the scoring model still working — which signals have drifted? |
| **Content Generation** | What should we post on LinkedIn/Facebook this week? |

---

## 6. Lead Scoring Model (Reference)

The Lead Score is a weighted composite. The agent should implement this formula as a tool.

```
Lead Score =
  0.20 × Fit +
  0.25 × OperationalPain +
  0.20 × Timing +
  0.15 × FirstPartyIntent +
  0.10 × TechnographicOpportunity +
  0.05 × HumanRoute +
  0.05 × Geography
```

**Bounded modifiers (added to composite — not multipliers):**

| Event | Modifier |
|---|---|
| Champion moved from existing client | +8 |
| Ownership transfer / practice sold | +6 |
| New practice opening or second location | +5 |
| Live-answer failure + after-hours gap confirmed | +4 |
| DSO opened within 5 miles | +3 |
| First-party demo-line call | +3 |
| Likely inactive / dead phone | −6 |
| Strong incumbent stack, no pain evidence | −4 |
| OIG-excluded provider | immediate disqualify |

**Signal decay (half-life function):**
```
Decayed Value = Raw Value × e^(−ln(2) × days_since_signal / half_life)
```

| Signal | Half-life |
|---|---|
| Demo-line call / identified website visit | 7 days |
| Active front-desk job posting | 14 days |
| Review complaint spike / live-answer failure | 21 days |
| Ownership transfer | 60 days |
| New NPI / SBA loan / new practice opening | 90 days |
| Technographic gap | 180 days |

**HOT qualification — all must be true:**
- Composite score ≥ 78
- Fit score ≥ 65
- At least one major pain signal AND one timing/intent signal
- At least one key signal within the last 30 days
- Owner or office manager contact identified
- No major disqualifier present

---

## 7. Key Constraints and Requirements

### Must-haves
- The system must run autonomously — no human triggers required for data collection
- Each sub-fragment must be independently schedulable and independently failsafe (one broken collector does not break others)
- All data must be written to a central PostgreSQL database (shared state layer)
- The database is the only shared layer — sub-fragments never call each other directly
- Every sub-fragment must have error handling, retry logic, and a last-run timestamp
- The system must be observable: we need to know which collectors are running, which are failing, and what data they last produced

### Compliance constraints
- LinkedIn automation: use Proxycurl API only — no browser simulation of LinkedIn sessions
- Facebook automation: official Graph API first; browser automation only for public content with no login
- Glassdoor: summary-level only; no bulk extraction
- Website visitor de-anonymization: requires disclosure in Sova's privacy policy before deployment
- `live_answer_audit` / `after_hours_coverage_audit` test calls: legal sign-off required before production; no false identity on calls

### Sub-fragments to NOT build (flagged in research)
- `facebook_creator_marketplace_scout` — low signal, high platform risk. Drop.
- `phone_system_age_estimator` — too speculative. Drop.

### Sub-fragments to replace with licensed sources
- `linkedin_jobs_collector` — replace with a licensed job data API (JSearch, Jobicy, or similar)
- `linkedin_profile_enricher` — replace with Proxycurl API

---

## 8. What We Want the Agent to Do

Given everything above, we need:

1. **A full architectural design** — how to structure this as a Django project. Which Django apps, which models, how the Celery task system is organized, how tools are implemented, how the orchestrator works.

2. **A database schema** — what tables do we need? Each sub-fragment writes to at least one table. What are the shared practice/lead tables? How is signal decay stored? How are scores stored and versioned?

3. **A phased build plan** — in what order do we build sub-fragments? (Suggested priority: NPPES + Google Places + job portals + competitor ads + lifecycle events + champion tracking first, then everything else)

4. **A tool design spec** — how should tools be structured in code? As Django management commands? As a tool registry? As API endpoints? The agent should propose and justify.

5. **A Celery task design** — how should task scheduling work? Celery Beat? How are retry, rate-limiting, and failure handling standardised across 100+ collectors?

6. **A Docker Compose setup** — Django + PostgreSQL + Redis + Celery Worker + Celery Beat + Flower (monitoring)

We are not prescribing the architecture. The agent should think from first principles and propose what will actually work at scale — modular, maintainable, and testable.

---

## 9. Development Philosophy

- **Modular and surgical** — no bloat, no abstractions beyond what the task requires
- **Teaching as we build** — the developer is learning Django. Code should be explained where patterns are non-obvious. Do not write code without explaining the why.
- **No premature optimisation** — build for correctness first; optimise when there is a proven bottleneck
- **Single environment for now** — local only. No multi-environment config yet.
- **Git is managed by the developer** — never run git commands
- **No Docker complexity beyond what Celery + Redis require**

---

## 10. Project File Context

The full sub-fragment strategy document (including all business logic, compliance flags, build validation, and fragment/tool descriptions) lives at:

```
/Docs/subfragment-strategy-map.md
```

This document is the authoritative reference for what each sub-fragment does, what data it collects, and what compliance considerations apply. The agent should read it in full before making any architectural decisions.
