# NovaMart assistant: from prototype to production

Product claims were checked against Google's published pages on 2026-11-24. **TBC** means to be confirmed: not verified, not fact. The registration page is labelled Preview, so details may change.

**Recommendation: hybrid.** Use Gemini Enterprise as the front door and document search, and register the ADK order agent in it as a custom A2A agent, hosted by NovaMart on Cloud Run. Why: search, connectors and the user interface come managed, while order logic, store-level authorization and the refusal rules stay in code we test. **Fallback** if end-user identity cannot reach the agent (see spike): run the ADK agent behind NovaMart's own sign-in (IAP is a candidate, TBC) and limit Gemini Enterprise to document search. **Revisit** if a fully custom build proves cheaper at NovaMart's volume.

## 1. Gemini Enterprise or custom build
- A custom A2A agent is registered by an admin in the console or through the REST API; NovaMart must host and maintain it. [1]
- Custom alone means we own search, connectors and UI. Gemini Enterprise alone would not carry our order rules. Hybrid splits the two.
- Cost: tokens x price. Current paid prices per 1M tokens: gemini-3.6-flash $0.75 in / $3.75 out (promotional, rising to $1.50 / $7.50 on 2027-01-01); gemini-3.5-flash-lite $0.30 / $2.50; gemini-embedding-001 $0.15 in. [2] Cost at 1,000 questions = measured per-question cost x 1,000; the figure comes from owner-run evals (not yet run). Seat pricing: TBC.

## 2. Connecting NovaMart's real data
- Documents: connectors or a custom data source, with document-level access control. The access-control setting is chosen when the data store is created; docs call it "a one-time procedure". [3] Whether it can be changed later: TBC, so decide it first.
- Orders: the agent calls NovaMart's real order API through the one adapter that replaces the prototype's JSON file: read-only scope, per-store filtering, rate limits.
- Policy facts stay in document front-matter, never in code.

## 3. Security and governance
- **Identity-propagation spike (do first).** With OAuth configured, Gemini Enterprise acquires an access or ID token for the signed-in user and sends it in the `Authorization` header; Cloud Run forwards it to the container. [1] Open: can the order API validate that token and enforce store scope itself, rather than trusting the agent? Owners: NovaMart's identity and order-API teams, plus Google support (on Agent Runtime the token authenticates the endpoint; passing it to our code is TBC). Exit: one call where the API returns a different result for two users. Fallback: as above.
- Encryption and residency: CMEK needs a US or EU multi-region app and data store, not global; an applied key cannot be swapped (versions can rotate). [4] Residency for NovaMart's country: TBC against the locations page.
- Data use: the free AI Studio tier may use content to improve products and human reviewers may read it; paid services do not. [2][5] Gemini Enterprise's own terms: TBC. Stay synthetic until contracts are checked.
- Audit records hold access decisions, not message text or customer data.

## 4. Evaluating and monitoring quality
- Re-run the eval sets (quality, security) on every prompt, model or document change; gate releases on pass rate.
- Track per question: calls, cost, route, confidence band, refusals; review a weekly sample of low-confidence answers.
- Re-tune the retrieval threshold when documents change; alert on a rising "nothing found" rate or any out-of-scope order lookup that succeeds.

## Prototype limits (simulated, not implemented)
| Simulated | Production replacement |
|---|---|
| Persona via `NOVAMART_USER`, not authentication | Workforce sign-in and forwarded user token |
| Orders in a JSON file | Real order API enforcing store scope |
| Local numpy index, synthetic documents | Managed search over connected, access-controlled data |
| Local `adk web`, free key | Hosted agent, paid terms, monitoring |
| Combined order-and-policy questions: order path only, policy part not answered | Run both paths and merge (not decided) |

Sources, all read 2026-11-24: [1] docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent; [2] aistudio.google.com/docs/pricing; [3] docs.cloud.google.com/gemini/enterprise/docs/identity; [4] docs.cloud.google.com/gemini/enterprise/docs/cmek; [5] aistudio.google.com/docs/terms.
