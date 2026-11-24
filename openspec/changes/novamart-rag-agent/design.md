## Context

Greenfield project, time-boxed to roughly half a day. See proposal.md for motivation. Constraints: Python, Google ADK, Gemini via a free AI Studio key, synthetic data only, interaction through `adk web` / `adk run`. Behavior is specified in `specs/`.

Design input came from three read-only reviews (architecture, security threat model, and a documentation check on 2026-11-23). Product names and model IDs in this area are changing quickly: ADK docs moved to adk.dev, Vertex AI is now called Gemini Enterprise Agent Platform, and Agent Engine is now Agent Runtime. Anything marked VERIFY below was not confirmed against primary docs and must be re-checked when building.

## Goals / Non-Goals

**Goals:**
- Make the access-control enforcement point obvious and testable, because it is the main thing this prototype has to prove.
- Make refusal deterministic where possible.
- Keep the code small enough to explain end to end in an interview.

**Non-Goals:**
- Real authentication, SSO, or a real order API: persona selection and an in-memory stub stand in for them and are documented as such.
- Cloud deployment, a custom UI, multi-agent orchestration, write tools.
- Production-grade vector storage.

## Decisions

### D1. One root agent with three tools
`search_policy`, `get_order_status`, `check_return_eligibility`. Alternative: multi-agent with a retrieval specialist and an orders specialist. Rejected: more moving parts, harder to evaluate, nothing in the scenario needs it.

### D2. Identity is injected, never passed by the model
A callback before each session populates a principal (user, store, role) in session state from a stand-in auth context (`NOVAMART_USER` selects a persona from a users file). Tool signatures contain no user or store parameter; tools read the principal from the tool context. This is what makes "I'm the manager" in chat harmless. Alternative: pass role in the prompt and trust the model to enforce it. Rejected: the model decides tool arguments, so any prompt-level rule can be argued away.
The ADK docs describe session state as server-side but do not explicitly state that end users cannot alter it (VERIFY). In production, identity must be derived from the authenticated token in the application's API layer, never from the request body.

### D3. Authorization is a single choke point in tool code
One shared authorization function is called after fetch and before return by both order tools, deny-by-default, with a uniform "not found or not accessible" response for both nonexistent and out-of-scope orders. A before-tool callback adds a per-role tool allowlist and writes the audit record. Alternative: filter in the order stub only. Rejected: eligibility would become a second, unguarded path.

### D4. Hand-rolled retrieval with a deterministic refusal gate
Chunk documents by markdown heading, embed with `gemini-embedding-001` using `RETRIEVAL_DOCUMENT` and `RETRIEVAL_QUERY` task types, cache vectors on disk keyed by content hash, cosine similarity in numpy, top-3, threshold from configuration. Below threshold the tool returns `no_answer` and the prompt instructs the model to decline and point to escalation. Embed each chunk in its own call, because several strings in one call return a single aggregated embedding. Audience labels are carried in document front-matter and filtered before ranking.
Alternatives: (a) Gemini File Search tool: no similarity score to gate refusal. (b) Vertex AI Search / RAG Engine: the production answer, but needs cloud setup and is overkill for eight documents. (c) `gemini-embedding-2`: multimodal, no `task_type`, needs prefix conventions; unnecessary for text.
ADK still forbids mixing built-in tools with function tools in one agent, which another reason for a custom function tool.

### D5. Code decides eligibility, the model explains
Policy parameters (return window, excluded categories) live in structured front-matter in the returns document, and the prose is retrieved separately for citation. Python computes eligibility from order data plus those parameters. Alternative: let the model read the policy and do date math. Rejected: error-prone and untestable.

### D6. Model and backend configuration
Model ID comes from configuration, defaulting to a current stable Flash-class model (candidates reported: `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`; VERIFY availability on the free tier). `gemini-2.5-flash` is deprecated and must not be used. Backend switch: AI Studio via `GOOGLE_API_KEY`; Vertex-based via `GOOGLE_GENAI_USE_ENTERPRISE=TRUE` plus project and location (`GOOGLE_GENAI_USE_VERTEXAI` is documented as equivalent and is the safe choice on older ADK). Embedding calls must go through the same `google-genai` client so the switch needs no code change.

### D7. Evaluation uses ADK eval for trajectories and our own rule checks for content
Evalsets seed each persona through `session_input.state`. ADK's `tool_trajectory_avg_score` checks tool use. Content checks (must-contain, must-not-contain, refusal phrases, citations) are a small custom runner. `hallucinations_v1` is optional because it may need the Vertex evaluation service (VERIFY on free key). Security cases are a separate set. The threshold-versus-pass-rate table comes from re-running the quality set at three threshold values.

### D8. Layout
```
backend/                      (run: adk web backend/src)
  pyproject.toml
  src/novamart_agent/  agent.py, prompts.py, __init__.py
    security/  principal, guard, callbacks
    tools/     retrieval, orders, eligibility
    backends/  orders_api (stub, read-only)
    rag/       chunker, embedder (disk cache), index
  data/  docs/*.md (8), orders.json, users.json
  evals/ *.evalset.json + test_config.json (quality, security), content-check runner, results/
  tests/ guard, retrieval threshold, eligibility (pytest, mirrors the package)
docs/  production_note.md
```

### D9. Production target (for the note, not built)
Hybrid: Gemini Enterprise as the front door and document search (permission-aware connectors, workforce identity), with the ADK agent registered as a custom agent through A2A for order logic and hosted on Agent Runtime or Cloud Run. The agent forwards end-user identity so the real order API enforces store scope itself. Document-level ACLs in the search data store must be enabled when the store is created and cannot be changed afterwards (VERIFY). Fallback if identity cannot be passed to registered agents: ADK agent behind IAP, with Gemini Enterprise limited to document search.

## Risks / Trade-offs

- [Cosine threshold is brittle and model-dependent] → tune on the eval set, report the threshold table, keep the deterministic gate plus prompt rule as two layers.
- [Prototype identity is simulated] → state it in the README and the note; never describe it as authentication.
- [Prompt-injection defences are probabilistic] → the guarantee comes from tool-side authorization and read-only tools; the model-facing rules are defense in depth.
- [Free-tier limits or model availability may flake the eval] → cache embeddings, temperature 0, retry with backoff, pin the model ID in configuration.
- [`adk web` shows full event traces] → synthetic data only, stated in the README.
- [Free AI Studio terms may allow use of inputs to improve products (VERIFY)] → synthetic data only; production uses the paid enterprise platform.
- [Doc claims in the production note go stale] → mark unverified items "to be confirmed" and re-check on the day of writing.
- [Scope vs. time box] → if time runs short, cut rate limiting and the optional judge metric first, and keep cross-store denial, document injection, and log-hygiene tests.

## Open Questions

- Which model IDs are available on the current free tier, and at what rate limits? Resolved by checking AI Studio at build start.
- Do ADK's LLM-judge eval metrics work with a free key? Resolved when the eval is built; the fallback is the custom checks.
- How does Gemini Enterprise pass end-user identity to an A2A-registered agent? A production spike item for the note, not a prototype task.
