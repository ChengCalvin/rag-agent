# Gemini Enterprise: product, editions, pricing (as of 2026-11-24)

Method note: ~10 tool calls. Google's pricing page (cloud.google.com/gemini-enterprise/pricing) returned 404, and the main product page and FAQ fetched empty. List prices therefore come mainly from a third-party article (Dupple) and are flagged as unverified. Docs-derived facts come from WebFetch summaries (a small model), not raw page text.

## What are the named editions, list prices and included features?

### Takeaway
Docs list five editions: Business, Standard, Plus, Frontline and Pay-as-you-go. Only the Business price (about $21/seat/month) and a "from $30" Standard/Plus price are reported, and only by a third-party site. Google's own help page lists no prices.

### Cited Findings
- Edition seat rules and pooled storage per user: Business 1-500 users, 25 GiB; Standard 1+ users, 30 GiB; Plus 1+ users, 75 GiB; Frontline needs 150+ users of Standard or Plus, 2 GiB; Pay-as-you-go needs 1 minimum seat to start. Storage is pooled per project and location. — [Gemini Enterprise editions doc](https://docs.cloud.google.com/gemini/enterprise/docs/editions)
- The editions doc does not state list prices, trial terms or audiences, and its feature checkmarks did not render in the fetch. Feature rows include: connectors, permission-aware search, Deep Research, Data Insights, Gemini Notebook Enterprise, no-code agents (preview), Agent Marketplace, custom/shared skills, full-code agents built outside Gemini Enterprise, AI developer tools, console access, enterprise security. — [editions doc](https://docs.cloud.google.com/gemini/enterprise/docs/editions)
- Audiences: Business is for SMBs and small teams that don't need complex IT setup (max 500 users per this page). Standard is for employees in large organizations with complex environments. Plus is for employees who need the most comprehensive AI and agent-building tools. Frontline is a lower-cost tier with essential tools. The page lists no prices. — [Google support: Choose your edition](https://support.google.com/g/answer/16547364?hl=en)
- Business is a web SaaS app. Admins don't use the Google Cloud console or project-level IAM. Frontline users can't create or upload skills and can only use admin-provisioned agents. — [editions doc](https://docs.cloud.google.com/gemini/enterprise/docs/editions)
- Third-party price report (read from Google's US page on 28 Oct 2026): Business from $21/seat/month, self-serve, 25 GiB, "Start a trial"; Standard from $30, contact sales; Plus has no separate price and is shown with Standard as "from $30"; Standard/Plus add higher usage limits, custom/third-party agents, VPC Service Controls, CMEK, data residency controls. The article says Business is capped at 300 seats. — [Dupple (third-party, unofficial)](https://dupple.com/learn/gemini-enterprise-pricing)
- Pay-as-you-go edition: GA Aug 1, 2026; requires an invoiced Cloud Billing account; opened to all invoiced accounts Sep 10; prepaid credits GA for self-serve billing accounts Nov 5. Self-serve accounts pay from prepaid credits. — [Gemini Enterprise release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes); [editions doc](https://docs.cloud.google.com/gemini/enterprise/docs/editions)
- License editions can enable "Pay-as-you-go usage above quota" (renamed from "Overages", Oct 6) with spend limits. Claude Opus 5.5 / Sonnet 5.5 are billed as consumption and count toward the project spend cap. — [release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)

### Inferences
- Treat Business $21 and Standard/Plus "from $30" as indicative only. The Business seat cap conflicts across sources (500 in Google docs, 300 in Dupple); prefer Google's 500.
- No official source I reached gives a Frontline or Plus price.

### Gaps
- Official list prices (Google pricing page 404'd; product page fetch empty). Confirm in the Google Cloud console or with sales.
- Per-edition feature matrix and usage quotas (checkmarks lost; licenses-and-quotas URL 404'd).
- Whether the pay-as-you-go edition has per-unit rates, and what they are.

## Main components and positioning (no-code vs pro-code)

### Takeaway
Gemini Enterprise is the employee-facing assistant and agent platform, with chat, permission-aware enterprise search, notebooks, Deep Research, a no-code Workflow Builder and an agent marketplace. The pro-code side is the separate Gemini Enterprise Agent Platform (ex-Vertex AI).

### Cited Findings
- Workflow Builder (formerly Agent Designer) reached GA on Sep 3, 2026, and can import existing A2A and ADK agents. Canvas assistant reached GA Jul 24. Projects GA Sep 4. Gemini Notebook is the NotebookLM-style feature. — [release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)
- Business features per a third-party article: Gemini assistant, Gemini Notebook, connectors, no-code Workflow Builder, prebuilt agents, security and governance. — [Dupple](https://dupple.com/learn/gemini-enterprise-pricing)
- AI developer tools (Antigravity 2.0/CLI, Android Studio) reached GA Aug 18. Antigravity for IDEs was added to Standard, Plus and PAYG on Aug 20. New Standard/Plus subscriptions no longer include Gemini Code Assist; existing entitlements end Mar 31, 2027. — [release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)
- Models in the app: Gemini 4 Argon (Oct 13), Gemini 4 Carbon and Hydrogen GA (Nov 10-12), Claude Opus 5.5 and Sonnet 5.5 (Oct 15). — [release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)
- Granular IAM for apps and data stores (Sep 28). Single-user quota limits GA (Oct 22). — [release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)

### Inferences
- The release-notes summary only covered Jul 16 to Nov 13, 2026 (and was truncated), so launches earlier in 2026 are not covered here.

### Gaps
- Agent Gallery appears as "Agent Marketplace" in the docs; I did not confirm whether these are the same feature.
- Deep Research and Data Insights per-edition availability not confirmed.

## Free tier, trials and minimum seats

### Takeaway
There is no confirmed free tier. Business has a self-serve free trial (length not found), and Pay-as-you-go may allow starting with 1 seat. No higher minimum seat count was found except Frontline's 150.

### Cited Findings
- Google's help page links to a Business-edition free trial, with no length or terms. — [Google support](https://support.google.com/g/answer/16547364?hl=en)
- Minimums: Business and Standard and Plus 1+ users; Frontline 150+ (as add-on to Standard/Plus); PAYG 1 seat to start. — [editions doc](https://docs.cloud.google.com/gemini/enterprise/docs/editions)

### Gaps
- Trial length; whether any perpetual free tier exists (none found).

## Regions and data residency

### Cited Findings
- Data residency options listed: us, eu, global. — [editions doc](https://docs.cloud.google.com/gemini/enterprise/docs/editions)
- Data residency controls and VPC-SC/CMEK are attributed to Standard/Plus only by the third-party article. — [Dupple](https://dupple.com/learn/gemini-enterprise-pricing)
- Gemini 2.5 Pro was discontinued in Canada and Japan on Oct 20. — [release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)

### Gaps
- Per-edition regions; Canadian data residency (relevant to the project owner) not confirmed.

## Relationship to Agentspace, Vertex AI, Agent Engine and ADK

### Takeaway
At Cloud Next 2026 (Apr 22), Agentspace was folded into Gemini Enterprise and Vertex AI was consolidated into the "Gemini Enterprise Agent Platform". Vertex AI Agent Engine is now Agent Runtime. ADK agents can be registered into the Gemini Enterprise app by admins.

### Cited Findings
- Vertex AI was rebranded into Gemini Enterprise Agent Platform; Agentspace was absorbed into Gemini Enterprise; Vertex AI Studio became Agent Studio and Agent Engine became Agent Runtime. — [Google Cloud blog](https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise-agent-platform); [Agent Platform release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes); [TNW](https://thenextweb.com/news/google-cloud-next-ai-agents-agentic-era)
- Admins can register ADK agents hosted on Agent Engine in a Gemini Enterprise app via console or REST API, including cross-project agents. — [Register ADK agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)
- A2A and A2UI agent registration GA Aug 17; 3-legged OAuth for ADK A2A agents on Agent Runtime GA Nov 13. Agent Starter Pack says A2A agents on Agent Engine are not yet supported for its register command. — [release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes); [Agent Starter Pack](https://googlecloudplatform.github.io/agent-starter-pack/cli/register_gemini_enterprise.html)

### Inferences (for the NovaMart RAG prototype)
- The prototype's pinned stack (ADK + Gemini free AI Studio key, run via adk web/run) needs none of this. Registering an ADK agent in Gemini Enterprise requires a deployed Agent Runtime agent, a Google Cloud project with billing, and a Gemini Enterprise app (paid seat or PAYG), so it is an optional later deployment path, not a free-tier option.
- Gemini Enterprise's own search/connectors would replace the hand-rolled numpy retrieval, which the project's architecture rules out.

### Gaps
- Agent Runtime pricing; exact Vertex-to-Agent-Platform name mapping beyond the sources above.
