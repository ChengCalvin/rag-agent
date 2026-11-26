# NovaMart assistant: from prototype to production

This is a proposal; none of it is built. It assumes the users are NovaMart store staff. **TBC** means not yet verified.

## 1. Gemini Enterprise or custom build
**Recommendation: a custom ADK agent on Cloud Run, with Gemini Enterprise as an optional front end.** One core serves NovaMart's apps over HTTPS and Gemini Enterprise over A2A.
- **Why custom:** store-level access, refusals and confidence rules stay in code we test. Workflow Builder documents agent, condition and human-input steps, and no custom-code step. [1]
- **Why keep Gemini Enterprise:** it offers staff a ready interface. It can register an A2A agent hosted anywhere [2]; release notes say this is generally available, though the setup page still says Preview. [3] Registering as an ADK agent instead requires Agent Runtime. [4]
- **Trade-off:** we own more engineering and operations.
- **What would change it:** if staff already use Gemini Enterprise and the identity test passes, make it the main front end and build no UI.
- **Cost:** model tokens averaged about $0.88 per 1,000 questions on gemini-3.5-flash-lite (18 test questions, paid list price [5]). Hosting, seats (TBC) and engineering are extra.

## 2. Connecting NovaMart's real data
- **Documents:** name an owner for each policy source. Ingest read-only with audience metadata, re-index changes, remove deletions, and escalate contradictions to the owner.
- **Search:** keep our index if it meets scale and freshness needs. Move to managed search if it returns usable relevance scores (TBC) and supports role filtering; otherwise the refusal and confidence rules need redesign.
- **Access settings:** decide before creating data stores. For Cloud Storage and BigQuery sources, Google calls turning on access control "a one-time procedure". [6]
- **Orders:** replace the JSON adapter with a read-only, rate-limited client for NovaMart's order API. No model-written queries.

## 3. Security and governance
- **First, test identity end to end.** Replace the simulated persona with company sign-in. Our service validates each token and derives role and store in code, never from the model or message. Gemini Enterprise can send the user's token to an A2A agent. [2]
  - **Open question:** can the order API validate that identity and enforce store scope itself? NovaMart's identity and order-API owners must answer, with Google support for the hand-off.
  - **Exit test:** two users get different, correctly limited results; no valid token gets nothing.
  - **Fallback:** if the hand-off fails, use NovaMart's own sign-in and app, with order lookups off in Gemini Enterprise. If the API cannot enforce scope, keep lookups off until it can or NovaMart accepts our service as the only control.
- **Release-blocking tests:** wrong-app or expired tokens, other-store orders, manager-only documents, transferred or departed staff, prompt injection, leaked customer data.
- **Data protection:** use paid services. On the free tier Google may use content and people may review it; paid prompts are not used to improve products but are logged for a limited time for abuse detection. [7] Confirm residency, privacy law, retention and encryption keys (TBC).
- **Governance:** least privilege, managed secrets, access audits without message text or customer data, and named owners for incidents and changes.

## 4. Evaluating and monitoring quality
- **Before release:** collect real staff questions with expected answers, including refusals, and hold some out. Run quality and security evals on every model, prompt, document or threshold change. Any security failure blocks release; agree the quality bar with NovaMart.
- **In use:** track route, refusals, retrieval score, confidence, latency, errors and cost. Alert on any out-of-scope access.
- **Human review:** check thumbs-down, low-confidence answers and a random sample, since confident answers can be wrong. Redact and limit stored text. People approve fixes; confirmed failures become eval cases.
- **Outcomes:** measure correct-answer rate, escalations to operations and staff time saved against today's baseline.
- **Rollout:** one pilot group first, with agreed criteria to expand or roll back.

**Prototype today:** simulated sign-in, orders in a JSON file, synthetic documents with local numpy search, local `adk web` on a free key. Combined order-and-policy questions get only the order answer.

**Confirm with NovaMart:** users, roles, stores and countries; where staff should use it; any current Gemini Enterprise use; which answers need human approval.

<sub>Google pages checked 2026-11-25; paths are under docs.cloud.google.com/gemini/enterprise/docs unless a domain is shown. [1] /workflow-builder/workflow-agents [2] /register-and-manage-an-a2a-agent [3] /release-notes (17 August 2026) [4] /register-and-manage-an-adk-agent [5] aistudio.google.com/docs/pricing [6] /identity [7] aistudio.google.com/docs/terms</sub>
