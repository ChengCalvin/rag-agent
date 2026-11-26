# Custom-build deployment paths for a Google ADK (Python) agent (as of Nov 2026): Agent Runtime vs Cloud Run vs GKE

Research scope note: ~20 tool calls; fetched pages were summarized by a small model, so exact flag lists should be re-checked against the CLI reference before implementation. ADK docs have moved from google.github.io/adk-docs to adk.dev (301 redirect). GA/Preview labels were mostly NOT shown on the pages fetched; where unlabeled, I say so rather than assume GA.

## 1. Deploy mechanics per path (adk deploy agent_engine / cloud_run / gke, Agents CLI / Agent Starter Pack; packaging, deps, env vars, secrets)

### Takeaway
Three hosting targets are documented by ADK: Agent Runtime (managed; Vertex AI Agent Engine was folded into "Gemini Enterprise Agent Platform"), Cloud Run (container), and GKE (container + Kubernetes, `adk deploy gke` is Python-only). The Agent Starter Pack appears to have been succeeded/wrapped by "Agents CLI" (`agents-cli`), which scaffolds CI/CD + Terraform for all three targets. Local data files (numpy index) ship inside the container/package on Cloud Run/GKE easily; on Agent Runtime the packaging details were not documented on pages I could read (gap).

### Cited Findings
- ADK deploy page lists: Agent Runtime on Agent Platform (fully managed, auto-scaling), Cloud Run (container), GKE (more control, open models), and any container host. The page does not label GA/Preview. — [adk.dev/deploy](https://adk.dev/deploy/)
- Naming: the ADK page says "Agent Runtime on Agent Platform"; the old `agent-engine` URL redirects to `agent-runtime`; REST URL still uses `reasoningEngines` and `aiplatform.googleapis.com`. A May 14, 2026 release note reportedly folded Vertex AI and Agent Builder into "Gemini Enterprise Agent Platform" (from search-engine summary; lower confidence). No release-note entry explicitly announcing an "Agent Engine -> Agent Runtime" rename was found. — [adk.dev/deploy/agent-runtime](https://adk.dev/deploy/agent-runtime/), [release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)
- Agent Runtime (Python): `adk deploy agent_engine --project --region --display_name <agent_folder>`; expected layout `.env`, `__init__.py`, `agent.py`. ADK says deployment builds a container; handling of `.env` is not explained. Called via REST `...:query` / `:streamQuery` on `reasoningEngines/<id>`. ADK docs says Python deploys do not include ADK API server or web UI (Agent Runtime provides the API server). Supported in ADK Python and Go v1.2.0. — [adk.dev/deploy/agent-runtime/deploy](https://adk.dev/deploy/agent-runtime/deploy/), [overview](https://adk.dev/deploy/agent-runtime/)
- Agent Runtime SDK path: `client.agent_engines.create(agent=AdkApp(agent=...), config={requirements:[...], staging_bucket:"gs://...", identity_type: AGENT_IDENTITY})`; needs `google-cloud-aiplatform[agent_engines,adk]>=1.112`; roles `roles/aiplatform.user` and `roles/storage.admin`; deploying auto-creates a managed session resource; USER_ID max 128 chars; quickstart uses Vertex client (project + location), no mention of Gemini API keys. — [Agent Runtime ADK quickstart](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk)
- Agent Runtime is a paid service with a no-cost access tier; pricing on a linked page (not read). — [adk.dev/deploy/agent-runtime](https://adk.dev/deploy/agent-runtime/)
- Cloud Run: `adk deploy cloud_run [ADK_FLAGS] -- [GCLOUD_FLAGS]`; required `--project`, `--region`; options `--service_name`, `--app_name`, `--port` (8000), `--allow_origins`, `--with_ui`, `--session_service_uri`, `--artifact_service_uri`, `--memory_service_uri`, `--temp_folder`. Packages agent code + declared deps + ADK API server; Cloud Build builds it (default compute SA needs `roles/cloudbuild.builds.builder`). Alternative: custom FastAPI `main.py` using `get_fast_api_app()`, Dockerfile on python:3.13-slim, `gcloud run deploy --source .`. — [adk.dev/deploy/cloud-run](https://adk.dev/deploy/cloud-run/)
- Cloud Run env vars shown: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_GENAI_USE_ENTERPRISE=True` (for Vertex path, per the page as summarized; the older name was `GOOGLE_GENAI_USE_VERTEXAI`); API-key path: create `GOOGLE_API_KEY` in Secret Manager, grant `roles/secretmanager.secretAccessor`; page does not explain mounting the secret. — [adk.dev/deploy/cloud-run](https://adk.dev/deploy/cloud-run/)
- GKE: `adk deploy gke --project --cluster_name --region [--service_type ClusterIP|LoadBalancer] [--with_ui] [--log_level] AGENT_PATH` (Python only); needs an existing cluster, kubectl, gcloud, Cloud Build/Container Registry/GKE APIs, and roles container.developer, storage.objectViewer, artifactregistry.createOnPushWriter, logging.logWriter. Generated manifest uses `default` KSA; for Vertex models grant `roles/aiplatform.user` to the Workload Identity principal; AI Studio key users can skip that. Docs do not describe env var/secret passing for `adk deploy gke`. Gotcha: copied-in SQLite `sessions.db` is read-only in image; use `.dockerignore`. — [adk.dev/deploy/gke](https://adk.dev/deploy/gke/)
- Agents CLI: `agents-cli scaffold enhance --deployment-target agent_runtime` adds `.cloudbuild/`, `deployment/` (Terraform), `app/`, `tests/`, `Makefile`, `GEMINI.md` to an existing ADK project; `agents-cli deploy` builds/pushes/deploys per target in `pyproject.toml`; `agents-cli infra single-project` provisions telemetry (prompt-response logging, BigQuery). Release status not labeled. — [adk.dev agents-cli](https://adk.dev/deploy/agent-runtime/agents-cli/)
- Agents CLI deployment guide: targets `agent_runtime` (scaffolded Dockerfile, Agent Runtime builds/runs container), `cloud_run` (`gcloud run deploy` from source), `gke` (Terraform, Cloud Build, `kubectl set image`). Cloud Run: private by default; `--iap`, `--ingress internal`; new projects run as Agent Identity principal. On Agent Runtime with Agent Identity, first deploy starts image before env vars/secrets are applied so the image must boot without them. `--build-args` supported for Agent Runtime. — [google.github.io/agents-cli deployment](https://google.github.io/agents-cli/guide/deployment/index.md)
- Search snippet: adk.dev docs use `--deployment-target agent_engine` while agents-cli uses `agent_runtime` (naming inconsistency; verify installed CLI). Agent Starter Pack GitHub repo (GoogleCloudPlatform/agent-starter-pack) has a Cloud Run CI/CD pipeline (staging->prod) per a third-party DeepWiki page (lower confidence). — [search result: DeepWiki](https://deepwiki.com/GoogleCloudPlatform/agent-starter-pack/7.1-cloud-run-deployment)

### Inferences
- For NovaMart, packaging a numpy index + synthetic data is simplest on Cloud Run (files live in the container image; read-only; rebuild to update). Same on GKE. On Agent Runtime, use the Agents CLI scaffolded Dockerfile/container path (or `extra_packages` in the SDK; not verified here) so data files are bundled.
- Bundling data in the image is only appropriate because data is synthetic; real data would warrant GCS/Vector Search/DB instead.

### Gaps
- Exact `extra_packages` / local-file bundling behaviour for `adk deploy agent_engine` was not found on the fetched pages.
- GA vs Preview status for Agent Runtime, Agents CLI, `adk deploy gke` not labeled on fetched pages.
- Agent Starter Pack's current relationship to Agents CLI not confirmed from an official page.
- How env vars/secrets are passed on `adk deploy agent_engine` and `adk deploy gke` not documented on fetched pages.

## 2. Session, memory and artifact services (what changes from in-memory defaults)

### Takeaway
Local `adk web/run` uses in-memory services (lost on restart). On Cloud Run, if session/artifact URIs are unset the container silently falls back to in-memory (data lost on instance recycle), so you must set them. On Agent Runtime, a managed session resource is auto-created at deploy.

### Cited Findings
- In-memory session/memory services are "designed specifically for local testing"; persistence needs cloud-based or DB-backed options. — [adk.dev/sessions](https://adk.dev/sessions/)
- Cloud Run flags: `--session_service_uri` accepts `agentengine://<id>`, `memory://`, or SQLAlchemy URL; `--artifact_service_uri` accepts `gs://bucket`, `file://`, `memory://`; `--memory_service_uri` accepts `rag://`, `agentengine://`, `memory://`. Unset = in-memory fallback. — [adk.dev/deploy/cloud-run](https://adk.dev/deploy/cloud-run/)
- DatabaseSessionService requires an async driver (example `sqlite+aiosqlite`); SQLite on a Cloud Run container is ephemeral/non-shared across instances (inference; see below). — [adk.dev/deploy/cloud-run](https://adk.dev/deploy/cloud-run/)
- Agent Runtime: deploy "automatically generates a managed session resource"; deleting agent with force=True removes it. — [quickstart](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk)
- Memory Bank: memory profiles GA Jul 15, 2026; separate metering for session and memory bank compute started Sep 1, 2026; Memory Bank is not supported in northamerica-northeast2. — [release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes), [locations](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/agent-locations)

### Inferences
- Minimum production change for NovaMart: persistent session store (Agent Runtime managed sessions, or Cloud SQL/Postgres via DatabaseSessionService on Cloud Run) plus GCS artifact service if artifacts are used. Memory Bank is optional (only for cross-session personalization; adds PII/retention considerations).

### Gaps
- Sessions GA status not stated in release-note excerpts; VertexAiSessionService class naming after the rename not verified; per-session pricing not read.

## 3. Authentication: how end users reach the agent; getting the user principal in safely

### Takeaway
Cloud Run is private by default via Agents CLI (identity token), with `--iap` and ingress controls; raw `adk deploy cloud_run` prompts for unauthenticated yes/no (default N). Agent Runtime endpoints are IAM-protected Google APIs (not directly end-user-facing); a custom front end or Gemini Enterprise registration is needed for end users. Trusting a client-supplied user_id is unsafe; derive it from verified identity at the front end.

### Cited Findings
- `adk deploy cloud_run` prompts "Allow unauthenticated invocations (y/N)"; N requires identity token (`gcloud auth print-identity-token`). — [adk.dev/deploy/cloud-run](https://adk.dev/deploy/cloud-run/)
- Agents CLI: Cloud Run service requires an identity token; no flag makes it public; `--iap` fronts with IAP; `--ingress internal[-and-cloud-load-balancing]`. Authentication for Agent Runtime/GKE not described there. — [agents-cli deployment](https://google.github.io/agents-cli/guide/deployment/index.md)
- Agent Runtime call surface is the regional aiplatform REST endpoint `:query`; caller needs Google credentials/IAM (`roles/aiplatform.user` in the quickstart). — [adk.dev deploy](https://adk.dev/deploy/agent-runtime/deploy/), [quickstart](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk)
- Agent Identity: Agent Runtime supports `identity_type=AGENT_IDENTITY`; Aug 31, 2026 release note mentions end-to-end agent identity authentication (mTLS, DPoP) and Agent Gateway using IAP + access policies; Oct 28, 2026 note on associating Agent Gateways with regional Agent Registry for Gemini Enterprise apps. — [release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)

### Inferences
- Recommended pattern: custom front end (or backend-for-frontend) authenticates the customer (OIDC/Firebase/Identity Platform), then calls the agent with a service identity and passes the verified user id as the session `user_id` (never taken from the chat body). For order tools, enforce authorization in the tool layer using that verified id, not the model's argument.
- IAP is suited to employee/Google-identity users, not retail customers (inference; IAP docs not read). Gemini Enterprise registration targets internal workforce use (separate research area).

### Gaps
- Official Gemini Enterprise registration steps for a custom ADK agent not read in this pass. IAP-with-Cloud-Run details and whether IAP can sit in front of Agent Runtime not verified. How `user_id` propagates in `:streamQuery` was not verified beyond the 128-char limit.

## 4. Model access: AI Studio key vs Vertex; free-tier terms

### Takeaway
An AI Studio key can technically be used from Cloud Run/GKE (ADK docs show `GOOGLE_API_KEY` in Secret Manager; GKE page says AI Studio users skip Workload Identity), but free-tier (unpaid) usage lets Google use prompts/responses for product improvement and human review, and terms say not to submit sensitive/personal info. Agent Runtime quickstart is Vertex/ADC-based. For production, use paid quota (billed project) or Vertex.

### Cited Findings
- Unpaid Services: Google uses submitted content and responses to improve products/ML; human reviewers may read them (disconnected from account/key/project first); "Do not submit sensitive, confidential, or personal information to the Unpaid Services." — [Gemini API terms](https://aistudio.google.com/docs/terms) (redirected from ai.google.dev/gemini-api/terms)
- Paid Services: prompts/responses not used to improve products; logged for limited time for abuse detection/legal; DPA applies. Gemini API counts as paid only via a billed Cloud project. — same source
- In the EEA, Switzerland and UK, only Paid Services may be used for API clients made available to users (paid-service data terms apply to all services there). — same source
- Terms: professional/business use, 18+, region-limited availability; agentic services: you are responsible for their actions and must not auto-bypass human confirmation requests. — same source
- Pricing page: free tier "used to improve our products: Yes" for most free models; paid "No" for most; free tier described as "limited access" vs paid "higher rate limits for production deployments". Exact per-model rate limits not on that page. Notes 2.5 Flash/Flash-Lite deprecated with routing changes effective Dec 1, 2026. — [AI Studio pricing](https://aistudio.google.com/docs/pricing)
- Gemini 3.8 Flash GA in Canada `northamerica-northeast1` on Vertex (Nov 9, 2026), regional endpoint, in-region ML processing, Provisioned Throughput. — [release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)

### Inferences
- Free tier is acceptable only for the synthetic-data prototype. Any real customer data (names, orders) makes free tier inappropriate; the prompts/responses would be used for training and human review. Canada (PIPEDA/Quebec Law 25) data-residency needs favor Vertex in northamerica-northeast1 (inference, compliance out of scope).
- Switching to Vertex is mostly env vars: set `GOOGLE_GENAI_USE_ENTERPRISE=True` (formerly `GOOGLE_GENAI_USE_VERTEXAI`), project, location; drop the API key; grant `roles/aiplatform.user` to the runtime service account. Model IDs in code are unchanged.

### Gaps
- Free-tier RPM/RPD numbers not retrieved (rate-limits page not read). Model names in pricing page (e.g., "Gemini 4 Hydrogen") were taken from the summarizer output and not independently confirmed. Whether AI Studio keys on Cloud Run are "allowed" is not explicitly addressed in terms; only paid-vs-unpaid distinction found.

## 5. Observability, evaluation, logging, scaling, cold starts, quotas, regions (incl. Canada)

### Takeaway
Canada is supported: Cloud Run in northamerica-northeast1 (Montreal) and -northeast2 (Toronto) (Tier 2 pricing); Agent Runtime and Sessions in both, Memory Bank only in Montreal; Gemini 3.8 Flash in Montreal. Cold-start/scaling/quota specifics were not retrieved.

### Cited Findings
- Cloud Run lists northamerica-northeast1 (Montreal) and northamerica-northeast2 (Toronto), Tier 2 pricing (another localized version said Tier 1; the English page fetched said Tier 2). — [Cloud Run locations](https://docs.cloud.google.com/run/docs/locations)
- Agent platform locations: Montreal supports Runtime, Sessions, Memory Bank; Toronto supports Runtime and Sessions but not Memory Bank; v1 = GA features, v1beta1 = Preview features; data-at-rest residency in selected location (agent source, deployment packages, sessions, memories). — [agent locations](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/agent-locations)
- Agents CLI `infra single-project` provisions prompt-response logging and BigQuery Agent Analytics via Terraform; ADK telemetry entry for Agent Runtime Aug 13, 2026 in release notes. — [agents-cli](https://adk.dev/deploy/agent-runtime/agents-cli/), [release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)
- Cloud Run flags like `--min-instances=2` can be passed through after `--`. — [adk.dev/deploy/cloud-run](https://adk.dev/deploy/cloud-run/)
- Pricing changes: Sep 1, 2026 session/memory bank compute metering; Sep 10 Standard PayGo Tier 4; Nov 16 Deferred tier GA (50% discount on inference, ADK v2.10.0+). — [release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)

### Inferences
- Cold starts: on Cloud Run, set min-instances >=1 for customer chat (standard Cloud Run behaviour; not verified from a fetched page). Loading a numpy index at import time adds to cold start; keep index small or lazy-load.
- ADK eval (`adk eval`/eval sets) works locally against the same agent and can run in CI via Agents CLI's `.cloudbuild/` (inference; not verified).

### Gaps
- No fetched source on cold-start latency, max instances, concurrency, Agent Runtime quotas, Cloud Trace/Logging integration specifics, or production eval tooling. Agent Runtime pricing numbers not read.

## 6. Migration effort estimates (official guides/codelabs)

### Takeaway
No official time estimate for migrating a prototype was found in fetched pages. Codelabs exist for each path, indicating a low-to-moderate effort (hours to days of work for first deploy; the real effort is auth, persistence, secrets, and data).

### Cited Findings
- Codelabs/quickstarts exist: Deploy an ADK agent to Agent Runtime using Agents CLI (expense agent); Deploy, manage, observe ADK agents on Cloud Run; Cloud Run quickstart for ADK. Durations not retrieved. — [Agents CLI codelab](https://codelabs.developers.google.com/enterprise-cloud-scale-deploying-the-expense-agent-to-agent-runtime-on-google-cloud), [Cloud Run codelab](https://codelabs.developers.google.com/deploy-manage-observe-adk-cloud-run), [Cloud Run quickstart](https://docs.cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-adk-service)
- The Agents CLI guide recommends reviewing generated Terraform/CI configs before production. — [adk.dev agents-cli](https://adk.dev/deploy/agent-runtime/agents-cli/)

### Inferences
- Checklist of changes from local: (1) move from AI Studio free key to paid key or Vertex; (2) persistent sessions (+ artifacts); (3) secrets in Secret Manager; (4) package index/data in image (or external store); (5) verified-user identity plumbing and front end; (6) region choice (northamerica-northeast1 for Canada); (7) logging/telemetry and min-instances; (8) CI/CD via Agents CLI. Rough ordering by effort: Cloud Run < Agent Runtime (with Agents CLI) < GKE. This ordering is my judgment, not an official estimate.

### Gaps
- No official hour/day estimates found; codelab durations not retrieved. Tradeoffs on pricing among the three paths were not quantified.
