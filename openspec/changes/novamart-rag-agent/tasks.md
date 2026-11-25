## Chunk map

```
 1 Setup + verify ADK --+--> 2 Synthetic data --+
                        |                       |
                        +--> 3 Access control --+--> 5 Order tools --+
                        |                       |                    |
                        +--> 4 Retrieval -------+--> 6 Pipeline -----+--> 7 Agents --> 8 Evaluation --> 9 Docs --> 10 Final
                                                      logic (pure)

 Independent after 1:  2, 3, 4          (can be built in any order)
 5 needs 2, 3          6 needs 4 (models, chunk metadata)
 7 needs 3, 4, 5, 6 and the owner-run results of 1.4 recorded (every agent and the orchestrator `Workflow`; first point where adk run works end to end)
 8 needs 7             9 and 10 need 8
 Revision 2 (architecture v4) added chunks 6 and 7, replaced old task 5.3, and extended 1, 2, 3, 4, 8.
```

## 1. Setup and verification of assumptions

owner: backend-dev
tags: none
gates: code-reviewer, qa-engineer

- [x] 1.1 Create the project skeleton per design D8 (everything under `backend/`, including `agents/`, `prompts/`, `pipeline/`) with `backend/pyproject.toml`, `.gitignore` (excluding `.env` and cache) and `backend/.env.example` (moved from `backend/src/novamart_agent/`; sets `GOOGLE_API_KEY` and `GOOGLE_GENAI_USE_ENTERPRISE=FALSE`, design D6); verify `pip install -e backend[dev]` succeeds and `adk web backend/src` lists the agent and `.env` is ignored by git
- [x] 1.2 Check AI Studio for the free-tier model IDs and rate limits, choose the default chat model and record it in configuration, and record the text-only embedding model ID (default `gemini-embedding-001`) in configuration too, plus the published per-million-token prices for both (design D17); verify a one-line `google-genai` generate call and one embedding call succeed with the key (authored, not run until the owner supplies the key and says run; ARCH-TEST-3; the model ID default stays provisional until then)
- [x] 1.3 Confirm current ADK syntax on adk.dev (agent definition, callbacks, `adk eval`); verify a minimal agent runs under `adk run` and `adk eval --help` works (authored, not run until the owner supplies the key and says run)
- [x] 1.4 Confirm on adk.dev every ADK behaviour that design D1, D11 and D16 assume: a routed `Workflow` cycle (retrieval, validator, a function node that emits `Event(route=...)`) that runs a second pass, exits by a code-decided route and is bounded by a pass counter in state (the `Workflow` has no iteration cap and `LoopAgent` is deprecated), `LlmAgent` as a `single_turn` node with its callbacks and `RetryConfig`, `output_schema` together with tools (settled from source: they coexist), state shared across sub-agents of one orchestrator, argument mutation in `before_tool_callback`, `{key}` instruction templating, an after-tool callback (or `skip_summarization`/`escalate` tool-context action) that ends an agent's turn at a `no_answer`, `not_found` or `not_determinable` tool result with no further model call, `usage_metadata` fields and thinking-token billing, and whether embedding returns token counts; verify with a throwaway `Workflow` script under `adk run`, replacing the `loop-escalate` and `custom-baseagent-branch` probes in `backend/evals/check_adk_assumptions.py` with `workflow-loop-two-passes`, `skip-summarization-in-workflow-node` and `workflow-final-reply`, and record each result (confirmed, or the deviation and the design change it needs) in design.md under "Workflow findings" and Open Questions (authored, not run until the owner supplies the key and says run)
- [x] 1.5 Run the `architect` agent review of the current architecture version (v7) and re-derive `docs/engineering-standards.md` from it; verify the standards file's `architecture_version` equals the architecture spec's `version` and the owner approves the spec (status draft to approved) before chunk 7 starts
- [x] 1.6 Update `backend/pyproject.toml` (outside this change's planning artifacts; carried here): pin `google-adk` to the version verified in 1.3 and add `google-adk[eval]` to the `dev` optional-dependencies; verify `pip install -e backend[dev]` succeeds and `adk eval --help` runs

## 2. Synthetic data

owner: backend-dev
tags: personal-data
gates: code-reviewer, qa-engineer, security-compliance, compliance-reviewer

- [x] 2.1 Write 8 short policy documents with audience and `doc_type: policy` front-matter, including a returns document with structured window and exclusion parameters, one category exception, one manager-only document, a store operations document (audience: all staff, indexed normally like the others) with an `escalation_contact` front-matter field, and deliberate gaps (such as bulk orders); verify each parses, the contact field is read, and the gaps are listed in `backend/data/README.md` (a small README written in this task)
- [x] 2.2 Write about 10 orders across 3 stores covering delivered, in-transit and returned states with seeded customer name, email and address; verify the file loads and includes cross-store cases
- [x] 2.3 Write about 4 personas (two stores' employees, a manager, a regional manager); verify they load into principals
- [x] 2.4 Write 3 short product documents with `doc_type: product`, each containing one ASCII diagram in a fenced code block (plain ASCII only); verify they parse, the diagram blocks are intact, and one product document has audience restrictions

## 3. Access control

owner: backend-dev
tags: auth, api
gates: code-reviewer, qa-engineer, security-compliance

- [x] 3.1 Implement principal loading and the before-agent callback that sets identity in session state from `NOVAMART_USER`; verify with a test that a tool reads the principal and no tool signature has identity parameters
- [x] 3.2 Implement order-ID validation and the shared authorization function, with uniform denial responses; verify that a malformed ID is rejected only in the order tool (intake and precheck never reject or reroute it) and unit tests for malformed IDs, cross-store denial, regional-manager allow, unknown role deny, and identical denial vs not-found replies (covers requirements 'Order access is scoped to store and role' and 'Denials do not reveal existence')
- [x] 3.3 Implement the before-tool callback with per-role tool allowlist and the audit log with hashed order references and PII redaction; verify a test that seeded name, email and address never appear in log output (covers requirement 'Access-related events are audit-logged without PII')
- [x] 3.4 Implement the denied-lookup counter with session throttling; verify a test that sequential probing is throttled and returns nothing (cut first if time runs short)
- [x] 3.5 Write a pure test helper under `backend/tests/` that builds a fake tool context carrying a principal in session state; verify tasks 3.1 to 3.3 use it and that task 7.5 can reuse it for the multi-agent case

## 4. Retrieval

owner: backend-dev
tags: api
gates: code-reviewer, qa-engineer, security-compliance

- [x] 4.1 Implement the chunker (by heading, never splitting inside a fenced code block), embedder with per-chunk calls and content-hash disk cache, and cosine index with audience filtering; verify tests that a manager-only chunk is never returned to a non-manager, that cached vectors are reused, and that a fenced diagram stays whole in one chunk
- [x] 4.2 Implement `search_policy` returning chunks, document IDs, section headings, file paths, `doc_type` and scores, or `no_answer` below the configurable threshold, with an `embedding_cache_hit` field in every result including `no_answer`, set by the `rag` embedder (no ADK import); verify tests for an answerable query, a gap query and an unrelated query, and that `embedding_cache_hit` is present and correct on a cache miss, a cache hit and a `no_answer` result
- [x] 4.3 Add the "closest titles" lookup (up to 3 audience-filtered document titles, used by refusal case C, independent of the answer threshold); add a non-model lookup of the escalation contact from a front-matter field in the store operations document, read at load, used by the code that assembles case C and order-eligibility "cannot determine" replies; verify a test that no restricted title is ever returned to a non-permitted persona, that the contact is read from the document and not hard-coded, and that a missing field fails loudly

## 5. Order tools

owner: backend-dev
tags: api, personal-data
gates: code-reviewer, qa-engineer, security-compliance, compliance-reviewer

- [x] 5.1 Implement the read-only order backend stub (`adapters/orders_api`) and `get_order_status` returning the minimised, masked view; verify tests for permitted, denied and unknown orders and that no full email or address is returned
- [x] 5.2 Implement `check_return_eligibility` with deterministic date and category logic from policy parameters, returning the cited policy document id and the parameters used, or a `not_determinable` status when the parameters are missing or unreadable (the orchestrator then emits canned wording plus the escalation contact from 4.3, with no composer); verify unit tests for within-window, category-exception, outside-window and undeterminable-policy cases

## 6. Pipeline logic (pure, no ADK imports)

owner: backend-dev
tags: none
gates: code-reviewer, qa-engineer

- [x] 6.1 Add typed `Rubric`, `Verdict`, `ConfidenceBand` and the pipeline settings (loop exit threshold T, weights, band thresholds, `max_iterations`, rewrite length cap, clarification cap) to `models.py` and `config`; verify tests that bad values fail at load and that the shipped defaults load and satisfy the invariants (weights sum to 1, band thresholds ordered, `max_iterations` is 2); the other default values are chosen at build and tuned in 8.5, so the test does not compare them to the design
- [x] 6.2 Implement `pipeline/precheck` (empty, over-length, known injection patterns) and `pipeline/routing` (route from the rubric: order, knowledge, clarify, oos; clarification cap of one per question); verify tests for each route, the cap, and that a malformed or empty rubric falls back to a single criterion made from the user message
- [x] 6.3 Implement `pipeline/rubric_check` (coverage fraction; required-criterion cap; downgrade-only rule so a verdict can never lift a deterministic `no_answer`) and `pipeline/confidence` (composite, band, loop-exit decision, best-attempt selection); verify tests for each band, the cap, the downgrade-only rule, iteration exhaustion, and that a worse second pass never replaces a better first pass
- [x] 6.4 Implement the code-side output assembly: Sources list from chunk metadata, confidence footer, and the check that every fenced block in a reply appears verbatim in the retrieved chunks (strip otherwise); verify tests including a model-invented diagram being stripped and a fabricated citation being impossible; on the order route, resolve the policy document id from `check_return_eligibility` to title and path via a loader (title and path only, no section heading), with tests for a known id, an unknown id (no entry, no crash), and no id returned
- [x] 6.5 Implement `pipeline/cost` (pure): per-call usage record, `TurnCost`, session total, price table lookup by model ID with "cost unavailable" for unpriced models, embedding estimate, and the cost-line text; add price entries and `NOVAMART_SHOW_COST` (default true) to `config`; verify tests for a rewrite turn summing every call, a precheck decline at $0.00 with 0 calls, a cache hit adding nothing, an unpriced model, two turns summing into the session total, and flag on and off

## 7. Pipeline agents and orchestrator (`Workflow`)

owner: backend-dev
tags: api, auth
gates: code-reviewer, qa-engineer, security-compliance

- [x] 7.1 Write one prompt module per agent in `prompts/` (intake, retrieval, validator, composer, order; refusal, clarification and escalation wording as canned strings used by code, not composer decline rules; retrieved text, rubric and rewrites treated as data; role claims and instruction disclosure refused); verify by review against ARCH-CFG-2 that no policy facts are hard-coded
- [x] 7.2 Prerequisite: the owner-run results of task 1.4 are recorded in design.md Open Questions. Implement the intake agent (no tools, `output_schema` Rubric) and the orchestrator (a `Workflow` graph with function nodes that call `pipeline/routing` and emit route values, order shortcut, clarification turn state, and code assembly of the final reply on every route: canned decline, Sources, band; the cost line is added in 7.6; intake flags unanswered policy criteria in the rubric); verify by running `adk run` (authored, not run until the owner supplies the key and says run) through one policy question, one product question, one order lookup, one under-specified question, and one out-of-scope question
- [x] 7.3 Implement the retrieval and validator agents as nodes of the routed cycle in the orchestrator `Workflow` (no `LoopAgent`), the `loop_decide` function node that calls `pipeline/confidence` and bounds the loop at `max_iterations`, and the query-hint override in `before_tool_callback`; verify by `adk run` (owner-gated, as 7.2) on a question that needs one rewrite and one that exhausts iterations, and by unit tests that the exit decision comes from `pipeline/confidence` (no model-set `escalate`), that every route value a node can emit has an edge, and that the composer is given the best-scoring attempt, not the last, and that the retrieval agent has one combined after-tool callback that records the embedding estimate first and then halts on `no_answer` with no further model call (a `no_answer` on a cache miss still records one embedding estimate)
- [x] 7.4 Implement the order agent and the composer (formats by `doc_type`, order label, Low-band caveat; declines and clarifications are canned text from code and skip the composer), wire the after-model callback that strips unverified diagrams (Sources and band are appended by the orchestrator), append the fixed limitation sentence on the order route when the rubric flags unanswered policy criteria, and finish `agent.py` as wiring only; the orchestrator appends the order-route Sources entry from the 6.4 loader; verify by `adk run` (owner-gated, as 7.2) that the combined order-and-policy question shows a Sources line with title and path and no heading, and through one combined order-and-policy question, one unanswerable question, and a product question that shows its diagram; verify that the order agent's halt callback ends the turn on `not_found` and `not_determinable` with no summarising model call, and that `not_determinable` yields canned text plus the contact; the order agent's after-tool callback also stores the structured eligibility success result (policy id and parameters) in state, and a test shows the Sources id comes from that tool result, not from model output
- [x] 7.5 Write the identity-propagation test: the principal injected by the orchestrator's first node is read by the tool in `retrieval` and in `order`, no sub-agent output can change it, and intake, validator and composer have no tools; verify it passes with the fake context from 3.5 and again once under `adk run` (covers requirement 'Identity propagation is addressed', with 9.3)
- [x] 7.6 Wire cost capture: an after-model callback on every LLM agent appends its `usage_metadata` record to the per-turn list in state, the combined after-tool callback on retrieval appends the query-embedding estimate (before the `no_answer` halt) unless the result's `embedding_cache_hit` is true (key-free tests: a cache miss adds one embedding record, a cache hit adds none, and `rag/` imports no ADK), the orchestrator clears the list each turn and updates the session total, and the orchestrator appends the cost line on every route after the composer's own usage is counted by its callback; verify by `adk run` (owner-gated, as 7.2) that the line appears with the flag on and not with it off, that the session total grows across questions, and by key-free tests: (a) the full orchestrator run under ADK with a stub model class that counts calls and returns scripted outputs, asserting equal whole-turn call counts for the nonexistent, out-of-scope and malformed denial causes, with no further model call after the order tool result (a malformed id is routed to `order` by intake, never to `clarify`); (b) fake usage records showing those three replies are the same code-produced text (token totals are compared only for the same message text); and, for each outcome A to E and the not-determinable reply, that the cost line is present with the flag on and absent with it off (covers requirement 'Cost does not reveal why an order was denied')
- [x] 7.7 Append the escalation contact (from the 4.3 lookup, not hard-coded) to every outcome E reply in the finishing node, after Sources and the band; verify a key-free test that an E reply ends with the contact text from the document, that C, D and order replies are unchanged, and that the three eval cases that hit E on silent topics now include the contact line

## 8. Evaluation

owner: backend-dev
tags: none
gates: code-reviewer, qa-engineer

- [x] 8.1 Update the spec scenarios in `specs/` for the clarification turn, the refusal split (C against E), the confidence band, the order shortcut and the malformed order id (uniform not-found text, no lookup), each with a testable scenario; verify every new requirement maps to an eval case id
- [x] 8.2 Write 15 to 18 quality cases across policy, product, order and combined questions with persona, expected behavior and rule checks, plus one case for each refusal outcome A to E; the combined cases are labelled known-limitation and pass when the order part is correct and the reply says it cannot answer the policy part; verify at least two cases per question type and exactly the five outcomes covered
- [x] 8.3 Write the security cases (cross-store access, role-override claim, poisoned document, rubric or rewrite injection, PII in logs, manager-only content, denial indistinguishable from not-found through the validator); verify each has an unambiguous pass condition
- [x] 8.4 Build the runner (ADK eval for tool trajectories plus custom content checks, call count and cost per question) and run both sets; verify it produces per-case results and an overall pass rate
- [ ] 8.5 Tune the loop-exit threshold T, composite weights and band thresholds, and run the quality set at three cosine threshold values; verify the tuning table and the chosen defaults are written to the results summary
- [ ] 8.6 Write the results summary listing every failure with a diagnosis, validator agreement against a hand-labelled subset, model calls per question, and cost per question with the mean per route and the cost at 1,000 questions; verify no failing case is omitted and fix or document each one (covers requirement 'Results are reported honestly')
- [ ] 8.7 Re-label the silent-topic eval cases for outcome E with the contact line (task 7.7): change `question-the-documents-are-silent-on-bulk-orders` (quality), `employee-asks-about-manager-only-content` and `employee-asks-about-manager-only-product-briefing` (security) to expect outcome E plus the contact text, keeping every no-leak check; add one new quality refusal case that genuinely scores below the cosine threshold (find the question with an owner-run embedding check, no model call) and labels it outcome C, so each of A to E stays the labelled outcome of exactly one case; verify the case counts in `quality.json` and the spec still hold, and the evalsets are rebuilt with `build_evalsets.py`

## 9. Documentation and production note

owner: backend-dev
tags: none
gates: code-reviewer, qa-engineer

- [ ] 9.1 Write the README with setup (`.env` in `backend/`, AI Studio flags, `pip install -e backend[dev]`), persona table, run commands, eval commands, the pipeline diagram, the synthetic-data statement and the "persona is not authentication" statement, and a link to `backend/data/README.md` for the document gap list; verify a fresh clone follows it to a working session
- [x] 9.2 Re-check the Google product claims for the note against current docs (Gemini Enterprise registration of custom agents, identity passing, ACL setup, CMEK and residency, data-use terms) and the token prices used in the cost line; verify each claim has a source or is marked to be confirmed (covers requirement 'Claims about products are verified or flagged')
- [x] 9.3 Write the one-page production note with the four required sections, a stated recommendation and fallback, the identity-propagation spike, and a prototype-limits list; verify it renders to a single page (covers requirements 'Prototype limits are disclosed' and 'Identity propagation is addressed'; lists the combined order-and-policy limitation)
- [x] 9.4 Run a secret scan over the repository and its history; verify zero findings

## 10. Final check

owner: backend-dev
tags: none
gates: code-reviewer, qa-engineer

- [ ] 10.1 Run all unit tests, the quality and security evals, and one end-to-end demo per persona from a clean environment; verify the results match the summary
- [x] 10.2 Review each spec scenario against the delivered behavior; verify every scenario has a test, an eval case, or a stated reason it is covered by documentation
