## Change map (revision 2: staged multi-agent pipeline)

```
WHAT CHANGES                                     WHAT STAYS UNTOUCHED
------------                                     --------------------
D1 rewritten: one root LlmAgent                  D2 identity injection (callback -> state)
   -> deterministic staged pipeline              D3 guard = single choke point in tools
NEW  agents/    intake, retrieval, order,        D4 numpy retrieval, per-chunk embeds,
                validator, composer,                content-hash cache, threshold gate
                orchestrator (Workflow)          D5 code computes eligibility
NEW  pipeline/  precheck, routing,               D6 models and backend switch
                rubric_check, confidence (pure)  D9 production note target
NEW  prompts/   one module per agent             The three tools and their signatures
CHG  rag/chunker  keep fenced blocks whole       Data: orders.json, users.json
CHG  data/docs    doc_type + audience front-matter
CHG  config       threshold T, weights, loops

DATA FLOW (details in D10-D16)
  user -> [orchestrator Workflow: principal injected by its first node]
       -> [1 intake: precheck + rubric + route]
            |-- invalid / out of scope ---> decline (B)
            |-- missing slot ------------> ask ONE question (A), end turn
            |-- order -------------------> [order agent] --------------+
            '-- policy | product                                        |
                  -> routed cycle (max 2): [retrieval] -> [validator]  |
                       exit decided in code node (confidence vs T)     |
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
The root is one ADK `Workflow` graph (the orchestrator; revision 3 of D1, 2026-11-24, replacing the custom `BaseAgent` plus `LoopAgent` of revision 2 because ADK 2.15.0 marks `LoopAgent` deprecated in favour of `Workflow`: `agents/loop_agent.py:58-61`). It runs five single-purpose agents in a fixed order, with plain-Python branching: **intake** (validate, classify, build the rubric), **retrieval** and **validator** in a routed cycle (policy and product questions only), **order** (shortcut for order questions), and **composer** (format the reply). The five agents are `LlmAgent` nodes in `single_turn` mode (the workflow default). Between them sit thin function nodes that read session state, call one pure function from `pipeline/` or `security/principal`, write state and emit a route value (`Event(route=...)`). The three tools are unchanged; only `retrieval` holds `search_policy`, only `order` holds the two order tools, and intake, validator and composer have no tools.

Graph (static edges; a route value is chosen by a pure function, never by a model; names are working names):
```
START -> inject_identity -> precheck
precheck        --decline-->    finish_reply
precheck        --proceed-->    intake -> route_turn
route_turn      --clarify|decline--> finish_reply
route_turn      --order-->      order_agent -> after_order
after_order     --compose-->    prepare_compose
after_order     --final-->      finish_reply        (D not_found, F not_determinable)
route_turn      --knowledge-->  retrieval -> after_retrieval
after_retrieval --refuse-->     finish_reply        (C no_answer)
after_retrieval --validate-->   prepare_validation -> validator -> loop_decide
loop_decide     --retry-->      retrieval           (the cycle, max 2 passes)
loop_decide     --done-->       prepare_compose -> composer -> finish_reply
```
`finish_reply` is the last node on every route: it assembles the canned or composed text, Sources, band and cost line in code (D15, D17). `loop_decide` calls `pipeline/confidence` and increments a pass counter in state; it routes `retry` when the composite is below T and fewer than `max_iterations` (2) passes have run, else `done`. `Workflow` has no iteration cap, so this function is the only bound; the graph validator rejects an unconditional cycle, and the cycle here has a routed edge. Adapter nodes (`prepare_validation`, `prepare_compose`) build the validator and composer input as message content from state, so untrusted text is data, not instruction (D16). `agent.py` exposes this `Workflow` as `root_agent`, so `adk web backend/src` and `adk run` load it (the loader accepts a `BaseNode` root: `cli/utils/agent_loader.py:140`).
Why: the owner wants input validation, cross-checking of retrieved output against the user's intent, and a reply template per document type. Each is a separate responsibility with a separate failure mode, and separate agents let each be evaluated alone. A `Workflow` expresses the whole fixed pipeline, including the branch for the order shortcut and the bounded loop, in one declared graph, with no custom `BaseAgent` subclass.
Rejected alternatives: (a) the previous single agent with three tools: cannot cross-check its own retrieval or format by document type without stuffing all duties into one prompt; (b) an LLM router with `sub_agents` or `AgentTool`: the model would choose the route and the identity-propagation story becomes harder to prove; (c) `SequentialAgent`: no branch for the order shortcut (D14), and also deprecated in 2.15.0; (d) custom `BaseAgent` plus `LoopAgent` (revision 2): `LoopAgent` is deprecated and will be removed; owner decision not to build on it; (e) custom `BaseAgent` with its own Python `while` loop over `sub_agent.run_async`: not deprecated and workable, but it keeps a hand-written orchestrator the framework is moving away from; kept as the fallback if the `Workflow` probes in task 1.4 fail, with the deviation recorded; (f) one `Workflow` node that runs the agents dynamically with `ctx.run_node()` inside a Python loop: also valid, but it hides the pipeline in one large function and loses the visible graph in `adk web`.
Cost: one policy question now costs 4 to 6 model calls (intake, retrieve, validate, optional retry pair, compose) instead of 1 to 2, which matters on the free tier (see Risks) and is why the user is shown the cost (D17).
Architect agent review: run as task 1.5 on architecture v7 (see "Task 1.5 findings" below); the spec is owner-approved before chunk 7.
ADK APIs relied on (source-read in 2.15.0; behaviour VERIFY owner-run in task 1.4, see "Workflow findings"): `Workflow(name, edges=[...])`, `START`, function nodes and `Event(route=...)`, a routed cycle, `LlmAgent` as a `single_turn` node, node retry config, session state shared across nodes, `output_schema` (works with tools; no structural effect here), and `before_tool_callback` argument mutation.

### D2. Identity is injected, never passed by the model
A callback before each session populates a principal (user, store, role) in session state from a stand-in auth context (`NOVAMART_USER` selects a persona from a users file). Tool signatures contain no user or store parameter; tools read the principal from the tool context. This is what makes "I'm the manager" in chat harmless. Alternative: pass role in the prompt and trust the model to enforce it. Rejected: the model decides tool arguments, so any prompt-level rule can be argued away.
The ADK docs describe session state as server-side but do not explicitly state that end users cannot alter it (VERIFY). In production, identity must be derived from the authenticated token in the application's API layer, never from the request body.

### D3. Authorization is a single choke point in tool code
One shared authorization function is called after fetch and before return by both order tools, deny-by-default, with a uniform "not found or not accessible" response for both nonexistent and out-of-scope orders. A before-tool callback adds a per-role tool allowlist and writes the audit record. Alternative: filter in the order stub only. Rejected: eligibility would become a second, unguarded path.

### D4. Hand-rolled retrieval with a deterministic refusal gate
Chunk documents by markdown heading, embed with the configured embedding model (default `gemini-embedding-001`, D6) using `RETRIEVAL_DOCUMENT` and `RETRIEVAL_QUERY` task types, cache vectors on disk keyed by content hash, cosine similarity in numpy, top-3, threshold from configuration. Below threshold the tool returns `no_answer` and code produces the decline from canned wording (D13 case C), with no model call (the halt mechanism is in D13). Embed each chunk in its own call, because several strings in one call return a single aggregated embedding. Audience labels are carried in document front-matter and filtered before ranking.
Alternatives: (a) Gemini File Search tool: no similarity score to gate refusal. (b) Vertex AI Search / RAG Engine: the production answer, but needs cloud setup and is overkill for eight documents. (c) `gemini-embedding-2`: multimodal, no `task_type`, needs prefix conventions; see D6 for why a text-only model is the choice.
ADK still forbids mixing built-in tools with function tools in one agent, which another reason for a custom function tool.

### D5. Code decides eligibility, the model explains
Policy parameters (return window, excluded categories) live in structured front-matter in the returns document, and the prose is retrieved separately for citation. Python computes eligibility from order data plus those parameters. Alternative: let the model read the policy and do date math. Rejected: error-prone and untestable.

### D6. Models and backend configuration
Model ID comes from configuration, defaulting to a current stable Flash-class model (candidates reported: `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`; VERIFY availability on the free tier). `gemini-2.5-flash` is deprecated and must not be used. Backend switch: AI Studio via `GOOGLE_API_KEY`; Vertex-based via `GOOGLE_GENAI_USE_ENTERPRISE=TRUE` plus project and location (`GOOGLE_GENAI_USE_VERTEXAI` is documented as equivalent and is the safe choice on older ADK). Embedding calls must go through the same `google-genai` client so the switch needs no code change.

**Setup for the free key.** `.env` (real) and `.env.example` live in `backend/`, next to `pyproject.toml` and outside the importable package; ADK finds `backend/.env` by walking up from `backend/src/novamart_agent/`. `.env.example` sets `GOOGLE_API_KEY` and, explicitly, `GOOGLE_GENAI_USE_ENTERPRISE=FALSE` (and the legacy `GOOGLE_GENAI_USE_VERTEXAI=FALSE`) so an ambient Vertex flag in the developer shell cannot route to Vertex. `google-adk` is pinned to the version verified in task 1.3. Live model calls during setup and agent verification are owner-gated (ARCH-TEST-3): authored, not run, until the owner supplies the key and says to run.

**Embedding (retrieval) model.** Text-only `gemini-embedding-001` by default, read from configuration (`ARCH-CFG-1`), not a constant. The corpus is eight markdown documents, so a multimodal embedding model adds cost and dependence on behavior we do not use. The on-disk vector cache key includes the embedding model ID as well as the content hash, so changing the model never serves stale vectors. The similarity threshold is model-dependent: changing the embedding model means re-tuning it on the eval set.

### D7. Evaluation uses ADK eval for trajectories and our own rule checks for content
Evalsets seed each persona through `session_input.state`. ADK's `tool_trajectory_avg_score` checks tool use. Content checks (must-contain, must-not-contain, refusal phrases, citations) are a small custom runner. `hallucinations_v1` is optional because it may need the Vertex evaluation service (VERIFY on free key). `adk eval` needs the `google-adk[eval]` extra, declared in the `dev` optional-dependencies and installed with `pip install -e backend[dev]`. Security cases are a separate set. The threshold-versus-pass-rate table comes from re-running the quality set at three threshold values.

### D8. Layout
```
backend/                      (run: adk web backend/src)
  pyproject.toml
  .env.example                (copy to .env; gitignored)
  src/novamart_agent/  agent.py (wiring only), __init__.py
    agents/    intake, retrieval, order, validator, composer, orchestrator (the Workflow graph and its function nodes)
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
A pure `pipeline/precheck` runs first, with no model call: empty, over-length, and known injection patterns return a decline (case B) and the pipeline ends. Otherwise the intake agent (no tools, `output_schema` = typed `Rubric`, VERIFY) returns: `route` (`order`, `knowledge`, `clarify`, `oos`), `doc_type` (`policy` or `product`, for `knowledge`), `criteria` (a short list, each with `text` and `required: bool`), and `missing_slots` (for `clarify`). A malformed order id (for example `10x2`) is never treated as a missing slot: intake routes it to `order` and the order tool rejects it (AG-43), so the whole turn makes the same model calls as for a nonexistent order. The rubric breaks the user's intent into checkable parts, for example "states the return window" (required) and "mentions the exception for opened electronics" (optional). The route is a function of the rubric in `pipeline/routing`, so branching is plain, testable Python, not a model decision about which agent runs next. The rubric is model output and therefore untrusted data (D16).

### D11. Validation loop with query rewrite
The loop is a routed cycle in the orchestrator `Workflow` (D1): `retrieval`, then `validator`, then the `loop_decide` function node, which routes back to `retrieval` or onward, with at most 2 passes (`max_iterations`, configuration). On the first pass `retrieval` calls `search_policy` with a query derived from the user message. The validator (no tools, `output_schema` = `Verdict`) receives the rubric and the retrieved chunks and returns, per criterion, `covered: bool` plus a short quote or chunk id, an `llm_confidence` between 0 and 1, and, when coverage is weak, a `rewritten_query`.
The exit decision is made in code, not by the model: the `loop_decide` function node calls `pipeline/confidence` (D12) and routes `done` when the composite reaches the configured threshold T or when the pass counter in state reaches `max_iterations`, else `retry`; no model-driven agent sets an `escalate` flag. If it does not exit, the rewrite (capped in length, from configuration) goes into state as `query_hint`, and a `before_tool_callback` on `retrieval` overwrites the tool's `query` argument with it, so the model does not choose the argument twice (VERIFY that callbacks may mutate arguments). The loop keeps the best-scoring attempt in state; the composer uses that one, not necessarily the last.
Layering rule (downgrade only): if `search_policy` returns `no_answer` (below the cosine threshold, or audience-filtered), the `after_retrieval` node routes straight to `finish_reply` with case C (D13) and no query rewrite is attempted, because the validator has no chunks to judge; the validator can never turn a deterministic refusal into an answer. It can only lower confidence or trigger a rewrite.

### D12. Confidence is a composite, shown as a band
A model's self-reported confidence is poorly calibrated, so it is one input of three: (1) rubric coverage, the fraction of criteria marked covered, computed in code; (2) top cosine score from the retrieval result, normalised; (3) the validator's `llm_confidence`. Composite = weighted sum, weights in configuration. The user sees a band, High, Medium or Low (thresholds in configuration), never a precise number. Cap rule: if any `required` criterion is uncovered, the band cannot exceed Low, regardless of the sum. Defaults are chosen at build time and tuned on the eval set (tasks chunk 8). The band is appended by code, not written by the model. The user remains the final judge; the Sources list (D15) is how they check.

### D13. Refusal and clarification matrix
Declining is not one behavior. Each case has one observable output and one eval scenario:

| Case | Cause | Where | Output |
|---|---|---|---|
| A | Intent under-specified (missing order id, product) | intake | Ask exactly one question, end the turn. At most one clarification per user question (counter in state), then proceed with best effort or decline. |
| B | Empty, injected, or out of scope | precheck or intake | Short decline plus what the assistant covers. No request for more detail. |
| C | No evidence: the gate returns `no_answer` (no rewrite is attempted) | loop | Tell the user nothing was found and to ask a new question, give the escalation contact, and up to 3 closest document titles ("you might mean"). Titles come only from chunks that passed the audience filter, so restricted documents cannot leak. The text is canned wording assembled by code with no model call and the composer is skipped. The escalation contact comes from a non-model lookup of a front-matter field in the store operations document, read at load (`ARCH-CFG-2`: no policy fact is hard-coded); the same lookup serves the order-eligibility "cannot determine" reply. |
| D | Order not found, out of scope, malformed, or throttled | order path | The uniform not-found text, identical for every cause, produced by code (a fixed string) so that the turn ends with no further model call that could differ by cause. A malformed id is rejected the same way, with no lookup, and only inside the order tool: intake and precheck never reject or reroute it (AG-43), so the whole-turn call count equals that of a nonexistent order. No follow-up questions about the order, because a question such as "which store?" would confirm existence (`ARCH-ERR-1`). |
| E | Chunks exist, but the validator doubts coverage | composer | Not a refusal: answer with a Low band, a one-line caveat, and Sources. Code then appends the escalation contact on every E reply, because the assistant could not fully help; it comes from the same non-model front-matter lookup as case C (`ARCH-CFG-2`), never from model text. NOTE: this extends `ARCH-ERR-2`, which describes E without a contact line; the architecture edit needs the owner's approval as a separate proposal. |
| F | `check_return_eligibility` returns `not_determinable` (policy parameters missing or unreadable in the returns document front-matter) | order path | Canned wording saying eligibility cannot be determined, plus the escalation contact from the same non-model lookup as case C. Produced by code, no composer, no model call after the tool result. |

Split rule: no deterministic evidence means refuse (C); weak intent match with evidence means answer and flag (E).

Ending the turn at a deterministic result (AG-24): the retrieval and order agents are LLM agents holding a tool, and a standard `LlmAgent` calls the model again after a tool result to write text. For `no_answer` (C), `not_found` (D) and `not_determinable` (F) that extra call must not happen. The order agent's after-tool callback also stores the structured `check_return_eligibility` success result (policy id and parameters) in state, so the orchestrator reads the id from state and never from model-written text (AG-41). On the retrieval agent there is one combined after-tool callback (AG-40): it first records the query-embedding cost estimate (skipped when the result's `embedding_cache_hit` is true), then performs the halt below, so the `no_answer` path, which still embeds the query, is still costed. An after-tool callback on those two agents recognises the status, stores the result in state, and sets the tool context's `skip_summarization` so the agent node halts at the tool result and completes with no output; the next function node (`after_retrieval` or `after_order`) reads the status from state and routes to `finish_reply`, which assembles the canned reply in code. VERIFY in task 1.4 that this halts without a further model call; if it does not, fall back to the orchestrator calling the guarded tool in code (revisit D1 and D16) and record the deviation under Open Questions.

### D14. Order shortcut
`route = order` skips the loop. The orchestrator runs `order` (tools `get_order_status`, `check_return_eligibility`, each calling the guard, D3) and then `composer`. There is no validator and no confidence band; the composer labels the reply "from order records". Eligibility already returns the cited policy document id and the front-matter parameters it used (D5), so a normal eligibility answer needs no `search_policy` call. A message that mixes an order question with a free-text policy question is handled by the order path only in this revision (see Open Questions). Intake marks the unanswered policy criteria in the rubric, and code appends a fixed limitation sentence to the order reply saying the policy part is not answered; it is testable without a key.

### D15. Composer, Sources and visuals
The composer (no tools) formats by `doc_type` of the cited chunks:
- policy: a short summary (at most 5 sentences) plus Sources;
- product: the answer, the diagram, plus Sources;
- order: status or eligibility, the cited policy id, "from order records";
- decline or clarification: not composed by the model; code produces the canned wording from `prompts/` and the composer is skipped (D13).
Visuals are not generated by the model. Product documents carry ASCII diagrams in fenced code blocks; the chunker keeps a fenced block inside one chunk, and code extracts the blocks from the cited chunks and hands them to the composer to include unchanged. An after-model callback checks that every fenced block in the reply appears verbatim in the retrieved chunks and strips any that do not. The final reply on every route (composer text or canned decline, Sources, confidence band, cost line) is assembled by the orchestrator in code after the last sub-agent or decline, including precheck declines and the not-found text, which make no model call. The Sources list (document title, section heading, file path under `backend/data/docs/`) and the confidence band are appended by code from chunk metadata, so the model cannot invent a citation. On the order route there are no retrieved chunks: code builds the Sources entry from the policy document id returned by `check_return_eligibility` and stored in state by the order agent's after-tool callback (AG-41), resolving it to document title and file path through a loader in `rag/` (ARCH-CFG-2: the id-to-document mapping is config-driven). The section heading is omitted on that route. No id returned means no Sources entry. `adk web` cannot open local files, so Sources are shown as text paths.

### D16. Trust boundaries in a multi-agent pipeline
- Identity is injected once at the orchestrator (D2) and read from state by tools only. Sub-agents of one orchestrator share the session; a unit test must prove the principal reaches every agent that has a tool, and that no model output can write it (VERIFY ADK state semantics).
- Only `retrieval` and `order` hold tools, so the allowlist and audit callbacks (D3) attach to those two. The guard remains the only path to order data.
- The validator and composer see only the model-facing, already-guarded tool results. Denial and non-existence are indistinguishable there; the audit record stays internal.
- The rubric, the verdict, the rewritten query and retrieved text are all untrusted data. They are passed as message content, not templated into instruction text with `{key}` (ADK instruction templating is a prompt-injection surface; VERIFY). The rewritten query is used only as the `search_policy` query and carries no identity.
- All security guarantees stay in code (guard, allowlist, throttle, audience filter, citation and diagram checks). The validator and the band are quality features, not security controls.

### D17. Cost per question and per session, shown behind a flag
Every model call has a cost, and the pipeline makes 4 to 6 of them per question (D1), so the user is told what the answer cost.
- **Capture (always on).** An after-model callback on every LLM agent reads `usage_metadata` from the response (prompt, candidate, thinking and cached token counts; VERIFY field names and that thinking tokens bill as output) and adds one record (agent, model ID, token counts) to a per-turn list in session state. The orchestrator clears the list at the start of each turn. Pure `pipeline/cost` turns the list into a `TurnCost` (USD, call count, token totals) using a price table keyed by model ID. The query embedding is added as an estimate (`count_tokens` or a character heuristic, because AI Studio may not return embedding token counts; VERIFY) by the combined after-tool callback on the retrieval agent (D14), not by the pure `rag` layer or the orchestrator. `search_policy` returns an `embedding_cache_hit` field in every result, including `no_answer`, set by the `rag` embedder with no ADK import (AG-40). The callback records the estimate first, then does the halt, and adds the record only when `embedding_cache_hit` is false, so cache hits cost nothing.
- **Prices are configuration** (`ARCH-CFG-1`): USD per million input and output tokens per model ID, and for the embedding model, next to the model IDs they belong to. Prices are VERIFY items against the current published tier. A model ID with no price entry yields "cost unavailable", never $0.
- **Running session total.** The orchestrator adds each `TurnCost` to a session total in state, which survives for the life of the `adk web` session or `adk run` process. A new session starts at zero.
- **Display (flag).** `NOVAMART_SHOW_COST`, default `true` because the demo is the main audience; `false` hides the line. The flag affects display only: capture and the audit record stay on, because the evals need them. The line is appended by code with Sources and the band (D15), after the composer's own usage has been counted, so the orchestrator assembles it on every route, including routes with no model call; the composer's after-model callback only counts the composer's own usage first, and the model never writes a figure:
```
Cost: ~$0.0021 this answer (5 calls, 3,840 in / 410 out tokens) | session ~$0.0187 over 9 questions
```
  The label says "API-equivalent estimate, not billed" once per session (first reply) because the free key bills nothing; the figure is tokens times the public paid price.
- **Every route shows it.** Precheck declines show `$0.00 (0 calls)`. The order path (D14, D13 case D) shows the same line, and the uniform not-found text is unchanged. Cost must not reveal why an order was denied: the denial text is code-produced and ends the turn, so the call count for "nonexistent", "out of scope" and "malformed" is equal and the reply comes from one code path (`ARCH-ERR-1`). Token totals are not promised equal across different user messages, because prompt text differs; they are compared only for the same message text in the eval. A key-free test with fake usage records checks the call count and that the three replies are the same text.
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
- How does Gemini Enterprise pass end-user identity to an A2A-registered agent? A production spike item for the note, not a prototype task. Kept open by owner decision (2026-11-23); no prototype task depends on it.
- Which ADK behaviours in D1, D11 and D16 hold as assumed (a routed `Workflow` cycle that re-runs the retrieval and validator nodes, `output_schema` with tools (settled: they coexist), state sharing across nodes, argument mutation in `before_tool_callback`, instruction templating, and an after-tool callback or `skip_summarization` action that ends an agent node's turn at a `no_answer`, `not_found` or `not_determinable` result with no further model call)? Resolved in task 1.4 before any agent is built. Decided (owner, 2026-11-24): `LoopAgent` is not used because it is deprecated; the orchestrator is a `Workflow` (D1). The `Workflow` items still needing an owner-run probe are listed under "Workflow findings".
- Combined questions ("can I return order 1042, and what is the policy on gift cards?"): this revision serves them from the order path only. Should the orchestrator instead run the order path and then the knowledge path and merge? Decided (owner, 2026-11-23): order path only for the prototype; the policy part of a combined question is a documented limitation in the README and production note.
- Defaults for the confidence weights, band thresholds, the loop-exit threshold T and the rewrite length cap: decided (owner, 2026-11-23) to live in configuration, be set at build and tuned in task 8.5; no task waits.
- Spec scenarios in `specs/` need updating for the clarification turn, the refusal split (C against E), the confidence band and the order shortcut. Decided (owner, 2026-11-23): carried by task 8.1; no other task waits on it.
- Cost: do `usage_metadata` field names and thinking-token billing match D17, and does AI Studio return embedding token counts? Resolved in task 1.4 alongside the other ADK checks.
- Cost: the price table defaults (chat and embedding models) are filled at build from the published pricing page and re-checked in 9.2. Decided (owner, 2026-11-23); no task waits.

### Task 1.4 findings (2026-11-23, backend-dev chunk 1)

Source of each line: **source-read** = read in the installed `google-adk` 2.15.0 / `google-genai` 2.34.0 under `backend/.venv`; **doc** = adk.dev / AI Studio page text; **owner-run needed** = `backend/evals/check_adk_assumptions.py` and `backend/evals/verify_models.py` (authored, not run; ARCH-TEST-3). Nothing here was proven by a live model call.

| Assumption | Status | Evidence and design effect |
|---|---|---|
| `LoopAgent` exits on `escalate` | source-read: confirmed, with a deviation | `agents/loop_agent.py` sets `should_exit` when `event.actions.escalate` is true. But 2.15.0 marks `LoopAgent` **deprecated in favour of `Workflow`** (and says `Workflow` cannot yet be an `LlmAgent` sub-agent). **Superseded 2026-11-24: owner decided to move to `Workflow`; see "Workflow findings".** Probe `loop-escalate` is replaced by a `Workflow` loop probe. |
| Custom `BaseAgent` with plain-Python branching | source-read: confirmed (now only the fallback option (e) of D1; `BaseAgent` itself is not deprecated) | `BaseAgent._run_async_impl(ctx)` is an async generator; an orchestrator may call `sub_agent.run_async(ctx)` and yield its events; `ctx.session.state` is readable. Probe: `custom-baseagent-branch`. |
| `output_schema` disables tools | source-read: **deviation** | `LlmAgent.output_schema` docstring (llm_agent.py ~L471): "ADK supports using `output_schema` and `tools` together" (tools exposed during the thought loop, structure enforced on the final output). So the assumption that an `output_schema` agent cannot hold tools is false on 2.15.0. Effect: none on the design, since intake and validator hold no tools by rule (ARCH-MOD-5), not by ADK limitation. Owner confirmed 2026-11-24: D1's earlier assumption was wrong, no structural change. Probe: `output-schema-with-tools`. |
| State shared across sub-agents of one orchestrator | source-read: confirmed | Sub-agents run with the same `InvocationContext` and `session`; `output_key` and `tool_context.state` write to the one session. Whether a model output can write the principal key still needs the unit test in D16. Probe: `custom-baseagent-branch` (reads shared state). |
| Argument mutation in `before_tool_callback` | source-read: confirmed | `flows/llm_flows/tools/_caller.py` passes the same `function_args` dict to the before-tool callback (`args=function_args`) and later to the tool (`args=prepared_call.function_args`). Mutating it in place applies. A callback that returns a dict instead replaces the tool result and skips the tool. Probe: `before-tool-arg-mutation`. |
| `{key}` instruction templating | source-read: confirmed as an injection surface | `inject_session_state` (flows/llm_flows/prompt/_instructions_utils.py) substitutes `{name}` from session state into instruction text (regex engine by default). Keep D16 rule: untrusted text goes in message content, never into templated instructions. Probe: `instruction-templating`. |
| After-tool callback ends the turn with no further model call (C, D, F) | source-read: confirmed, mechanism named | Setting `tool_context.actions.skip_summarization = True` (inside the tool or in `after_tool_callback`) makes the function-response event `is_final_response()` true (events/event.py ~L312), and `BaseLlmFlow.run_async` breaks on a final-response last event (base_llm_flow.py ~L300). `EventActions.skip_summarization` docs: "If true, it won't call model to summarize function response." Note: `_build_response_event` also adds a displayable text part of the tool result when summarization is skipped, so the canned wording must be what the orchestrator replaces (D15), not what the user sees from the tool dict. Probe: `skip-summarization-no-extra-call` (expects 1 model call). |
| `usage_metadata` fields | source-read: partial | `LlmResponse.usage_metadata` is `google.genai.types.GenerateContentResponseUsageMetadata`; ADK code reads `thoughts_token_count` and `cached_content_token_count`, with cached tokens a breakdown of `prompt_token_count`. Exact field values from AI Studio for `gemini-3.6-flash` need the owner-run probe (prints `usage_metadata`). |
| Thinking tokens bill as output | doc: unconfirmed for this model | The AI Studio pricing page labels Flash output price "(incl. thinking)" per the fetched text; mark **VERIFY** against the live page and a billed call; D17 sums `thoughts_token_count` into output until then. |
| Embedding returns token counts | owner-run needed | `verify_models.py` prints `embed_content` `metadata` and per-embedding `statistics`. Until seen, keep D17's estimate path (`count_tokens` or character heuristic). |

Other setup findings (source-read):
- ADK `.env` loading (`cli/utils/envs.py`): walks up from the agent folder to the first `.env` (so `backend/.env` is found from `backend/src/novamart_agent`), but variables already set in the shell **win over `.env`** (`os.environ.update(explicit_env)` after the load). The `GOOGLE_GENAI_USE_ENTERPRISE=FALSE` line in `.env` therefore does not override an ambient `TRUE` in the shell; the README must say to unset it.
- ADK 2.15.0 reads `GOOGLE_GENAI_USE_ENTERPRISE` (legacy `GOOGLE_GENAI_USE_VERTEXAI` still accepted per `agents/_managed_agent.py`), as D6 says.
- ADK's own default model is `gemini-3.5-flash`; it does not appear in the AI Studio pricing rows read on 2026-11-23, so this project keeps its own configured default.

### Task 1.2 findings (doc-read 2026-11-23; live check owner-run needed)

Read on the AI Studio pricing page (`aistudio.google.com/docs/pricing`, via a summarising fetch; **VERIFY** every figure against the live page): free tier listed for `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3-flash-preview`, `gemini-2.5-flash` (deprecated; routes to `gemini-3.5-flash-lite` from 2026-12-01), `gemini-2.5-flash-lite`, and `gemini-embedding-001`. Paid standard prices per 1M tokens (input / output incl. thinking): `gemini-3.6-flash` 0.75 / 3.75 through 2026-12-31 then 1.50 / 7.50 from 2027-01-01; `gemini-3.8-flash` same; `gemini-3.5-flash-lite` 0.30 / 2.50; `gemini-embedding-001` 0.15 input. The rate-limits page publishes no per-model free-tier figures (they are shown in the AI Studio rate-limit view for the key), so the limits are an owner-run item. Default chat model stays the provisional `gemini-3.6-flash`; prices and IDs are in `config.py` marked VERIFY. Price promo ends mid-project horizon (2027-01-01): D17's table should be re-read before 9.2.

### Workflow findings (2026-11-24, architect, for task 1.4 and the v7 proposal)

Source of each line: **source-read** = installed `google-adk` 2.15.0 under `backend/.venv/Lib/site-packages/google/adk`; **doc** = adk.dev pages `workflows/`, `graphs/`, `agents/workflow-agents/loop-agents/` (summarising fetch, VERIFY wording); **owner-run needed** = not provable without a model call. Nothing here was run.

| Question | Status | Evidence and design effect |
|---|---|---|
| `LoopAgent` is deprecated | source-read: confirmed; doc: confirmed | `agents/loop_agent.py:58-61` `@deprecated('LoopAgent is deprecated in favor of Workflow and will be removed in a future version. Workflow cannot yet be used as an LlmAgent sub-agent.')`; `SequentialAgent` (`sequential_agent.py:86`) and `ParallelAgent` (`parallel_agent.py:172`) carry the same notice. The adk.dev loop page is marked "Deprecated: Use graph-based workflows" and gives no migration example. Our root is the `Workflow`, so the "not yet an LlmAgent sub-agent" limit does not apply. |
| `Workflow` is a public, non-experimental API with `START`, `Edge`, `Node` | source-read: confirmed | `workflow/__init__.py` exports `Workflow`, `START`, `BaseNode`, `FunctionNode`, `JoinNode`, `RetryConfig`, `DEFAULT_ROUTE`; `_workflow.py` has no experimental or deprecated marker. `BaseAgent` is a `BaseNode` subclass (`agents/base_agent.py:126`), so `LlmAgent` can be an edge target directly. |
| A cycle is allowed when it has a routed edge | source-read: confirmed | `workflow/utils/_graph_validation.py` `_detect_unconditional_cycles` raises only for a cycle made entirely of unrouted edges ("Cycles must include at least one conditional (routed) edge to avoid infinite loops"). Our `loop_decide -> retrieval` edge has the route `retry`. |
| `Workflow` has an iteration cap like `LoopAgent.max_iterations` | source-read: **no** | No `max_iterations` or loop limit in `_workflow.py` (only `max_concurrency`). The bound is ours: `loop_decide` counts passes in state and routes `done` at `max_iterations`. This stays a pure function in `pipeline/` with a key-free test (task 6.3). An unbounded loop would need a bug in that function; the test must cover iteration exhaustion. |
| Code-decided exit and routing | source-read + doc: confirmed | A function node returns `Event(route=...)` (`events/event.py:34,190,237` convenience kwarg `route`; adk.dev `graphs/` page shows `Event(route=routes)` and a routing map). `graph.get_next_pending_nodes` follows the matching edge, falls back to `DEFAULT_ROUTE`, and logs a warning and ends the branch if nothing matches, so every route value must have an edge (test it). Route values are `bool`, `int` or `str`. Routing stays plain Python (AGENT-2). |
| Function nodes read and write session state | source-read: confirmed | `_function_node.py` `_to_event` attaches `ctx.actions.state_delta` to the emitted event, so `ctx.state` writes in a function node persist. Parameters bind from `ctx.state` by name by default (`parameter_binding='state'`); a `state_schema` can type them. |
| `LlmAgent` runs as a node with its callbacks | source-read: confirmed, behaviour owner-run | `workflow/_llm_agent_wrapper.py:490-500`: a `single_turn` node runs `effective_agent.run_async(ic)`, the normal flow, so `before_tool_callback`, `after_tool_callback`, `after_model_callback` and `skip_summarization` apply. `effective_agent` may be a clone (`LlmAgent.clone`, `llm_agent.py:~1425`); VERIFY callbacks survive it. Output: the final model text becomes the node output; with `output_schema` it is validated into the typed value (`_llm_agent_wrapper.py:409-413`) and `output_key` is also written to state. |
| A node halted at a tool result (`skip_summarization`) completes and triggers its successor | owner-run needed | The function-response event has no model text, so `process_llm_agent_output` sets no output (the event role is `user`, line ~396). The successor must therefore read state (the after-tool callback already stores the result), not `node_input`. VERIFY the node completes (not `wait_for_output`) and the successor runs, with one model call only. Probe: `skip-summarization-in-workflow-node`. |
| Re-running an agent node in a cycle | owner-run needed | Second pass of `retrieval` and `validator` in one invocation: VERIFY the node gets the intended input (`prepare_validation` builds it) and that the first pass's conversation is not replayed to the model. Mitigation if it is: `include_contents='none'` on those agents (`llm_agent.py:448`), with every input passed by the adapter node. Probe: `workflow-loop-two-passes`. |
| Retry on model failure | source-read: partial | `RetryConfig(max_attempts, initial_delay, max_delay, backoff_factor, jitter, exceptions)` on any node (`_retry_config.py`); a node failure with no retry shuts the workflow down (`_workflow.py:430,487` `error_shut_down`), and there is no error edge. So a model failure ends the turn visibly through ADK after retries; it cannot be routed to a canned message. VERIFY `retry_config` on an agent node retries a 429. Recorded in `ARCH-ERR-1`. |
| Final reply from a function node | source-read: confirmed, display owner-run | `_to_event` turns a returned `types.Content` into `Event(content=...)`, and a `str` or dict into `Event(output=...)`. VERIFY which the `adk web` chat and `adk run` show as the final answer. |
| `adk web` / `adk run` load a `Workflow` root | source-read: confirmed | `cli/utils/agent_loader.py:140,192` accept `root_agent` that is a `BaseAgent` or `BaseNode`; `runners.py:1240,1374` route a `BaseNode` root through the node runner. |
| `adk eval` works with a `Workflow` root | owner-run needed | Not read. If it does not, the eval trajectory metric (D7) falls back to the custom runner reading tool calls from events. Record the result in 1.4. |
| Identity injection | design change | The old before-agent callback on the orchestrator becomes the first function node `inject_identity` (calls `security/principal`, writes state). The identity-propagation test (7.5) is unchanged in intent. |

Probes are written by `backend-dev` in `backend/evals/check_adk_assumptions.py` (outside the architect's write scope): replace `loop-escalate` and `custom-baseagent-branch` with `workflow-loop-two-passes` (routed cycle, pass counter, code exit), `skip-summarization-in-workflow-node` and `workflow-final-reply`; keep the others. Authored, not run, until the owner supplies the key and says run (ARCH-TEST-3).

### Live probe results (2026-11-24, owner-run, tasks 1.2 to 1.4; google-adk 2.15.0, google-genai 2.34.0)

Run from the repo root with `backend/.venv`: `verify_models.py` and `check_adk_assumptions.py`, plus `adk eval --help` and `adk run` by hand. Every Workflow assumption in D1, D11 and D16 held; no design change is needed.

| Probe | Result | Note |
|---|---|---|
| `verify_models.py` chat (`gemini-3.6-flash`) | PASS | One call answered on the free key. `usage_metadata` has `prompt_token_count`, `candidates_token_count`, `thoughts_token_count` (58 on a one-word reply), `total_token_count`. Thinking tokens are reported apart from candidates tokens, so D17 must sum `thoughts_token_count` into output. |
| `verify_models.py` embedding (`gemini-embedding-001`) | PASS | 3072 dimensions. `metadata` and per-embedding `statistics` are `None`: AI Studio returns no embedding token counts, so D17 keeps the estimate path (characters per token). |
| `workflow-loop-two-passes` | PASS | A routed cycle ran two passes, the second saw only its own input (no replay of pass one), the counter in state persisted, and the code-decided route exited. |
| `skip-summarization-in-workflow-node` | PASS | One model call; the node completed and the successor ran; the result is in state and `node_input` is `None`, so the successor must read state. |
| `workflow-final-reply` | PASS (partial) | Under `adk run`, an `Event(content=...)` reply is shown and a `str`/`output` return is not. Use `Event(content=...)` for the user-facing reply. How `adk web` renders each form still needs a look by eye in chunk 7. |
| `callbacks-survive-clone` | PASS | Callbacks and tools survive `LlmAgent.clone` (attribute level). |
| `retry-config-429` | PASS | A 429 on an agent node was retried (2 attempts) and then answered, so ARCH-ERR-1 wording stands. |
| `before-tool-arg-mutation` | PASS | In-place mutation reaches the tool. |
| `output-schema-with-tools` | PASS | Coexist. |
| `instruction-templating` | PASS | `{key}` is rendered from state (keep untrusted text out of instructions). |
| `embedding-token-counts` | INCONCLUSIVE (answers the question: none returned) | See the embedding row above. |
| `adk eval --help` | PASS | Runs. |
| `adk run backend/src/novamart_agent` | PASS | The minimal agent replied to one line. |
| `adk-eval-workflow-root` | open | Needs the `Workflow` root and an evalset (chunk 7/8). If it fails then, D7 falls back to the custom runner reading tool calls from events. |

Task 1.2: default chat model stays `gemini-3.6-flash` and default embedding model `gemini-embedding-001` (both answered live). Published prices in `config.py` are unchanged (read 2026-11-23, re-check in 9.2). Free-tier rate limits are not published per model; they are visible in the AI Studio rate-limit view for the key and are not recorded here. Task 1.6: `google-adk==2.15.0` and `google-adk[eval]==2.15.0` in `dev` are in `pyproject.toml`; `pip install -e backend[dev]` succeeds.

### Task 1.5 findings (2026-11-24, architect review of architecture v7)

1. [fixed in v7] The v6 text tied the loop to `LoopAgent` and its `escalate` flag in `ARCH-LAYER-1`, the pattern table, section 13 and `ARCH-ERR-2`; v7 moves loop exit to a code decision on a routed edge and bans deprecated ADK APIs (`AGENT-6`).
2. [fixed in v7] `ARCH-ERR-1` did not say what happens when a model call fails (free-tier 429 is likely). v7 states: retried by the node retry policy, then the turn fails visibly; no model-written fallback. Not an outcome A-E, as the generic failure already was not. The owner should confirm this is acceptable for the demo.
3. [open, owner] `Workflow` has no on-error route, so the "fixed non-model message" for an unexpected failure (`ARCH-ERR-1`) applies to tool exceptions (converted by the tool layer), not to node or model failures. If the owner wants a canned message for those too, the pipeline would run each agent through `ctx.run_node()` inside try/except in a function node (D1 option (f)); that is a larger change and is not proposed.
4. [open, VERIFY] The `Workflow` items in section 13 (cycle re-run without stale history, halted-node successor, callbacks on a node, retry on agent nodes, final-reply display, `adk eval` with a `Workflow` root) are source-read plausible but unproven; each has a probe name above. If the two-pass or halt probe fails, fall back to D1 option (e) and record a v8.
5. [info] Loop bound now lives only in `pipeline/` (`ARCH-LAYER-3`, `AGENT-6`, test in 6.3); there is no framework backstop. Task 6.3 must include iteration exhaustion (already in its wording) and a route-coverage test (every emitted route value has an edge).
6. [info] The term "orchestrator" now names the `Workflow` graph plus its function nodes, kept so that task ids, D13-D17 and ARCH rows stay valid. Function nodes must stay thin (`STRUCT-3`, `AGENT-2`); decisions in a node body are a review failure.
7. [info, minor wording] `ARCH-EDGE-1` describes `rag/embedder` both as one of "exactly two adapters" and as living outside `adapters/`; the sentence is correct but awkward. Not changed in v7 to keep the proposal to one subject; fix at the next version.
8. [info] `ARCH-LIM-4` (4 parameters) applies to function nodes whose arguments are state keys; a node reading more than four state keys should take `ctx` and read state inside, or a typed state model, not a longer signature.
9. [owner decision carried] `config` in LAYER-4 is not in D8's layout; approving the spec approves it (unchanged from v6).
10. [no issue found] Layer directions, the guard choke point, `ARCH-MOD-5` (now a rule, not an ADK limit), trust boundaries, the closed outcome set, and testing split (key-free pipeline tests, live-only evals) are consistent with v7 and with standards v5.

What the owner approves: architecture v7 (status draft to approved), which bakes in the `Workflow` orchestrator, the code-decided loop bound, the model-failure behaviour in `ARCH-ERR-1`, the Migration row for the `loop-escalate` probe, and the `config` module in LAYER-4.
