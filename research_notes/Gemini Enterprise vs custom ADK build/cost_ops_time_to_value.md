# Gemini Enterprise vs custom ADK build: cost, operations and time-to-value (as of 2026-11-24)

Method note: WebFetch returned usable text for the Google docs pages cited below. Several Google marketing and pricing pages returned 404, empty (JS-rendered) or oversize content. Those are flagged as unverified. Figures from secondary sources are labelled "(secondary)". Model names and prices are quoted exactly as the fetched pages showed them.

## 1. Gemini Enterprise pricing: per-seat prices, pay-as-you-go rates, consumption, minimums

### Takeaway
The official Google docs pages I could read do not list per-seat prices. Seat prices come from search snippets that attribute them to Google pages, and from secondary sources. Business is about $21 per user per month, Standard about $30, and Plus $30 or $50 depending on the source. Overage rates are officially documented: $0.10 per Assistant query, $4.00 per Deep Research query, and $5 per GiB-month for storage. I could not retrieve a Google pricing page for Gemini Enterprise at all (see Gaps).

### Cited Findings
- cloud.google.com/gemini-enterprise/pricing returned HTTP 404 when fetched, and cloud.google.com/gemini-enterprise returned only a title with no body text. No official pricing page was retrievable. — fetch attempts of [pricing](https://cloud.google.com/gemini-enterprise/pricing) and [product page](https://cloud.google.com/gemini-enterprise)
- Editions listed in the official docs are Business, Standard, Plus, Pay-as-you-go and Frontline. The docs editions page lists no prices. — [Editions docs](https://docs.cloud.google.com/gemini/enterprise/docs/editions)
- Seat ranges per the editions docs:
  - Business: 1-500 users, 25 GiB pooled storage per user.
  - Standard: 1 or more users, 30 GiB.
  - Plus: 1 or more users, 75 GiB.
  - Pay-as-you-go: 1 minimum seat to start.
  - Frontline: 150 or more Standard or Plus users, 2 GiB.
  — [Editions docs](https://docs.cloud.google.com/gemini/enterprise/docs/editions)
  - An older or different copy of the editions page shows Business as 1-300 users, per a search snippet. The sources conflict on the 300 versus 500 cap. — [search snippet, docs editions](https://docs.cloud.google.com/gemini/enterprise/docs/licenses?hl=sv)
- Business is a SaaS app at business.gemini.google. Admins do not need the Cloud console and there are no project-level IAM roles. — [Editions docs](https://docs.cloud.google.com/gemini/enterprise/docs/editions)
- Pay-as-you-go billing:
  - Self-serve accounts pay from prepaid credits. Invoiced accounts are billed monthly.
  - Included monthly seat credits apply only to first-party Gemini models.
  - Partner models (Anthropic Claude Opus 5.5 and Sonnet 5.5) are billed pay-as-you-go once an admin enables them.
  - Usage is subject to a monthly spend limit.
  — [Editions docs](https://docs.cloud.google.com/gemini/enterprise/docs/editions)
- Overage (pay-as-you-go) unit rates, which apply equally to all editions:
  - Storage and data indexing: $5 per GiB-month.
  - Assistant: $0.10 per query.
  - Video generation: $0.40 per second.
  - Image generation: $0.02 per image.
  - Deep Research: $4.00 per query.
  - No-code agent use: priced by underlying agent actions.
  - No minimum commitment is stated.
  — [Overages docs](https://docs.cloud.google.com/gemini/enterprise/docs/overages)
- Per-seat AI developer tool credits: Standard $10 per user per month, Plus $15 per user per month. They are available only on invoiced billing accounts and enforced as a rolling 7-day shared pool. — [Overages docs](https://docs.cloud.google.com/gemini/enterprise/docs/overages)
- Seat prices, search-result summary that attributes them to Google pages:
  - Business $21 per user per month, annual commitment.
  - Standard $30.
  - Plus starts at $30 (one source says about $50).
  - A UK G-Cloud pricing document lists Standard at $35.
  - Trials: Business has a 30-day free trial, and Plus has a 30-day trial that does not require sales.
  — [WebSearch summary, 2026-11-24](https://dupple.com/learn/gemini-enterprise-pricing) and [G-Cloud pricing doc](https://assets.applytosupply.digitalmarketplace.service.gov.uk/g-cloud-15/documents/720213/107330696325999-pricing-document-2026-01-30-0036.pdf). I could not open these pages myself.
- Annual versus flex seat prices (secondary):
  - Business $21 on both terms.
  - Standard $30 annual and $35 flex.
  - Plus $50 annual and $60 flex.
  - Frontline custom, with a 150-seat minimum.
  - The page says compute and tokens are billed on top of seats, and cites 10-20% volume discounts above 500 seats.
  - The same page is internally inconsistent on memory pricing.
  — [ecorpit.com](https://ecorpit.com/gemini-enterprise-agent-platform-cost-breakdown-2026/) (secondary)
- Gartner reports that on 2026-08-26 Google changed Gemini Enterprise pricing to user-based licensing with pooled quotas, consumption-based pay-as-you-go, and flexible savings plans. The summary comes from a search snippet because the page returned 403. — [Gartner First Take](https://www.gartner.com/en/insights/gartner-first-takes/gemini-enterprise-pricing-changes-push-software-engineering-leaders-ai-finops) (snippet only)
- A Stanford IT rates page and a G2 pricing page exist as further secondary references, but I did not open them. — [Stanford](https://uit.stanford.edu/rates/gemini-enterprise-ai), [G2](https://www.g2.com/products/google-gemini-enterprise/pricing)

### Inferences
- For a small support team, the seat cost is minor. Five Business seats at $21 is $105 per month. Seats are not the main cost driver.
- If someone applied Assistant overage pricing to 10,000 conversations of 6 turns, the cost would be 60,000 queries × $0.10 = $6,000 per month. This is not a real scenario, because Gemini Enterprise is not designed for external users (see section 2). It is useful only to show why per-query employee pricing is a poor fit for customer volume.

### Gaps
- There is no official per-seat price page I could read. Seat prices rest on search snippets and secondary sources, and Plus is disputed ($30 versus $50).
- I could not retrieve the PAYG seat fee, if any, or the exact meaning of the "Pay-as-you-go" edition beyond the docs bullets above. The docs state no minimum charges.
- The Gartner page and the eWeek PAYG article returned 403, so their details are unverified.

## 2. Is Gemini Enterprise allowed for customer-facing use, and what are the alternatives

### Takeaway
I found no explicit statement either way that Gemini Enterprise seats can serve external end customers. The editions docs say nothing on external users, and every licensing mechanism I found is per-seat, and sign-in requires a license, so it is employee-oriented by design. The Google offering built for customer-facing agents is Gemini Enterprise for Customer Experience (formerly Customer Engagement Suite and Dialogflow CX), which prices per session. Treat "Gemini Enterprise for customers" as unconfirmed and ask Google in writing.

### Cited Findings
- The editions docs do not address external users or customer-facing use. — [Editions docs](https://docs.cloud.google.com/gemini/enterprise/docs/editions)
- A user must have a license to sign in to the Gemini Enterprise app. Admins assign licenses by email or automatically on first access. Self-serve and resold accounts are capped at 25 seats per account in the console, and invoiced accounts at 1,000 seats. — [Licenses docs](https://docs.cloud.google.com/agentspace/docs/licenses) (search snippet)
- Business Edition terms say admins control who can join a Team as an "End User" (archived Dec 2025 version). — [Business Edition Additional Terms](https://cloud.google.com/terms/agentspace-business)
- Gemini Enterprise for Customer Experience (Essentials) has its own terms. Use is limited to trade, business or professional purposes, users must be 18 or older, and the customer is solely responsible for supervising AI agents and for all actions they perform. — [GECX Additional Terms](https://cloud.google.com/terms/gecx) (search snippet; the fetch returned only the title)
- CX Agent Studio pricing is per session, where a session is a conversation between an end user and an agent. Base rate is $0.50 per session for chat or voice, with $0.45 and $0.40 on 1-year and 3-year flexible savings plans. A chat session bills again after 50 turns or 30 minutes of inactivity. Evaluations, AI augmentation and monitoring are included. A separate Food Ordering AI Agent is $0.25 per session. — [CX Agent Studio pricing](https://cloud.google.com/products/gemini-enterprise-for-customer-experience/cx-agent-studio/pricing) (search snippet; the page body would not fetch)
- ADK agents hosted on Agent Engine (Agent Runtime) can be registered in a Gemini Enterprise app, via console or REST. The Discovery Engine service account needs the Vertex AI User and Vertex AI Viewer roles. Cross-project registration is supported. The description field tells the LLM when to invoke the agent. — [Register ADK agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)
- Editions docs list "Full-code agents built outside Gemini Enterprise" as a feature row. Which editions include it is unknown, because the check marks did not survive extraction. — [Editions docs](https://docs.cloud.google.com/gemini/enterprise/docs/editions)

### Inferences
- Because registration exposes the agent only "to users within a Gemini Enterprise app", the hybrid option serves staff (for example support agents asking an internal copilot). It does not put the agent in front of retail customers.
- For a retailer's customer-facing agent the realistic choices are: a custom ADK agent on Agent Runtime or Cloud Run behind your own front end, or GECX / CX Agent Studio at about $0.50 per session.
- The hybrid also makes sense as a two-surface setup: the same ADK agent serves customers through your front end and staff through Gemini Enterprise seats.

### Gaps
- No Google FAQ or terms text I could read states whether external (non-employee) users may hold seats. Resolve this with a Google account rep or by reading the full Service Specific Terms. The GECX and Business terms pages did not render fully.
- The CX Agent Studio pricing page body did not render. Figures come from search summaries.

## 3. Custom build costs: Agent Runtime, Cloud Run, Gemini API tokens, logging, and a 10,000-conversation estimate

### Takeaway
A custom ADK agent at 10,000 conversations per month costs roughly $175 to $500 per month in runtime plus tokens under the assumptions below, or about $0.02 to $0.05 per conversation. Token cost dominates, and it doubles on gemini-3.8-flash on 1 January 2027.

### Cited Findings
- Gemini API prices per 1M tokens (Standard tier, paid), from the official pricing page, which now redirects to aistudio.google.com/docs/pricing:
  - `gemini-3.8-flash`: input $0.75 through 2026-12-31, then $1.50 from 2027-01-01. Output $3.75, then $7.50.
  - `gemini-3.6-flash`: same as 3.8 Flash.
  - `gemini-3.5-flash-lite`: input $0.30, output $2.50.
  - `gemini-3.1-flash-lite`: $0.25 in, $1.50 out.
  - `gemini-3-flash-preview`: $0.50 in, $3.00 out.
  - `gemini-3.1-pro-preview`: $2.00 in and $12.00 out up to 200k prompt tokens. No free tier.
  - `gemini-2.5-flash`: $0.30 in, $2.50 out. `gemini-2.5-pro`: $1.25 in, $10.00 out.
  — [Gemini API pricing](https://aistudio.google.com/docs/pricing) (previously ai.google.dev/gemini-api/docs/pricing, 301 redirect)
- Deprecation: from 2026-12-01, `gemini-2.5-pro` requests route to `gemini-3.8-flash` and `gemini-2.5-flash` requests route to `gemini-3.5-flash-lite`. — [Gemini API pricing](https://aistudio.google.com/docs/pricing)
- Free tier: most Flash and Flash-Lite models are marked "free of charge". `gemini-3.1-pro-preview` has no free tier. Caching is not available on the 3.5 Flash-Lite free tier. The page does not list RPM or TPM limits. Search grounding is capped at 1,500 requests per day. — [Gemini API pricing](https://aistudio.google.com/docs/pricing). The page was 118,372 characters and I read the first 100,000 only.
- Context caching is implicit only on the newer models. Batch is priced separately (for example 3.8 Flash batch input $0.375 through 2026-12-31). — [Gemini API pricing](https://aistudio.google.com/docs/pricing)
- Agent Runtime (Agent Platform) consolidated SKUs, effective 2026-09-01 per a Google price sheet:
  - Compute $0.085 per vCPU-hour.
  - Memory $0.009 per GiB-hour.
  - Storage $0.30 per GiB-month for Sessions and Memory Bank.
  - Memory Bank retrieval $0.50 per 1,000 memories.
  - Previous runtime compute was $0.0864 per vCPU-hour, and sessions were $0.25 per 1,000 events.
  — figures from a search-result summary of [Google price sheet PDF](https://services.google.com/fh/files/emails/b_502770571_gemini_enterprise_agent_platform_pricing.pdf). The PDF text was compressed and unreadable to my fetch, so confirm against the SKU pages.
- A secondary source says Sessions and Memory Bank are $0.30 per GiB-month plus $0.085 per 1M write operations, and that a free usage tier applies per account per month. The same source mixes units, so treat the write-operation rate as unverified. — [ecorpit.com](https://ecorpit.com/gemini-enterprise-agent-platform-cost-breakdown-2026/) (secondary)
- Cloud Run: I could not retrieve the pricing page body. My fetch tool returned approximate figures from its own training data: instance-based about $0.00001 per vCPU-second and $0.000001 per GiB-second, request-based about $0.000024 per vCPU-second and $0.0000025 per GiB-second, $0.40 per million requests, and a free tier of 180,000 vCPU-seconds, 360,000 GiB-seconds and 2M requests per month. These are unverified. — [Cloud Run pricing](https://cloud.google.com/run/pricing) (page body not retrieved)
- Logging and monitoring prices: not retrieved (unverified).

### Illustrative monthly estimate (10,000 conversations per month)
Assumptions, all mine and labelled as such:
- 6 turns per conversation, one model call per turn.
- Each call has about 3,000 input tokens (system prompt, retrieved context and history) and 300 output tokens including thinking.
- Monthly volume: 10,000 × 6 × 3,000 = 180M input tokens, and 10,000 × 6 × 300 = 18M output tokens.
- No caching or batching discounts.

Token cost:
| Model | Arithmetic | Monthly |
|---|---|---|
| gemini-3.5-flash-lite | 180 × $0.30 + 18 × $2.50 = $54 + $45 | $99 |
| gemini-3.8-flash, through 2026-12-31 | 180 × $0.75 + 18 × $3.75 = $135 + $67.50 | $202.50 |
| gemini-3.8-flash, from 2027-01-01 | 180 × $1.50 + 18 × $7.50 = $270 + $135 | $405 |
| gemini-3.1-pro-preview | 180 × $2.00 + 18 × $12.00 = $360 + $216 | $576 |

Hosting, assuming one always-on instance of 1 vCPU and 2 GiB for 730 hours:
- Agent Runtime: 730 × (1 × $0.085 + 2 × $0.009) = 730 × $0.103 = $75.19 per month. This is a ceiling. Billing may be lower if compute is metered only while active, which I could not confirm.
- Sessions storage: 10,000 conversations × about 20 KB = about 0.2 GB × $0.30 = about $0.06 per month. Memory Bank is excluded.
- Cloud Run alternative (unverified rates): 730 × 3,600 = 2,628,000 s. CPU 2,628,000 × $0.00001 = $26.28. Memory 2 GiB × 2,628,000 × $0.000001 = $5.26. Total about $31.5 before the free tier.
- Logging: assume under 10 GiB per month. I believe Cloud Logging includes a free allotment (50 GiB per project) from my own knowledge, but did not verify it. Assumed $0 to about $5.

Total:
- Low case (3.5 Flash-Lite, Cloud Run): $99 + $31.5 = about $130 per month.
- Mid case (3.5 Flash-Lite, Agent Runtime): $99 + $75.19 + $0.06 = about $174 per month.
- High case (3.8 Flash from 2027 on Agent Runtime): $405 + $75.19 + $0.06 = about $480 per month.
- Per conversation: about $0.013 to $0.048.

For comparison, GECX at the base $0.50 per session is 10,000 × $0.50 = $5,000 per month ($4,000 at $0.40 per session on a 3-year plan). That is roughly 10 to 40 times the custom build's infrastructure and token cost, and the session price includes Google-managed evaluations and monitoring.

### Inferences
- The model choice swings the bill far more than hosting does. Moving from Flash-Lite to 3.8 Flash from January 2027 raises the cost by about $306 per month.
- If real conversations use retrieval-heavy prompts (for example 10,000 input tokens per call), input cost scales linearly and the Flash-Lite cost rises to about $330 per month.
- The free tier is suitable for prototyping. I did not verify its data-use terms, so check those before sending real customer data to a free-tier key.

### Gaps
- The Cloud Run pricing body, logging and monitoring prices, and Google's own Agent Runtime SKU page were not retrievable. Cloud Run numbers are unverified model recall.
- Rate limits (RPM and TPM) were not on the pricing page.
- Whether Agent Runtime compute bills only while handling requests is unconfirmed.

## 4. Operations burden, staffing, and compliance (Canada)

### Takeaway
Gemini Enterprise and GECX move most operations to Google, while a custom ADK build leaves evaluation, security guarding, prompts, retrieval, observability and incident response with your team. Canada data residency exists for Gemini Enterprise but with notable model gaps, and it needs allowlist access from Google.

### Cited Findings
- Business edition is SaaS and admins do not need the Cloud console. Standard and Plus use the Cloud console and project IAM. — [Editions docs](https://docs.cloud.google.com/gemini/enterprise/docs/editions)
- GECX terms: the customer is solely responsible for judging whether AI agents fit the use case, for supervising them, and for all actions they perform. So even the managed option leaves accountability with you. — [GECX terms](https://cloud.google.com/terms/gecx) (search snippet)
- CX Agent Studio session pricing includes automated evaluations, AI augmentation and monitoring at no extra charge. — [CX Agent Studio pricing](https://cloud.google.com/products/gemini-enterprise-for-customer-experience/cx-agent-studio/pricing) (search snippet)
- Canada (`ca`) is an in-country location for Gemini Enterprise with at-rest data residency and ML processing for base functionality. Access is "GA with allowlist", so you contact your Google account team. — [Gemini Enterprise locations](https://docs.cloud.google.com/gemini/enterprise/docs/locations)
- In `ca`:
  - Supported: Gemini 3.5 Flash, Model Armor, CMEK.
  - Not offered: Gemini 3.8 Flash ("CA, IN, and JP regions don't offer the 3.8 Flash model"), Gemini 3.1 Pro, Gemini 2.5 Pro, and Claude Opus 5.5 and Sonnet 5.5.
  - `global` only: Gemini 3.6 Flash, Gemini 3.7 Flash, and Grounding with Google Search.
  — [Gemini Enterprise locations](https://docs.cloud.google.com/gemini/enterprise/docs/locations)
- If you turn on a model that Canada does not support, traffic routes to the `global` endpoint, which has no regional data residency. — [Gemini Enterprise locations](https://docs.cloud.google.com/gemini/enterprise/docs/locations)
- Agent Runtime in `ca`: Memory Bank, Sessions and Runtime support at-rest DRZ. Code execution does not. — [Gemini Enterprise locations](https://docs.cloud.google.com/gemini/enterprise/docs/locations)
- The page does not mention the `northamerica-northeast1` (Montreal) region name, and it does not say which editions support `ca`. — [Gemini Enterprise locations](https://docs.cloud.google.com/gemini/enterprise/docs/locations)
- The Agent Platform has its own data residency page with a per-model table including a Canada column (northamerica-northeast1). The values were not extractable. — [Agent Platform data residency](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/data-residency?hl=en)
- A 2024 Google Canada blog announced at-rest and ML-processing residency in Canada for Gemini 1.5 models (older context). — [Google Canada blog](https://blog.google/intl/en-ca/company-news/technology/announcing-data-residency-at-rest-and-during-machine-learning-ml-processing/)

### Inferences
- Staffing, by option:
  - Gemini Enterprise only: an admin role of a few hours per week, with no engineering.
  - Custom ADK: at least part of an engineer's time for prompts, retrieval, tool integrations, evals, guardrails, deployment, cost monitoring and on-call. This is my judgment and not a sourced figure.
  - Hybrid: both of the above, plus managing registration permissions.
- Canada residency constrains the model choice. The model I priced as the likely default (3.8 Flash) is not offered in `ca`. Only 3.5 Flash is confirmed as supported there, which makes it the practical residency-compliant Flash model. Using the AI Studio API key, as this repo's pinned stack does, gives no Canadian residency guarantee. I found no evidence that AI Studio offers it, so verify before using real customer data.
- Grounding with Google Search is `global` only and has no residency, which matters if the support agent uses web grounding.

### Gaps
- I could not confirm which Gemini Enterprise editions support `ca`.
- Montreal-specific (northamerica-northeast1) support for the Gemini models used by the ADK agent was not extractable.
- No source on PIPEDA or Quebec Law 25 specific to these products was gathered, and that is out of scope here.

## 5. Time-to-value

### Takeaway
I found no documented, authoritative setup-time figures for either path. What exists is process evidence: Gemini Enterprise has a self-serve Business edition with a free trial, and registration of an ADK agent is a console or REST step. Treat all durations below as my estimates.

### Cited Findings
- Business edition has a 30-day free trial and is the self-serve edition. Plus offers a 30-day trial without sales. — [WebSearch summary](https://dupple.com/learn/gemini-enterprise-pricing) (secondary)
- Registering an existing ADK agent in a Gemini Enterprise app requires only an existing app, an agent deployed on Agent Engine, two IAM roles for the service account, and a console or REST call. — [Register ADK agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)
- Standard and Plus data residency in Canada needs allowlist access from the Google account team, which adds a lead time I could not quantify. — [Gemini Enterprise locations](https://docs.cloud.google.com/gemini/enterprise/docs/locations)

### Inferences (my estimates, not sourced)
- Gemini Enterprise Business, internal assistant over existing connectors: days to 1-2 weeks, mostly connector and permission setup.
- GECX / CX Agent Studio customer-facing agent: roughly 2-6 weeks to build intents, tools, evaluation and channel integration.
- Custom ADK build with retrieval, tools and evals, deployed behind your own front end: roughly 4-10 weeks for a small team. This repo already has a working ADK prototype with retrieval, a security guard and order tools, which shortens it.
- Hybrid: add about 1-2 days on top of the custom build to register it (the prerequisites above are the only steps documented).

### Gaps
- No practitioner write-up with measured setup times was found. Estimates above are unverified.

## Decision implications (summary for the report writer)
- Gemini Enterprise only does not appear to fit a customer-facing retail support agent (no external-user licensing evidence, seats are per employee), though it is unconfirmed in writing.
- Custom ADK costs about $130 to $480 per month at 10,000 conversations on stated assumptions, against about $4,000 to $5,000 for GECX per-session pricing, but needs engineering ownership.
- Hybrid is viable only as an internal staff-facing surface. Registration docs describe availability to users within a Gemini Enterprise app.
- Biggest unresolved items to ask Google: external-user licensing, official seat prices, Cloud Run, Agent Runtime and logging SKUs, and Canada support for the exact model in use.
