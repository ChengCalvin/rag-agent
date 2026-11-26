# 2. Connecting the client's real data

## Question
How do NovaMart's real data sources replace the synthetic data?

## Prototype to production mapping
| Prototype | Real counterpart (to confirm with client) | Notes |
|---|---|---|
| `backend/data/docs/*.md` (policies, product briefs) | Client's Drive / SharePoint / CMS, read through the platform's MCP or API by an ingestion job | Situational: depends on what the client uses and what read-only access it offers |
| `backend/data/orders.json` via `adapters/orders_api` | Client order API (preferred) or a read-only copy behind views | Only the adapter's backend changes; tools and guard stay as they are |
| `backend/data/users.json` + `NOVAMART_USER` persona | Client identity / customer records, mapped to the principal in code | Principal never comes from the model |
| numpy retrieval + `rag/embedder` | numpy kept, or a managed index that returns raw scores and supports metadata filters | Scale and ops decision, not a correctness one |

## Things to investigate
- [ ] Where do policy documents live today (Drive, SharePoint, CMS, other)?
- [ ] Managed index options: Vertex AI Search vs Vector Search; what replaces the hand-rolled numpy
- [ ] Ingestion: chunking, metadata (audience, policy parameters from front-matter), re-indexing on change
- [ ] Freshness and content ownership: who keeps policies current?
- [ ] Order API: read-only access, auth, rate limits, latency
- [ ] Only two integration points in the prototype (`ARCH-EDGE-1`): how small is the swap?

## Notes

Framing: everything here is situational. This note maps options and what each depends on; it does not prove or pick one.

### Client records (orders, users): deterministic layer, not the LLM
The data is sensitive, so a non-deterministic model never touches it directly. Access goes through a thin read-only tool layer with guardrails that hold even if the agent derails.
- Preferred source: the client's own read-only order API (they keep authorization and freshness). Fallback: a read-only copy.
- If a copy: database role with `SELECT` only, on views exposing just the columns the tools need, not raw tables. Copying PII adds residency and retention duties and replication lag.
- No free-form SQL tool. Tools take parameterized arguments; the principal comes from the session (`ARCH-MOD-4`, guard is the single choke point).
- Rate limits and an audit log per principal.
- Read-only end to end. Starting a return would be a write, so it stays a handoff to a human or a ticket.

### Documents (Drive, SharePoint, other)
- Assume the client's service is secured. Our job is to verify it offers an MCP or an API, then either connect to the MCP or call their endpoint.
- Verify our access is scoped: app-only vs delegated, read-only per-site or per-folder scope, raw content vs search snippets only.
- Use the MCP or API as the source for an ingestion job (our code as the client, no LLM in the loop), not as a per-question fetch. A live fetch gives no similarity scores for the confidence composite and adds latency.
- Policies are mostly customer-readable, so audience metadata matters more than per-user ACLs.

### Ingestion and managed index (what they are)
- Ingestion: fetch, parse, chunk, attach metadata (audience, policy parameters from front-matter), embed, store; re-run on change (modified time or content hash); remove chunks for deleted documents. In the prototype this happens implicitly at load.
- Managed index: hosted store and search replacing in-memory numpy (Vertex AI Search, Vertex Vector Search, pgvector). Requirements for us: raw scores returned (Vertex AI Search hides them) and metadata filters. Judgment, unverified: a corpus of dozens to hundreds of documents may run fine on numpy; a managed index matters when there are multiple instances or updates without redeploy.

### Freshness and ownership
- Staleness is an ownership problem, not a retrieval problem. If the responsible person does not update the documents, the agent answers from stale policy, and we cannot fix that from our side.
- Proposed direction: give the policy owner an agent that automates their internal process and overhead (a separate, write-capable agent, not the customer-facing one). Once the owner decides a policy change, that agent updates the affected documents, so time spent stale shrinks. One approval from the policy maker propagates to all affected documents.
- Ingestion then picks up the changes on its next run. Keep the approval step human, and keep this agent separate from the read-only customer agent.
- Out of scope for this prototype; to scope with the client.

### Questions for the client
- Does an order API exist, and what are its auth, rate limits and latency?
- Where do policies live, and does that platform offer an MCP or API with read-only scoping?
- Data residency requirements?
- Who owns policy content, and what is their current update process?

## Decision


## One-line summary for the note
