# Sova — Sub-fragment Strategy Map

> Every sub-fragment is a specialized data collector. Each one monitors a specific slice of the internet relevant to our business. Together they feed the fragments, which feed the brain.
>
> **Goal:** 2,000 operational locations by end of 2027. Currently at 200. This document maps every strategy we are using to find, qualify, and understand our target customers.

---

## How to Read This Document

- Each **strategy** is a category of intelligence we want to gather
- Each **sub-fragment** under a strategy is one autonomous data collector
- Sub-fragments only collect and write data — they do not act on it
- Fragments (the layer above) compose sub-fragments to answer a business question
- The Brain orchestrates all fragments

---

## Classification System

Every piece of data collected by a sub-fragment is eventually classified as one of:

| Class | What it means | Example |
|---|---|---|
| **Opportunity** | Actionable lead — we can pitch this practice now | A clinic posted a front desk job opening |
| **Content** | Useful industry info — post on our social channels | A new dental AI regulation was published |
| **Noise** | Irrelevant — discard | A dentist reviewed a restaurant |

---

## Strategy 1 — Job Portal Scouting

**Business logic:** We build an AI receptionist that replaces front desk staff. Any dental or medical practice actively hiring for a front desk role is a practice experiencing the exact pain we solve. We find them before anyone else does and reach out first.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `dentalpost_collector` | Scrapes DentalPost for front desk / patient coordinator job postings at dental practices. Detects chronic re-posting (same role 3+ times in 12 months = chronic turnover signal). | HTTP fetch + BeautifulSoup HTML parsing. DentalPost is public, no auth required. |
| `indeed_collector` | Broader coverage — finds dental/medical front desk openings on Indeed to catch practices not posting on DentalPost. | HTTP fetch + BeautifulSoup. Indeed API is closed — scraping only. |
| `linkedin_jobs_collector` | Finds front desk / receptionist openings at dental/medical practices on LinkedIn Jobs. Job descriptions often reveal current PMS (e.g., "must know Dentrix"). | LinkedIn Jobs search is public HTML. HTTP fetch + parse. Falls back to Hyperbrowser if gating appears. |
| `ihiredental_collector` | Specialty dental job board with postings that don't appear on DentalPost or Indeed. High signal-to-noise ratio. | HTTP fetch + BeautifulSoup. |
| `ziprecruiter_collector` | Additional job board for dental/medical front desk roles. Adds geographic and volume coverage. | HTTP fetch + BeautifulSoup. |
| `glassdoor_collector` | Scans Glassdoor employee reviews for dental practices. "Revolving door" or "management chaos" reviews = chronic turnover signal without checking a job board. | HTTP fetch + BeautifulSoup. Glassdoor is partially public. |

---

## Strategy 2 — Social Platform Intelligence

**Business logic:** Our ICP (dental practice owners, office managers) is active on Facebook, LinkedIn, YouTube, and increasingly TikTok. These platforms expose hiring intent, pain points, competitor engagement, and direct contact opportunities. We use official APIs first for compliance and reliability, then Hyperbrowser automation for data the APIs don't expose.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `facebook_api_collector` | Collects publicly available data on dental practice Facebook pages: follower count, post frequency, last activity date, engagement rate. Dormant pages = low tech engagement. | Facebook Graph API (official). Requires approved Facebook App. Public page data accessible without special permissions. |
| `linkedin_api_collector` | Collects competitor and practice LinkedIn Company Page data: follower count, employee count, recent post themes, follower growth rate. | LinkedIn Company Pages API (official). Public company data accessible. Limited but reliable. |
| `facebook_hyperbrowser_agent` | When official API hits limits, simulates a human browser session on Facebook. Collects richer data — group posts, comment threads, ad engagement not exposed in the API. | Hyperbrowser SDK. Human-like browser sessions. Read-only, no login required for public content. |
| `linkedin_hyperbrowser_agent` | Simulates a human browser session on LinkedIn. Specifically: commenter profiles on competitor posts, practice owner activity, dental group discussions. These commenters are warm leads. | Hyperbrowser SDK. Targets public post engagement data not available via official API. |
| `youtube_competitor_monitor` | Monitors competitor YouTube channels for new video uploads, view counts, engagement rates, and topic patterns. Also monitors YouTube search results for category terms ("dental AI receptionist", "dental answering service", "voice AI dental") to track which content ranks and what competitors are producing. A competitor publishing demo videos or testimonials is signalling what messaging is converting for them. | YouTube Data API v3 (official, free tier). Searches by channel ID for known competitors + keyword searches for category terms. Tracks upload frequency, view velocity, and comment sentiment on competitor content. |
| `tiktok_industry_monitor` | Monitors TikTok for dental practice owner content, competitor presence, and AI receptionist category discussions. TikTok is where younger dental associates and new practice owners discover vendors — it surfaces a different ICP demographic than LinkedIn or Dentaltown. A competitor running TikTok ads or an influencer reviewing AI tools there is early signal the category is expanding. | TikTok Research API (official, available for approved researchers). Public video search by hashtag and keyword. Targets: `#dentist`, `#dentalpractice`, `#dentaloffice`, competitor brand handles, category keywords. Falls back to Hyperbrowser for public content not accessible via API. |

---

## Strategy 3 — Seminar & Conference Scouting

**Business logic:** Major dental and healthcare conferences (HLTH, ADA Annual, Dentsply Sirona World) are where decision-makers gather. Speakers are influential practice owners. Sponsors are our competitors and partners. Attendees are our ICP. We monitor conference activity to surface leads and track competitor presence.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `conference_website_monitor` | Tracks official websites of major dental/healthcare conferences. Monitors speaker lists, sponsor lists, session topics, and attendee counts. Surfaces influential practice owners (speakers) as premium leads. | HTTP fetch + BeautifulSoup. Monitors: HLTH, ADA Annual Meeting, Dentsply Sirona World, Oral Health Conference, and others. |
| `conference_social_tracker` | Tracks the Facebook and LinkedIn pages of major conferences. Collects post engagement and who is commenting. Practice owners commenting on dental conference posts are highly qualified ICP. | Facebook Graph API + LinkedIn API first. Hyperbrowser fallback. |

---

## Strategy 4 — Newsletter Intelligence Agent

**Business logic:** Industry newsletters surface news before it hits search engines. New clinic openings, acquisitions, regulatory changes, and competitor announcements all appear first in newsletters. A dedicated inbox subscribed to every relevant newsletter becomes a live intelligence feed.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `email_inbox_reader` | Connects to a dedicated Gmail inbox subscribed to relevant dental/healthcare/AI newsletters. Reads incoming emails, strips HTML, extracts plain text content. Passes content to the classifier. | Gmail API (official, OAuth). Reads from a dedicated Sova intelligence email account. |
| `newsletter_classifier` | Takes extracted newsletter content and classifies each item as Opportunity, Content, or Noise using an LLM. Opportunity = actionable lead. Content = social media material. Noise = discard. | OpenAI API (gpt-4o-mini). Runs against extracted email text. Returns structured classification with a reason. |

**Newsletter subscriptions to maintain:**
- Dental Economics newsletter
- Dentistry Today newsletter
- ADA News
- Modern Healthcare daily
- HLTH community digest
- CB Insights health tech
- Rock Health digest
- Relevant local dental association newsletters

---

## Strategy 5 — Opinion Platform Scrapers

**Business logic:** Reddit, Quora, and dental forums are where practice owners speak candidly about their problems. A post asking "how do I handle after-hours calls?" is a direct, unprompted pain signal. These platforms give us first-hand, unfiltered evidence of the exact problems we solve.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `reddit_scout` | Monitors relevant dental subreddits for posts where practice owners or staff mention phone management, front desk problems, hiring struggles, or patient communication issues. | Reddit API (official, free). Targets: `r/dentistry`, `r/DentalHygiene`, `r/DentalPracticeManagement`, `r/smallbusiness`, `r/Entrepreneur`. |
| `quora_scout` | Monitors Quora questions tagged with dental practice management, front desk automation, and patient communication. Practice owners asking operational questions are research-phase leads. | HTTP fetch + BeautifulSoup. Quora questions are publicly indexed. |
| `dentaltown_forum_scout` | Scrapes Dental Town (dentaltown.com) forums — the most active dental practice owner community online. Surfaces operational pain discussions, vendor complaints, tech questions. | HTTP fetch + BeautifulSoup. Public forum content. |
| `facebook_groups_scout` | Monitors public Facebook groups for dental practice owners. Scrapes public posts for hiring complaints, tech frustrations, patient communication problems. | Facebook Graph API for public groups. Hyperbrowser for groups not accessible via API. |

---

## Strategy 6 — Practice Data Foundation

**Business logic:** Before any signal can be collected, we need a master database of every dental and medical practice in the US. NPPES is the official US government registry of all licensed healthcare providers. It is the starting point for everything — we know a practice exists, where it is, and how to contact it before any other fragment runs.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `nppes_collector` | Ingests the NPPES government NPI registry. Builds and refreshes the master list of all dental/medical practices in the US. Extracts: NPI, practice name, address, phone, specialty taxonomy code, solo vs. group classification. | Downloads the monthly NPPES CSV (~7GB). Streams row-by-row using Python's built-in `csv` module. Filters for dental taxonomy codes. No API key required. |
| `google_places_collector` | For each known practice, fetches review count, star rating, review velocity, and review text. Surfaces phone friction signals (review keywords: "couldn't get through", "voicemail", "on hold"). Stagnant review count = no review automation tool. | Google Places API (official). Requires `GOOGLE_MAPS_API_KEY`. Paid per call — batch carefully. |
| `clinic_hours_change_monitor` | Tracks changes to a practice's listed opening hours on Google Business Profile. Extending to evenings or weekends = volume growth = needs call handling automation. Reducing hours = financial stress signal. Both are meaningful. | Google Places API. Polls each practice's `opening_hours` field weekly. Detects diffs against stored baseline. |

---

## Strategy 7 — Website & RSS Monitoring

**Business logic:** Practice websites reveal what tools a practice is using (or not using). Industry websites reveal where the market is moving. RSS feeds let us monitor both without polling every source manually.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `website_crawler` | Visits each practice's homepage. Detects automation gaps: no booking widget, no patient comms embed (Weave, NexHealth, Birdeye), no online scheduling CTA. Absence of these tools = gap we can sell into. | `httpx` HTTP fetch + BeautifulSoup. Scans for known embed signatures and CTA text patterns. |
| `rss_feed_monitor` | Maintains a curated list of industry-relevant websites. Polls their RSS feeds for new articles. Feeds content into the newsletter classifier. Catches regulatory changes, market shifts, and product announcements. | Python `feedparser` library. RSS/Atom feed parsing. No auth required for public feeds. |
| `competitor_website_monitor` | Monitors competitor homepages and pricing pages for changes. A competitor changing pricing, adding a feature, or updating their messaging is a threat signal and a sales talking point. | HTTP fetch + hash comparison (detect page changes). Alerts when meaningful content changes. |

**RSS sources to monitor:**
- ADA News (`ada.org/en/publications/ada-news`)
- Dentistry Today
- Dental Economics
- Modern Healthcare
- CMS.gov news
- HIPAA Journal
- Rock Health

---

## Strategy 8 — Competitor Intelligence

**Business logic:** We operate in a crowded and fast-moving market (15+ voice AI competitors in dental as of 2026). Knowing exactly what competitors are advertising, which clients they have, what they are building, and where they are expanding is essential for staying ahead. We do this through legitimate, publicly available data sources only.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `facebook_ads_library_collector` | Tracks every active ad run by competitors on Facebook/Instagram. Collects: ad copy, creative format, run duration, geographic targeting, estimated audience size. Signals where competitors are spending and what messaging is working. | Meta Ad Library API (official, free). No ad spend required. Search by competitor Facebook Page ID or keyword. |
| `facebook_creator_marketplace_scout` | Monitors Creator Marketplace for dental/healthcare influencer partnerships by competitors. Reveals which influencers competitors are using and what campaigns are running. | Hyperbrowser browser automation. Creator Marketplace is public-facing. |
| `competitor_client_scout` | Scans competitor websites for case studies, testimonials, and named client logos. Extracts practice names. These practices are existing competitor clients — targets for competitive displacement pitches. | HTTP fetch + BeautifulSoup. Targets competitor case study and testimonials pages. |
| `competitor_jobs_tracker` | Monitors what roles competitors are actively hiring for. Engineering hires = new feature in development. Sales hires = expanding into new markets. Support hires = product has problems. Each is a different kind of intelligence. | Scrapes competitor career pages + searches DentalPost/Indeed by company name. |
| `crunchbase_monitor` | Tracks funding rounds, acquisitions, and executive hires for competitor companies. A competitor raising a Series A = they are about to ramp sales. A threat signal and urgency trigger for our own outreach. | Crunchbase API (official, limited free tier) or HTTP fetch of public company pages. |
| `competitor_pr_monitor` | Dedicated news monitor for competitor brand mentions, press releases, and product announcements. Every time a competitor gets a news article, we know same day. | Google News RSS + custom keyword alerts. Targets competitor brand names and product names. |
| `google_ads_intelligence_collector` | Tracks which competitors are running Google search ads and on which keywords. A competitor bidding heavily on "dental AI receptionist" or "dental answering service" tells us exactly which terms they believe convert — their paid search strategy is their ICP targeting strategy, exposed. Also tracks ad copy patterns: what angles are they using, what proof points, what CTAs. | Google Ads Transparency Center (public, free — `adstransparency.google.com`). HTTP fetch + BeautifulSoup. Supplemented by SEMrush API or SpyFu API for historical keyword data and estimated spend ranges. Runs weekly on all known competitor domains. |
| `linkedin_ads_library_collector` | Monitors LinkedIn's Ad Library for all active ads run by competitor companies. LinkedIn's ad library is publicly accessible and shows ad creative, copy, and run duration. A competitor running LinkedIn ads targeting "dental practice owners" or "office managers" reveals their exact buyer targeting and message framing. | LinkedIn Ad Library (`linkedin.com/ad-library`). HTTP fetch + BeautifulSoup or Hyperbrowser. Search by competitor company name. Extracts: ad copy, format, CTA, and approximate run duration. Runs weekly. |
| `weave_truelark_displacement_monitor` | Weave acquired TrueLark in May 2025. TrueLark had 500+ dental clients. Post-acquisition, those clients face contract uncertainty, product roadmap confusion, and support disruption — the classic conditions that produce churn. This sub-fragment monitors for TrueLark client churn signals: review complaints mentioning TrueLark by name, job postings from known TrueLark clients mentioning "phone system," Glassdoor reviews from TrueLark employees flagging product chaos. The 18-month post-acquisition window is open now. It closes. | HTTP fetch + NLP on review platforms and job boards filtered by known TrueLark client names (scraped from their pre-acquisition case study pages). Cross-references against `competitor_client_scout` data for TrueLark. Time-bounded — escalate priority of this sub-fragment immediately. |
| `competitor_churn_poison_monitor` | Monitors public reviews (G2, Capterra, Google, Yelp), Glassdoor employee comments, and community forum threads for complaints about competitor reliability — dropped calls, billing chaos, cancelled contracts, poor support. A competitor's market reputation decaying in public is a displacement opening. Different from `competitor_product_monitor` which tracks features — this tracks sentiment. | NLP on existing review platform output filtered by competitor brand names. Plus targeted HTTP fetch + BeautifulSoup on G2/Capterra reviews for each competitor. Runs weekly. Flags any competitor with a downward rating trend or spike in complaint velocity. |
| `competitor_product_monitor` | Tracks competitor feature pages, pricing pages, and changelog/update pages. Detects when pricing tiers change, new features are added, or positioning language shifts. Output: structured diff of what changed and the current state of their offer. Answers: how should we price, position, and differentiate? | HTTP fetch + BeautifulSoup + hash comparison for change detection. On detected change: LLM extracts structured fields (price points, feature list, positioning language). Runs weekly on competitor feature, pricing, and changelog URLs. **Competitors to monitor:** Rondah AI (DSO-first, $3.5M raised), TensorLinks AI FrontDesk (omnichannel, mobile app), Arini (YC-backed, real-time insurance eligibility during calls), Viva AI (100+ languages, emotion detection), TrueLark (10M+ conversation training set), mConsent (hybrid AI + human insurance concierge), AINORA (European, persistent patient memory), NexHealth (Synchronizer API, $1B valuation), Weave, HeyGent, Dentina.AI. |

---

## Strategy 9 — Google Cloud API Suite

**Business logic:** Our existing Google Cloud account gives us access to a suite of APIs beyond just Google Maps. These APIs surface market signals, trend data, and search intent data that no scraper can replicate.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `google_news_collector` | Monitors healthcare, dental, voice AI, and practice management topics in Google News. Surfaces regulatory changes, competitor coverage, and market news. | Google News RSS feeds (free) or Google Cloud Natural Language API for topic classification. |
| `google_trends_monitor` | Tracks search trend volume for relevant keywords: "dental receptionist AI", "voice AI healthcare", "front desk automation", "dental answering service". Rising trends = growing market awareness = better timing for outreach. | Google Trends unofficial API (`pytrends` Python library). Free. No official API but well-maintained. |

---

## Strategy 10 — Review Platform Expansion

**Business logic:** Google Maps is one review source. But practices in certain regions have more Yelp or Healthgrades reviews than Google reviews. Expanding to multiple review platforms increases signal coverage and reduces blind spots.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `yelp_collector` | Yelp business listings for dental practices. Fetches review count, star rating, and review text. Supplements Google Places where Yelp is stronger (typically West Coast USA). | Yelp Fusion API (official, free tier available). Requires API key. |
| `healthgrades_collector` | Healthgrades.com patient reviews for dentists. Fetches rating, review count, and whether the practice profile is "claimed". Unclaimed profile = low tech engagement. | HTTP fetch + BeautifulSoup. Public listings. |
| `zocdoc_listing_detector` | Checks if a practice is listed on Zocdoc (online booking platform). Listed = they already have some booking automation. Not listed = an automation gap we can sell into. | HTTP fetch or Zocdoc search scrape. Cross-reference against known practice domains. |
| `review_response_rate_tracker` | Measures how consistently a practice responds to Google and Yelp reviews. Zero or near-zero response rate = low operational engagement and reputation neglect. These practices are also the ones letting phones go unanswered. Both signal the same underlying problem. | Computation on existing `google_places_collector` and `yelp_collector` output. Tracks response timestamp vs. review timestamp per listing. Low maintenance — no new data source. |
| `reputation_shock_detector` | Detects sudden bursts of negative reviews containing phone, scheduling, or accessibility complaints ("couldn't get through," "voicemail," "never answers"). A spike of 3+ complaints within 30 days = acute operational pain, not background noise. Highest-priority outreach window. | Time-series anomaly detection on existing review collector output. LLM classification of complaint type. Fires an alert when spike threshold is crossed at any monitored practice. |

---

## Strategy 11 — Local Market Intelligence

**Business logic:** New practices opening are greenfield leads — they are actively building their systems and have no vendor lock-in. Practices expanding to a new location are in a growth buying cycle. Both are the highest-conversion lead types. We want to find them the moment they become active.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `business_license_monitor` | Many US counties publish new business license filings publicly. A new dental LLC filing = a new practice opening = a greenfield lead before the practice even has a Google listing. | County-level public records scraping. Varies by state/county. Requires building a source list per state. |
| `commercial_real_estate_scout` | Monitors LoopNet and similar commercial listing sites for new dental office space leases or buildouts. A practice signing a new location lease = expansion = active tech buying cycle. | HTTP fetch + BeautifulSoup on LoopNet public listings. Filter by property type (medical/dental office). |

---

## Strategy 12 — Partnership & Channel Intelligence

**Business logic:** Dental supply companies like Henry Schein and Patterson Dental have direct relationships with tens of thousands of practices. Their partner ecosystems, event sponsorships, and product promotions surface which practices are actively buying technology. Dental insurance networks surface which practices are enrolled and operating.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `dental_supplier_monitor` | Monitors Henry Schein and Patterson Dental websites for technology partner changes, new product promotions, and affiliated practice listings. Their tech partners are our competition — and their customer base is our ICP. | HTTP fetch + BeautifulSoup on public partner and product pages. |
| `insurance_network_collector` | Scrapes public dentist directories from Delta Dental, MetLife, and other major insurers. Cross-references against NPPES to discover practices not yet in our database. | HTTP fetch + BeautifulSoup. Public dentist directories. Paginated scraping. |
| `insurance_plan_change_monitor` | Detects when a practice joins or leaves a major insurance network. Joining = patient volume spike incoming = call handling demand rises. Leaving = revenue drop = cost pressure = efficiency pitch. Tracks the *delta*, not just the static directory. | Polls insurer directories on a schedule and diffs against stored snapshots. Flags new additions and removals with effective dates. |
| `dental_insurer_credentialing_monitor` | Tracks newly enrolled practices that are publicly signaling a credentialing delay — waiting on Delta Dental, MetLife, or Cigna to approve their provider enrollment. During this window, the practice cannot see new insurance patients but still handles all inbound calls and inquiries. Maximum phone chaos, zero booking conversion. Prime outreach window. | HTTP fetch + NLP on practice websites, Google Business posts, and Facebook page updates for credentialing language ("now accepting new patients pending insurance approval," "credentialing in process"). Cross-references `insurance_network_collector` diffs for newly appearing NPIs. |
| `insurance_ppo_density_monitor` | Counts how many PPO networks each practice participates in. Practices on 5+ PPO networks face dramatically higher admin burden — continuous eligibility verification, complex claim tracking, constant billing complexity. High PPO count = strongest possible AI receptionist candidate. | Aggregates counts from `insurance_network_collector` output per practice NPI. Pure computation on existing data — no new source required. |

---

## Strategy 13 — Signal Enrichment Layer

**Business logic:** Once a practice is identified as a hot lead, we need to find who to contact and how. This layer enriches a practice record with direct contact information for the decision-maker — the practice owner or office manager.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `hunter_enricher` | Given a practice domain, finds the decision-maker's email address and confidence score. | Hunter.io API (official). Paid per lookup — run only on high-score leads. Requires `HUNTER_API_KEY`. |
| `linkedin_profile_enricher` | Given a practice name and location, finds the practice owner's or office manager's LinkedIn profile. Adds a direct professional outreach channel. | LinkedIn People Search (Hyperbrowser). Public profiles. |
| `phone_validator` | Validates and formats phone numbers from NPPES and other sources. Removes disconnected lines. A practice with a dead phone number is either closed or in operational chaos — worth flagging. | Twilio Lookup API or `phonenumbers` Python library for format validation. Paid per lookup for line-type check. |

---

---

## Strategy 14 — Champion Tracking

**Business logic:** The warmest possible lead is a dental office manager or front desk coordinator who already works at one of our client locations and then moves to a new practice. We already sold them once — they know the product works. When they land at a new practice that doesn't have us, they are already an internal champion. At 200 locations with ~200–400 staff in relevant roles, even a 10% annual job change rate is 20–40 warm leads per year at practices we've never touched. UserGems reports this channel produces 114% higher win rates and 3x close rates vs. cold outreach.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `champion_job_change_tracker` | Monitors LinkedIn for job changes among dental staff from current client locations. When a known contact moves to a new practice, flags it as a warm lead immediately. | Proxycurl API (official LinkedIn data proxy). Cross-references a seed list of known contacts from client practices against their current employer field. Weekly polling. |

---

## Strategy 15 — Practice Lifecycle Event Monitoring

**Business logic:** The single most predictive buying trigger is a lifecycle event — a practice opening, a change in ownership, a new associate joining. These events create a 30–90 day window where the practice is actively rebuilding systems and has zero incumbent vendor loyalty. We need to find these practices the moment the event occurs, not weeks later.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `npi_new_registration_monitor` | Tracks the monthly NPPES data delta — specifically new NPI registrations with dental taxonomy codes and solo/individual classification. New solo NPI = new practice starting up = greenfield lead. | Downloads two consecutive monthly NPPES CSVs and diffs them. New rows with dental taxonomy = new practices. Built on top of `nppes_collector` output. |
| `dental_broker_listing_monitor` | Scrapes dental practice brokerage websites for new listings (practice for sale) and closed transactions (listing disappeared = sold = new owner rebuilding everything). | HTTP fetch + BeautifulSoup on: Henry Schein Dental Practice Transitions, AFTCO, Omni Practice Group, Professional Transition Strategies. Monitors listing inventory changes daily. |
| `dental_school_new_licensee_monitor` | Scrapes all 50 state dental board websites monthly for newly issued dental licenses. Fresh graduates entering practice are building their stack from scratch — zero incumbent vendors. | HTTP fetch + BeautifulSoup. Per-state scrapers required. Priority states first: CA, TX, NY, FL, IL. |
| `building_permit_monitor` | Monitors county-level building permit databases for commercial renovation or build-out permits filed for dental office spaces. A practice pulling a renovation permit = expanding = active tech buying cycle. | HTTP fetch + BeautifulSoup on county permit portals. Start with top 20 US metro areas. Filter by permit type (commercial interior) + business classification (dental/medical). |
| `multi_location_expansion_detector` | Tracks NPPES data for existing practices that register a new NPI under the same tax ID or add a new address to an existing entity. Different from `npi_new_registration_monitor` — this is not a new practice, it is an existing client or prospect adding a location. Adding a second location = scaling fast = needs systems that don't break with growth. | NPPES monthly delta comparison + entity resolution on practice names, tax IDs, and addresses. Runs on the same NPPES pipeline as `npi_new_registration_monitor` — zero marginal data cost. |

---

## Strategy 16 — Government Data Sources

**Business logic:** The US government publishes more healthcare provider data than almost anyone uses. CMS, SBA, and state licensing boards contain signals that no commercial data vendor offers — scattered across hundreds of agency websites. Aggregating this data is pure competitive advantage. Nobody in the dental AI space is doing this systematically.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `cms_enrollment_collector` | Downloads Medicare Fee-For-Service Provider Enrollment data from CMS Open Data. Extracts dental specialist enrollment dates, practice locations, and Medicare acceptance status. Enrollment date = approximate practice start date. | CMS Open Data Portal API (`data.cms.gov`). Free, official. Bulk CSV download or JSON API. NAICS/taxonomy filter for dental specialties. |
| `sba_loan_monitor` | Monitors SBA FOIA loan data for new SBA 7(a) and 504 loans issued to dental practices (NAICS code 621210 = Offices of Dentists). New SBA loan = new practice startup or major expansion. | SBA FOIA data releases. Periodic batch downloads. Filter by NAICS 621210. Free public data. |
| `dea_registration_checker` | Validates that a practice is currently active by checking DEA registration status for the practicing dentist. Lapsed DEA = potentially closed or inactive practice. Cleans dead leads from the database. | DEA Diversion Control Division verification tool (`deadiversion.usdoj.gov`). Rate-limited HTTP lookup per NPI/DEA number. |
| `state_medicaid_provider_monitor` | Scrapes state Medicaid dental provider directories. Identifies practices accepting Medicaid — different patient demographic, different workflow pressure, often underserved by tech vendors. Also surfaces practices not in NPPES. | HTTP fetch + BeautifulSoup on state Medicaid agency provider lookup pages. Priority states: CA, TX, NY, FL, IL, OH. |
| `ucc_loan_filings_monitor` | Monitors Uniform Commercial Code (UCC) financing statements filed at Secretary of State offices. A dental practice filing for commercial equipment financing = modernisation cycle in progress = active buying window. Complements SBA loan monitoring with a broader net. | HTTP fetch on state SoS UCC search portals. Filter filings by debtor business classification (dental/medical). Free public data. Varies by state. |
| `oig_exclusion_checker` | Checks each practice's providers against the HHS Office of Inspector General (OIG) LEIE exclusion list — healthcare providers barred from federal programs for fraud, abuse, or other violations. An OIG-excluded provider cannot participate in Medicare or Medicaid. Their practice is either defunct or operating outside normal reimbursement — almost certainly not a viable lead. Prevents wasting outreach cycles on permanently disqualified accounts. Immediate negative signal: removes from all outreach queues. | HHS OIG LEIE downloadable database (free, updated monthly at `oig.hhs.gov/exclusions/exclusions_list.asp`). Cross-reference against NPPES provider NPI list. Batch process monthly. Simple text match on provider name + NPI. |
| `hrsa_hpsa_monitor` | Downloads HRSA Health Professional Shortage Area (HPSA) dental designations by geography. Practices in HPSA-designated areas face the most severe dental workforce shortages in the country — staffing is structurally impossible, not just cyclically tight. These are the strongest automation candidates in existence. Also surfaces Federally Qualified Health Centers (FQHCs) and community health centers — a distinct buyer segment with different procurement but very high volume and acute staffing pain. | HRSA data warehouse API or bulk download (`data.hrsa.gov`). Free, official. Filter for dental HPSA designation type. Join against practice ZIP codes in the database. Flag HPSA-located practices with a structural staffing urgency modifier. |
| `osha_fda_recall_monitor` | Monitors OSHA safety alerts and FDA device recall notices for dental equipment. A practice affected by a device recall is forced to evaluate replacement technology — active disruption = open buying window for adjacent tech upgrades. | FDA MedWatch RSS feed + OSHA news RSS. Filter by dental device category. Free, public. |
| `bls_staffing_heatmap` | Downloads Bureau of Labor Statistics dental office employment and wage data by metro area. Rising wages or declining employment in a metro = structural staffing shortage = broad intent for automation across all practices in that market. Adds a market-context layer on top of per-practice signals. | BLS API (`api.bls.gov`). Free, official. NAICS 621210 (Offices of Dentists). Quarterly updates. Joins against practice ZIP codes in the database to add a metro-level staffing pressure modifier. |

---

## Strategy 17 — Dental Association & Specialty Databases

**Business logic:** The ADA and dental specialty associations maintain member directories that are more current and complete than any commercial vendor list for this vertical. Specialty practices (orthodontists, oral surgeons, periodontists) are higher-revenue, larger staff, and stronger AI receptionist candidates. These directories are publicly searchable even where not bulk-downloadable.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `ada_member_finder_scraper` | Scrapes the ADA's public "Find a Dentist" directory by zip code and specialty. Extracts practice name, address, phone, and ADA membership status. ADA members self-select as engaged with the profession — better leads than cold NPPES records. | HTTP fetch + BeautifulSoup on `findadentist.ada.org`. Paginated by zip code grid across all US zip codes. |
| `dental_specialty_association_scraper` | Scrapes member finder tools for AAO (Orthodontists), AAOMS (Oral Surgeons), AAP (Periodontists), AAPD (Pediatric Dentists). Higher-revenue practices, larger staff, better candidates. | HTTP fetch + BeautifulSoup. One scraper per association directory. All are publicly searchable by location. |
| `aadom_member_intelligence_collector` | Scrapes the AADOM (American Association of Dental Office Management) public member directory and event attendee lists. AADOM members are office managers who have self-identified as professionally engaged — they pay for membership, attend conferences, and actively seek to improve their practice's operations. These are not just any office managers. These are the most reachable, most influential buying committee members in the entire industry. AADOM membership = internal champion pre-qualified. | HTTP fetch + BeautifulSoup on `aadom.net` public member/chapter pages. Extracts practice name, city, and state. Cross-references against NPPES to match to practice records. Outputs a prioritised subset of the practice database where the OM is already professionally engaged. |
| `beckers_dental_review_scraper` | Scrapes Becker's Dental Review editorial content — DSO deal announcements, practice acquisitions, tech adoption stories, named practice lists. Any practice named in Becker's is growing, being acquired, or tech-forward. All three = priority lead. | HTTP fetch + BeautifulSoup + RSS on `beckershospitalreview.com/dentistry`. Public content. |

---

## Strategy 18 — Technographic Intelligence

**Business logic:** Knowing what software a practice currently runs is more valuable than knowing their location. A practice running Dentrix (30-year-old desktop software) is a very different pitch than one on Curve Dental (cloud-native). We can infer most of this from publicly visible signals — job postings, website embeds, Google Business profiles — without paying enterprise data vendors.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `pms_signal_extractor` | Parses dental job postings already collected by job board sub-fragments and extracts software mentions ("must know Dentrix", "Eaglesoft experience required"). Builds a PMS inference map: which practice uses which software. Practices switching PMS = in buying mode. | NLP/regex extraction on job description text already stored. No additional data source — runs on existing job collector output. Zero marginal cost. |
| `booking_tech_detector` | Enhanced website crawl specifically identifying which patient booking or communication tool is embedded on each practice site. Absence of any modern tool = automation gap. Presence of a competitor tool = displacement target. | `httpx` + BeautifulSoup. Scans for embed signatures of: Zocdoc, NexHealth, Weave, Birdeye, Podium, Lighthouse 360, RevenueWell, Demandforce. |
| `bilingual_demand_detector` | Detects practices serving non-English-speaking patient populations: scans website service pages for Spanish/Mandarin/Vietnamese/Tagalog language options, and job postings for "bilingual required" or "Spanish-speaking front desk." Multilingual practices have dramatically more complex call routing — wrong-language calls are almost always abandoned. The AI receptionist's multilingual capability is a direct, unambiguous value proposition here. | HTTP fetch + BeautifulSoup on practice website language indicators + hreflang tags. NLP on existing job collector output for bilingual keywords. Zero new data sources — runs on existing crawl passes. |
| `g2_intent_monitor` | Monitors G2 category pages for "AI receptionist" and "dental answering service" to detect which companies are actively browsing competitor listings. Practices on G2 researching this category are in active evaluation mode — highest intent. | G2 Buyer Intent API (official, paid). Fallback: scrape G2 public category review pages and track review velocity as a proxy intent signal. |
| `pms_migration_detector` | Parses job postings already collected by job board sub-fragments for language indicating a PMS switch in progress: "transitioning from Dentrix to Curve", "experience with Open Dental preferred — we are migrating", "must be comfortable learning new systems". A practice mid-PMS migration is re-evaluating its entire tech stack. Zero-resistance window to introduce a complementary AI layer. | NLP/regex on existing job posting text. No additional data source. Enhancement of `pms_signal_extractor` — same pipeline, different pattern matching. |
| `patient_financing_badge_detector` | Detects CareCredit, Cherry, Sunbit, and LendingClub Health Finance badges on practice websites and intake pages. Practices offering patient financing are elective/cosmetic-revenue oriented — higher average patient value, higher cost per missed call. Stronger economic case for AI receptionist. | `httpx` + BeautifulSoup. Scans for known badge embed signatures and financing link patterns. Runs on the same crawl pass as `website_crawler`. Zero marginal fetch cost. |

---

## Strategy 19 — Website Visitor De-Anonymization

**Business logic:** 70% of buying activity happens before a prospect ever contacts a vendor. When a dental office manager visits the Sova pricing page, we don't know who they are. De-anonymization tools match IP addresses against company databases to identify which practice is on the site right now — before they fill out a form. This catches practices in active evaluation mode so we can reach out first.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `bombora_b2b_intent_integration` | Integrates Bombora B2B intent data — Bombora tracks which companies are actively consuming content on specific topics across thousands of third-party B2B publishing sites. When a dental practice is reading articles about "AI receptionist," "dental answering service," or "front desk automation" on external sites, Bombora surfaces them as in active research mode — before they ever visit Sova's website or fill out a form. Catches demand at the earliest possible moment in the buying cycle. | Bombora Company Surge API (official, paid). Filter by topic categories: "AI Receptionist," "Healthcare Automation," "Voice AI," "Dental Practice Management Software." Match returning company domains against the NPPES practice database by domain. Fires a first-party intent signal to the outreach queue. |
| `website_visitor_deanonymizer` | Identifies which dental practices are visiting the Sova website by IP-to-company matching. When a dental practice network hits key pages (pricing, how-it-works, comparisons), fires a lead alert to the outreach queue. | RB2B API (person-level de-anonymization, free tier available) or Clearbit Reveal (IP-to-company). Integrates with Sova website via a tracking pixel. Not a scraper — reads inbound traffic. |

---

## Strategy 20 — DSO Proximity Intelligence

**Business logic:** When a DSO (Aspen Dental, Heartland Dental, Pacific Dental Services) opens a new location within 5 miles of an independent practice, that independent practice owner enters fight-or-flight mode. They need to modernize to compete with a corporate chain. This is an emotional buying trigger — fear of losing patients — and the exact moment to pitch a technology edge.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `dso_expansion_monitor` | Monitors Google Maps and commercial real estate listings for new DSO location openings. Cross-references against the existing practice database to find independent practices within a 5-mile radius. Flags those independents as urgency leads. | Google Places API new business monitoring by chain name + category. Tracks: Aspen Dental, Heartland Dental, Pacific Dental Services, Bright Now! Dental, Western Dental, Smile Brands. |
| `saturation_zip_analyzer` | Calculates DSO penetration percentage per ZIP code using accumulated DSO expansion data. Independent practices in high-penetration zones (>30% DSO share) receive a fear-of-competition urgency multiplier in Lead Scoring. Reuses existing data — no new source required. | Aggregates output from `dso_expansion_monitor` + NPPES practice counts per ZIP. Pure computation on existing DB data. Runs weekly. |

---

## Strategy 21 — Dark Social & Community Intelligence

**Business logic:** The most valuable dental conversations happen in places analytics cannot track — private Facebook groups, WhatsApp chains between dental school classmates, local dental society email threads. We cannot read these directly. But we can engineer our way into them: monitor branded search spikes, track public community mentions, and create content designed to be shared privately.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `branded_search_spike_monitor` | Monitors Google Search Console for spikes in branded query volume (people Googling "Sova AI", "Sova receptionist"). A spike with no corresponding paid campaign = dark social sharing happening somewhere. Cross-references event calendar to identify the source community. | Google Search Console API (official, free). Reads branded query impressions and clicks daily. Flags anomaly days for manual investigation. |
| `dental_community_mention_tracker` | Monitors public dental Facebook groups, LinkedIn groups, and Reddit threads for any mention of Sova or competitor products. Surfaces discussions where the product is being recommended or criticized by peers — peer recommendation is the strongest buying signal in this industry. | Facebook Graph API (public groups) + Reddit API + LinkedIn API. Keyword monitoring for brand names, competitor names, and category terms ("AI receptionist", "answering service"). |
| `practice_advisor_network_mapper` | Tracks CPAs, dental-specific practice-transition attorneys, and dental consultants (Dental Intel advisors, Ekwa Marketing consultants, large dental coaching firms like Spear Education or Dental Nachos) who repeatedly appear around practice sales, ownership changes, and expansions. These advisors influence tech vendor decisions during transitions — a practice-transition attorney who knows Sova recommends it to every buyer they serve. | HTTP fetch on advisory firm websites for client lists and case studies. Conference sponsor pages where advisors sponsor dental events. NLP on broker listing text for "represented by" and "advised by" mentions. LinkedIn public posts from known advisors. Builds a warm introduction graph distinct from clinical referrals. |
| `peer_influence_mapper` | Tracks who is recommending specific tools or complaining about competitors in Dentaltown, Reddit, and public Facebook groups. Identifies local community influencers — dentists who get heavily replied to, whose recommendations others act on. These are not just leads, they are referral channels. A dentist who has already recommended Sova to peers is worth more than 10 cold prospects. | Graph analysis on existing opinion platform scout output. Tracks reply-to relationships, quote patterns, and sentiment on brand mentions. Runs weekly. Outputs influencer score + connection graph. |
| `referral_network_mapper` | Builds a graph of who refers to whom across the dental ecosystem. Extracts links from practice websites (referring specialist pages), sponsor lists from conferences and CE events, webinar collaborator lists, and podcast guest networks. Labs, specialists, brokers, and consultants influence tech buying. This maps those routes before any cold outreach. | HTTP fetch + BeautifulSoup on practice referral pages + conference sponsor pages + podcast episode notes. Graph construction using NetworkX or similar. Outputs: top-influence paths into each unclosed account. |

---

## Strategy 22 — Patent & Trademark Monitoring

**Business logic:** A competitor filing a new patent reveals what they are building 12–18 months before launch. A trademark filing signals a new product line or market expansion before any press release. Both are actionable intelligence — accelerate your own roadmap or get ahead in the market they are about to enter.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `uspto_trademark_monitor` | Monitors USPTO trademark filings by competitor companies. When a competitor files a new trademark in the "telephone answering service" or "virtual receptionist" class, alerts immediately. | USPTO TESS system (`tmsearch.uspto.gov`). Free public access. Weekly polling by assignee name (competitor company names). |
| `patent_filing_monitor` | Monitors Google Patents and USPTO for new patent applications filed by competitors in voice AI, automated scheduling, and dental-specific communication categories. | Google Patents RSS feed or USPTO PatFT/AppFT bulk data. Filter by assignee name + IPC classification codes for speech recognition and telephony. |

---

## Strategy 23 — Podcast & Webinar Intelligence

**Business logic:** Dental practice owners who register for industry webinars and listen to dental business podcasts are self-identifying as operators actively looking to improve their practice. This is high-intent, self-selected behavior. Monitoring which topics get traction and which practice owners are public guests surfaces both market intelligence and premium leads.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `dental_podcast_monitor` | Monitors major dental business podcasts for episode topics, guest names, and content themes. Practice owners who appear as guests are opinion leaders in their communities — premium targets for outreach and partnership. | RSS feed scraping of: The Dental Marketer, Dentist Freedom Blueprint, Dental Practice Heroes, Practice Growth HQ, The Thriving Dentist. |
| `dental_webinar_calendar_scraper` | Scrapes webinar calendars from Patterson Dental, Henry Schein Education, Dental Economics, and ADA CE Online for upcoming events. Surfaces sponsorship opportunities and identifies which topics the ICP is actively learning about. | HTTP fetch + BeautifulSoup on public webinar listing pages. |

---

## Strategy 24 — Phone System Lease Cycle Tracking

**Business logic:** Most dental practice phone systems (Avaya, RingCentral, 8x8, AT&T Business) are sold on 3–5 year lease contracts. When a lease approaches renewal, the practice is actively evaluating alternatives. If we can estimate when a practice's phone system was installed, we can predict their renewal window and time outreach to arrive exactly when they are open to switching.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `phone_system_age_estimator` | Infers the approximate age of a practice's current phone system from observable signals: job postings mentioning specific phone platforms, LinkedIn employee skill endorsements for VoIP tools, website mentions of specific providers. Flags practices likely approaching a renewal window. | Text extraction from job postings (already collected) + Proxycurl LinkedIn skills data + website crawl. Heuristic scoring on signal recency vs. expected lease length. |

---

## Strategy 25 — PMS Vendor Pain Monitoring

**Business logic:** When a dental practice complains publicly about their practice management software (Dentrix, Eaglesoft, Open Dental), they are primed to reconsider their entire tech stack. Dissatisfaction with one system creates an "everything is up for review" mindset — the lowest-resistance window to introduce new tools. These complaints appear on public vendor support forums before they appear anywhere else.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `pms_vendor_support_forum_sentinel` | Monitors public support forums for major PMS vendors (Dentrix, Eaglesoft, Open Dental, Curve Dental) for threads mentioning scheduling failures, crashes, or workflow complaints. Extracts any practice names or user handles mentioned. Cross-references against the practice database. | HTTP fetch + BeautifulSoup on public forum pages. Keyword filter: "can't schedule", "keeps crashing", "data loss", "support is useless", "looking for alternative". Open Dental forums are fully public. |

---

## Strategy 26 — Contextual Trigger Monitoring

**Business logic:** External events outside a practice's control — severe weather, local disasters, public health events — force sudden increases in unanswered calls and after-hours demand. These moments create immediate, visceral pain. Outreach timed to these events with messaging like "your AI answered every call during the storm" is psychologically resonant because it speaks to a problem the practice just experienced.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `weather_disruption_monitor` | Monitors NOAA severe weather alerts (hurricanes, snowstorms, ice events) and cross-references storm paths against practice ZIP codes from the practice database. Flags affected practices for time-sensitive outreach in the 48-hour window after the event. | NOAA Weather API (`api.weather.gov`). Free, official. ZIP code geospatial lookup against practice database. Storm severity filter: Winter Storm Warning, Hurricane Warning, Ice Storm Warning. |

---

## Strategy 27 — Continuing Education Monitoring

**Business logic:** A dental practice owner or office manager who voluntarily enrols in a continuing education course on "practice automation", "technology adoption", or "business growth" is self-identifying as growth-minded and actively seeking to improve. This is high-intent, self-selected behaviour with no sales pressure involved — the learner is already in a change mindset when we reach them.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `ce_enrollment_monitor` | Monitors CE course calendars and topic listings from ADA CE Online, dental society CE programs, and Dental Economics webinar series. Identifies courses covering operations, technology, or business management. Scrapes publicly listed attendee or registration data where available. Feeds the CE Engagement Tracker fragment. | HTTP fetch + BeautifulSoup on ADA CE Online, local dental society event pages, Dental Economics webinar calendar. RSS feeds where available. Keyword filter on course titles and descriptions. |

---

## Strategy 28 — Local Business Journal & Chamber Monitoring

**Business logic:** Regional business journals, local newspapers, and chamber of commerce feeds publish practice sales, new openings, expansions, and owner retirements weeks or months before national databases update. A dentist retirement announcement in a local biz journal is a lead 60–90 days ahead of when it shows up in NPPES or broker listings. New business chamber registrations often predate Google Maps. These sources give us the earliest possible alert.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `local_biz_journal_monitor` | Monitors regional bizjournals.com editions, local chamber of commerce new-member feeds, and local newspaper business sections for dental practice announcements: new openings, ownership changes, retirements, expansions. Extracts practice names and cross-references against the NPPES database. | RSS feeds on BizJournals.com regional editions (free). HTTP fetch on chamber new-member pages (varies by city). NLP entity extraction for dental/medical + cross-ref NPPES. Priority: top 30 US metros by dental practice density. |

---

## Strategy 29 — Staff Burnout & Operational Stress Signals

**Business logic:** The clearest purchase signal is not an open job posting — it is the language used around that job posting and in reviews. Words like "revolving door," "understaffed," "burnout," and "can't keep a receptionist" are unprompted confessions of the exact pain we solve. Aggregating this language across job boards, review platforms, and forums surfaces practices at the breaking point. They are not looking for AI — they are desperate enough to try anything.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `dental_staffing_agency_monitor` | Monitors dental staffing agencies (Dental Temps of America, Dental Staffers, DentalPost Temp, regional temp agencies) for spikes in front desk temp demand in a metro area. When staffing agencies in a market are flooded with dental front desk requests, the structural pain is not one practice — it is the entire local market. Every independent practice in that metro is under staffing pressure simultaneously. Metro-level signal that amplifies individual practice signals. | HTTP fetch + BeautifulSoup on staffing agency job board pages. Filter by metro area and role type (front desk, patient coordinator, receptionist). Tracks listing volume week-over-week per metro. Outputs metro-level staffing stress index. |
| `staff_burnout_aggregator` | Runs NLP across all existing job posting collectors and review platform data to find burnout and chronic turnover language at the practice level. Extracts: job posting velocity per practice (same role re-posted 3+ times in 12 months), burnout keywords in job descriptions ("high-energy environment," "fast-paced," "we've had recent turnover"), and similar signals in Glassdoor and Google reviews. Outputs a per-practice burnout risk score. | Runs on top of existing job collector and review collector output tables. NLP using spaCy or LLM classifier. No new data sources — pure signal extraction from data already being collected. |
| `patient_access_complaint_velocity` | Detects sudden spikes in review language specifically about phone access, voicemail, and scheduling friction. "We couldn't get through," "always goes to voicemail," "scheduling is a nightmare" appearing multiple times in a 30-day window = the phones just became a crisis, not background noise. | Time-series analysis on review collector output. Sliding 30-day window. Fires an alert when complaint rate exceeds baseline × 3. Feeds the Access Failure Index fragment. |

---

## Strategy 30 — Access & Availability Intelligence

**Business logic:** The best signal a practice needs an AI receptionist is evidence that their front door is broken right now. Secret-shopper test calls to practices reveal pickup failures, voicemail outcomes, and after-hours black holes directly — no inference required. Availability scanners detect unused chair time (recall leakage) and demand-softness banners ("new patient specials"). These are first-party operational signals that no third-party data source can replicate and that score higher than any resume review of a dental job posting.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `live_answer_audit` | Places automated test calls to a sample of target practices during normal business hours. Records: pickup speed (seconds), whether a human answered vs. voicemail, hold time if transferred, whether an appointment was offered. Practices that consistently miss calls or route to voicemail during the workday are prime candidates. | Twilio programmable voice + call recording API. Calls a practice once per quarter from a non-Sova number. Compliant test call — no false identity. Extracts outcomes via speech-to-text. High signal, low cost per call. |
| `after_hours_coverage_audit` | Places test calls to target practices on Friday evenings, Saturdays, and after 6 PM on weekdays. Detects: voicemail only, answering service (human or AI), emergency routing. Practices with no after-hours coverage at all are losing emergency and urgent-care callers every weekend — pure revenue leakage. | Same Twilio infrastructure as `live_answer_audit`. Separate call schedule targeting off-hours windows. Runs monthly on high-priority practices. |
| `same_day_availability_scanner` | Searches online booking widgets, practice websites, and Zocdoc listings for the number of same-day or next-day appointment slots available. Excess near-term availability = recall leakage and reactivation need. A practice with 8 open slots tomorrow is losing revenue while their phones go unanswered. | `httpx` + BeautifulSoup targeting scheduling widget APIs and Zocdoc availability. Runs weekly. Combines with `zocdoc_listing_detector` output. |
| `new_patient_promo_detector` | Scans practice homepage hero banners, pop-ups, and promo pages for "new patient special," "welcome offer," and emergency/urgent-care messaging. Practices running these promotions are in demand-softness mode — they need more new patients, which means their phone conversion rate is the highest-value problem to fix. | `httpx` + BeautifulSoup. Image alt-text and visible text analysis. Runs weekly on the practice's homepage URL. Easy build — high signal. |
| `contact_friction_scorer` | Scores the total contact friction of each practice's web presence across both desktop and mobile. Factors scored: is there a click-to-call button visible above the fold? Are business hours listed on the homepage? Is there a contact form, live chat, or text option? Is the phone number in the page header or buried in a footer? Is there any online booking CTA? Outputs a friction score (0 = frictionless, 100 = completely inaccessible). High friction = the practice is losing patients before they ever pick up the phone. | `httpx` + BeautifulSoup. Distinct from `mobile_conversion_friction_scanner` which focuses on mobile performance — this scores overall contact accessibility across the full site. Runs quarterly per practice. |
| `mobile_conversion_friction_scanner` | Crawls each practice's website from a mobile user-agent. Detects: absence of a click-to-call button, slow mobile load time (Lighthouse score <50), broken forms, no online booking CTA visible above the fold. A practice that is hard to reach from a phone is losing the most valuable new-patient traffic in existence. | Lighthouse API (Node.js, free) + mobile BeautifulSoup crawl for CTA detection. Runs quarterly per practice. Flags any mobile score below 50 or missing click-to-call. |

---

## Strategy 31 — Staff Transition Intelligence

**Business logic:** When a key person leaves or arrives at a practice, the entire system is temporarily fluid. An office manager departure means whoever replaces them has no loyalty to current tools — they will recommend what they already know or what is easiest to learn. A new associate joining means the schedule needs to expand, the phones need to handle more volume, and someone is actively thinking about systems. The 30–90 day window after a staff transition is when practices are most open to changing vendors.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `office_manager_turnover_detector` | Monitors practice staff pages and LinkedIn for office manager or practice administrator departures. When the "About Us" page loses a known OM and gains a new name — or shows no OM at all — the practice is in a workflow re-evaluation window. | Diffs staff/team pages weekly using stored HTML snapshots. Proxycurl API for LinkedIn job title changes at known practice contacts. Flags any OM-role change at monitored practices. |
| `associate_arrival_detector` | Tracks practice provider bio pages, board rosters, and staff pages for new clinician names. A new associate joining = schedule needs to fill fast = volume pressure on the front desk = phones need to handle more calls immediately. | Diffs provider-bio pages weekly against stored snapshots. Cross-references against state dental board new-licensee data from `dental_school_new_licensee_monitor`. Flags additions, not just removals. |
| `answering_service_vendor_loss_monitor` | Detects practices that recently switched away from or cancelled a legacy telephone answering service (Ruby Receptionist, PATLive, Specialty Answering Service, MAP Communications). Signals include: voicemail greeting change to generic, job posting mentioning "phone coverage gap," Glassdoor or Indeed reviews mentioning "we used to have an answering service," or social post about front desk challenges. | NLP on job descriptions (existing collectors) for answering-service keywords. Periodic test calls detecting greeting changes. Review mining for vendor mention patterns. High build complexity — worth it for the precise switching intent. |

---

## Strategy 32 — First-Party Intent Systems

**Business logic:** The highest-quality lead signal is a prospect who has already interacted with Sova directly. A dental office manager who called our demo line, clicked our pricing page, or responded to a direct mail piece is self-identifying as in-market right now. These signals are not inferred — they are observed. Building a system that captures and matches first-party intent to our practice database converts Sova's own infrastructure into a lead generation engine.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `first_party_voice_demo_tracker` | Sova maintains a public, always-on AI demo line that any practice can call to experience the product. When a call comes in, the system captures the calling number, resolves it against the practice database (via NPPES phone match), and fires an immediate high-intent lead alert. A practice calling our demo line is the warmest possible prospect — they are self-persuading in real time. | Twilio Programmable Voice for demo line. Reverse phone lookup against the NPPES phone number database. Fires a webhook to the outreach queue with practice identity + call timestamp. Easy build, exceptionally high signal. |
| `lost_deal_reason_miner` | Mines CRM notes, call recordings (Gong or similar), support tickets, and closed-lost reason fields for patterns in why prospects did not convert. Objection patterns (pricing, implementation fear, staff resistance, integration concern) are predictive of which current prospects will need specific handling. Converts lost deals into a training signal for the outreach engine. | Structured CRM data export + LLM classification of free-text notes. Outputs: top objection taxonomy, which objections correlate with eventual conversion vs. permanent loss, and which practice types surface each objection most. Runs monthly. |
| `direct_mail_response_tracker` | Sends physical dimensional mail (not generic flyers — a personalised letter tied to a specific signal we detected) to the highest-scored practices. Each piece contains a practice-specific QR code and vanity URL tied to the practice's account ID in the database. When a practice scans the QR or visits the URL, it registers as a first-party intent event — offline-to-online intent capture. | QR code generation tied to practice IDs. UTM-tagged vanity URLs redirecting to a landing page that resolves identity. Sent only to HOT-tier practices. Combines the physical attention advantage of mail with digital intent capture. |

---

## Strategy 33 — X/Twitter Intelligence *(Planned — v2)*

> **Note:** This strategy is planned for a future version. X/Twitter data access has changed significantly since the 2023 API restructure — free tier is severely rate-limited, and full access requires a paid Enterprise plan. Build this after v1 is stable and generating revenue to fund the API cost. The signal is real; the timing is not v1.

**Business logic:** X/Twitter is where dental industry thought leaders, DSO executives, and dental tech vendors announce things before they hit press releases. Competitors signal product launches, funding, and positioning shifts on X. A dental practice owner venting about their phones on X at 11pm is showing you live, unfiltered pain. This platform has higher signal density than LinkedIn for spontaneous, real-time opinion — but lower density of verified practice identities. Worth monitoring for trends and competitor moves even if individual lead identification is harder.

| Sub-fragment | What It Does | How It Does It |
|---|---|---|
| `x_competitor_tracker` | Monitors all competitor X/Twitter accounts for new posts, replies, and engagement patterns. Tracks: announcement cadence, messaging themes, which posts get significant RT/like traction, and @mentions of competitor accounts (who is talking about them). A competitor's most-engaged tweet is a window into what messaging is resonating with the dental market. | X/Twitter API v2 (official). Free tier limited — paid Basic tier ($100/mo) needed for meaningful volume. Targets: known competitor account handles. Tracks post metrics + quoted/replied-to threads. |
| `x_industry_monitor` | Monitors X for dental practice owner discussions, AI receptionist mentions, and front desk pain posts. Real-time, unfiltered ICP sentiment. A practice owner tweeting "our front desk just quit again" at 10pm is a live buying signal. | X/Twitter API v2. Keyword and hashtag tracking: `#dentalpractice`, `#dentaloffice`, "dental receptionist", "answering service dental", competitor brand names. LLM classification of Opportunity / Content / Noise. |

---

---

## Fragments

### Sub-fragment vs Fragment — The Core Distinction

| | Sub-fragment | Fragment |
|---|---|---|
| **Job** | Collects raw data from one specific source | Composes multiple sub-fragments, interprets combined data, answers one business question |
| **Output** | Raw rows — job postings, NPI records, reviews, ad creatives | Structured intelligence — a score, a ranking, a report, a content draft |
| **Has intelligence?** | No. Fetches and stores. Does not interpret. | Yes. Runs logic, scoring, LLM calls, comparisons across sources. |
| **Awareness of others?** | None. Fully independent. | Explicit. Reads from one or more sub-fragment output tables. |
| **Triggered by** | Schedule (every N hours) | Schedule OR completion of its sub-fragments |
| **Analogy** | A sensor | A brain region that processes what the sensors send |
| **Example** | `facebook_ads_library_collector` — fetches competitor ads and stores them | `Competitive Leaderboard` — reads ad data + follower counts + client estimates and produces a ranked table |

**The rule in one sentence:** Sub-fragments produce data. Fragments produce intelligence.

---

### Fragment 1 — Fit Score

**Business question:** Does this practice match our Ideal Customer Profile?

**Sub-fragments consumed:**
- `nppes_collector` — practice exists, specialty, solo vs. group, location
- `website_crawler` + `booking_tech_detector` — automation gap confirmed
- `pms_signal_extractor` — legacy PMS detected from job postings
- `zocdoc_listing_detector` — online booking absent
- `healthgrades_collector` + `yelp_collector` — profile claimed or unclaimed (tech engagement signal)
- `cms_enrollment_collector` — Medicare enrollment date (practice age proxy)

**Output:** Fit score (0–100) per practice + a structured profile of their current tech posture. Written to the `sova_fit_score` table. Feeds into the Lead Score fragment.

---

### Fragment 2 — Intent Score

**Business question:** Is this practice experiencing the pain we solve right now?

**Sub-fragments consumed:**
- `dentalpost_collector`, `indeed_collector`, `linkedin_jobs_collector`, `ihiredental_collector` — active front desk hiring
- `google_places_collector`, `yelp_collector` — phone friction keywords in reviews, stagnant review velocity
- `glassdoor_collector` — chronic turnover signals in employee reviews
- `reddit_scout`, `quora_scout`, `dentaltown_forum_scout` — candid pain signals in community posts
- `champion_job_change_tracker` — warm contact moved to this practice from an existing client

**Output:** Intent score (0–100) per practice + list of signals that fired with source evidence. Written to `sova_intent_score`. Feeds into the Lead Score fragment.

---

### Fragment 3 — Lead Score

**Business question:** How hot is this lead overall — act now, nurture, or ignore?

**Fragment inputs:**
- Fit Score (Fragment 1)
- Intent Score (Fragment 2)
- Access Failure Index (Fragment 22)
- Transition Window Detector (Fragment 23)
- Staff Churn & Operational Stability Predictor (Fragment 17)
- Practice Growth Predictor (Fragment 11)
- All lifecycle event sub-fragments: `npi_new_registration_monitor`, `dental_broker_listing_monitor`, `dso_expansion_monitor`, `sba_loan_monitor`, `building_permit_monitor`, `multi_location_expansion_detector`

**Scoring formula (research-validated):**

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

| Component | What feeds it | Weight |
|---|---|---|
| Fit | Fragment 1 output | 20% |
| Operational Pain | Fragment 2 + Access Failure Index + Staff Churn score | 25% |
| Timing | Transition Window Detector + lifecycle sub-fragment signals | 20% |
| First-Party Intent | `website_visitor_deanonymizer` + `first_party_voice_demo_tracker` + `branded_search_spike_monitor` | 15% |
| Technographic Opportunity | Displacement Intelligence Engine output | 10% |
| Human Route | `champion_job_change_tracker` + Buying Committee Intelligence | 5% |
| Geography | DSO proximity + BLS staffing heatmap | 5% |

**Bounded modifiers** (added to composite score — not multipliers):

| Event | Modifier |
|---|---|
| Champion moved from existing client | +8 |
| Ownership transfer / practice sold | +6 |
| New practice opening or second location | +5 |
| Live-answer failure detected + after-hours gap confirmed | +4 |
| DSO opened within 5 miles | +3 |
| First-party demo-line call | +3 |
| Likely inactive / dead phone / stale web presence | −6 |
| Clear incumbent stack with no pain evidence | −4 |
| Enterprise/DSO central procurement (not current sales motion) | −4 |
| Specialty or scale mismatch | −3 |

**Signal decay:** Each signal has a half-life. A job posting that fired 60 days ago is not the same as one that fired today. Score is recalculated daily using:

```
Decayed Value = Raw Value × e^(−ln(2) × days_since_signal / half_life)
```

| Signal | Half-life |
|---|---|
| Demo-line call / identified website visit | 7 days |
| Active front-desk job posting | 14 days |
| Review complaint spike / live-answer test failure | 21 days |
| Branded search spike / webinar attendance | 21 days |
| Ownership transfer / broker listing sold | 60 days |
| New NPI / SBA loan / new practice opening | 90 days |
| Technographic gap (no modern booking tool) | 180 days |

**HOT qualification — all conditions must be true:**

| Condition | Threshold |
|---|---|
| Composite score | **78+** |
| Fit score | **65+** |
| Pain or timing signal | At least **one major pain signal** AND **one timing or intent signal** |
| Recency | At least one key signal in the last **30 days** |
| Reachability | Owner or office manager contact identified |
| No major disqualifier | Not obviously closed, centralised, or out of segment |

**Output per lead:**
- Composite score (0–100) with component breakdown
- Priority tier: `HOT` (act within 48h) / `WARM` (nurture) / `COLD` (monitor)
- Signal evidence: which signals fired, when, and their current decayed weight
- Recommended action with reason: "Call — live-answer test failed twice this month + front desk role re-posted 3× in 90 days"

---

### Fragment 4 — Competitive Leaderboard

**Business question:** Where does Sova rank against every competitor across every measurable dimension right now?

**Sub-fragments consumed:**
- `facebook_ads_library_collector` — active ad count, estimated spend range, run duration
- `linkedin_api_collector` — competitor follower count, employee count, growth rate
- `facebook_api_collector` — competitor page followers, post frequency, engagement
- `competitor_client_scout` — named clients from case studies and testimonials
- `crunchbase_monitor` — funding raised, investor count
- `competitor_jobs_tracker` — headcount direction
- `competitor_product_monitor` — feature count, pricing tiers, positioning language
- `g2_intent_monitor` — G2/Capterra review count and star rating

**Dimensions tracked per company (including Sova):**

| Dimension | How measured |
|---|---|
| Estimated client locations | Named clients × average locations per client |
| Online following | LinkedIn + Facebook combined follower count |
| Ad activity | Active ad count + estimated monthly spend bracket |
| Content velocity | Posts per week across LinkedIn + Facebook |
| Funding raised | Total from Crunchbase |
| Employee count | LinkedIn headcount |
| Feature breadth | Feature list length from product page |
| Review score | G2/Capterra star rating + review count |
| Sova rank | Position on each dimension vs. field |

**Output:** A ranked leaderboard table per dimension. Updated weekly. Stored in `sova_competitive_leaderboard`. Surfaced as a dashboard view — where we lead, where we trail, and by how much.

---

### Fragment 5 — Competitive Intelligence Report

**Business question:** What did each competitor do this week — new ads, hires, features, press, client wins?

**Sub-fragments consumed:**
- `facebook_ads_library_collector` — new ads launched, paused ads
- `competitor_jobs_tracker` — new role postings
- `competitor_product_monitor` — pricing or feature page changes
- `competitor_pr_monitor` — press mentions
- `crunchbase_monitor` — funding events
- `patent_filing_monitor` + `uspto_trademark_monitor` — IP filings
- `competitor_client_scout` — new case studies published

**Output:** Weekly intelligence brief per competitor. Format: what changed this week, what it signals strategically, what Sova should do in response. Written to `sova_competitive_brief`. Example entry: "Competitor X paused all Facebook ads this week after running 14 active campaigns last week — possible budget cut or campaign reset. Opportunity to increase our own ad spend in their target geographies."

---

### Fragment 6 — Market Intelligence Report

**Business question:** What is happening in the dental and voice AI market this week that we need to know about?

**Sub-fragments consumed:**
- `google_news_collector` — industry news
- `google_trends_monitor` — search volume shifts on key terms
- `rss_feed_monitor` — trade publication articles
- `newsletter_classifier` — content-classified newsletter items
- `beckers_dental_review_scraper` — DSO acquisition and deal news
- `dental_podcast_monitor` — trending topics in dental business podcasts
- `reddit_scout` + `dentaltown_forum_scout` — community discussions and emerging pain points

**Output:** Weekly market briefing: top industry stories, trending search terms, regulatory developments, DSO consolidation activity, and emerging pain points being discussed in the practitioner community. Written to `sova_market_brief`.

---

### Fragment 7 — Client Health Monitor

**Business question:** How are our existing client locations doing — who is at risk of churning, and who is ready for an upsell?

**Sub-fragments consumed:**
- `google_places_collector` — review velocity and sentiment for our own client practices (improving = product working, declining = at-risk signal)
- `champion_job_change_tracker` — key contacts leaving our client practices
- `linkedin_api_collector` — client practice employee count trends (shrinking = financial stress = churn risk)
- `dso_expansion_monitor` — DSO opened near a client (potential acquisition = contract risk or re-sell)
- `dental_broker_listing_monitor` — any of our clients listed for sale (ownership change = re-sell opportunity or early churn)
- `npi_new_registration_monitor` — client practice opening a new location (upsell opportunity)

**Output per client location:**
- Health score (0–100)
- Flag type: `AT_RISK` / `STABLE` / `GROWTH_OPPORTUNITY`
- Reason: "Office manager left 3 weeks ago — relationship at risk" or "Practice just registered a second NPI — pitch additional location"

---

### Fragment 8 — Outreach Intelligence Brief

**Business question:** For a specific HOT lead, what is everything we know — and what should the outreach say?

**Sub-fragments consumed:** All relevant sub-fragment data for a single practice: job postings, reviews, tech stack, contact info, location, practice size, signals fired, proximity to DSOs, LinkedIn profiles of owner and office manager.

**Output per HOT lead:**

| Field | Content |
|---|---|
| Practice summary | Name, location, specialty, size, years in operation |
| Why they are hot | Which signals fired, with evidence snippets and dates |
| Recommended opener | One personalized sentence tied to the specific signal |
| Decision-maker | Owner name, office manager name |
| Contact channels | Email (Hunter.io), LinkedIn profile, phone (NPPES) |
| Suggested channel | Email / LinkedIn DM / phone (based on what's available) |
| Urgency reason | How long this window is likely to stay open |

This is the bridge between intelligence collection and outreach execution. The outreach agent (built separately, later) takes this brief and drafts the actual message.

---

### Fragment 9 — Regulatory & Compliance Watch *(medium priority)*

**Business question:** Are there regulatory changes — HIPAA, CMS, FCC, state dental boards — that affect our product or our pitch?

**Sub-fragments consumed:**
- `rss_feed_monitor` (CMS.gov, HIPAA Journal, FCC news feeds)
- `cms_enrollment_collector` — enrollment rule changes
- `google_news_collector` (regulatory keyword filter)
- `dental_specialty_association_scraper` — association policy updates

**Output:** Flagged regulatory items with: what changed, who it affects, and whether it changes our pitch or product requirements. Example: "New FCC rule on AI-generated calls requires disclosure — update our onboarding script and use as a trust differentiator vs. competitors who may not be compliant."

---

### Fragment 10 — Content Generation *(non-critical — build last)*

**Business question:** What should we post on LinkedIn and Facebook this week, and what blog post can we publish this month?

**Sub-fragments consumed:**
- `newsletter_classifier` output (content-classified items only)
- Market Intelligence Report output
- `google_trends_monitor` — what people are currently searching for
- `reddit_scout` + `dentaltown_forum_scout` — questions the community is actively asking

**Output:**
- 3–5 short-form post drafts (LinkedIn/Facebook) per week — ready for human review before publishing
- 1 long-form blog post draft per month based on aggregate signal data
- All output goes into a review queue — never auto-publishes without explicit approval

**Note:** This fragment depends on LLM calls for generation (not just classification). Non-critical until the data pipeline is stable and producing reliable input.

---

### Fragment 11 — Practice Growth Predictor

**Business question:** Which practices are on a growth trajectory right now and therefore likely to have budget and willingness to invest in new technology?

**Sub-fragments consumed:**
- `google_places_collector` — rising review count and velocity (more patients = growth)
- `yelp_collector` — review volume trend
- `insurance_plan_change_monitor` — joining new networks = volume incoming
- `npi_new_registration_monitor` — practice registering a new NPI = opening a second location
- `dso_expansion_monitor` — DSO pressure nearby = competitive urgency
- `clinic_hours_change_monitor` — extending hours = volume growth
- `saturation_zip_analyzer` — operating in a high-competition zone = motivated to differentiate

**Output:** Growth score (0–100) per practice. Practices in active growth phase are prioritised in Lead Scoring — they have budget and urgency. Written to `sova_growth_score`.

---

### Fragment 12 — Competitive Churn Risk Analyzer

**Business question:** Which practices currently using a competitor's product are most likely to switch to Sova?

**Sub-fragments consumed:**
- `competitor_client_scout` — identifies named competitor clients
- `glassdoor_collector` — employee dissatisfaction at competitor client practices
- `reddit_scout` + `dentaltown_forum_scout` — public complaints about specific competitor products
- `g2_intent_monitor` — competitor clients browsing alternatives on G2
- `competitor_product_monitor` — competitor pricing increases or feature removals
- `pms_vendor_support_forum_sentinel` — dissatisfaction with connected PMS that competitor integrates with

**Output:** Churn risk index per competitor client. High churn risk + known contact = competitive displacement outreach brief generated automatically. Output includes suggested talking points: "We noticed [Competitor X] changed their pricing — here's what Sova offers at that tier."

---

### Fragment 13 — Relocation & Renovation Detector

**Business question:** Which practices are physically moving or renovating — creating a guaranteed system-rebuild moment?

**Sub-fragments consumed:**
- `business_license_monitor` — new dental LLC filing at a new address
- `building_permit_monitor` — commercial renovation permit for dental office
- `commercial_real_estate_scout` — new dental office lease on LoopNet
- `dental_broker_listing_monitor` — practice sale closed = new ownership at new or same address
- `cms_enrollment_collector` — address change in Medicare enrollment records

**Output:** Ranked list of practices likely relocating or renovating, with estimated move-in window and recommended outreach timing. A practice mid-renovation is building their systems list — that is the window. Written to `sova_relocation_signals`.

---

### Fragment 14 — CE Engagement Tracker

**Business question:** Which dental practice owners and office managers are actively learning about operations and technology — indicating openness to change?

**Sub-fragments consumed:**
- `ce_enrollment_monitor` — actively enrolling in business/tech CE courses
- `dental_podcast_monitor` — listening to or appearing on dental business podcasts
- `dental_webinar_calendar_scraper` — attending Patterson/Henry Schein/ADA webinars on technology
- `dentaltown_forum_scout` — posting questions or engaging in technology discussions
- `newsletter_classifier` — newsletter content on CE topics

**Output:** Learning engagement score per practice contact. High learners go into a nurture track with educational content rather than a direct sales pitch — they self-convert faster when given the right content. Written to `sova_ce_engagement`.

---

### Fragment 15 — Financial Stress Indicator

**Business question:** Which practices are under financial pressure — either at risk of churning as a client or too stressed to buy as a prospect?

**Sub-fragments consumed:**
- `google_places_collector` — declining review score trend
- `glassdoor_collector` — staff complaining about compensation or instability
- `ucc_loan_filings_monitor` — high frequency of new financing statements
- `sba_loan_monitor` — new SBA loan (could be growth OR distress)
- `dental_broker_listing_monitor` — practice listed for sale (owner exiting)
- `insurance_plan_change_monitor` — leaving major insurance networks (revenue loss)
- `champion_job_change_tracker` — multiple key staff departing in short window

**Output:** Financial stress score per practice. For existing clients: flags to customer success for retention intervention. For prospects: deprioritises from outreach or routes to a lower-cost offer track. Reduces wasted sales effort on practices unlikely to close or likely to churn. Written to `sova_financial_stress`.

---

### Fragment 16 — DSO Enterprise Pipeline

**Business question:** Which accounts are DSO-scale targets that require a completely different sales approach — enterprise routing, multi-stakeholder engagement, and portfolio-wide pitch?

**Why this is a separate fragment:** The DSO buyer is psychologically and operationally distinct from an independent practice owner. An independent dentist buys on Perceived Usefulness and peer trust. A DSO executive buys on operational scalability, cross-portfolio standardisation, and labour cost elimination at scale. Mixing these two buyer types into the same Lead Score fragment and the same outreach cadence is a mistake — the DSO gets under-prioritised or receives the wrong message.

**Sub-fragments consumed:**
- `nppes_collector` — group practice NPI registrations, multiple NPIs at same tax ID
- `crunchbase_monitor` — DSO funding rounds, acquisition announcements
- `beckers_dental_review_scraper` — named DSO deal announcements (acquisition closed = new portfolio to standardise)
- `linkedin_api_collector` — company employee count >50 at a dental group = DSO-scale
- `dso_expansion_monitor` — actively opening new locations = scaling fast = needs standardisation now
- `insurance_ppo_density_monitor` — multi-location groups on many PPO networks = enormous admin burden
- `npi_new_registration_monitor` — multiple new NPIs registered under same tax ID in short window = DSO acquiring practices

**DSO-specific scoring dimensions (from Gemini research):**

| Signal | Score |
|---|---|
| Multi-location practice / active DSO affiliation | +20 |
| High operatory count (5+ clinical chairs per location) | +15 |
| Pediatric or orthodontic specialty (high patient turnover) | +10 |
| Rural / underserved geography (chronic staff shortage) | +10 |
| Premium bidirectional PMS integration confirmed | +20 |
| Modern patient engagement software present (NexHealth, Weave) | +15 |
| Active receptionist job posting across multiple locations | +25 |
| Recent DSO acquisition announcement | +20 |
| Legacy/fragmented servers detected | −15 |

**Output:** DSO-tier accounts scored separately from individual practices. Tier A (85+ points) bypasses SDR entirely — routed directly to Senior AE or Enterprise Sales Director with a multi-threaded outreach brief covering CEO, Clinical Director, and Operations Manager simultaneously. Written to `sova_dso_pipeline`.

---

### Fragment 17 — Staff Churn & Operational Stability Predictor

**Business question:** Which practices have chronically unstable front desks — making them both urgent outreach targets and the highest-priority practices to stabilize with automation?

**Sub-fragments consumed:**
- `staff_burnout_aggregator` — burnout language score and job re-post velocity per practice
- `glassdoor_collector` — employee review themes (compensation, chaos, management instability)
- `dentalpost_collector`, `indeed_collector`, `linkedin_jobs_collector` — front desk re-posting cadence
- `patient_access_complaint_velocity` — recent spike in access complaints (downstream of turnover)
- `champion_job_change_tracker` — departing staff from a practice signals instability

**Output:** Churn risk score (0–100) per practice + flagged evidence snippets ("Same front desk role re-posted 4 times in 11 months," "3 Glassdoor reviews mention turnover in last 6 months"). Top recommended outreach angle: "Stabilise your team before the next resignation" rather than "upgrade your technology." Written to `sova_staff_stability`.

---

### Fragment 18 — Displacement Intelligence Engine

**Business question:** Which practices are currently using a competitor or legacy tool — and how easy is it to displace them?

**Sub-fragments consumed:**
- `pms_signal_extractor` — PMS in use, any migration language in job posts
- `pms_migration_detector` — active PMS switch signals
- `booking_tech_detector` — current booking/comms tool embedded on site
- `competitor_client_scout` — practices named on competitor case study pages
- `g2_intent_monitor` — competitor clients browsing alternatives on G2
- `answering_service_vendor_loss_monitor` — practices leaving legacy answering services now
- `competitor_product_monitor` — competitor pricing changes or feature removals

**Output per practice:**
- Current tech stack inferred (PMS, booking tool, answering solution)
- Displacement ease rating: `EASY` (known pain + switching signal) / `MODERATE` (incumbent but no loyalty signal) / `HARD` (positive evidence of satisfaction)
- Specific attack angle: "You're on Dentrix + Ruby Receptionist — here's how Sova layers in with less friction and captures what Ruby misses after hours"

Written to `sova_displacement_targets`. Feeds the Outreach Intelligence Brief.

---

### Fragment 19 — Influence & Network Map

**Business question:** Who can credibly move this account — peer dentist, dental consultant, supplier rep, referring specialist, or lab partner?

**Sub-fragments consumed:**
- `peer_influence_mapper` — local community influencer graph from Reddit/Dentaltown/Facebook
- `referral_network_mapper` — website cross-links, conference sponsor lists, podcast guest networks
- `dental_specialty_association_scraper` — association leadership and active members
- `conference_website_monitor` — speakers and sponsors at major events
- `dental_podcast_monitor` — podcast guests and hosts with community authority

**Output:** For each HOT or WARM account, a ranked list of warm introduction paths:
- "Dentist X is connected to this practice via Dentaltown and spoke at the same ADA session in 2025 — they are a current Sova user"
- "Henry Schein rep covering this territory has introduced us to 3 practices in this ZIP"

Turns cold outreach into warm introductions. Written to `sova_influence_graph`. Feeds the Outreach Intelligence Brief with a "warm route" field.

---

### Fragment 20 — Revenue Rescue Planner

**Business question:** What exact revenue-leak story should we tell this practice — with a specific dollar figure and a named proof point?

**Sub-fragments consumed:**
- `google_places_collector` + `yelp_collector` — phone friction keyword count in reviews
- `live_answer_audit` + `after_hours_coverage_audit` — measured call failures at this practice
- `same_day_availability_scanner` — unused chair time quantified
- `patient_access_complaint_velocity` — complaint spike evidence
- `first_party_voice_demo_tracker` — direct interest signal from the practice
- `lost_deal_reason_miner` — known objection patterns to pre-empt

**Revenue model:** Missed calls in reviews × local new-patient average value × Sova's proven capture rate = estimated monthly revenue leakage. Tailored to this practice's specialty and review volume.

**Output:**
- Estimated monthly revenue leakage at this specific practice (dollar figure with source evidence)
- Before/after projection: "Practices like yours capture an average of $X/month in new-patient revenue within 90 days"
- Recommended objection pre-emption based on lost-deal patterns
- Persona-split pitch angle: Owner version (ROI and practice valuation) vs. Office Manager version (relief from phone chaos)

Written to `sova_revenue_rescue`. This is the highest-converting element of the Outreach Intelligence Brief — it converts abstract product benefits into a number the practice owner can explain to their accountant. Written to `sova_revenue_rescue`.

---

### Fragment 21 — Buying Committee Intelligence

**Business question:** For this lead, who is the economic buyer (the dentist-owner who writes the cheque) vs. the daily user and champion (the office manager who lives with the pain) — and what is the right message for each?

**Sub-fragments consumed:**
- `hunter_enricher` — decision-maker email addresses
- `linkedin_profile_enricher` — job titles, tenure, and role transitions
- `nppes_collector` — solo vs. group classification, owner-operated vs. associate-run
- `glassdoor_collector` + job postings — who feels the pain (OM vs. owner signals)
- `champion_job_change_tracker` — known warm contacts and their current roles

**Stakeholder map output per practice:**

| Role | Who | Key Fear | Right Message |
|---|---|---|---|
| Economic buyer (dentist-owner) | Name, LinkedIn | Practice valuation impact, patient experience risk, DSO competition | "Never miss a new-patient call — protect your practice revenue and your valuation multiple" |
| Daily user / champion (office manager) | Name, LinkedIn | Burnout, hiring chaos, being blamed for missed calls | "Stop the revolving door. Your team focuses on patients in the chair — we handle every call they can't get to" |

Written to `sova_buying_committee`. Feeds directly into the Outreach Intelligence Brief's recommended channel and message sections.

---

### Fragment 22 — Access Failure Index

**Business question:** How badly is this practice leaking patient demand at the front door right now?

**Sub-fragments consumed:**
- `live_answer_audit` — direct call failure rate measured
- `after_hours_coverage_audit` — evening and weekend coverage gaps
- `reputation_shock_detector` — review complaint spike
- `patient_access_complaint_velocity` — review trend for access friction
- `same_day_availability_scanner` — unused chair time
- `google_places_collector` — star rating trend and phone friction keywords
- `staff_burnout_aggregator` — staffing instability at the front desk

**Output:** Access Failure Score (0–100) per practice + evidence summary:
- `CRITICAL` (80+): "Live test call went to voicemail. 5 access complaints in 30 days. No after-hours coverage. 7 open slots tomorrow."
- `HIGH` (60–79): "2 recent access complaints. After-hours gap confirmed."
- `MODERATE` (40–59): "No live test failures but review keywords suggest occasional friction."

This is the most operationally direct fragment in the system. It does not infer pain from hiring signals — it measures it directly. Written to `sova_access_failure`. Feeds the Lead Score fragment as the highest-weight input in the Operational Pain component.

---

### Fragment 23 — Transition Window Detector

**Business question:** Is this practice in an active 30–90 day system reconfiguration period — the window where they will evaluate and adopt new technology?

**Sub-fragments consumed:**
- `npi_new_registration_monitor` — new NPI registered (new practice opening)
- `multi_location_expansion_detector` — second location being added
- `dental_broker_listing_monitor` — practice sold (new owner rebuilding)
- `building_permit_monitor` — renovation in progress
- `sba_loan_monitor` — new SBA loan for expansion
- `office_manager_turnover_detector` — key staff change
- `associate_arrival_detector` — new clinician joining
- `ucc_loan_filings_monitor` — new equipment financing

**Scoring logic:** Any single lifecycle event opens a transition window. Multiple concurrent events = the window is wide open and time-sensitive.

| Event combination | Window urgency |
|---|---|
| Ownership change + new permit | `CRITICAL` — rebuild everything now |
| New associate + OM departure | `HIGH` — workflow is in flux |
| New NPI only | `HIGH` — greenfield setup |
| SBA loan + equipment financing | `MODERATE` — expansion buying cycle |

**Output:** Transition score per practice + estimated window duration + recommended outreach cadence ("Reach out within 7 days — this window closes in approximately 60 days.") Written to `sova_transition_window`. This fragment improves timing more than any other. The same lead scored WARM without transition signals becomes HOT when a window is open.

---

### Fragment 24 — Local Pressure Index

**Business question:** How much competitive pressure is this practice under from its immediate geography right now?

**Why this is a separate fragment:** The Lead Score already has a Geography component, but it is a single weighted input. The Local Pressure Index is a dedicated view of geographic competitive dynamics — useful for territory planning, campaign sequencing, and metro-level outreach timing. When an entire ZIP code heats up (multiple new DSO openings + two new practice registrations + a staffing spike), every independent in that ZIP becomes a higher-priority outreach target simultaneously.

**Sub-fragments consumed:**
- `dso_expansion_monitor` — new DSO locations within 3–5 miles
- `saturation_zip_analyzer` — DSO market share % per ZIP
- `npi_new_registration_monitor` — new practices entering the local market
- `building_permit_monitor` — commercial dental buildouts in the area
- `bls_staffing_heatmap` — metro-level dental staffing shortage index
- `dental_staffing_agency_monitor` — temp agency demand spikes per metro
- `business_license_monitor` — new dental business filings per ZIP

**Output:** Pressure score (0–100) per ZIP code + per-practice urgency multiplier for practices in high-pressure zones. Updated weekly. Visualisable as a geographic heatmap of market tension. Allows Sova to sequence outreach campaigns by territory: "This week, focus on ZIP codes 90210–90214 — three new DSO locations opened and the staffing index hit its highest point this year." Written to `sova_local_pressure`.

---

### Fragment 25 — Trust Vector

**Business question:** For this specific lead, what proof asset will most reduce resistance — and who is the right peer to reference?

**Why this matters:** Dental practice owners buy through trust before they buy through ROI. A cold email with a case study from a practice in a different specialty and state does almost nothing. A message that says "Your study club colleague Dr. Martinez uses Sova at her Pasadena practice and captured 23 new patients in 90 days" closes in one call. The Trust Vector fragment identifies the *best available trust pathway* for each individual lead, ranked by credibility to that specific practice.

**Sub-fragments consumed:**
- `peer_influence_mapper` — local community connections in Dentaltown/Reddit/Facebook
- `referral_network_mapper` — site cross-links and conference co-appearances
- `practice_advisor_network_mapper` — shared CPAs, brokers, or consultants
- `dental_specialty_association_scraper` — shared specialty association membership
- `conference_website_monitor` — shared conference attendance or speaking
- `dental_podcast_monitor` — podcast appearances relevant to this practice's specialty
- `champion_job_change_tracker` — existing Sova contacts connected to this practice

**Proof angle taxonomy:**

| Proof type | When it's strongest | Example |
|---|---|---|
| **Peer** | Practice owner knows a current Sova client | "Dr. X in your study club has been on Sova for 8 months" |
| **Specialty** | Same specialty type as a named case study | "We work with 14 orthodontic practices in the Southwest" |
| **Operational** | Review friction and phone pain matches a published story | "A practice matching your profile recovered $4,200/month in new-patient revenue" |
| **Geographic** | Same metro, relatable context | "Three practices in your ZIP code are already on Sova" |
| **Advisor** | Shared CPA or broker who can vouch | "Your practice broker at AFTCO has referred 6 practices to us" |

**Output per lead:** Ranked list of trust pathways with strength score + suggested proof asset to lead with in outreach. Feeds directly into the Outreach Intelligence Brief — replaces generic "here's a case study" with "here's the most credible thing we can say to this specific person." Written to `sova_trust_vector`.

---

### Fragment 26 — ICP Accuracy & Signal Calibration Monitor

**Business question:** Is our scoring model still working — and which signals have drifted since we last tuned it?

**Why this exists:** Every other fragment assumes the scoring weights are correct. They won't be after 6 months. A hiring signal that strongly predicted a win in Q1 may be weak by Q3 if the market shifts. Without a feedback loop from real outcomes back into the model, the Lead Score becomes confidently wrong. This fragment is the self-improvement mechanism.

**Inputs consumed:**
- CRM win/loss data — which HOT leads converted, which didn't
- Signal log — which sub-fragment signals fired for each won/lost lead
- Lead Score history — what the composite score was at time of outreach
- Time-to-close data — how long HOT leads actually took to convert

**What it computes:**
- Signal accuracy per sub-fragment: does this signal actually predict a win, or just appear to?
- Weight drift: which scoring components are over- or under-weighted vs. actual win-rate data?
- False-positive rate: what percentage of HOT leads are not converting — and what signals they share
- HOT threshold calibration: is 78 still the right threshold based on real outcomes?

**Output:** Monthly calibration report with specific weight adjustment recommendations. Example: "`live_answer_audit` has a 71% win-rate correlation vs. its current 15% weight in Operational Pain — consider elevating. `google_trends_monitor` shows near-zero predictive correlation — consider removing from scoring." Written to `sova_model_calibration`. Does not auto-adjust weights — surfaces recommendations for deliberate human review before any change is applied.

---

### Fragment 27 — Churn Early Warning System

**Business question:** Which existing client practices are in the 30–60 day window before churn — when intervention still works?

**Why this is different from Fragment 7 (Client Health Monitor):** The Client Health Monitor scores overall practice health continuously. This fragment is specifically designed to detect the *pre-churn signal cluster* — the combination of events that appear 30–60 days before a client cancels. At that window, a proactive customer success call recovers most at-risk accounts. After cancellation, recovery rates drop to near zero. The distinction is between a dashboard and an alarm.

**Sub-fragments consumed:**
- `champion_job_change_tracker` — the OM or primary contact who championed the purchase has left
- `google_places_collector` — client review velocity has dropped (fewer patients, less activity)
- `dental_broker_listing_monitor` — client practice listed for sale (owner exiting)
- Internal Sova call volume data — a sudden drop in AI call volume at a client = practice reducing reliance on the product (direct leading indicator)
- Support ticket data — unresolved tickets or complaint frequency spike

**Pre-churn signal cluster:**

| Signal | Churn correlation |
|---|---|
| Call volume through Sova dropped >40% week-over-week | Very high |
| Primary contact (OM) departed from client practice | Very high |
| Client practice listed with a dental broker | High |
| 2+ unresolved support tickets in 30 days | High |
| Client practice appearing in a competitor case study | High |
| Review velocity declining for 60+ days | Medium |

**Output:** Pre-churn risk tier per client: `CRITICAL` (intervene this week) / `AT_RISK` (schedule check-in call) / `MONITOR`. Includes the specific signals that fired and the recommended customer success action. Routes automatically to the CS queue when `CRITICAL`. Written to `sova_churn_alert`.

---

### Fragment 28 — Cross-Platform Persona Stitcher

**Business question:** What does this practice's complete digital footprint look like across every platform we monitor — and does activity on multiple platforms simultaneously indicate a stronger buying signal than any single source alone?

**Why this matters:** Each sub-fragment sees one slice of a practice's behavior. The `dentalpost_collector` sees a front desk job posting. The `reddit_scout` sees a practice owner venting about phones. The `google_places_collector` sees a spike in bad reviews. But if all three fire for the same practice within 30 days — that is not three weak signals. That is one very loud signal. The Cross-Platform Persona Stitcher is the correlation layer that connects dots across platforms into a single unified practice profile.

**Sub-fragments consumed (correlation inputs):**
- All job portal collectors — hiring activity fingerprint
- All review platform collectors — sentiment and engagement pattern
- `reddit_scout`, `dentaltown_forum_scout`, `facebook_groups_scout` — opinion platform footprint
- `linkedin_api_collector` — company page and employee data
- `youtube_competitor_monitor`, `tiktok_industry_monitor` — content engagement signals
- `branded_search_spike_monitor` — search interest spikes
- `website_visitor_deanonymizer` — direct site visit
- `bombora_b2b_intent_integration` — third-party content consumption

**How it works:**

1. **Entity resolution** — matches a practice across platforms by domain, phone number, NPI, and practice name. One practice may appear as "Bright Smiles Dental" on Facebook, "Bright Smiles Dental Group" on Indeed, and NPI 1234567890 in NPPES. These are resolved into one entity.
2. **Signal co-occurrence scoring** — when multiple platforms show activity for the same practice in the same 30-day window, the score compounds. Two signals from different platforms = stronger evidence than two signals from the same platform.
3. **Behavioral archetype tagging** — classifies each practice's digital behavior pattern: `ACTIVE_RESEARCHER` (consuming content across platforms), `PASSIVE_PAIN` (complaints visible but no active search), `DARK` (no digital footprint — outreach harder), `ENGAGED_BUYER` (multiple high-intent signals across platforms simultaneously).

**Output:** Enriched practice profile with unified cross-platform signal map + behavioral archetype tag. Practices tagged `ENGAGED_BUYER` with 3+ platform signals in 30 days are automatically elevated to `HOT` regardless of their composite Lead Score. Written to `sova_persona_map`. This is the closest thing Sova has to knowing what a practice is doing on the open internet at any given moment.

---

### Fragment Summary

| Fragment | Business Question | Priority | Feeds Into |
|---|---|---|---|
| Fit Score | Does this practice match our ICP? | Critical | Lead Score |
| Intent Score | Is this practice in active pain? | Critical | Lead Score |
| Lead Score | How hot is this lead — act, nurture, ignore? | Critical | Outreach Brief |
| Competitive Leaderboard | Where do we rank vs. competitors? | High | — |
| Competitive Intelligence Report | What did competitors do this week? | High | — |
| Client Health Monitor | Who is at risk or ready to upsell? | High | — |
| Outreach Intelligence Brief | What do we know about this HOT lead? | High | Outreach agent |
| Market Intelligence Report | What is happening in the market? | Medium | Content Generation |
| Regulatory & Compliance Watch | Are there regulatory changes that affect us? | Medium | — |
| Content Generation | What should we post and publish? | Low — build last | Social publishing agent |
| Practice Growth Predictor | Which practices are in active growth? | High | Lead Score |
| Competitive Churn Risk Analyzer | Which competitor clients are ready to switch? | High | Outreach Brief |
| Relocation & Renovation Detector | Which practices are rebuilding their systems? | High | Outreach Brief |
| CE Engagement Tracker | Which contacts are open to learning and change? | Medium | Content Generation |
| Financial Stress Indicator | Which practices are under financial pressure? | Medium | Client Health Monitor |
| DSO Enterprise Pipeline | Which accounts are DSO-scale and need enterprise routing? | Critical | Outreach Brief (Enterprise track) |
| Staff Churn & Operational Stability Predictor | Which practices have chronically unstable front desks? | High | Lead Score, Outreach Brief |
| Displacement Intelligence Engine | Which practices using a competitor tool are ready to switch? | High | Outreach Brief |
| Influence & Network Map | Who can credibly introduce us to this account? | Medium | Outreach Brief |
| Revenue Rescue Planner | What exact revenue-leak story should we tell this practice? | High | Outreach Brief |
| Buying Committee Intelligence | Who is the economic buyer vs. daily champion — and what do we say to each? | High | Outreach Brief |
| Access Failure Index | How badly is this practice leaking patient demand at the front door? | Critical | Lead Score |
| Transition Window Detector | Is this practice in an active system reconfiguration window right now? | Critical | Lead Score, Outreach Brief |
| Local Pressure Index | How much competitive pressure is this practice under from its geography? | High | Lead Score (Geography component) |
| Trust Vector | What proof asset will most reduce resistance for this specific lead? | High | Outreach Brief |
| ICP Accuracy & Signal Calibration Monitor | Is our scoring model still working — which signals have drifted? | Critical — ongoing | Lead Score (weight updates) |
| Churn Early Warning System | Which clients are in the 30–60 day pre-churn window when intervention still works? | Critical | Customer success queue |
| Cross-Platform Persona Stitcher | What does this practice's complete digital footprint look like — and do multiple simultaneous signals compound into a confirmed buying signal? | High | Lead Score (ENGAGED_BUYER override) |

---

## Full Sub-fragment Count by Strategy

| Strategy | Sub-fragments | Status |
|---|---|---|
| Job Portal Scouting | 6 | Priority — build first |
| Social Platform Intelligence | 6 | Priority — build second |
| Seminar & Conference Scouting | 2 | Medium |
| Newsletter Intelligence Agent | 2 | Priority — inbox already set up |
| Opinion Platform Scrapers | 4 | Medium |
| Practice Data Foundation | 3 | Priority — NPPES is the base |
| Website & RSS Monitoring | 3 | Medium |
| Competitor Intelligence | 11 | Priority — competitive market |
| Google Cloud API Suite | 2 | Low effort, high value |
| Review Platform Expansion | 5 | Medium |
| Local Market Intelligence | 2 | Medium |
| Partnership & Channel Intelligence | 5 | Low |
| Signal Enrichment Layer | 3 | Runs after leads are scored |
| Champion Tracking | 1 | Priority — highest win rate |
| Practice Lifecycle Events | 6 | Priority — highest conversion |
| Government Data Sources | 10 | Medium — free, underutilised |
| Dental Association Databases | 4 | Medium |
| Technographic Intelligence | 6 | Medium |
| Website Visitor De-Anonymization | 2 | High value, low effort |
| DSO Proximity Intelligence | 2 | Medium |
| PMS Vendor Pain Monitoring | 1 | High — direct competitor dissatisfaction |
| Contextual Trigger Monitoring | 1 | Medium — time-sensitive |
| Continuing Education Monitoring | 1 | Medium |
| Dark Social & Community Intel | 5 | Medium |
| Patent & Trademark Monitoring | 2 | Low — competitive intelligence only |
| Podcast & Webinar Intelligence | 2 | Low |
| Phone System Lease Cycle | 1 | Low — long build, niche signal |
| Local Business Journal & Chamber Monitoring | 1 | Medium — high timing value |
| Staff Burnout & Operational Stress Signals | 3 | High — pure NLP on existing data |
| Access & Availability Intelligence | 6 | Critical — first-party operational signals |
| Staff Transition Intelligence | 3 | High — workflow re-evaluation window |
| First-Party Intent Systems | 3 | Critical — highest intent signals |
| X/Twitter Intelligence *(v2 — planned)* | 2 | Future version — API cost gates this |
| **Total** | **116** | |

---

## What Is Not in This Document

These capabilities are planned but are not sub-fragments — they belong to a separate execution layer built after the brain is collecting data:

- **Outreach agent** — drafts and sends personalized cold emails using collected signals
- **Content agent** — generates LinkedIn/blog posts from content-classified intelligence
- **Scoring engine** — computes composite lead scores from sub-fragment output
- **Social publishing agent** — posts generated content to Facebook and LinkedIn
- **Competitor GitHub repo audit** — monitoring public GitHub repos of competitors (Arini, TrueLark, etc.) for commit history, tech stack decisions, and feature development direction. This is a **one-time manual research task**, not a sub-fragment. A few targeted Google searches + `github.com/<competitor_org>` visits gives you 80% of the intelligence in 30 minutes. Not worth automating unless a competitor becomes a sustained threat requiring ongoing tracking.
- **Inbound demand optimisation** — landing page A/B testing strategy, SEO architecture, paid acquisition funnel design. These are downstream of the data collection layer. v1 of Sova collects the data that will tell us what changes to make. Build the intelligence first; optimise inbound once the data says what to change.

---

## TCPA / FCC Compliance — Critical Product & Outreach Requirement

On **February 8, 2024**, the FCC issued a ruling that explicitly classifies AI-generated synthetic voices as "artificial or prerecorded voices" under the Telephone Consumer Protection Act (TCPA). This applies to Sova in two ways: (1) the product itself — every inbound call the AI handles, and (2) any outbound AI-assisted sales calls.

| Requirement | What it means in practice |
|---|---|
| **Prior express written consent** | Any outbound AI call for commercial/marketing purposes requires explicit written consent — specifically disclosing AI voice. Cannot be buried in ToS or pre-checked boxes. |
| **AI disclosure at call start** | The AI must identify itself as AI *before* any conversation begins. This must be the first thing said. |
| **Opt-out within 2 seconds** | A voice or keypad opt-out must be offered within 2 seconds of the initial AI message. |
| **Per-violation fines** | $500 per call for standard violations. $1,500 per call for willful violations. No cap on aggregate damages. |
| **State recording laws** | Some states require two-party consent for call recording. The AI must detect the caller's state and apply the correct disclosure. One-party states: most of the US. Two-party states: CA, FL, IL, MD, MA, NV, NH, OR, PA, WA. |

**Product implication:** The AI receptionist must be architecturally designed to deliver TCPA-compliant disclosures on every inbound call before substantive conversation begins. This is not optional and is not a post-launch retrofit.

**Outreach implication:** Any use of AI voice for outbound sales prospecting requires a full consent infrastructure. Until that exists, outbound prospecting must use human callers or compliant text/email channels only.

---

## Compliance & Legal Risk Flags

These sub-fragments carry ToS or legal risks that must be reviewed before building. Flagged by GPT research.

| Sub-fragment | Risk | Mitigation |
|---|---|---|
| `linkedin_hyperbrowser_agent` | LinkedIn explicitly prohibits automated people-search and session simulation | Use Proxycurl API (licensed LinkedIn data proxy) instead of browser automation |
| `facebook_hyperbrowser_agent` | Simulating human sessions may violate Facebook ToS | Limit to official Graph API; use Hyperbrowser only for genuinely public content with no login |
| `glassdoor_collector` | Glassdoor ToS restricts bulk scraping | Use only publicly visible summary data per listing; do not bulk-extract |
| `facebook_groups_scout` | Group scraping may violate community rules | Limit strictly to public groups; never scrape private or closed groups |
| `website_visitor_deanonymizer` | IP collection subject to CCPA and GDPR | Add explicit disclosure in Sova's privacy policy before deploying; do not store raw IPs |
| `dea_registration_checker` | DEA diversion control site limits automated queries | Rate-limit heavily (1 req/sec max); consider a licensed third-party verification service |
| `dental_specialty_association_scraper` | Some associations prohibit bulk extraction | Confirm ToS per association; contact for data licensing if bulk is needed |
| `linkedin_profile_enricher` | LinkedIn prohibits automated people search | Use Proxycurl API with explicit data license; never simulate a human session |

---

## Build Validation & Priority Flags

Cross-research validation from GPT, Gemini, Grok, and deep research. Each sub-fragment has been reviewed for legal risk (L/E), technical feasibility at scale (Feas.), signal strength for our ICP (Signal), and a build recommendation.

**Legend:** `G` = Green (low risk, official API or public data) | `A` = Amber (gray area, proceed with care) | `R` = Red (high risk, ToS or legal exposure)

### Drop — Do Not Build

These sub-fragments were flagged by multiple research sources as low signal, high risk, or technically not viable as described.

| Sub-fragment | Reason | Alternative |
|---|---|---|
| `facebook_creator_marketplace_scout` | Low signal for our ICP. High platform risk — Creator Marketplace access is gated. Marginal competitor intelligence at best. | No alternative needed. Competitor ad monitoring via `facebook_ads_library_collector` is sufficient. |
| `phone_system_age_estimator` | Too speculative. Inferring phone system age from job skills endorsements and website text is not reliable enough to act on. High build effort for a heuristic that will misfire often. | Remove from roadmap. Phone friction is better detected directly via `live_answer_audit`. |

### Do Not Build As Described — Replace Method

These sub-fragments have high signal but the current implementation approach is legally problematic. Build the signal, not the described method.

| Sub-fragment | Problem with current approach | Replacement approach |
|---|---|---|
| `linkedin_hyperbrowser_agent` | LinkedIn explicitly prohibits automated session simulation. CFAA exposure at scale. High enforcement risk. | Proxycurl API — licensed LinkedIn data proxy with explicit ToS permission for B2B enrichment. |
| `facebook_groups_scout` | Automated scraping of Facebook Groups (even public ones) is prohibited by Meta's ToS. Platform detection risk is high. | Replace with `facebook_api_collector` (Graph API, official) + `dental_community_mention_tracker` for brand monitoring. |
| `linkedin_jobs_collector` | LinkedIn aggressively blocks scrapers; CFAA exposure possible for commercial use. | Use a licensed job-data API (e.g., JSearch API, Jobicy, or RapidAPI job boards) that aggregates LinkedIn and other platforms. |
| `linkedin_profile_enricher` | Same LinkedIn scraping risk as above. | Proxycurl API — same licensed proxy solution. |

### Deprioritise — Build Last or Skip

Low signal relative to build effort, or redundant with higher-signal alternatives.

| Sub-fragment | Reason |
|---|---|
| `quora_scout` | Quora dental traffic is sparse. Low volume of practice-owner-level discussion. Reddit and Dentaltown cover this signal better. |
| `dea_registration_checker` | Very low signal (validates a practice exists, which NPPES already does). High rate-limiting risk. Skip unless dead-practice cleanup becomes a specific problem. |
| `uspto_trademark_monitor` | Competitor IP filing intelligence is interesting but does not affect outreach timing or messaging. Build only if competitive intelligence becomes a dedicated function. |
| `patent_filing_monitor` | Same as above. Patent filings are 12–18 months ahead of any product — not actionable for near-term sales. |
| `dental_podcast_monitor` | Low volume of practice-level leads. Podcast guests are influencers, not necessarily buyers. Use `peer_influence_mapper` instead for community authority mapping. |
| `glassdoor_collector` | ToS risk + low marginal signal. Job re-post velocity from `dentalpost_collector` / `indeed_collector` + burnout language from `staff_burnout_aggregator` covers the same signal more safely. |

### Merge Opportunities — Avoid Duplicate Pipelines

These sub-fragments do closely related things and should share infrastructure rather than run as fully independent collectors.

| Merge group | What to do |
|---|---|
| `website_crawler` + `booking_tech_detector` + `zocdoc_listing_detector` | One technographic crawl pass per practice. Store all results (booking tool detected, CTA present, Zocdoc listed, page speed) in one `sova_technographic` table. Three separate HTTP fetches to the same domain is wasteful. |
| `competitor_website_monitor` + `competitor_product_monitor` | One change-detection pipeline per competitor URL. `competitor_website_monitor` is redundant — `competitor_product_monitor` already does page-change detection. |
| `conference_social_tracker` | Not a standalone sub-fragment. Merge into `facebook_api_collector` and `linkedin_api_collector` as a query preset targeting conference page accounts. |
| `google_news_collector` + `rss_feed_monitor` + `newsletter_classifier` + `competitor_pr_monitor` | One news ingestion service with topic routing. All four produce "article text that needs classification." Build one ingestion queue + one classifier rather than four parallel stacks. |

---

## Open Questions

1. **Build order Phase 0:** NPPES + `google_places_collector` + website technographics + job portals + `champion_job_change_tracker` + lifecycle events + `sba_loan_monitor` are agreed as first tier. What is the exact sprint sequence?
2. **Polling frequency:** Defined when we build the scheduling layer. Champion tracking and lifecycle events need near-real-time (daily). Job portals can be every 48h. Review platforms weekly.
3. **Champion seed list:** The `champion_job_change_tracker` requires a seed list of current client contacts. How is this maintained? Manual CSV upload? CRM sync? Who owns it?
4. **State dental board priority:** CA, TX, NY, FL, IL confirmed as priority. Which states have bulk-downloadable licensee data vs. requiring per-page scraping?
5. **State SoS UCC portals:** Which states support automated lookups? Requires per-state research before building `ucc_loan_filings_monitor`.
6. **Financial Stress Indicator:** Should it automatically suppress outreach (remove from queue) or flag for human review? Decision affects the Celery task design.
7. **Live answer audit consent:** Test calls to practices for `live_answer_audit` and `after_hours_coverage_audit` — confirm no identity disclosure is required in the relevant states. Get legal sign-off before production deployment.
8. **Lead Score HOT threshold calibration:** 78+ is the research-recommended starting point. After the first 3–6 months of data, this should be trained against actual win rates and adjusted.
9. **Merge sequencing:** The four merge groups (technographic crawl, competitor pipeline, conference social, news ingestion) should be resolved in architecture before building — to avoid refactoring two separate stacks into one later.
10. **Medical market expansion:** Deep research identified state medical board monitoring (FSMB) and HHS OCR Breach Portal as the analogous entry points when Sova expands beyond dental. Document separately when that motion begins.
