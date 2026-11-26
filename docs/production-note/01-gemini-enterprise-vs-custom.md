# 1. Gemini Enterprise vs custom build

## Question
Would NovaMart use Gemini Enterprise, a custom build, or a hybrid? Why?

## What the prototype needs (evidence from the repo)
- Code-enforced access control, never prompt-enforced (`ARCH-DRV-1`, D2, D3)
- Fixed pipeline: 5 agents, retrieval-validator loop, confidence composite, outcomes A-E
- Custom tools: `search_policy`, `get_order_status`, `check_return_eligibility`
- Per-user identity (principal) that the model can never supply

## Things to investigate
- [x] What Gemini Enterprise offers today: built-in connectors, agent builder, permission model (researched Nov 2026; see Notes)
- [x] Can it call custom tools / external APIs (order lookup, eligibility)? Yes, via Custom MCP, A2A, or a registered ADK agent
- [x] Can it enforce per-user authorization in code, or only via source ACLs? Index = source ACLs only; code-level only in tools you host. Identity hand-off to ADK tools unverified, needs a PoC
- [x] Can it express deterministic routing / confidence gating? Not natively (no code step in Workflow Builder); only inside an ADK agent or MCP tool
- [x] Custom path: ADK on Agent Runtime (formerly Agent Engine) vs Cloud Run; what changes from `adk web`
- [x] Cost / ops / time-to-value trade-offs (prices partly unverified; see Notes)

## Notes

Source: two research reports (Nov 2026): `reports/Gemini Enterprise offerings overview.md` and `reports/Gemini Enterprise vs custom ADK build.md`. This is a map of what to leverage vs keep custom, not a recommendation.

### What Gemini Enterprise is
- A managed employee AI workspace: chat UI, permission-aware search over connected company systems, Deep Research, notebooks, agent marketplace, and a no-code **Workflow Builder** (formerly Agent Designer).
- Editions: Business, Standard, Plus, Frontline, Pay-as-you-go. Per-seat licensing. Google's pricing page returned 404; Business ~$21 and Standard ~$30 per seat/month come from a third-party article only.
- Mental model: Gemini Enterprise = managed workspace with a no-code builder inside it; ADK = code framework for the agent; n8n-style tools = general automation. ADK agents can be **registered inside** Gemini Enterprise, so it is not strictly either/or.

### Who the end users are decides most of this
- If users are the client's **employees**: Gemini Enterprise can supply UI, login, hosting and connectors.
- If users are the client's **customers**: no source says external customers may hold seats. Front end, auth and hosting stay custom. Google's customer-facing product is a different one (Gemini Enterprise for Customer Experience, ~$0.50/session, search snippet only).

### What we can leverage from Gemini Enterprise (employee-facing case)
| Layer | What it gives | Caveat |
|---|---|---|
| Chat front end | Ready-made UI | Staff only; registered agents visible only inside a Gemini Enterprise app |
| Login / identity | Google Identity or Entra/Okta via Workforce Identity Federation | Workforce identities, not retail customers |
| Hosting | Agent Runtime runs the ADK agent as a managed service | Needs a billed Google Cloud project; the free AI Studio key does not carry over |
| Document search over client systems | Connectors (SharePoint, Confluence, ServiceNow, Jira, Box, Slack GA; Salesforce, Zendesk public preview per earlier report) with source ACLs inherited | No visible relevance scores in the chat app, so it cannot feed our confidence composite |
| Governance | No training on customer data, audit logs, VPC-SC, certifications | Canada (`ca`) residency by allowlist; not all models available there |
| Evals / tracing | Agent evaluation GA (31 Jul 2026); Cloud Trace and Logging by default | |

### What must stay custom (any option)
- **The pipeline**: 5 agents, retrieval-validator loop, confidence composite, outcomes A-E. Workflow Builder has no code step; Condition steps only branch on returned fields.
- **The access guard**: platform auth is source ACLs. "This user may see this order" must be decided in code we host (tool body or `before_tool_callback`), failing closed when no token arrives.
- **Identity-to-customer mapping**: platform token to NovaMart customer / order owner.
- **The three tools**: `search_policy`, `get_order_status`, `check_return_eligibility`. Gemini Enterprise can call them but does not supply them.
- **Model Armor calls**: not applied automatically to registered ADK/A2A agents; must be called from agent code.

### Retrieval is the real fork
- Keep numpy retrieval: full control of scores and the confidence gate; we own the index and ingestion.
- Use Gemini Enterprise search: policies stay in the client's systems with inherited permissions, but no score-level control, so the composite needs a different signal.

### Two ways to integrate
- **Custom MCP connector**: Gemini Enterprise's own LLM picks the tools; our fixed pipeline is lost.
- **Register the whole ADK app on Agent Runtime**: pipeline survives in principle; identity hand-off is the least documented part.

### Use cases for the no-code Workflow Builder
- Fits: client staff maintaining workflows without engineers; low-stakes internal tasks (summarize, draft, find a policy); work centered on the client's connected data; human-in-the-loop flows (documented "Request info" step; write actions need human review); no-ops hosting; fast prototyping and demos.
- Does not fit (our case): measured confidence, code-enforced access, a fixed testable pipeline, external customers.
- Not verified: whether the canvas assistant (GA 24 Jul 2026) generates Workflow Builder agents from a prompt. Test before showing a client.
- Possible framing (inference, not sourced): use no-code to explore a client's workflow quickly, then build the production version in ADK.

### Custom path: what changes from `adk web`
- Targets: Cloud Run (lowest effort), Agent Runtime (only target Gemini Enterprise can register; not directly end-user-facing), GKE (most work). Effort ordering is our judgment.
- Changes: paid/Vertex model credential (free AI Studio terms allow product-improvement use and human review; synthetic data only); persistent sessions (Cloud Run silently falls back to in-memory if no session URI); secrets in Secret Manager; a front end that authenticates the customer and sets the session `user_id`; region (Cloud Run and Agent Runtime support Montreal and Toronto); `min-instances` and cold start with a numpy index; CI and evals.
- Unknown: how the local numpy index is bundled for `adk deploy agent_engine`; CLI target name differs between docs (`agent_engine` vs `agent_runtime`).

### Rough cost (illustrative, assumptions in the report)
- Custom build at 10,000 conversations/month, 6 turns each: about $130-$480/month (tokens $99-$576 depending on model, hosting up to ~$75). Excludes engineering time. Gemini 3.8 Flash price doubles on 1 Jan 2027.
- Gemini Enterprise overage: $0.10 per Assistant query, $4.00 per Deep Research query (official overages doc). Customer-facing per-session product: ~$4,000-$5,000/month at the same volume.
- Time-to-value (our estimates, unsourced): days to 2 weeks (Gemini Enterprise internal assistant); 4-10 weeks (custom from scratch, shorter here since a prototype exists); +1-2 days to register an ADK agent for the hybrid.

### Corrections to the first report (launch stages)
ADK agent registration GA 20 Apr 2026; A2A registration GA 17 Aug; Custom MCP data store GA 7 Aug; Workflow Builder GA 3 Sep; 3-legged OAuth for ADK A2A agents on Agent Runtime GA 13 Nov. Unresolved: launch stage of the tool-authorization resource and of sharing registered agents. The last ~16k characters of the release notes were not read.

### Open items before committing to a client
**Needs written confirmation from Google:** whether external (non-employee) users may hold seats; official per-seat prices; which editions include full-code agents and support `ca`; launch stage of tool-authorization; Agent Runtime and Cloud Run price lists.

**Needs a 1-2 day proof of concept on a billed project:** what identity reaches ADK tool code (one Google page says the user's email; the ADK maintainers say nothing unless a tool authorization is configured); fail-closed behavior with no token; Sequential/Loop agents, callbacks and a custom `BaseAgent` running unchanged once registered; how intermediate events show in the chat UI and the latency of a 5-agent run; bundling the numpy index.

**Smaller unknowns:** Business seat cap (300 vs 500), MCP action cap (100 vs 150), `rankSignals` ranges, Agent Runtime free tier. Several findings rest on search snippets or small-model page summaries.

## Options considered
| Option | Pros | Cons |
|---|---|---|
| Gemini Enterprise only | Fastest to a working internal assistant; no hosting or front end to build; source ACLs inherited; Google-managed ops | No confirmed external-customer licensing; no code step, so no confidence composite or A-E gating; platform LLM chooses tools; per-seat cost; auth only via source ACLs inside the index |
| Custom ADK build only | Full control of pipeline, guard, retrieval and confidence; works for external customers behind our own front end; roughly $130-$480/month at 10k conversations | We own front end, auth, sessions, evals, guardrails and on-call; slower to start |
| Hybrid (ADK agent registered in Gemini Enterprise) | Keeps pipeline and guard; adds a staff-facing chat surface with managed hosting | Staff only; needs Agent Runtime (billed project) plus seats; identity hand-off and UI behavior unverified; highest ops (both stacks) |

## Decision


## One-line summary for the note
