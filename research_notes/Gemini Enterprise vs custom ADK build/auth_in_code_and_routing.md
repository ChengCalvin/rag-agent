# Gemini Enterprise: per-user authorization in code and deterministic routing / confidence gating (as of 2026-11-24)

Method note: about 16 tool calls. Fetch summaries were produced by a small model, so wording is paraphrased unless quoted. This note only closes gaps left by `agents_extensibility.md` and `connectors_permissions.md`. It corrects one earlier status (A2A registration is now GA) and adds dated launch stages from the release notes.

## 1. How does the end user's identity reach ADK tool code on Agent Runtime, and can the model be kept from supplying it?

### Takeaway
By default it does not reach the code at all: the accepted answer in the ADK maintainers' discussion says Gemini Enterprise calls Agent Runtime with its own service identity and passes no end-user information. Identity arrives only if an admin configures a tool authorization (OAuth), after which the user's access token is placed in ADK session state and read in code. The token is written by the platform into session state, not through a model-visible tool argument, but no official page states "the LLM cannot supply or alter it". That guarantee comes from your own tool design (read from `tool_context`, never from tool arguments).

### Cited Findings
- Official page says only that "ADK agents receive the user's email address from Gemini Enterprise" for personalization and permissions. It does not describe session state keys, `tool_context`, `user_id`, or how a token reaches agent code. Registration REST uses `v1alpha`. No GA/Preview label on the page. — [Register ADK agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)
- Conflict on the email: the ADK maintainers' discussion, accepted answer (April 2026), says that by default Gemini Enterprise calls Agent Engine with its own service identity and "passes no end-user information"; to get the user you configure a tool authorization. With Entra ID, you create an app registration and attach it to the authorization, then Gemini Enterprise passes the user's Entra access token and the agent can inspect its claims. With Google APIs, the AAAuth helper can pass a workforce federation token that lets the agent act as the user "but does not identify them". This conflicts with the registration page's blanket email statement; the discussion is more specific. — [adk-python discussion 3488](https://github.com/google/adk-python/discussions/3488)
- Same discussion, January 2026 maintainer comment: Gemini Enterprise forwards the user's access token into session state, no OIDC scheme is needed, and ADK lacks built-in support for injecting it into tool calls (developers add it). An earlier auto-generated reply (flagged experimental) suggested decoding an ID token from `tool_context.auth_response` without signature verification; treat as low confidence. Any claim decoding must verify signatures in production. — [adk-python discussion 3488](https://github.com/google/adk-python/discussions/3488)
- Google-hosted sample (GoogleCloudPlatform iam-federation-tools) says tools read the forwarded access token from `context.session.state`, exposed via a custom `GeminiEnterpriseDelegatedAuthProvider` that turns it into an ADK `AuthCredential`, wired in code through an auth scheme on the toolset. Page does not name the state key or authorization ID, and does not explicitly say the model never sees it. Community-hosted, lower confidence. — [aaauth-adk-credentials](https://googlecloudplatform.github.io/iam-federation-tools/aaauth-adk-credentials)
- A search summary of a community wrapper (`GeminiEnterpriseAuthorizedTool`) says it pulls the token from session state keyed by the authorization ID and injects it into the call, else returns "authorization required". Snippet only, lower confidence. — [search result via aaauth page](https://googlecloudplatform.github.io/iam-federation-tools/aaauth-adk-credentials)
- ADK context docs: `ReadonlyContext` exposes `user_id` and `state`; `Context` can read/write state and has `request_credential` / `get_auth_response`; framework "passes the relevant contextual information implicitly to your agent code, callbacks, and tools". The page does not say whether the model can influence `user_id` or state prefixes, nor that context is hidden from the model. — [ADK context](https://adk.dev/context/)
- Forum thread: asking the root agent to pass `user_id` to an AgentTool as an argument did not work; user fell back to state set at session creation. Anecdotal. — [discuss.google.dev thread](https://discuss.google.dev/t/how-to-pass-user-id-from-root-agent-to-agenttool/246552) (snippet only)
- Agent Runtime page: no information on `user_id` handling. — [Agent Runtime](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime)
- Known issue: A2A or ADK agents needing user OAuth cannot continue the same run after authentication; authenticate first, then start a new run (Workflow Builder context). — [Workflow Builder known issues](https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder/known-issues)
- Agent Identity + auth manager 3-legged OAuth for A2A agents built with ADK on Agent Runtime reached GA on 2026-11-13. — [Release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)

### Inferences
- Pattern that preserves your invariant: a `before_tool_callback` or tool body reads the token from `tool_context.state` (written by platform), validates it (signature/tokeninfo), derives the customer principal, and ignores any identity-like model-supplied argument. The platform makes this possible; it does not make it automatic. Your existing code-side principal logic carries over, but the principal source changes from your own session creation to a platform-forwarded token.
- Because the token is a Workforce/Google or Entra token, mapping it to a NovaMart customer or order owner is still your code's job. If end customers are not workforce identities (see earlier note), Gemini Enterprise's identity model does not fit.
- Per-user identity depends on admin-configured authorization; without it the agent is effectively anonymous. That is a deployment-time failure mode to test (fail closed when no token).

### Gaps
- No official doc naming the exact session-state key, how `user_id` on Agent Runtime sessions is set when invoked from Gemini Enterprise, or whether it is the user's identity or a service identity.
- No official statement that the LLM cannot supply or alter the forwarded credential or state.
- Conflict between "email is passed" (registration page) and "no end-user info by default" (maintainer discussion) is unresolved; needs a live test.

## 2. Can a custom MCP server or A2A agent make per-user authorization decisions server-side, and what claims does it get?

### Takeaway
Yes. Both receive the user's OAuth token in the `Authorization` header, so the server can validate it and decide per user. Neither page documents token claims; claims depend on your IdP and the scopes you configure. The A2A path also gets a Google-signed service ID token (Cloud Run only), which is consumed by Cloud Run, not your code.

### Cited Findings
- Custom MCP: Gemini Enterprise sends `X-Serverless-Authorization` (Google-signed ID token for the Gemini Enterprise service agent, only on default `.run.app` URLs) and `Authorization` ("Preserves the user's OAuth token intact"). Scopes are configured in the OAuth settings and requested during user authorization. Page does not describe token claims, does not say the model cannot alter the token, and does not state GA. — [Set up custom MCP server](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/custom-mcp-server/set-up-custom-mcp-server)
- Custom MCP server data stores: Public Preview July 22, 2026 (unauthenticated variant), GA August 7, 2026; `citation_mappings` GA Oct 16; VPC connectivity and static IP egress GA Oct 27. — [Release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)
- A2A: with OAuth configured, `Authorization` carries `Bearer USER_OAUTH_TOKEN` (access or ID token); Cloud Run passes it through to the container. The doc lists no claims beyond the service token's audience (your agent URL) and service agent identity. Scopes set on the authorization resource; Agent Runtime-hosted agents need `cloud-platform`. Google `ya29` access tokens are opaque; validate via tokeninfo (`aud`, `scope`). Doc does not describe in-container validation. `securitySchemes`, `apiKey` and static custom headers are not used/supported. — [Register A2A agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent)
- A2A auth interrupts: agent emits `adk_request_credential`, `A2aAgentExecutor` converts to `TASK_STATE_AUTH_REQUIRED`; Gemini Enterprise prompts sign-in and resumes. Supports A2A v0.3 streaming. No timeouts documented. — [Register A2A agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent)
- Registering A2UI and A2A agents reached GA on Aug 17, 2026 ("generally available instead of Public Preview"). This supersedes the earlier note's "Preview" label (earlier note's page predates it). — [Release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)
- Governance for agents and MCP servers (import from Agent Registry) GA June 25, 2026. — [Release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)

### Inferences
- A custom MCP server is the closest platform-sanctioned equivalent to "authorization enforced in code with a principal the model never supplies": the principal is the validated bearer token on the HTTP request, outside the model's tool arguments. Trade-off: Gemini Enterprise's own LLM then chooses which tools to call and in what order, so the fixed 5-agent pipeline is not preserved.
- Same pattern in an ADK agent registered via Agent Runtime keeps the pipeline but depends on the session-state hand-off in section 1.

### Gaps
- Token claim set (email, sub, groups) delivered per IdP not documented; test with your IdP.
- Whether MCP tool arguments can be overridden by the model is inherent to MCP; no Google statement on argument-vs-header trust.

## 3. Do ADK callbacks, SequentialAgent, LoopAgent, custom BaseAgent, escalate work unchanged on Agent Runtime and in Gemini Enterprise? Limits?

### Takeaway
No official statement either way. The registered ADK agent is the deployed ADK app, so code constructs should run as written, but I found no official documentation confirming each construct, no timeout figures, and nothing on how intermediate events are displayed in the Gemini Enterprise UI. Treat as unverified; requires a proof-of-concept.

### Cited Findings
- Registration is GA for ADK agents on Agent Runtime (April 20, 2026 entry, including cross-project agents). — [Release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)
- Registration page states no platform timeout values; advises explicit connection timeouts and bounded retries so slow dependencies do not cause turn timeouts. Streaming behavior not covered. — [Register ADK agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)
- Agent Runtime page: ADK listed under "Full integration" ("Features are integrated to work across the framework, Agent Runtime, and broader Google Cloud ecosystem"); does not enumerate supported ADK features, callbacks, or workflow agents; points to a separate Quota and system limits page (not fetched). Only A2A multi-agent capability labeled preview there. — [Agent Runtime](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime)
- ADK semantics (framework-level, not Gemini Enterprise-specific): LoopAgent runs until a sub-agent escalates or `max_iterations`; a LoopAgent does not transfer control back to a parent LlmAgent, so place it as a sibling within a SequentialAgent to act on results. ParallelAgent events may interleave. — [ADK multi-agents](https://google.github.io/adk-docs/agents/multi-agents) (via search snippet and Java API ref)
- A search for how Gemini Enterprise surfaces intermediate sub-agent events returned nothing. — (no source)
- Workflow Builder "existing agent steps" support only ADK and A2A registered agents and clarifying questions only through A2A `input-required` or ADK `RequestInput`. — [Workflow Builder known issues](https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder/known-issues)

### Inferences
- Deterministic code (a custom `BaseAgent` computing the composite, a `before_tool_callback` guard) is plain Python inside the ADK app and has no obvious platform dependency, so it should survive deployment; the unknowns are UX (intermediate event display, latency per turn) not logic.

### Gaps
- No evidence on timeout for a chat turn, streaming of intermediate events, or UI rendering of multi-agent pipelines. Quota and system limits page not read.
- No ADK-callback-specific Gemini Enterprise documentation found; recommend a one-day PoC.

## 4. Can Workflow Builder express deterministic branching, loops, thresholds on a computed score? Step types?

### Takeaway
Only partly. It is GA, with three documented step types (Gemini Agent, Condition, Request info), no code step, and loop behavior documented only as a feature mention. A Condition can compare a variable to a value ("greater than" is cited as an example), so a threshold on a numeric field is plausible, but the numeric would have to be produced by an agent step, an MCP tool, or an imported ADK/A2A agent.

### Cited Findings
- Step table: Gemini Agent (plain text or structured JSON output), Condition (logical statements controlling flow; example operators "contains", "equals", "greater than"; AND/OR combinable), Request info (human input). Triggers (manual, schedule, event) are separate. Features text says "Add conditional branching, data filtering, and loops", but no loop step appears in the table; no code step; no expression/threshold syntax; no numeric limits; only Gemini 3.0+ supported. — [Workflows overview](https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder/workflow-agents)
- Existing ADK and A2A agents can be imported as steps. — [Release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes); [known issues](https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder/known-issues)
- Known issues: execution timeouts under heavy load; event-triggered workflows with RESOURCE_EXHAUSTED are not retried; the conversational designer cannot add human-in-the-loop approvals, event triggers or "Data filtering" via prompts (add manually). No loop or code issues listed. — [Known issues](https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder/known-issues)
- Edit-workflow doc offers "Add a loop that processes each search result" as an example change request, indicating loops exist in the builder. Search snippet only. — [Edit a workflow](https://docs.cloud.google.cn/gemini/enterprise/docs/workflow-builder/edit-workflow-agent)
- Launch stages: "Workflow Builder (formerly Agent Designer)" GA on Sept 3, 2026; "Workflow agents (GA with allowlist)" June 18, 2026; visual flow builder for existing agents GA Jan 26, 2026. — [Release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)
- Unrelated product: Workspace Studio added "loop over list of items" in June 2026; do not conflate with Workflow Builder. — [Workspace Updates](https://workspaceupdates.googleblog.com/2026/06/introducing-ability-to-loop-over-list-of-items-in-Workspace-Studio.html)

### Inferences
- A retrieval-validator loop with retry-until-confident logic and a weighted composite across several signals mapping to outcomes A-E is not expressible natively; the realistic route is to compute the composite in an imported ADK agent or MCP tool and use Conditions only to branch on its returned fields.
- Branching on an LLM-produced JSON value is deterministic in routing but not in the value itself.

### Gaps
- Loop step semantics (bounds, exit conditions) undocumented in pages read; whether "greater than" works on numbers vs strings not stated.
- Conflicting snippet: June 18 "GA with allowlist" vs Sept 3 plain GA; the later entry is the current state.

## 5. Can Discovery Engine / Gemini Enterprise search expose relevance scores or thresholds usable in a confidence gate?

### Takeaway
The Discovery Engine v1 API's `SearchResult.rankSignals` exposes several numeric signals, but I found no documented score range, cross-query comparability, or cutoff parameter, and nothing showing the Gemini Enterprise assistant UI exposes them. Treat as weak for a calibrated confidence gate.

### Cited Findings
- `SearchResponse.SearchResult.RankSignals` fields (per reference): keyword similarity, semantic relevance/similarity, predicted conversion rate, topicality, document age, custom boosts, default rank, and `custom_signals`; some are ranks rather than scores. Range and comparability not stated. — [Python reference](https://docs.cloud.google.com/python/docs/reference/discoveryengine/latest/google.cloud.discoveryengine_v1.types.SearchResponse.SearchResult.RankSignals) (via search summary)
- From earlier notes: check-grounding citation threshold default 0.6 and grounding score 0-1; `ignoreLowRelevantContent` and `filteringLevel` exist in answer specs. These are API-level, not available inside the Gemini Enterprise chat. — [Check grounding](https://docs.cloud.google.com/generative-ai-app-builder/docs/check-grounding) (earlier note, snippet)
- Release notes portion read (up to ~200k chars) had no entry on a search relevance score. — [Release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)

### Inferences
- A gate on these scores would only work if you call the Discovery Engine API yourself from a tool, and you would need to calibrate thresholds empirically. It would not replace your numeric composite of retrieval, validator, and policy signals.

### Gaps
- Not verified: fetched reference page directly; value ranges; whether rankSignals populate for ingested Gemini Enterprise data stores.

## 6. Status summary (GA/Preview, as of 2026-11-24)

### Takeaway
Most hosting and registration paths are GA now; token-delivery mechanics are the least documented.

### Cited Findings
- ADK agent registration on Agent Runtime: GA (April 20, 2026 release entry). — [Release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)
- A2A (and A2UI) registration: GA (Aug 17, 2026); 3-legged OAuth with Agent Identity auth manager for ADK A2A agents: GA (Nov 13, 2026). — [Release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)
- Custom MCP server data stores: GA (Aug 7, 2026). — [Release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)
- Workflow Builder: GA (Sept 3, 2026). — [Release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)
- Sharing custom registered agents: Public Preview as of Dec 2025 entry; later status not found. — [Release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)
- Tool-authorization resource (OAuth for ADK agents): no explicit launch stage found in the portion read; registration page unlabeled. — [Register ADK agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)

### Inferences
- The "A2A is Preview" statement in `agents_extensibility.md` is outdated; treat A2A registration as GA.

### Gaps
- Final ~16k characters of the release notes (offset 200000) were not read; later entries could change statuses.
