## Change map (revision 2: staged multi-agent pipeline)

```
WHAT CHANGES                                     WHAT STAYS UNTOUCHED
------------                                     --------------------
D1 rewritten: one root LlmAgent                  D2 identity injection (callback -> state)
   -> deterministic staged pipeline              D3 guard = single choke point in tools
NEW  agents/    intake, retrieval, order,        D4 numpy retrieval, per-chunk embeds,
                validator, composer,                content-hash cache, threshold gate
                orchestrator (BaseAgent)         D5 code computes eligibility
NEW  pipeline/  precheck, routing,               D6 models and backend switch
                rubric_check, confidence (pure)  D9 production note target
NEW  prompts/   one module per agent             The three tools and their signatures
CHG  rag/chunker  keep fenced blocks whole       Data: orders.json, users.json
CHG  data/docs    doc_type + audience front-matter
CHG  config       threshold T, weights, loops

DATA FLOW (details in D10-D16)
  user -> [orchestrator: principal injected]
       -> [1 intake: precheck + rubric + route]
            |-- invalid / out of scope ---> decline (B)
            |-- missing slot ------------> ask ONE question (A), end turn
            |-- order -------------------> [order agent] --------------+
            '-- policy | product                                        |
                  -> LoopAgent(max 2): [retrieval] -> [validator]      |
                       exit decided in code (confidence vs T)          |
                  -> [composer] <--------------------------------------'
                       code appends SOURCES + confidence band
```

## Context

Greenfield project, time-boxed to roughly half a day. See proposal.md for motivation. Constraints: Python, Google ADK, Gemini via a free AI Studio key, synthetic data only, interaction through `adk web` / `adk run`. Behavior is specified in `specs/`.

Revision 2 (2026-11-23, architecture v4): the owner replaced the single-agent design (old D1) with a staged pipeline that validates the input, retrieves, cross-checks the result against an intent rubric, and formats the reply by document type. D10-D16 record the new decisions. Spec scenarios in `specs/` have not yet been updated for the refusal split, the confidence band or the clarification turn; that is a follow-up (see tasks.md chunk 8).

Design input came from three read-only reviews (architecture, security threat model, and a documentation check on 2026-11-23). Product names and model IDs in this area are changing quickly: ADK docs moved to adk.dev, Vertex AI is now called Gemini Enterprise Agent Platform, and Agent Engine is now Agent Runtime. Anything marked VERIFY below was not confirmed against primary docs and must be re-checked when building.

## Goals / Non-Goals

**Goals:**
- Make the access-control enforcement point obvious and testable, because it is the main thing this prototype has to prove.
- Make refusal deterministic where possible.
- Keep the code small enough to explain end to end in an interview.

**Non-Goals:**
- Real authentication, SSO, or a real order API: persona selection and an in-memory stub stand in for them and are documented as such.
- Cloud deployment, a custom UI, write tools, LLM-driven delegation between agents (`AgentTool`, transfer), image assets.
- Production-grade vector storage.

## Decisions

### D1. A deterministic staged pipeline of small agents (replaces "one root agent")
The root is a custom `BaseAgent` orchestrator that runs five single-purpose agents in a fixed order, with plain-Python branching: **intake** (validate, classify, build the rubric), **retrieval** and **validator** inside a `LoopAgent` (policy and product questions only), **order** (shortcut for order questions), and **composer** (format the reply). The three tools are unchanged; only `retrieval` holds `search_policy`, only `order` holds the two order tools, and intake, validator and composer have no tools.
Why: the owner wants input validation, cross-checking of retrieved output against the user's intent, and a reply template per document type. Each is a separate responsibility with a separate failure mode, and separate agents let each be evaluated alone.
Rejected alternatives: (a) the previous single agent with three tools: cannot cross-check its own retrieval or format by document type without stuffing all duties into one prompt; (b) an LLM router with `sub_agents` or `AgentTool`: the model would choose the route and the identity-propagation story becomes harder to prove; (c) a plain `SequentialAgent`: has no branch for the order shortcut (D14).
Cost: one policy question now costs 4 to 6 model calls (intake, retrieve, validate, optional retry pair, compose) instead of 1 to 2, which matters on the free tier (see Risks) and is why the user is shown the cost (D17).
Architect agent review: required by the project rules and not yet run; the decision here is owner-directed. Run it before `docs/architecture.md` v4 is approved.
ADK APIs assumed, all VERIFY against adk.dev before building: `LoopAgent` and its exit by `escalate`; custom `BaseAgent` with `_run_async_impl`; sub-agents of one orchestrator sharing session state; `output_schema` (and that it disables tools on that agent); `before_agent_callback` and `before_tool_callback` argument mutation.

### D2. Identity is injected, never passed by the model
A callback before each session populates a principal (user, store, role) in session state from a stand-in auth context (`NOVAMART_USER` selects a persona from a users file). Tool signatures contain no user or store parameter; tools read the principal from the tool context. This is what makes "I'm the manager" in chat harmless. Alternative: pass role in the prompt and trust the model to enforce it. Rejected: the model decides tool arguments, so any prompt-level rule can be argued away.
The ADK docs describe session state as server-side but do not explicitly state that end users cannot alter it (VERIFY). In production, identity must be derived from the authenticated token in the application's API layer, never from the request body.

### D3. Authorization is a single choke point in tool code
One shared authorization function is called after fetch and before return by both order tools, deny-by-default, with a uniform "not found or not accessible" response for both nonexistent and out-of-scope orders. A before-tool callback adds a per-role tool allowlist and writes the audit record. Alternative: filter in the order stub only. Rejected: eligibility would become a second, unguarded path.

### D4. Hand-rolled retrieval with a deterministic refusal gate
Chunk documents by markdown heading, embed with the configured embedding model (default `gemini-embedding-001`, D6) using `RETRIEVAL_DOCUMENT` and `RETRIEVAL_QUERY` task types, cache vectors on disk keyed by content hash, cosine similarity in numpy, top-3, threshold from configuration. Below threshold the tool returns `no_answer` and the prompt instructs the model to decline and point to escalation. Embed each chunk in its own call, because several strings in one call return a single aggregated embedding. Audience labels are carried in document front-matter and filtered before ranking.
Alternatives: (a) Gemini File Search tool: no similarity score to gate refusal. (b) Vertex AI Search / RAG Engine: the production answer, but needs cloud setup and is overkill for eight documents. (c) `gemini-embedding-2`: multimodal, no `task_type`, needs prefix conventions; see D6 for why a text-only model is the choice.
ADK still forbids mixing built-in tools with function tools in one agent, which another reason for a custom function tool.

### D5. Code decides eligibility, the model explains
Policy parameters (return window, excluded categories) live in structured front-matter in the returns document, and the prose is retrieved separately for citation. Python computes eligibility from order data plus those parameters. Alternative: let the model read the policy and do date math. Rejected: error-prone and untestable.

### D6. Models and backend configuration
Model ID comes from configuration, defaulting to a current stable Flash-class model (candidates reported: `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`; VERIFY availability on the free tier). `gemini-2.5-flash` is deprecated and must not be used. Backend switch: AI Studio via `GOOGLE_API_KEY`; Vertex-based via `GOOGLE_GENAI_USE_ENTERPRISE=TRUE` plus project and location (`GOOGLE_GENAI_USE_VERTEXAI` is documented as equivalent and is the safe choice on older ADK). Embedding calls must go through the same `google-genai` client so the switch needs no code change.

**Embedding (retrieval) model.** Text-only `gemini-embedding-001` by default, read from configuration (`ARCH-CFG-1`), not a constant. The corpus is eight markdown documents, so a multimodal embedding model adds cost and dependence on behavior we do not use. The on-disk vector cache key includes the embedding model ID as well as the content hash, so changing the model never serves stale vectors. The similarity threshold is model-dependent: changing the embedding model means re-tuning it on the eval set.

### D7. Evaluation uses ADK eval for trajectories and our own rule checks for content
Evalsets seed each persona through `session_input.state`. ADK's `tool_trajectory_avg_score` checks tool use. Content checks (must-contain, must-not-contain, refusal phrases, citations) are a small custom runner. `hallucinations_v1` is optional because it may need the Vertex evaluation service (VERIFY on free key). Security cases are a separate set. The threshold-versus-pass-rate table comes from re-running the quality set at three threshold values.

### D8. Layout
```
backend/                      (run: adk web backend/src)
  pyproject.toml
  src/novamart_agent/  agent.py (wiring only), __init__.py
    agents/    intake, retrieval, order, validator, composer, orchestrator
    prompts/   one module per agent (instructions, refusal and escalation wording)
    pipeline/  precheck, routing, rubric_check, confidence (pure, no ADK imports)
    security/  principal, guard, callbacks
    tools/     retrieval, orders, eligibility
    adapters/  orders_api (stub, read-only; the order-system integration)
    rag/       chunker (keeps fenced blocks whole), embedder (disk cache), index
    models.py  typed models: principal, order, chunk, tool result, rubric, verdict, confidence band
  data/  docs/*.md (8 policy + a few product, with doc_type front-matter), orders.json, users.json
  evals/ *.evalset.json + test_config.json (quality, security), content-check runner, results/
  tests/ guard, retrieval threshold, eligibility (pytest, mirrors the package)
docs/  production_note.md
```

### D9. Production target (for the note, not built)
Hybrid: Gemini Enterprise as the front door and document search (permission-aware connectors, workforce identity), with the ADK agent registered as a custom agent through A2A for order logic and hosted on Agent Runtime or Cloud Run. The agent forwards end-user identity so the real order API enforces store scope itself. Document-level ACLs in the search data store must be enabled when the store is created and cannot be changed afterwards (VERIFY). Fallback if identity cannot be passed to registered agents: ADK agent behind IAP, with Gemini Enterprise limited to document search.

### D10. Intake validates the input and builds an intent rubric
A pure `pipeline/precheck` runs first, with no model call: empty, over-length, and known injection patterns return a decline (case B) and the pipeline ends. Otherwise the intake agent (no tools, `output_schema` = typed `Rubric`, VERIFY) returns: `route` (`order`, `knowledge`, `clarify`, `oos`), `doc_type` (`policy` or `product`, for `knowledge`), `criteria` (a short list, each with `text` and `required: bool`), and `missing_slots` (for `clarify`). The rubric breaks the user's intent into checkable parts, for example "states the return window" (required) and "mentions the exception for opened electronics" (optional). The route is a function of the rubric in `pipeline/routing`, so branching is plain, testable Python, not a model decision about which agent runs next. The rubric is model output and therefore untrusted data (D16).

### D11. Validation loop with query rewrite
`LoopAgent(max_iterations=2)` holds `retrieval` then `validator`. On the first pass `retrieval` calls `search_policy` with a query derived from the user message. The validator (no tools, `output_schema` = `Verdict`) receives the rubric and the retrieved chunks and returns, per criterion, `covered: bool` plus a short quote or chunk id, an `llm_confidence` between 0 and 1, and, when coverage is weak, a `rewritten_query`.
The exit decision is made in code, not by the model: an after-agent callback calls `pipeline/confidence` (D12) and sets `escalate` when the composite reaches the configured threshold T, or when iterations are spent. If it does not exit, the rewrite (capped in length, from configuration) goes into state as `query_hint`, and a `before_tool_callback` on `retrieval` overwrites the tool's `query` argument with it, so the model does not choose the argument twice (VERIFY that callbacks may mutate arguments). The loop keeps the best-scoring attempt in state; the composer uses that one, not necessarily the last.
Layering rule (downgrade only): if `search_policy` returns `no_answer` (below the cosine threshold, or audience-filtered), the loop exits at once with case C (D13); the validator can never turn a deterministic refusal into an answer. It can only lower confidence or trigger a rewrite.

### D12. Confidence is a composite, shown as a band
A model's self-reported confidence is poorly calibrated, so it is one input of three: (1) rubric coverage, the fraction of criteria marked covered, computed in code; (2) top cosine score from the retrieval result, normalised; (3) the validator's `llm_confidence`. Composite = weighted sum, weights in configuration. The user sees a band, High, Medium or Low (thresholds in configuration), never a precise number. Cap rule: if any `required` criterion is uncovered, the band cannot exceed Low, regardless of the sum. Defaults are chosen at build time and tuned on the eval set (tasks chunk 8). The band is appended by code, not written by the model. The user remains the final judge; the Sources list (D15) is how they check.

### D13. Refusal and clarification matrix
Declining is not one behavior. Each case has one observable output and one eval scenario:

| Case | Cause | Where | Output |
|---|---|---|---|
| A | Intent under-specified (missing order id, product) | intake | Ask exactly one question, end the turn. At most one clarification per user question (counter in state), then proceed with best effort or decline. |
| B | Empty, injected, or out of scope | precheck or intake | Short decline plus what the assistant covers. No request for more detail. |
| C | No evidence: the gate returns `no_answer` after the allowed rewrite | loop | Decline, escalation contact from the policy docs, and up to 3 closest document titles ("you might mean"). Titles come only from chunks that passed the audience filter, so restricted documents cannot leak. |
| D | Order not found, out of scope, malformed, or throttled | order path | The uniform not-found text, identical for every cause. No follow-up questions about the order, because a question such as "which store?" would confirm existence (`ARCH-ERR-1`). |
| E | Chunks exist, but the validator doubts coverage | composer | Not a refusal: answer with a Low band, a one-line caveat, and Sources. |

Split rule: no deterministic evidence means refuse (C); weak intent match with evidence means answer and flag (E).

### D14. Order shortcut
`route = order` skips the loop. The orchestrator runs `order` (tools `get_order_status`, `check_return_eligibility`, each calling the guard, D3) and then `composer`. There is no validator and no confidence band; the composer labels the reply "from order records". Eligibility already returns the cited policy document id and the front-matter parameters it used (D5), so a normal eligibility answer needs no `search_policy` call. A message that mixes an order question with a free-text policy question is handled by the order path only in this revision (see Open Questions).

### D15. Composer, Sources and visuals
The composer (no tools) formats by `doc_type` of the cited chunks:
- policy: a short summary (at most 5 sentences) plus Sources;
- product: the answer, the diagram, plus Sources;
- order: status or eligibility, the cited policy id, "from order records";
- decline or clarification: the canned wording from `prompts/`.
Visuals are not generated by the model. Product documents carry ASCII diagrams in fenced code blocks; the chunker keeps a fenced block inside one chunk, and code extracts the blocks from the cited chunks and hands them to the composer to include unchanged. An after-model callback checks that every fenced block in the reply appears verbatim in the retrieved chunks and strips any that do not. The Sources list (document title, section heading, file path under `backend/data/docs/`) and the confidence band are appended by code from chunk metadata, so the model cannot invent a citation. `adk web` cannot open local files, so Sources are shown as text paths.

### D16. Trust boundaries in a multi-agent pipeline
- Identity is injected once at the orchestrator (D2) and read from state by tools only. Sub-agents of one orchestrator share the session; a unit test must prove the principal reaches every agent that has a tool, and that no model output can write it (VERIFY ADK state semantics).
- Only `retrieval` and `order` hold tools, so the allowlist and audit callbacks (D3) attach to those two. The guard remains the only path to order data.
- The validator and composer see only the model-facing, already-guarded tool results. Denial and non-existence are indistinguishable there; the audit record stays internal.
- The rubric, the verdict, the rewritten query and retrieved text are all untrusted data. They are passed as message content, not templated into instruction text with `{key}` (ADK instruction templating is a prompt-injection surface; VERIFY). The rewritten query is used only as the `search_policy` query and carries no identity.
- All security guarantees stay in code (guard, allowlist, throttle, audience filter, citation and diagram checks). The validator and the band are quality features, not security controls.

### D17. Cost per question and per session, shown behind a flag
Every model call has a cost, and the pipeline makes 4 to 6 of them per question (D1), so the user is told what the answer cost.
- **Capture (always on).** An after-model callback on every LLM agent reads `usage_metadata` from the response (prompt, candidate, thinking and cached token counts; VERIFY field names and that thinking tokens bill as output) and adds one record (agent, model ID, token counts) to a per-turn list in session state. The orchestrator clears the list at the start of each turn. Pure `pipeline/cost` turns the list into a `TurnCost` (USD, call count, token totals) using a price table keyed by model ID. The query embedding is added as an estimate (`count_tokens` or a character heuristic, because AI Studio may not return embedding token counts; VERIFY). Cache hits cost nothing.
- **Prices are configuration** (`ARCH-CFG-1`): USD per million input and output tokens per model ID, and for the embedding model, next to the model IDs they belong to. Prices are VERIFY items against the current published tier. A model ID with no price entry yields "cost unavailable", never $0.
- **Running session total.** The orchestrator adds each `TurnCost` to a session total in state, which survives for the life of the `adk web` session or `adk run` process. A new session starts at zero.
- **Display (flag).** `NOVAMART_SHOW_COST`, default `true` because the demo is the main audience; `false` hides the line. The flag affects display only: capture and the audit record stay on, because the evals need them. The line is appended by code with Sources and the band (D15), after the composer's own usage has been counted, so it is assembled in the composer's after-model callback, and the model never writes a figure:
```
Cost: ~$0.0021 this answer (5 calls, 3,840 in / 410 out tokens) | session ~$0.0187 over 9 questions
```
  The label says "API-equivalent estimate, not billed" once per session (first reply) because the free key bills nothing; the figure is tokens times the public paid price.
- **Every route shows it.** Precheck declines show `$0.00 (0 calls)`. The order path (D14, D13 case D) shows the same line, and the uniform not-found text is unchanged. Cost must not reveal why an order was denied: the call count and tokens for "nonexistent" and "out of scope" are tested to be equal (`ARCH-ERR-1`).
- **Failed and retried calls.** A call that errors returns no usage and is not counted; retries that succeed are counted. The line is therefore a lower bound under errors, and the README says so.
- **Evals.** The runner reads the same per-turn records, so 8.6 reports cost per question, the mean per route, and the cost of rewrites and retries. The per-question figure also feeds the production note (cost at 1,000 questions).
Alternative: ask the model to report its own usage. Rejected: models do not know their token counts and can invent a number. Alternative: read cost from the Google billing console. Rejected: not per question, delayed, and $0 on a free key.

## Risks / Trade-offs

- [More model calls per question: 4 to 6 against 1 to 2 before] -> `max_iterations=2`, temperature 0, order shortcut skips the loop, embedding cache, retry with backoff; measure calls per question in the eval and report them.
- [The validator is an LLM judge and can be wrong in both directions] -> the deterministic gate refuses first (D11 downgrade-only), the required-criterion cap is code, and the Sources list lets the user verify; report validator agreement on a hand-labelled subset.
- [Rubric quality bounds everything downstream: a bad rubric makes the validator check the wrong things] -> evals include rubric-quality cases; criteria are few and typed; an empty or over-long rubric falls back to a single criterion made from the user message.
- [Clarification turns could loop or annoy] -> one clarification per question, counted in state.
- [Cosine threshold is brittle and model-dependent] → tune on the eval set, report the threshold table, keep the deterministic gate plus prompt rule as two layers.
- [Prototype identity is simulated] → state it in the README and the note; never describe it as authentication.
- [Prompt-injection defences are probabilistic] → the guarantee comes from tool-side authorization and read-only tools; the model-facing rules are defense in depth.
- [Token prices change and the free key bills nothing, so the cost line is a notional estimate] -> prices live in configuration, marked VERIFY, labelled "API-equivalent estimate, not billed"; an unpriced model shows "cost unavailable".
- [Failed calls return no usage, so the cost line is a lower bound under errors] -> stated in the README.
- [Free-tier limits or model availability may flake the eval] → cache embeddings, temperature 0, retry with backoff, pin the model ID in configuration.
- [`adk web` shows full event traces] → synthetic data only, stated in the README.
- [Free AI Studio terms may allow use of inputs to improve products (VERIFY)] → synthetic data only; production uses the paid enterprise platform.
- [Doc claims in the production note go stale] → mark unverified items "to be confirmed" and re-check on the day of writing.
- [Scope vs. time box] → if time runs short, cut rate limiting and the optional judge metric first, and keep cross-store denial, document injection, and log-hygiene tests.

## Open Questions

- Which model IDs are available on the current free tier, and at what rate limits? Resolved by checking AI Studio at build start.
- Do ADK's LLM-judge eval metrics work with a free key? Resolved when the eval is built; the fallback is the custom checks.
- How does Gemini Enterprise pass end-user identity to an A2A-registered agent? A production spike item for the note, not a prototype task.
- Which ADK behaviours in D1, D11 and D16 hold as assumed (LoopAgent exit, `output_schema` with no tools, state sharing across sub-agents, argument mutation in `before_tool_callback`, instruction templating)? Resolved in task 1.4 before any agent is built.
- Combined questions ("can I return order 1042, and what is the policy on gift cards?"): this revision serves them from the order path only. Should the orchestrator instead run the order path and then the knowledge path and merge? Decide after the first eval run shows how common they are.
- Defaults for the confidence weights, band thresholds, the loop-exit threshold T and the rewrite length cap: chosen at build, tuned in task 8.4.
- Spec scenarios in `specs/` need updating for the clarification turn, the refusal split (C against E), the confidence band and the order shortcut. Not done in this revision.
- Cost: do `usage_metadata` field names and thinking-token billing match D17, and does AI Studio return embedding token counts? Resolved in task 1.4 alongside the other ADK checks.
- Cost: the price table defaults (chat and embedding models) are filled at build from the published pricing page and re-checked in 9.2.
