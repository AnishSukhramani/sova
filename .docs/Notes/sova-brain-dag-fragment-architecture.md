# Sova Brain — DAG Fragment Architecture

> The Sova brain is a Directed Acyclic Graph (DAG): sub-fragments collect raw data, fragments compose and interpret that data, and the brain orchestrates everything. This is the architectural model agreed on in session — save this as the canonical reference.

---

## You Just Described a DAG

- **DAG = Directed Acyclic Graph** — the exact architecture used by Apache Airflow, Prefect, Dagster
- Data flows in **one direction only**: sub-fragments → fragments → brain
- "Acyclic" = no loops, no circular dependencies
- Anish arrived at this from first principles — it matches industry-standard pipeline design

### The Three Layers

| Layer | Name | Job |
|---|---|---|
| Bottom | **Sub-fragment** | Pure data collector. One source. No opinion. Just raw data. |
| Middle | **Fragment** | Composer + interpreter. Combines sub-fragments. Answers one specific question. |
| Top | **Brain** | Scheduler + orchestrator. Manages all fragments. Handles final output. |

---

## The Diagrams

### Full Brain → Fragment → Sub-fragment Layout

```
╔══════════════════════════════════════════════════════════════════╗
║                        THE BRAIN                                 ║
║                   (Main Orchestrator)                            ║
║         "Schedule, dispatch, collect final output"               ║
╚══════════════╤═════════════════════════╤═══════════════════════╝
               │                         │
    ╔══════════▼═════════╗    ╔══════════▼═════════════╗
    ║  FRAGMENT: FIT     ║    ║  FRAGMENT: INTENT       ║
    ║  "Does this        ║    ║  "Is this practice      ║
    ║   practice match   ║    ║   in active pain        ║
    ║   our ICP?"        ║    ║   right now?"           ║
    ╚══╤═══════╤═════╤══╝    ╚══╤═══════╤══════════╤══╝
       │       │     │          │       │          │
  ╔════▼╗  ╔══▼══╗ ╔▼════╗  ╔══▼══╗ ╔══▼══╗ ╔════▼══╗
  ║NPPES║  ║TECH ║ ║SITE ║  ║JOBS ║ ║REV- ║ ║COMPET-║
  ║     ║  ║STACK║ ║     ║  ║     ║ ║IEWS ║ ║ ITOR  ║
  ║sub- ║  ║sub- ║ ║sub- ║  ║sub- ║ ║sub- ║ ║ xray  ║
  ║frag ║  ║frag ║ ║frag ║  ║frag ║ ║frag ║ ║sub-   ║
  ╚═════╝  ╚═════╝ ╚═════╝  ╚═════╝ ╚═════╝ ║frag   ║
                                             ╚═══════╝

  Sub-fragments = pure collectors. No opinion. Just data.
  Fragments = composers + interpreters. One question answered.
  Brain = scheduler + final output handler.
```

### Plug-and-Play: One Sub-fragment, Multiple Parent Fragments

```
         ╔═════════════════╗     ╔════════════════════╗
         ║  FRAGMENT: FIT  ║     ║  FRAGMENT: PROFILE ║
         ║  (ICP match?)   ║     ║  (enrich record)   ║
         ╚═══╤══════════╤══╝     ╚══════╤══════════╤══╝
             │          │               │          │
             │          └───────────────┘          │
             │                  │                  │
         ╔═══▼════╗        ╔════▼═══╗         ╔════▼═══╗
         ║  NPPES ║        ║  SITE  ║         ║  TECH  ║
         ║sub-frag║        ║sub-frag║         ║ STACK  ║
         ╚════════╝        ╚════════╝         ║sub-frag║
                                              ╚════════╝

  NPPES sub-fragment feeds both FIT and PROFILE fragments.
  Run once. Output shared. That's the plug-and-play.
```

---

## Key Design Question: Sub-fragment Output Sharing

- When two fragments both need NPPES data — does `nppes_collector` run **once or twice**?
- **Option A — Independent runs:** Each fragment calls its own sub-fragments. Simple, no shared state. Wasteful at scale (NPPES runs twice across 10,000 practices).
- **Option B — Cached output:** Sub-fragment runs once. Output sits in a temporary store (Redis or staging table). Any fragment reads from there.
- **Recommendation:** Option B at scale. Design toward it from the start even if you start with Option A.

---

## Fragment 1: FIT

**Question it answers:** Does this practice match our ICP?

| Sub-fragment | Data it collects | Why it matters |
|---|---|---|
| `nppes_collector` | NPI, practice name, address, phone, specialty code, solo vs. group | Confirms it's a real dental/medical practice, gives size signal |
| `tech_stack_collector` | PMS software on site, patient comms tools (Weave, Birdeye, NexHealth), what's missing | Absence of modern tools = sellable gap |
| `website_collector` | Online booking presence, call-to-action type, site recency, SSL, practice size signals | No booking widget = automation gap |

**Output:** Fit score (0–100) + profile of practice's current tech posture

---

## Fragment 2: INTENT

**Question it answers:** Is this practice experiencing pain right now?

| Sub-fragment | Data it collects | Why it matters |
|---|---|---|
| `jobs_collector` | Front desk job postings, job title, description text, posting frequency | Hiring = active pain. Same role 3+ times = chronic pain. Job description mentions Dentrix = PMS confirmed |
| `reviews_collector` | Google review count, review velocity (rate of new reviews), keywords around phones/appointments/hold times | Review velocity drop = no automation. Phone keywords = phone friction pain |
| `competitor_xray_collector` | LinkedIn engagement on competitor posts, who's liking/commenting | Engaging with Weave or NexHealth content = actively researching |

**Output:** Intent score (0–100) + specific pain signals with evidence

---

## Fragment 3: SCORE (Future — Phase 2)

**Question it answers:** How hot is this lead overall?

- Takes output from Fit + Intent fragments
- Applies weights to each signal
- Produces composite score
- Routes to the opportunity pipeline

---

## Signal Priority (Revised)

From highest to lowest business value:

1. **Chronic front desk turnover** (same role posted 3+ times in 12 months) — strongest pain signal
2. **Active front desk hiring** — immediate pain signal
3. **Phone friction in reviews** — patient-facing problem, externally validated
4. **New practice opening** — greenfield, buying cycle just started
5. **No modern comms tool detected on website** — gap is confirmed and visible
6. **Legacy PMS detected** — cold fit signal, useful for personalization
7. **Competitor engagement** — deprioritize for now

---

## Missing Signal: Practice Growth

- Not tracked in the legacy system but has real value
- **New practice opening** — just opened a second location, just got acquired by a DSO, or posted a job for a *new* role (not backfill) → growth phase → active tech buying cycle
- Detectable via: NPPES monthly delta (new NPI registrations, address changes), Google Maps new listing detection
- Open question: does `nppes_collector` track changes over time, or is this a separate `nppes_delta_collector` sub-fragment?

---

## Key Terminology

- **DAG (Directed Acyclic Graph):** A system where tasks/nodes flow in one direction with no circular dependencies — the standard model for data pipelines
- **Sub-fragment:** An atomic data collector. One source, one type of raw data, no processing opinion
- **Fragment:** A composer. Combines multiple sub-fragments and answers one specific business question
- **Brain:** The main orchestrator. Schedules fragments, collects final output, routes it
- **ICP (Ideal Customer Profile):** The type of practice most likely to buy — in Sova's case: solo/small DSO, legacy PMS, no phone automation, active front desk hiring
- **Intent signal:** A data point showing a practice is experiencing active pain *right now*
- **Fit signal:** A data point showing a practice structurally matches the ICP (industry, size, tech posture)
- **Plug-and-play:** Sub-fragments are reusable building blocks — any fragment can wire in any sub-fragment without modification

---

## Explore Further

- [Apache Airflow Docs — DAG concept](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html) — canonical reference for DAG-based pipeline thinking
- [Prefect Docs — Tasks and Flows](https://docs.prefect.io/latest/concepts/tasks/) — more modern take on the same pattern, cleaner API
- [Dagster — Asset-based pipelines](https://docs.dagster.io/concepts/assets/software-defined-assets) — extends the DAG model to "data assets" rather than just tasks
- [Bombora Intent Data overview](https://bombora.com/intent-data/) — how the industry's largest intent data platform defines and collects signals
- [Apollo Signals — lead scoring](https://www.apollo.io/product/scores) — real-world example of fit + intent composite scoring

---

## How We Used It / Why It Matters

- This model replaced the flat "brain → fragments" design from the legacy system plan
- The key insight: sub-fragments are **reusable across multiple parent fragments** — build once, compose freely
- Fit and Intent are the two axes — directly mirrors how Apollo, ZoomInfo, and Bombora score leads
- This model scales: adding a new fragment = selecting existing sub-fragments + adding a new processing layer. No rewrites.
- The brain doesn't care what's inside a fragment — it just schedules them and collects output

---

## Open Questions (To Resolve Next Session)

1. Do Fit and Intent as the two top-level fragments match the final vision, or are there more?
2. Should `nppes_collector` track deltas (changes over time) or stay as a one-time ingest sub-fragment?
3. At what layer does DB persistence happen — sub-fragment, fragment, or brain?
4. What's the caching strategy for shared sub-fragment output at scale?
