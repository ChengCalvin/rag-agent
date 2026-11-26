# Gemini Enterprise agent-building and extensibility (as of 2026-11-24)

Naming note: In April 2026 Vertex AI / Agent Builder was rebranded "Gemini Enterprise Agent Platform"; "Vertex AI Agent Engine" is now "Agent Runtime" (Sessions and Memory Bank keep their names). Agent Designer appears to now be called "Workflow Builder" in the docs. Older blog posts and the customer's question wording ("Agent Engine", "Agent Designer") map to these. Sources: [Release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes), [Agent Runtime docs](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime). One search summary said a rename table exists in the release notes; my fetch of the release notes did not show it (only the first 100k of 139k chars read), so the exact mapping is from search snippets.

## 1. Can Gemini Enterprise call custom tools / external APIs, and how?

### Takeaway
Yes, via four routes: (a) a custom MCP server connector (per-user OAuth, StreamableHTTP only), (b) an ADK agent hosted on Agent Runtime and registered in the app, (c) an A2A agent you host (Preview), (d) MCP/connector actions inside Workflow Builder. I found no documented "OpenAPI tool" route for Gemini Enterprise itself; OpenAPI tooling exists inside ADK code (see Gaps). For the customer's three tools, the realistic options are wrapping them as an MCP server or hosting the existing ADK agent.

### Cited Findings
- Admins register ADK agents hosted on Agent Runtime via console (Agents > Add agent > Custom agent via Agent Runtime) or REST using the reasoning-engine resource path; REST examples use `v1alpha`. Requires Gemini Enterprise Admin role, Discovery Engine API, existing app; agent must stay hosted on Agent Runtime — [Register ADK agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)
- Custom A2A agents can be registered (Agents > Add agent > Custom agent via A2A). This feature is labeled **Preview** (Pre-GA terms). Gemini Enterprise supports A2A v0.3 streaming; ADK agents on Agent Runtime should list both 1.0 and 0.3 interfaces on the agent card — [Register A2A agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent)
- A2A limits: agent card `securitySchemes`/`security` fields are ignored; `apiKey` scheme unsupported; cannot add static API keys or custom headers; traffic does not pass through Agent Gateway — [Register A2A agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent)
- Custom MCP server data store: auth is OAuth 2.0 or none; only StreamableHTTP (no SSE); HTTPS with publicly trusted cert (unless via Agent Gateway); max 100 actions enabled at once (one third-party guide says 150 — conflicting); all actions off by default and must be enabled; every action call requires user confirmation unless the tool sets `readOnlyHint`. Needs `roles/discoveryengine.editor` and an org-policy override (a constraint blocks custom MCP data stores by default). Page does not state GA/Preview — [Custom MCP server setup](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/custom-mcp-server/set-up-custom-mcp-server); 150-tool figure from [Medium guide](https://medium.com/google-cloud/how-to-configure-gemini-enterprise-to-connect-to-a-custom-mcp-server-2e28adc96420) (via search snippet, not fetched)
- Private/VPC MCP servers can be routed through Agent Gateway (us-central1, europe-west1) and imported via Agent Registry — [Import MCP servers from Agent Registry](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/custom-mcp-server/import-govern-mcp-server-agent-registry) (search snippet only)
- Agent types in the Gemini Enterprise Agents page: Workflow Builder agents, pre-built (Core Assistant, Deep Research), custom ADK, A2A, Dialogflow agents — [Agents overview](https://docs.cloud.google.com/gemini/enterprise/docs/agents-overview)
- Each registration consumes pooled daily agent-creation quota: Standard license 1/user/day, Plus 10, Frontline 0; CI/CD rollouts can hit 429 — [Register ADK agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)
- Agent Runtime supports any containerizable framework; ADK full integration (Python `adk` CLI, Go), LangGraph/LangChain/AG2/LlamaIndex via SDK templates, CrewAI/custom via custom templates; deploy by prebuilt image or Dockerfile — [Agent Runtime](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime)

### Inferences
- The customer's three Python tools can be exposed either as ADK function tools inside an Agent Runtime-hosted agent (registered via "Custom agent via Agent Runtime") or as a custom MCP server. The former preserves their ADK pipeline; the latter makes Gemini Enterprise's own LLM decide when to call tools (loses fixed pipeline).
- The per-call confirmation default on MCP actions affects UX for read tools like get_order_status; `readOnlyHint` is the documented fix.

### Gaps
- No documented OpenAPI-spec import for Gemini Enterprise itself found. (ADK has OpenAPI toolsets in code; not verified here.)
- GA/Preview status of ADK registration and custom MCP connector not stated on their pages.
- Whether A2A-hosted-on-Agent-Runtime is supported conflicts: Google docs describe it (cloud-platform scope required); the Agent Starter Pack CLI doc reportedly says not yet supported ([starter pack](https://googlecloudplatform.github.io/agent-starter-pack/cli/register_gemini_enterprise.html), via snippet).

## 2. Can the end user's identity reach a custom tool/agent so authorization is enforced in code?

### Takeaway
Yes, in three documented forms: user email passed to registered ADK agents; per-user OAuth tokens via a Gemini Enterprise "authorization resource" (ADK/A2A/MCP); and newer Agent Identity + Auth Manager 3-legged OAuth. Token delivery details are thin in official docs; the common pattern is reading the token from ADK session state by authorization ID. Note these OAuth tokens are Google-style delegated tokens for downstream resources; the customer must map identity to order ownership in its own tool code.

### Cited Findings
- ADK agents receive the user's email address from Gemini Enterprise, so they can personalize/apply permissions; the page does not describe how the OAuth token is passed to agent code — [Register ADK agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)
- Authorization resource setup: OAuth web client (two Gemini Enterprise redirect URIs), create authorization resource (console or REST with `authorizationId`), reference in `authorizationConfig.toolAuthorizations` as `projects/PROJECT_NUMBER/locations/global/authorizations/AUTH_ID`; recommend `access_type=offline` and `prompt=consent` — [Register ADK agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)
- Community/forum: token is stored under the auth resource ID in ADK session state and tools read it via `tool_context.session.state`; older ADK needed a `before_tool_callback` to inject it; consent popup reportedly worked in local `adk web` but not appeared for a deployed agent in one thread (anecdotal) — [Google dev forum](https://discuss.google.dev/t/applicationintegrationtoolset-oauth/337717), [ADK + Agentspace datastores thread](https://discuss.google.dev/t/adk-agents-with-agentspace-authenticated-datastores/265466) (search snippets only)
- A2A: end-user OAuth token sent in `Authorization` header when OAuth configured; `X-Serverless-Authorization` carries the Discovery Engine service agent ID token for `.run.app` URLs; Agent Runtime A2A agents need `cloud-platform` scope; Google `ya29` tokens are opaque, so validate via tokeninfo — [Register A2A agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent)
- A2A + Agent Identity auth manager (3-legged OAuth, ADK agents only): Gemini Enterprise handles consent and resumption; requires specific package versions, `GcpAuthProvider` in runner builder, `A2aAgentExecutor`, `roles/agentidentity.user` — [Register A2A agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent)
- Custom MCP: per-user OAuth token preserved in `Authorization` header (on Cloud Run) alongside service-agent ID token — [Custom MCP setup](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/custom-mcp-server/set-up-custom-mcp-server)
- Agent Identity codelab: agent runs under its own SPIFFE-backed identity, requests user's delegated token from Auth Manager at runtime; deployed with `adk deploy agent_engine` and `AGENT_IDENTITY`; status not stated — [Codelab](https://codelabs.developers.google.com/agent-identity-auth-manager)

### Inferences
- For order-lookup authorization, the safest design is: take the verified user email (or validated token via tokeninfo/IdP) and enforce ownership in tool code, as the prototype already does. The user email being supplied by Gemini Enterprise is likely sufficient for identity, but Google's docs do not say the email is cryptographically verifiable by the agent; treat as trusted-platform-supplied.
- If the customer's identity provider is not Google, MCP custom connector OAuth (arbitrary IdP endpoints) is the cleaner fit than Google authorization resources (docs focus on Google Cloud scopes).

### Gaps
- Official doc on exactly how ADK on Agent Runtime exposes the user email/token (state key names, session `user_id` semantics) not found.
- Preview/GA of Agent Identity Auth Manager not stated.

## 3. Can an ADK multi-agent pipeline (sequential/loop, callbacks, deterministic routing, gating) be hosted on Agent Runtime and surfaced in Gemini Enterprise? Limits?

### Takeaway
Yes in principle: Gemini Enterprise registers a whole ADK agent (root agent) hosted on Agent Runtime, and the code runs as written, so SequentialAgent/LoopAgent/callbacks should execute unchanged. Google docs offer only performance cautions, not structural restrictions; I found no documented limit on agent topology. This is not independently confirmed by an official example of a Sequential+Loop pipeline.

### Cited Findings
- Registered ADK agent is the deployed reasoning engine; Google recommends limiting sequential sub-agent hops, `AgentTool(..., skip_summarization=True)`, setting `min_instances`, `resource_limits`, `container_concurrency`, pinning `google-adk`, `google-cloud-aiplatform`, `cloudpickle` versions, using the `global` Gemini endpoint, and explicit timeouts/bounded retries on external tools — [Register ADK agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)
- Location compatibility: `global` app works with any region; `us` app needs `us-` regions; `eu` app needs `europe-` regions — same page
- Agent Runtime supports long-running operations up to 7 days (release notes / search summary) — [Release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)
- ADK 2.6.0+ agents on Agent Runtime can emit OTel GenAI metrics to Cloud Monitoring (Aug 2026) — [Release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)

### Inferences
- Because a 5-agent fixed pipeline with a retrieval-validator loop adds LLM hops, latency inside the Gemini Enterprise chat UI is the main risk; Google's own guidance warns about sequential hops.
- Hand-rolled numpy retrieval and the synthetic corpus must be packaged with the deployment (container/bundle) or loaded from storage; Agent Runtime accepts custom containers, so this is feasible. Not verified for large in-memory arrays.

### Gaps
- No official statement that LoopAgent/SequentialAgent outputs (intermediate agent events) are or are not surfaced in the Gemini Enterprise UI; no streaming/timeout limit figures found for registered agents.
- No documented request timeout for chat turns in Gemini Enterprise.

## 4. Can the no-code builder express deterministic routing, loops, gating?

### Takeaway
Partly. Workflow Builder (formerly Agent Designer) mixes deterministic steps with Gemini Agent steps; it has Condition (branching) steps with AND/OR, human "Request info" steps, and MCP/connector steps. The overview mentions loops and data filtering, but the step table lists only Condition, so loop support is unconfirmed. It has no code step documented and Gemini 3.0+ only for agent steps. It cannot replicate a code-enforced access control or confidence gating beyond simple conditions.

### Cited Findings
- Workflow Builder overview: workflows built from triggers, steps, actions; can be deterministic or non-deterministic; chat agents primarily non-deterministic; preview/simulate and schedule — [Workflow Builder overview](https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder)
- Step types: Gemini Agent step (instructions, knowledge, connected apps, model; Gemini 3.0+ only; text or JSON-schema structured output), Condition step (variable/operator/value, AND/OR), Request info (human input); MCP servers usable as workflow steps or as tools for Gemini Agent steps; write actions require human review — [Workflows overview](https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder/workflow-agents)
- Overview text mentions "conditional branching, data filtering, and loops" but the step table lists only conditions; page mentions no code step, no numeric limits; known issues include execution timeouts under heavy load — same page
- Admin must enable Workflow Builder; actions limited to admin-provisioned connectors/tools — [Agents overview](https://docs.cloud.google.com/gemini/enterprise/docs/agents-overview)
- Press (April 2026) said Agent Designer would be generally available "in the next few weeks"; docs pages I fetched do not state status — [Computerworld](https://www.computerworld.com/article/4161990/gemini-enterprise-update-brings-ai-agents-into-collaborative-workflows.html) (snippet only)

### Inferences
- Structured JSON output from a Gemini Agent step plus a Condition step could approximate confidence gating, but the confidence value would be LLM-produced, not code-computed; custom scoring needs an MCP/ADK tool.

### Gaps
- Current GA/Preview status of Workflow Builder, existence of loop step, and Agent Studio (a separate low-code builder for technical teams, reported by press) not verified from primary docs.

## 5. Deployment alternatives, local vs deployed differences, sessions/memory, pricing

### Takeaway
Gemini Enterprise registration requires the ADK agent on Agent Runtime (ADK) or reachable as an A2A endpoint (Cloud Run/GKE/other). Cloud Run/GKE are valid for standalone hosting or A2A registration, not direct ADK registration. Moving from `adk web/run` adds packaging, IAM, managed session service, and OAuth setup.

### Cited Findings
- ADK deploy options: Agent Runtime (most managed), Cloud Run (container), GKE (more control, open models), other containers (offline) — [ADK deploy](https://adk.dev/deploy/)
- On Cloud Run, without `--session_service_uri`/`--artifact_service_uri` the deployed container falls back to in-memory services (state lost on instance recycling); `agentengine://<id>` URI can use managed sessions — [ADK Cloud Run](https://adk.dev/deploy/cloud-run/) (via search snippet)
- Agent Runtime natively manages sessions (VertexAiSessionService) and Memory Bank; Memory Bank profiles GA (Jul 15, 2026); console memory controls (Nov 6) — [Release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)
- Deferred tier for autonomous agent scheduling GA Nov 16, 2026 for ADK (google-adk 2.10.0+), Agent Runtime/Cloud Run/GKE, 50% inference discount — [Release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)
- Pricing (Google-hosted SKU PDF via search snippet): unified SKUs from June 17, 2026: compute $0.085 per vCPU-hour, memory $0.009 per GiB-hour, storage $0.30 per GiB-month; legacy runtime compute $0.0864/vCPU-hr; Sessions/Memory Bank metering begins Sept 1, 2026 — [Pricing PDF](https://services.google.com/fh/files/emails/b_502770571_gemini_enterprise_agent_platform_pricing.pdf), [Pricing page](https://cloud.google.com/products/gemini-enterprise-agent-platform/pricing)
- Third-party summary (July 2026) agrees on $0.085/$0.009/$0.30 and says sessions/memory bank writes metered per vCPU-hour per 1M writes; free monthly tier amount unstated; author flags unit ambiguity — [ecorpit](https://ecorpit.com/gemini-enterprise-agent-platform-cost-breakdown-2026/)
- Model inference (Gemini calls) is billed separately; project pins a free AI Studio key, which does not apply on Agent Runtime/Vertex — inference from [Register ADK agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent) (agent uses Gemini on Google Cloud)

### Inferences
- The prototype's constraint "free AI Studio key, not Vertex" is incompatible with Agent Runtime hosting; a migration means switching to Vertex AI/Agent Platform Gemini auth and a billed GCP project plus a Gemini Enterprise license for registration.
- Agent Runtime billing is by active compute, so a low-traffic pilot should be cheap relative to Gemini Enterprise seats; the exact cost needs the calculator.

### Gaps
- Gemini Enterprise per-seat edition pricing not covered here (other researchers).
- Primary pricing page was too large to fetch; rates are from snippets/secondary source. Free tier amount not found.
- No official Cloud Run vs Agent Runtime side-by-side with limits (timeouts, instance caps) found.

## 6. Guardrails, Model Armor, evaluation, observability

### Takeaway
Model Armor is not automatic for registered ADK/A2A agents; apply via Agent Gateway (ADK streamQuery only) or call the API in code. Evaluation and observability are GA on Agent Platform, with ADK integration.

### Cited Findings
- Console Model Armor settings "don't automatically protect ADK agents"; developers must configure it via REST in agent code; same for A2A — [Register ADK agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent), [Register A2A agents](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent)
- Model Armor via Agent Gateway ingress screens only `reasoningEngines.streamQuery` for ADK agents on Agent Runtime; non-ADK (e.g., LangChain) payloads are not screened; streaming sanitization only for ADK via streamQuery; egress screened by separate templates — [Model Armor + Vertex integration](https://docs.cloud.google.com/model-armor/model-armor-vertex-integration) (snippet)
- Agent Gateway: Cross-cloud Model Armor Nov 11 (Limited Preview); Agent Gateway for GKE Preview Nov 12; Cloud Trace integration Preview Sept 30; semantic governance policies from Aug 2026 — [Release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)
- Agent and Model Evaluations GA (July 31, 2026), accessible via SDK, agents-cli, console, and directly from ADK — [Google Developers Blog](https://developers.googleblog.com/agent-and-model-evaluations-in-gemini-enterprise-agent-platform-are-now-ga/) (snippet)
- Agent Observability reported GA (~June 24, 2026); Cloud Trace/Logging collected by default for ADK deployments; inference request metadata logging GA Oct 30; Feedback service Preview Jul 29 — [Release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes), [Agent Platform optimize](https://docs.cloud.google.com/gemini-enterprise-agent-platform/optimize)

### Inferences
- The prototype's code-based security guard remains necessary and complementary; Model Armor adds prompt-injection/PII filtering but does not replace tool-side authorization.

### Gaps
- Gemini safety-settings specifics (per-category thresholds on Vertex) not researched.
- Whether Agent Gateway ingress works for agents registered into Gemini Enterprise is unclear (A2A docs say no; ADK-registered not stated).
