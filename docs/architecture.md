---
version: 2
status: draft
---

# Architecture spec

The project's architecture, written as concepts, not as a description of existing code. It drives the code (`P-SPEC`). It is drafted by `architect`, approved by the owner, and changed only through a versioned proposal (`P-EVOLVE`). An `approved` spec must have no unfilled placeholders left.

Stack (pinned, from `docs/team/process.yaml`): Python, Google ADK, Gemini (free AI Studio key), hand-rolled numpy retrieval, synthetic data only, run via adk web / adk run (not Vertex AI Search, RAG Engine, Gemini File Search)

Sources: `openspec/changes/novamart-rag-agent/` (proposal, design decisions D1-D8, specs). Decision IDs below point there. This spec states the concepts; it does not describe existing code (there is none yet).

## 1. Drivers
The qualities and constraints the design must serve (for example: performance budget, privacy law, team size, offline use, scale).
- `ARCH-DRV-1` Top quality attributes, in priority order: (1) security: access control is enforced in code, never by prompt; the guarantee must hold even if the model is talked into anything (D2, D3); (2) testability: every security and refusal rule is checkable without calling the model; (3) small enough to explain end to end: one root agent, three tools, no framework beyond ADK (D1).
- `ARCH-DRV-2` Hard constraints: no real authentication and no real order API (persona selection and an in-memory read-only stub stand in, documented as simulation); no cloud deployment; no write tools; synthetic data only; Gemini through a free AI Studio key supplied by environment variable; interaction only through `adk web` / `adk run`; roughly a half-day build.

## 2. Layers and allowed dependencies
Name the layers from highest to lowest. A layer may depend only on layers listed in its row.

| ID | Layer | Responsibility | May depend on |
|---|---|---|---|
| `ARCH-LAYER-1` | Agent wiring (`agent.py`, `prompts.py`, `security/callbacks.py`) | Compose the root agent, register tools, install ADK callbacks that inject identity and run the per-role tool allowlist and audit record. Only composes. | LAYER-2, LAYER-3, LAYER-4 |
| `ARCH-LAYER-2` | Tools (`tools/`) | The three model-facing functions (`search_policy`, `get_order_status`, `check_return_eligibility`). Thin adapters: read the principal from the tool context, call lower layers, return a plain result dict. No identity parameters. | LAYER-3, LAYER-4 |
| `ARCH-LAYER-3` | Domain services (`security/principal`, `security/guard`, `rag/`, `backends/`, eligibility rule) | Authorization decision, retrieval and refusal gate, the order backend, return-eligibility computation. Pure logic except the two adapters in `ARCH-EDGE-1`. No ADK imports. | LAYER-4 |
| `ARCH-LAYER-4` | Shared (`config`, typed models, error types) | Settings loaded once, dataclasses for principal, order, chunk, tool result. No I/O besides reading the environment in `config`. | nothing in this project |

Direction is downward only. `security/` straddles layers by file: `callbacks.py` is LAYER-1, `principal.py` and `guard.py` are LAYER-3. `evals/` and `tests/` sit outside the layers and may import any public interface.

## 3. Module boundaries
- `ARCH-MOD-1` How a capability is packaged: standard Python src layout under `backend/`: package root `backend/src/novamart_agent/` (so `adk web backend/src` finds `agent.py`); one sub-package per concern (`security/`, `tools/`, `backends/`, `rag/`). Data lives outside the package in `backend/data/` (documents, orders, users); tests in `backend/tests/` and evals in `backend/evals/`. There is no frontend (`adk web` is the interface). Layout follows design decision D8 (v2 moved it under `backend/`).
- `ARCH-MOD-2` Public interface rule: each sub-package exposes its public names from `__init__.py`. Other packages import only those names, never submodules. The authorization function in `security/guard` is the single choke point (D3): both order tools and eligibility reach order data only through it; no module may call `backends/` order lookups except through a tool that calls the guard first.
- `ARCH-MOD-3` Naming and layout conventions: snake_case modules; tool function names equal the names the model sees; one tool per file in `tools/`; test files named `test_<module>.py` under `backend/tests/` mirroring the package; ADK evalsets (`*.evalset.json` with `test_config.json`) under `backend/evals/`; documents carry audience and policy parameters in front-matter.

## 4. Boundaries and validation
- `ARCH-BOUND-1` Where external input enters and how it is parsed. There are three untrusted inputs: (a) tool arguments chosen by the model (for example an order id), parsed and validated at the top of each tool into typed values, malformed input returns the same uniform not-found result; (b) retrieved document text, treated as data only and never as instructions; (c) the persona selector (`NOVAMART_USER`), resolved once into a typed principal by `security/principal` from `users.json`, then written to session state by the callback. Typed models live in LAYER-4. The principal is never accepted from the model, the user message or a tool parameter. Whether end users can alter ADK session state is unverified (VERIFY, see section 13).

## 5. Side effects and integrations
- `ARCH-EDGE-1` Where integrations are isolated: exactly two adapters. `rag/embedder` is the only module that imports `google-genai` or touches the network or the on-disk vector cache; it embeds each chunk in its own call (`RETRIEVAL_DOCUMENT` for chunks, `RETRIEVAL_QUERY` for queries) and caches by content hash. `backends/orders_api` is the only module that reads order data, is read-only, and stands in for the real order API. Everything else (chunking, cosine ranking, threshold gate, authorization, eligibility) is pure and unit-testable without a key. Audit logging is written through one logger in `security/`, not ad hoc.

## 6. Error model
- `ARCH-ERR-1` Tools do not raise to the model. Each returns a result dict with a `status` of `ok`, `no_answer` (retrieval below threshold or audience-filtered), or `not_found` (nonexistent, out of scope, malformed id, unknown role, or throttled: all identical in content, so denial never reveals existence). Authorization defaults to deny. Domain code raises typed errors; the tool layer is the single place that converts them to a result status. Unexpected exceptions are logged without PII and returned as a generic failure status. The audit record notes the true outcome (allowed or denied) internally; the model-facing response does not.

## 7. Configuration, secrets, text and design values
- `ARCH-CFG-1` Configuration and secrets are read in: `config` (LAYER-4) only, from environment variables (`GOOGLE_API_KEY`, model ID, embedding model ID, similarity threshold, top-k, persona selector, backend switch variables). No other module reads the environment. Secrets are never committed; `.env.example` lists names only. Model IDs are configuration, not constants (D6).
- `ARCH-CFG-2` User-facing text comes from: `prompts.py` for model instructions (refusal and escalation wording), and the policy documents in `backend/data/docs/` for policy content and the escalation contact. Policy parameters (return window, excluded categories) come from document front-matter, not code (D5). No policy facts are hard-coded.
- `ARCH-CFG-3` Design values (colour, spacing, type): n/a. There is no custom UI; `adk web` is the interface.

## 8. Testing strategy
- `ARCH-TEST-1` Levels and what each covers: unit tests (pytest, no network, no key) for the guard (cross-store denial, wider-scope role, unknown role denied, uniform denial), principal resolution, chunker, threshold gate and audience filter (with a fake embedder), eligibility rule, log hygiene (no seeded PII in logs), and throttle. Tool-level tests call tools with a constructed context and a fake backend. Evaluation level: ADK evalsets (seed each persona through `session_input.state`) for tool trajectories, plus a small custom runner for content checks and a separate security set; this level needs a key and is not part of the `pytest` gate. Security guarantees are proven at unit level in code, not by the model-dependent eval (D7).
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
| Single root agent with three function tools | Scope of this prototype | approved |
| Caller identity, role or store as a tool parameter or taken from prompt text | n/a | avoid |
| Authorization only in the prompt, or only in the order stub | n/a | avoid |
| Multi-agent orchestration, write tools, custom UI, cloud deployment | n/a (out of scope) | avoid |
| Built-in tools mixed with function tools in one agent | n/a (ADK restriction) | avoid |
| Vertex AI Search, RAG Engine, Gemini File Search | n/a (excluded by the pinned stack) | avoid |
| Customer names, emails, addresses in logs or traces | n/a | avoid |

## 11. Migration (how existing code catches up after a change)
Code in a legacy scope is not failed for the listed rule until its target version; new or changed code must conform from the version it was introduced.

| Rule or pattern | Introduced in version | Legacy scope (globs) | Target version |
|---|---|---|---|
| (none yet) | | | |

## 12. Change log
| Version | Date | Change | Proposal |
|---|---|---|---|
| 1 | 2026-11-23 | Initial architecture (draft, awaiting owner approval) | `openspec/changes/novamart-rag-agent/design.md` |
| 2 | 2026-11-23 | Layout moved under `backend/` (`backend/src/novamart_agent/`, `backend/tests/`, `backend/evals/`, `backend/data/`); no frontend; added `ARCH-TEST-3` (evals mandatory for agent behavior; live-only, authored but not run until the owner supplies the API key and says to run). Still draft: no code exists, so no Migration row. | `openspec/changes/novamart-rag-agent/design.md` (D8) |

## 13. Open items (carried from design.md, not resolved here)
- VERIFY: ADK docs do not explicitly say end users cannot alter session state; identity in production must come from the authenticated token in the API layer (D2).
- VERIFY: availability and free-tier rate limits of the candidate Flash-class model IDs; model ID stays configuration (D6).
- VERIFY: whether ADK LLM-judge eval metrics (`hallucinations_v1`) work on a free key; fallback is the custom content checks (D7).
- VERIFY: Gemini Enterprise document ACL behaviour and how end-user identity reaches an A2A-registered agent; production-note items only, not built (D9).
- Owner decision: this spec adds a small `config` module in LAYER-4, which D8's layout does not list. Approving this spec approves that addition.
