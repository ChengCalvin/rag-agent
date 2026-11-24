---
version: 7
status: approved
---

# Architecture spec

The project's architecture, written as concepts, not as a description of existing code. It drives the code (`P-SPEC`). It is drafted by `architect`, approved by the owner, and changed only through a versioned proposal (`P-EVOLVE`). An `approved` spec must have no unfilled placeholders left.

Stack (pinned, from `docs/team/process.yaml`): Python, Google ADK, Gemini (free AI Studio key), hand-rolled numpy retrieval, synthetic data only, run via adk web / adk run (not Vertex AI Search, RAG Engine, Gemini File Search)

Sources: `openspec/changes/novamart-rag-agent/` (proposal, design decisions D1-D17, specs). Decision IDs below point there. This spec states the concepts; it does not describe existing code (there is none yet).

## 1. Drivers
The qualities and constraints the design must serve (for example: performance budget, privacy law, team size, offline use, scale).
- `ARCH-DRV-1` Top quality attributes, in priority order: (1) security: access control is enforced in code, never by prompt; the guarantee must hold even if the model is talked into anything (D2, D3); (2) testability: every security and refusal rule is checkable without calling the model; (3) small enough to explain end to end: a fixed pipeline of five single-purpose agents with plain-Python routing, three tools, no framework beyond ADK (D1, D10-D16).
- `ARCH-DRV-2` Hard constraints: no real authentication and no real order API (persona selection and an in-memory read-only stub stand in, documented as simulation); no cloud deployment; no write tools; synthetic data only; Gemini through a free AI Studio key supplied by environment variable; interaction only through `adk web` / `adk run`; roughly a half-day build.

## 2. Layers and allowed dependencies
Name the layers from highest to lowest. A layer may depend only on layers listed in its row.

| ID | Layer | Responsibility | May depend on |
|---|---|---|---|
| `ARCH-LAYER-1` | Agent wiring (`agent.py`, `agents/`, `prompts/`, `security/callbacks.py`) | Define the five agents and the orchestrator (one ADK `Workflow` graph: the five agents as `single_turn` nodes, thin function nodes between them, routed edges), register tools on the two agents that hold them, install ADK callbacks (per-role tool allowlist, audit record, query-hint override, diagram check, usage capture). Function nodes only read session state, call one pure function from LAYER-3, write state and emit a route value (identity injection, routing, loop continue or exit, final reply assembly). Only composes and adapts ADK to the pure functions below; decisions live in LAYER-3. | LAYER-2, LAYER-3, LAYER-4 |
| `ARCH-LAYER-2` | Tools (`tools/`) | The three model-facing functions (`search_policy`, `get_order_status`, `check_return_eligibility`). Thin adapters: read the principal from the tool context, call lower layers, return a plain result dict. No identity parameters. | LAYER-3, LAYER-4 |
| `ARCH-LAYER-3` | Domain services (`security/principal`, `security/guard`, `rag/`, `adapters/`, `pipeline/`, eligibility rule) | Authorization decision, retrieval and refusal gate, the order backend, return-eligibility computation, and the pipeline decisions: input precheck, routing from the rubric, rubric coverage check, confidence composite and band, loop continue-or-exit and best-attempt selection (the only loop bound: ADK's `Workflow` has no iteration cap), cost per turn and session (`pipeline/cost`). Pure logic except the two adapters in `ARCH-EDGE-1`. No ADK imports. | LAYER-4 |
| `ARCH-LAYER-4` | Shared (`config`, typed models, error types) | Settings loaded once, dataclasses for principal, order, chunk, tool result, rubric, verdict, confidence band. No I/O besides reading the environment in `config`. | nothing in this project |

Direction is downward only. `security/` straddles layers by file: `callbacks.py` is LAYER-1, `principal.py` and `guard.py` are LAYER-3. `evals/` and `tests/` sit outside the layers and may import any public interface.

## 3. Module boundaries
- `ARCH-MOD-1` How a capability is packaged: standard Python src layout under `backend/`: package root `backend/src/novamart_agent/` (so `adk web backend/src` finds `agent.py`, whose `root_agent` is the orchestrator `Workflow`); one sub-package per concern (`agents/`, `prompts/`, `pipeline/`, `security/`, `tools/`, `adapters/`, `rag/`). Data lives outside the package in `backend/data/` (documents, orders, users); tests in `backend/tests/` and evals in `backend/evals/`. There is no frontend (`adk web` is the interface). Layout follows design decision D8 (v2 moved it under `backend/`; v4 added `agents/`, `prompts/`, `pipeline/`).
- `ARCH-MOD-2` Public interface rule: each sub-package exposes its public names from `__init__.py`. Other packages import only those names, never submodules.
- `ARCH-MOD-3` Naming and layout conventions: snake_case modules; tool function names equal the names the model sees; one tool per file in `tools/`; test files named `test_<module>.py` under `backend/tests/` mirroring the package; ADK evalsets (`*.evalset.json` with `test_config.json`) under `backend/evals/`; documents carry audience and policy parameters in front-matter.
- `ARCH-MOD-4` Guard choke point: the authorization function in `security/guard` is the single choke point (D3). Both order tools and eligibility reach order data only through it; no module may call `adapters/` order lookups except through a tool that calls the guard first.
- `ARCH-MOD-5` Tools only on retrieval and order agents: only the `retrieval` and `order` agents may be given tools; intake, validator and composer have none (D16).

## 4. Boundaries and validation
- `ARCH-BOUND-1` Where external input enters and how it is parsed. There are four untrusted inputs: (a) tool arguments chosen by the model (for example an order id, or a query rewritten by the validator), parsed and validated at the top of each tool into typed values, malformed input returns the same uniform not-found result; (b) retrieved document text and every model-produced intermediate (rubric, verdict, rewritten query), treated as data only, passed as message content, never templated into instruction text and never as instructions; (c) the persona selector (`NOVAMART_USER`), resolved once into a typed principal by `security/principal` from `users.json`, then written to session state by the first node of the orchestrator graph; (d) the raw user message, checked by `pipeline/precheck` before any model call. Typed models live in LAYER-4. The principal is never accepted from the model, the user message or a tool parameter. Whether end users can alter ADK session state is unverified (VERIFY, see section 13).

## 5. Side effects and integrations
- `ARCH-EDGE-1` Where integrations are isolated: exactly two adapters. `rag/embedder` is the only module that imports `google-genai` or touches the network or the on-disk vector cache; it embeds each chunk in its own call (`RETRIEVAL_DOCUMENT` for chunks, `RETRIEVAL_QUERY` for queries) and caches by content hash. `adapters/orders_api` is the only module that reads order data, is read-only, and stands in for the real order API. (`rag/embedder` is the other adapter but stays in `rag/`, because it is part of the retrieval pipeline; `adapters/` holds only integrations with the order system.) Everything else (chunking, cosine ranking, threshold gate, authorization, eligibility) is pure and unit-testable without a key. Audit logging is written through one logger in `security/`, not ad hoc.

## 6. Error model
- `ARCH-ERR-1` Tools do not raise to the model. Each returns a result dict with a `status` of `ok`, `no_answer` (retrieval below threshold or audience-filtered), or `not_found` (nonexistent, out of scope, malformed id, unknown role, or throttled: all identical in content, so denial never reveals existence). Authorization defaults to deny. Domain code raises typed errors; the tool layer is the single place that converts them to a result status. Unexpected exceptions are logged without PII and returned as a generic failure status. The audit record notes the true outcome (allowed or denied) internally; the model-facing response does not. A failed model call (rate limit, outage) is retried by the graph's node retry policy; if it still fails the turn fails visibly through ADK, and no model-written or invented fallback reply is produced (VERIFY the retry policy applies to agent nodes, see section 13). Mapping to `ARCH-ERR-2`: `ok` becomes an answer (outcome E when the validator doubts coverage), `no_answer` becomes C, `not_found` becomes D, and a generic failure is not an outcome A-E: the turn ends with a fixed, non-model message.
- `ARCH-ERR-2` Pipeline outcomes are a closed set, each with one observable output (D13): A clarify (one question, at most one per user question), B decline (invalid or out of scope), C decline with escalation contact and up to three audience-filtered closest titles (no evidence), D uniform not-found (order, no follow-up questions), E answer with Low confidence band, caveat and Sources (evidence present, intent coverage doubtful). A deterministic refusal (C, D) is never overturned by a model verdict; the validator can only lower confidence or request a rewrite. Loop exit, routing and the confidence band are computed in code (`pipeline/`).

## 7. Configuration, secrets, text and design values
- `ARCH-CFG-1` Configuration and secrets are read in: `config` (LAYER-4) only, from environment variables (`GOOGLE_API_KEY`, model ID, embedding model ID, similarity threshold, top-k, persona selector, per-model token prices, `NOVAMART_SHOW_COST` (display flag, default true), backend switch variables, and the pipeline tuning values: loop max iterations (default 2, enforced by the pure loop decision, not by ADK), loop-exit confidence threshold T, composite weights, High/Medium/Low band thresholds, rewrite length cap). The pipeline tuning values are configuration with defaults, not constants, per D11, D12 and the design change map ("config: threshold T, weights, loops"); defaults are chosen at build and tuned on the eval set. No other module reads the environment. Secrets are never committed; `.env.example` lists names only. Model IDs are configuration, not constants (D6).
- `ARCH-CFG-2` User-facing text comes from: `prompts/` (one module per agent) for model instructions (refusal, clarification and escalation wording), and the policy documents in `backend/data/docs/` for policy content and the escalation contact. Policy parameters (return window, excluded categories) come from document front-matter, not code (D5). No policy facts are hard-coded.
- `ARCH-CFG-3` Design values (colour, spacing, type): n/a. There is no custom UI; `adk web` is the interface.

## 8. Testing strategy
- `ARCH-TEST-1` Levels and what each covers: unit tests (pytest, no network, no key) for the guard (cross-store denial, wider-scope role, unknown role denied, uniform denial), principal resolution, chunker, threshold gate and audience filter (with a fake embedder), eligibility rule, log hygiene (no seeded PII in logs), and throttle. The pipeline decisions are also unit-tested with no key, using fake model outputs (hand-built rubric and verdict): `pipeline/precheck`, routing from the rubric, the rubric coverage check, the confidence composite and band (including the required-criterion cap), the outcome mapping to A-E, and `pipeline/cost`. Tool-level tests call tools with a constructed context and a fake backend. Evaluation level: ADK evalsets (seed each persona through `session_input.state`) for tool trajectories, plus a small custom runner for content checks and a separate security set; this level needs a key and is not part of the `pytest` gate. Security guarantees are proven at unit level in code, not by the model-dependent eval (D7).
- `ARCH-TEST-2` Traceability: each test name or docstring quotes the spec scenario title it proves (for example "Cross-store request"); the eval cases carry the scenario title in their id.
- `ARCH-TEST-3` Evals are mandatory for agent behavior: every spec scenario about tool use, refusal, access control or grounding has at least one ADK eval case under `backend/evals/` (run with `adk eval`), with pass criteria stated. Evals stay outside the `pytest` gate (`ARCH-TEST-1`), so the report shows the eval command and result separately. Evals are live-only: they call the real model with `GOOGLE_API_KEY`, and there is no mock mode. Agents author the evalsets, `test_config.json` and the content-check runner, but never run an eval (or any command that calls the model) until the owner has supplied the key and says to run. Until then, eval tasks are written and left unrun, and are reported as "authored, not run"; they stay open. Once run, a failing eval blocks the task.

## 9. Limits
Defaults shown; the architect adjusts them for the project. `SIZE-1` in the standards points here.

| ID | Limit | Value |
|---|---|---|
| `ARCH-LIM-1` | Lines per file | 300 |
| `ARCH-LIM-2` | Lines per UI component | n/a (no UI) |
| `ARCH-LIM-3` | Lines per function | 50 |
| `ARCH-LIM-4` | Parameters per function | 4 |

## 10. Approved patterns and anti-patterns
| Pattern | Use when | Status |
|---|---|---|
| Identity injected into session state by a callback; tools read it from the tool context | Any tool needs to know who the caller is | approved |
| Single authorization choke point called after fetch, before return, deny-by-default | Any tool returns order data | approved |
| Uniform "not found or not accessible" response | Order missing, out of scope, malformed, throttled | approved |
| Deterministic gate in code (score threshold, audience filter) plus a prompt rule as second layer | Refusing when documents do not support an answer | approved |
| Code computes eligibility from structured parameters; the model explains and cites | Any rule needing date or category logic | approved |
| Hand-rolled numpy cosine retrieval, one embedding call per chunk, content-hash disk cache | Retrieval over the small document set | approved |
| Deterministic orchestrator: one ADK `Workflow` graph running single-purpose agents (`single_turn` nodes) in a fixed order; function nodes call pure `pipeline/` functions and emit a route value; edges are static | Any request that needs validation, cross-checking or per-type formatting | approved |
| Retrieval-validator loop as a routed cycle in the `Workflow`: retrieval, validator, then a function node calling the pure loop decision (composite confidence, iteration count, best attempt) that routes `retry` back to retrieval or `done` onward; max 2 passes; rewrite applied by overwriting the tool's query argument in `before_tool_callback` | Policy and product questions only | approved |
| Order shortcut: intake routes order questions to the order agent then the composer, skipping the loop (a route on the `Workflow` graph) | Order status and eligibility | approved |
| Sources, confidence band and diagram blocks appended or verified by code from chunk metadata; the model never writes citations or diagrams | Every knowledge answer | approved |
| Per-question and session cost computed by code from recorded `usage_metadata` and a configured price table, appended with Sources and the band; the flag hides display only, recording stays on (D17) | Every reply | approved |
| Caller identity, role or store as a tool parameter or taken from prompt text | n/a | avoid |
| Authorization only in the prompt, or only in the order stub | n/a | avoid |
| Write tools, custom UI, cloud deployment | n/a (out of scope) | avoid |
| LLM-driven delegation between agents (`AgentTool`, transfer, `sub_agents` chosen by the model); agent nodes in `chat` or `task` mode | n/a (routing is code, D1) | avoid |
| ADK APIs marked deprecated in the pinned version (`LoopAgent`, `SequentialAgent`, `ParallelAgent`, YAML agent configs) | n/a (use `Workflow`; owner decision 2026-11-24) | avoid |
| An unconditional cycle, or a loop whose exit is decided by the model or by an `escalate` set by a model-driven agent | n/a (exit is a code decision on a routed edge) | avoid |
| Tools on intake, validator or composer; any agent other than `retrieval` and `order` touching order data | n/a | avoid |
| Model-generated visuals or citations; a validator verdict used to override a deterministic refusal | n/a | avoid |
| Built-in tools mixed with function tools in one agent | n/a (ADK restriction) | avoid |
| Vertex AI Search, RAG Engine, Gemini File Search | n/a (excluded by the pinned stack) | avoid |
| Customer names, emails, addresses in logs or traces | n/a | avoid |

## 11. Migration (how existing code catches up after a change)
Code in a legacy scope is not failed for the listed rule until its target version; new or changed code must conform from the version it was introduced.

| Rule or pattern | Introduced in version | Legacy scope (globs) | Target version |
|---|---|---|---|
| No deprecated ADK API (`LoopAgent`) in new or changed code | 7 | `backend/evals/check_adk_assumptions.py` (throwaway verification probe `loop-escalate`; replaced by a `Workflow` loop probe under task 1.4) | 8 |

## 12. Change log
| Version | Date | Change | Proposal |
|---|---|---|---|
| 1 | 2026-11-23 | Initial architecture (draft, awaiting owner approval) | `openspec/changes/novamart-rag-agent/design.md` |
| 2 | 2026-11-23 | Layout moved under `backend/` (`backend/src/novamart_agent/`, `backend/tests/`, `backend/evals/`, `backend/data/`); no frontend; added `ARCH-TEST-3` (evals mandatory for agent behavior; live-only, authored but not run until the owner supplies the API key and says to run). Still draft: no code exists, so no Migration row. | `openspec/changes/novamart-rag-agent/design.md` (D8) |
| 3 | 2026-11-23 | Renamed sub-package `backends/` to `adapters/` (`backend/src/novamart_agent/adapters/orders_api`): the old name read as "backend inside `backend/`". Still draft: no code exists, so no Migration row. | `openspec/changes/novamart-rag-agent/design.md` (D8) |
| 4 | 2026-11-23 | Replaced the single-agent design (D1) with a staged pipeline: intake (validate, classify, rubric), `LoopAgent` of retrieval and validator with query rewrite, order shortcut, composer. New sub-packages `agents/`, `prompts/` (replaces `prompts.py`), `pipeline/`; new typed models (rubric, verdict, band) in LAYER-4. Added `ARCH-ERR-2` (closed set of pipeline outcomes), a fourth untrusted input, pattern rows and avoid rows; removed the multi-agent avoid row. Still draft: no code exists, so no Migration row. Engineering standards must be re-derived from this version before approval. | `openspec/changes/novamart-rag-agent/design.md` (D1, D10-D16) |
| 5 | 2026-11-23 | Added cost per question and per session (D17): `pipeline/cost` in LAYER-3, price table and display flag in `ARCH-CFG-1`, a pattern row. Still draft: no code exists, so no Migration row. Standards must be re-derived. | `openspec/changes/novamart-rag-agent/design.md` (D17) |
| 6 | 2026-11-23 | `ARCH-TEST-1` adds key-free unit tests for the pipeline decisions (precheck, routing, rubric coverage, confidence composite and band, outcome mapping, cost); `ARCH-CFG-1` states loop max iterations, loop-exit threshold, weights, band thresholds and rewrite cap are configuration with defaults; `ARCH-ERR-1` gains a one-line mapping of tool statuses to `ARCH-ERR-2` outcomes; `ARCH-BOUND-1` inputs reordered (a)-(d), meaning unchanged; `ARCH-MOD-2` split into `ARCH-MOD-2` (public interface), `ARCH-MOD-4` (guard choke point) and `ARCH-MOD-5` (tools only on retrieval and order). Still draft: no code exists, so no Migration row. Standards re-derived (v4). | `openspec/changes/novamart-rag-agent/design.md` (D11, D12, D13, D16) |
| 7 | 2026-11-24 | Owner decision: do not build on a deprecated ADK API. ADK 2.15.0 marks `LoopAgent` (also `SequentialAgent`, `ParallelAgent`) deprecated in favour of `Workflow`. The orchestrator is now one `Workflow` graph instead of a custom `BaseAgent` plus `LoopAgent`: agents are `single_turn` nodes, function nodes call the pure `pipeline/` decisions and emit route values, the retrieval-validator loop is a routed cycle whose exit and 2-pass bound are a code decision (`pipeline/`). `LoopAgent` pattern row replaced; `ARCH-LAYER-1`, `ARCH-LAYER-3`, `ARCH-MOD-1`, `ARCH-BOUND-1`, `ARCH-ERR-1` (model-call failure), `ARCH-ERR-2`, `ARCH-CFG-1` and the orchestrator and order-shortcut pattern rows updated; two avoid rows added (deprecated ADK APIs, model-decided or unconditional loops) and one extended (chat/task-mode nodes). Migration row added for the one file that uses `LoopAgent` (a throwaway probe). Standards re-derived (v5, new `AGENT-6`). Still draft: no product code uses the old pattern. Also recorded: `output_schema` and tools can coexist in ADK 2.15.0 (no structural effect; `ARCH-MOD-5` stands as a rule, not an ADK limit). | `openspec/changes/novamart-rag-agent/design.md` (D1, D11, D16) |

## 13. Open items (carried from design.md, not resolved here)
- VERIFY: ADK docs do not explicitly say end users cannot alter session state; identity in production must come from the authenticated token in the API layer (D2).
- VERIFY: availability and free-tier rate limits of the candidate Flash-class model IDs; model ID stays configuration (D6).
- VERIFY: whether ADK LLM-judge eval metrics (`hallucinations_v1`) work on a free key; fallback is the custom content checks (D7).
- VERIFY: Gemini Enterprise document ACL behaviour and how end-user identity reaches an A2A-registered agent; production-note items only, not built (D9).
- VERIFY (ADK `Workflow`, 2.15.0; source-read in task 1.4, behaviour owner-run, see design.md "Workflow findings"): a routed cycle runs the retrieval and validator nodes a second time with correct input and without stale conversation history from pass one; a `single_turn` agent node that halts at a tool result (`skip_summarization`) completes with no output and triggers its successor; callbacks on an `LlmAgent` survive being a node; `RetryConfig` applies to agent nodes; a function node can emit the final reply as the turn's response in `adk web` and `adk run`; `adk eval` accepts a `Workflow` root. Settled from source: `output_schema` and tools coexist, `before_tool_callback` argument mutation works, instruction templating is an injection surface, nodes share session state.
- VERIFY: `usage_metadata` fields, thinking-token billing, embedding token counts, and current token prices (D17).
- Review: the whole-spec `architect` review (task 1.5) covered v7 and subsumes the v4 to v6 reviews; findings are in the task 1.5 report. `docs/engineering-standards.md` is re-derived from v7 (standards v5) in this proposal. The owner still approves the spec (status draft to approved) before chunk 7.
- Owner decision: this spec adds a small `config` module in LAYER-4, which D8's layout does not list. Approving this spec approves that addition.
