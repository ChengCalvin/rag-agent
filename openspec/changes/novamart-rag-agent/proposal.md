## Why

NovaMart store employees flood the operations team with questions about product policies, returns and order status. This change delivers the take-home prototype for Artefact: an internal assistant that answers from company documentation, looks up live order data, declines when it does not know, and restricts each employee to the data they are allowed to see. Secured data access is the emphasis, because an assistant that can read orders is only acceptable if the model cannot be talked into reading the wrong ones.

## What Changes

- New Python project built on Google ADK with Gemini, running on a free AI Studio key and switchable to the Vertex-based Gemini Enterprise Agent Platform through environment variables only.
- A staged pipeline of single-purpose agents (design D1) with three tools: `search_policy` (retrieval over ~8 invented policy documents), `get_order_status` and `check_return_eligibility` (both over a stubbed, read-only order API).
- Hand-rolled retriever (Gemini embeddings, cosine similarity, score threshold). A score below the threshold yields a deterministic `no_answer` result that drives the refusal, so declining does not depend on the model alone.
- Access control enforced in tool code: the caller's identity (user, store, role) is injected into session state by the harness and never accepted as a tool argument. Order access is scoped to the caller's store, denials look identical to "not found", PII is masked, and every tool call is audit-logged. One manager-only document demonstrates audience-filtered retrieval.
- Return eligibility is computed in plain Python from structured policy parameters. The model explains the result and cites the policy, but does not do date arithmetic.
- Evaluation suite: ~15-18 quality questions and ~6 security cases, run through `adk eval` plus rule-based checks, with a threshold-versus-pass-rate table and honest reporting of failures.
- One-page production note for NovaMart covering Gemini Enterprise versus custom build, connecting real data, security and governance, and quality monitoring.
- Everything uses synthetic data only. Persona selection stands in for SSO and is documented as such, not as authentication.

## Capabilities

### New Capabilities
- `policy-retrieval`: grounded, cited answers from the policy corpus, with deterministic refusal when retrieval confidence is low and audience-aware filtering of chunks.
- `order-tools`: order status and return-eligibility lookups against a stubbed read-only order API, with input validation and field minimisation.
- `access-control`: caller identity injected outside the model, store- and role-scoped authorization in tool code, uniform denial responses, audit logging, and PII-safe logs.
- `agent-evaluation`: quality and security evaluation sets, checks, and a reported results summary.
- `production-note`: the one-page production plan for NovaMart on Google's enterprise stack.
- `cost-reporting`: per-answer and per-session cost computed by code from recorded usage, shown behind a flag.

### Modified Capabilities
<!-- None. The repository has no existing specs. -->

## Impact

- New code: a `backend/src/novamart_agent` ADK package, `backend/data/` (docs, orders, users), `backend/evals/`, `backend/tests/`, a README, and `docs/production_note.md`.
- Dependencies: `google-adk`, `google-genai`, `numpy`, `pytest`.
- External services: Gemini API through an AI Studio key supplied via environment variable (never committed). No cloud deployment is in scope.
- Time box: roughly a half-day build.
- Open questions carried into the design: free-tier model availability and rate limits, whether ADK's LLM-judge eval metrics work on a free key, and how Gemini Enterprise passes end-user identity to a registered custom agent (a production spike, not a prototype task).
