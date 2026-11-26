# Gemini Enterprise: data connectors and permission/access-control model (as of Nov 2026)

Method note: ~14 tool calls. Primary sources are docs.cloud.google.com pages fetched in Nov 2026. Several fetch summaries were produced by a small model, so exact wording may be paraphrased. Google renamed Agentspace to Gemini Enterprise, and some pages still carry the Agentspace name or are marked deprecated. Treat older Agentspace/Vertex AI Search URLs as lower-confidence.

## 1. Which connectors exist (GA/preview), and are there custom/unstructured/structured data stores?

### Takeaway
There are a large number of connectors. The main enterprise ones (Microsoft 365, SharePoint, OneDrive, Outlook, Teams, ServiceNow, Jira Cloud/Data Center, Confluence Cloud/Data Center, Box, Slack, Google Drive/Gmail/Calendar, GitHub, Zendesk is preview) are listed as GA. Salesforce, Zendesk, Dynamics 365, Notion, Shopify, Google Chat and a Custom MCP Server are public preview. Cloud Storage and BigQuery work as custom data stores (unstructured or structured), and those are the route for custom order/policy data.

### Cited Findings
- Connector launch-stage list (this page lists only stage and `allowedDataSources` value; it does not give ACL, identity, sync or edition per source). GA includes: Asana, Box, Confluence Cloud, Confluence Data Center, Dropbox, Egnyte, Freshservice, GitHub, GitLab, Google Calendar, Google Drive, Google Mail, HubSpot, Intercom, Jira Cloud, Jira Data Center, Linear, Microsoft 365, Microsoft Entra ID, Microsoft Outlook, Microsoft Teams, OneDrive, PagerDuty, ServiceNow, SharePoint, Slack, Stripe, Zoho Desk, Zoho Projects, and many others. — [Connect a third-party data source](https://docs.cloud.google.com/gemini/enterprise/docs/connect-third-party-data-source)
- Public preview includes: Salesforce, Zendesk, Dynamics 365, Notion, Shopify, Smartsheet, Google Chat, Docusign, Oracle NetSuite, Zoho CRM, Zapier, MongoDB Atlas, Supabase, Wrike, Miro, Gong, and "Custom MCP Server". — [same page](https://docs.cloud.google.com/gemini/enterprise/docs/connect-third-party-data-source)
- Private preview (allowlist via Google account team): Confluence Data Center and Jira Data Center on-premises with data ingestion. — [same page](https://docs.cloud.google.com/gemini/enterprise/docs/connect-third-party-data-source)
- Not found on that list as a separate connector: a dedicated "websites" connector entry was not seen in the fetched list (website/public-site data stores exist in the broader Discovery Engine product but I did not verify them for Gemini Enterprise; see Gaps). BigQuery, Cloud Storage and Spanner are referenced as Google/custom data sources, not in the third-party list. — [Intro to connectors and data stores](https://docs.cloud.google.com/gemini/enterprise/docs/introduction-to-connectors-and-data-stores)
- Google data sources: Google Drive, Gmail, Google Calendar, People search. — [Intro](https://docs.cloud.google.com/gemini/enterprise/docs/introduction-to-connectors-and-data-stores)
- Connector availability differs by edition (Business vs Standard/Plus connector pages exist). — [Connect Google apps and third-party data (Business edition)](https://support.google.com/g/answer/16550932); [connectors overview](https://cloud.google.com/gemini-enterprise/connectors)
- Connecting a source creates a data store per entity type (e.g. Jira: issues, attachments, comments, worklogs). Unstructured data stores hold PDF, HTML, DOCX, PPTX, XLSX, XLSM; structured data stores hold structured content with auto-detected or API-defined schema. Storage location choice: global, US or EU. — [Intro](https://docs.cloud.google.com/gemini/enterprise/docs/introduction-to-connectors-and-data-stores)
- Two retrieval modes: federation (queries source live, nothing copied, "search quality may be lower") and ingestion (copied into the Gemini Enterprise index, "can improve search quality"). Where both are supported you choose. — [Intro](https://docs.cloud.google.com/gemini/enterprise/docs/introduction-to-connectors-and-data-stores)
- Federated search sends the query string, possibly including parts of the conversation history, to all enabled third-party backends; that data falls under those vendors' terms, not Google Cloud's. — [Intro](https://docs.cloud.google.com/gemini/enterprise/docs/introduction-to-connectors-and-data-stores)
- Custom data: Cloud Storage and BigQuery, unstructured or structured, with a document schema (`id`, `jsonData`, `content{mimeType,uri}`, `acl_info`). — [Configure access controls for custom data sources](https://docs.cloud.google.com/gemini/enterprise/docs/identity)
- Custom MCP Server connector: public preview in the connector list; supports StreamableHTTP only (no SSE); up to 100 enabled actions (one secondary source says 150 tools, conflicting); actions off by default; calls need user confirmation unless tools carry `readOnlyHint`; data store can only be created within an app. — [Set up custom MCP server](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/custom-mcp-server/set-up-custom-mcp-server); 150-tool figure and preview-since-April-2026 claim from secondary sources (search summary of [StackOne](https://www.stackone.com/blog/best-mcp-gateway-for-gemini-enterprise/), unverified).
- Sync types: full and incremental; identity sync (users/groups) is separate from entity sync (content). Incremental default every 3 hours; independent identity full sync every 30 min to 7 days; entity full sync every 3 hours to 7 days. Incremental sync does not capture identity data or deletions. — [Intro](https://docs.cloud.google.com/gemini/enterprise/docs/introduction-to-connectors-and-data-stores)
- Static IP egress is available for third-party data stores that support it. — [Intro](https://docs.cloud.google.com/gemini/enterprise/docs/introduction-to-connectors-and-data-stores)

### Inferences
- For a support agent with order data (structured) and policy docs (unstructured), the realistic Google-native paths are: BigQuery/Cloud Storage data stores with `acl_info`, or a Custom MCP server fronting an order API (preview). Salesforce/ServiceNow/Zendesk connectors only matter if the real systems of record live there; Salesforce and Zendesk are preview, ServiceNow GA.
- Incremental syncs skip deletions, so revoked documents depend on full-sync cadence.

### Gaps
- Per-connector detail (federated vs ingested, edition, ACL support per source) was not on the list page; per-connector pages were not fetched.
- Website/public-site data store availability and status in Gemini Enterprise not verified.
- Release-notes confirmation of dates/GA transitions not obtained.

## 2. How source ACLs and per-user authorization are enforced; can it be enforced in code?

### Takeaway
Enforcement is done by the Gemini Enterprise index/search layer using identities from Google Identity or Workforce Identity Federation, plus per-document ACLs (synced from source or supplied by you as `acl_info` on custom data). Users only see what the source (or your supplied ACL) allows. You can "enforce in code" only in the sense of supplying ACL metadata at import and mapping identities; you cannot inject arbitrary per-query filter logic as the access control mechanism (not documented). For preview custom MCP, per-user OAuth delegates the decision to your own backend.

### Cited Findings
- Users can only view and ground responses on information they can already access directly in the source application; Gemini Enterprise does not bypass source ACLs or grant extra permissions. Permissions are managed in the source system, not in connector settings. — [Configure identity provider](https://docs.cloud.google.com/gemini/enterprise/docs/configure-identity-provider)
- Identity options: Google Identity (recommended) or a third-party OIDC/SAML 2.0 IdP (Entra ID, Okta, AD FS) via Workforce Identity Federation. Google Workspace sources require Google Identity. Third-party ingestion: Google Identity, except Microsoft 365 sources (SharePoint, OneDrive, Outlook), which require Entra ID with Workforce Identity Federation. Third-party federated sources: users authenticate via OAuth, Google Identity. — [Configure identity provider](https://docs.cloud.google.com/gemini/enterprise/docs/configure-identity-provider)
- Access control must be enabled when a data store is created and cannot be toggled later. Each document allows up to 3,000 readers (each user or group counts as one). — [Configure identity provider](https://docs.cloud.google.com/gemini/enterprise/docs/configure-identity-provider)
- Changing IdP or moving to a new Workforce pool requires deleting and recreating ingestion data stores; existing stores do not update automatically. Changing a user's `google.subject` value makes them a new user (loses chat history, agents, licenses). Editing attribute mappings does not require recreation. — [Configure identity provider](https://docs.cloud.google.com/gemini/enterprise/docs/configure-identity-provider)
- Entra ID tokens omit group IDs for users in >150 groups (SAML) or >200 (OIDC), causing 403 errors unless group claims are restricted. — [Configure identity provider](https://docs.cloud.google.com/gemini/enterprise/docs/configure-identity-provider)
- Custom data ACL format: each document carries `acl_info.readers[].principals[]` where each principal is `user_id` or `group_id`. Enable with console checkbox "This data store contains access control information" or `"aclEnabled": "true"` in the create request. For Cloud Storage import `dataSchema` = `document`; for BigQuery use the predefined schema with `acl_info` column. "Google uses your identity provider to identify the searching user and determine which returned documents that user can access." — [Configure access controls for custom data sources](https://docs.cloud.google.com/gemini/enterprise/docs/identity)
- The Discovery Engine `Document.AclInfo` field exists in the client libraries (readers list), confirming ACLs are part of the document schema usable via document import. — [Python reference AclInfo](https://docs.cloud.google.com/python/docs/reference/discoveryengine/latest/google.cloud.discoveryengine_v1.types.Document.AclInfo)
- Ingestion identity sync captures users and groups; ingestion requires the connecting credential to have unrestricted access to the source resources. — [Intro](https://docs.cloud.google.com/gemini/enterprise/docs/introduction-to-connectors-and-data-stores)
- Custom MCP: admin registers Gemini Enterprise as an OAuth client with the IdP; scopes are requested "on behalf of a user"; the user's OAuth token is sent to the server (and a Google-signed ID token to default Cloud Run URLs). Your server therefore decides what each user can see. — [Set up custom MCP server](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/custom-mcp-server/set-up-custom-mcp-server)
- IAM: users need Gemini Enterprise User role (`roles/discoveryengine.agentspaceUser`). Workforce pool roles can modify attribute mappings, so grant narrowly. — [Security overview](https://docs.cloud.google.com/gemini/enterprise/docs/security-overview)
- Preview of access-controlled third-party results requires signing in to the federated console or web app. — [Configure identity provider](https://docs.cloud.google.com/gemini/enterprise/docs/configure-identity-provider)

### Inferences
- Order data per customer (many thousands of customers) maps poorly to per-document ACLs with a 3,000-reader cap and user identities from the company workforce IdP; the "user" in a support agent scenario is usually the support agent, but if end customers are the users, they would need workforce identities, which is not the product's target (it is an employee product). A custom MCP/API with your own authorization is the more natural fit for order data.
- Search-time user identity passing for programmatic API calls is not documented in what I fetched; do not assume `userInfo` in a search request enforces ACLs (it is described for analytics/personalization).

### Gaps
- Exactly how a programmatic Search/Answer API call carries the user identity for ACL filtering (e.g., Workforce token on the request) was not found.
- Whether ACL principals can be arbitrary application-defined IDs outside the IdP was not found.
- Per-connector ACL sync fidelity (e.g., Salesforce sharing rules, ServiceNow) not verified.

## 3. Retrieval: hybrid search, ranking, grounding/citations; tunable thresholds?

### Takeaway
Citations and grounding are supported, and some tunables exist on the underlying Discovery Engine API (citation inclusion, low-relevance filtering, a check-grounding threshold with default 0.6). I did not find official documentation of hybrid search internals or ranking algorithm tuning for the Gemini Enterprise app itself.

### Cited Findings
- Check-grounding API: citation confidence threshold float 0 to 1, default 0.6; higher threshold gives fewer but stronger citations. This is separate from the search answer method. — [Check grounding with RAG](https://docs.cloud.google.com/generative-ai-app-builder/docs/check-grounding) (from search summary, not fully fetched)
- Answer spec has `includeCitations` and `ignoreLowRelevantContent`; `filteringLevel` exists in GroundingSpec; no numeric threshold documented in what I saw. — search summary of [Search/Answer reference](https://docs.cloud.google.com/gemini/enterprise/docs/reference/rest/v1/SearchSpec) (unverified details)
- Grounded Generation API page: "The Grounded Generation API is deprecated" in favor of Gemini Enterprise Agent Platform; grounding response includes support chunks, claim text and chunk indices; grounding score is a float 0 to 1; dynamic retrieval threshold defaults to 0.7 (that applies to Google Search grounding); max 10 grounding sources per request. The page says nothing on end-user ACLs. — [Generate grounded answers with RAG](https://docs.cloud.google.com/generative-ai-app-builder/docs/grounded-gen)
- `userInfo` on search requests is described as for analytics and personalization, not access control. — search summary, unverified
- Federation vs ingestion quality tradeoff stated by Google (above). — [Intro](https://docs.cloud.google.com/gemini/enterprise/docs/introduction-to-connectors-and-data-stores)

### Inferences
- Inspectability: usage audit logs capture grounding metadata and sources used for `Search` (see section 4), which gives retrospective inspection, not tuning.

### Gaps
- No official statement on hybrid (keyword+vector) retrieval or reranking in the Gemini Enterprise app.
- Confidence/threshold controls specific to the Gemini Enterprise assistant UI not found.

## 4. Data governance: CMEK, VPC-SC, residency, audit logging, no training

### Takeaway
Governance is strong for Standard/Plus: CMEK, VPC Service Controls, data residency, Access Transparency (US/EU multi-region only, not `global`), audit logs, and no training on customer data. Several features have limits (global region, Google Search grounding).

### Cited Findings
- Gemini Enterprise "doesn't use your prompts, generated responses, or connected enterprise data" to train Google's foundation models; data isolated in your project. — [Security overview](https://docs.cloud.google.com/gemini/enterprise/docs/security-overview)
- CMEK and Access Transparency are not supported in the `global` region; CMEK is for US and EU multi-region only; EKM/HSM with CMEK is "in GA with allowlist". — [Compliance and security controls](https://docs.cloud.google.com/gemini/enterprise/docs/compliance-security-controls)
- VPC Service Controls supported for Standard/Plus and Notebook Enterprise, but "doesn't apply when Grounding with Google Search is enabled"; same caveat for data residency. — [Compliance and security controls](https://docs.cloud.google.com/gemini/enterprise/docs/compliance-security-controls)
- You cannot apply custom network controls (firewall rules, VPC-SC configs) directly on the Google-managed service; egress to external endpoints is secured with VPC firewall rules by FQDN, and VPC-SC does not block traffic to external non-Google endpoints. — [Security overview](https://docs.cloud.google.com/gemini/enterprise/docs/security-overview)
- Certifications listed: HIPAA, FedRAMP, ISO 27001/27017/27018/27701, SOC 1/2/3, PCI DSS, BSI C5:2020 (check per product). Antigravity in Gemini Enterprise lacks AXT, FedRAMP, IL4/5, ISO, SOC. — [Compliance and security controls](https://docs.cloud.google.com/gemini/enterprise/docs/compliance-security-controls)
- Audit logs: service `discoveryengine.googleapis.com`; Admin Activity and Data Access logs; `SearchService.Search` produces a Data Access log (permission `discoveryengine.servingConfigs.search`, DATA_READ). Whether Data Access logs are on by default was not confirmed on the page. — [Audit logging](https://docs.cloud.google.com/gemini/enterprise/docs/audit-logging)
- Separate opt-in "usage audit logs" via ObservabilityConfig capture prompts, responses and grounding metadata to Cloud Logging (`gemini_enterprise_user_activity`); one source says the admin role needed is `roles/discoveryengine.agentspaceAdmin`, another `roles/discoveryengine.admin` (conflict). — search summaries of [Usage audit logs](https://docs.cloud.google.com/gemini/enterprise/docs/set-up-usage-audit-logs) (not fully fetched)
- Workforce Identity Federation sign-in audit needs Data Access audit logs for the Security Token Service API enabled; the Entra extended-groups feature gives no detailed audit info. — search summary of [Configure identity provider](https://docs.cloud.google.com/gemini/enterprise/docs/configure-identity-provider)
- Data store storage regions: global, US, EU; US/EU require encryption (Google-managed by default, CMEK optional). — [Intro](https://docs.cloud.google.com/gemini/enterprise/docs/introduction-to-connectors-and-data-stores)

### Inferences
- If CMEK or Access Transparency is required, avoid the `global` location.

### Gaps
- Data-residency product limitations anchor page not read.
- Default state of Data Access logs not confirmed.
- The security-overview claim that data is encrypted "with CMEK" by default conflicts with the compliance page and intro (CMEK optional); I trust the intro/compliance pages.

## Fit note for the customer-support use case (summary of evidence only)
Gemini Enterprise is an employee-facing product with workforce identity. Per-user access to order data and policy docs works if users are workforce identities and either (a) data lives in a source with ACLs synced, (b) custom data carries `acl_info`, or (c) a custom MCP server (preview) enforces authorization with per-user OAuth. Enforcement is in the platform/source or your backend; not as an in-index code hook.
