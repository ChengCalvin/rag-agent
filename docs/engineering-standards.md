---
version: 4
architecture_version: 6
---

# Engineering standards (derived rules)

Derived from `docs/architecture.md` (which interprets `docs/team/principles.md` for this project). Every agent that writes or reviews code reads this file first. It is binding.

**Chain:** principles -> architecture spec -> these rules -> code. The code never defines a rule. Each rule shows its principle `[P-...]`; the numbers, paths and layer names it refers to live in the architecture spec, so changing the architecture changes the rules without editing every agent.

**Precedence:** this file > project `CLAUDE.md` > plugin defaults. The pinned stack always wins over a conflicting rule; note the exception in the report.

**Stack (pinned):** Python, Google ADK, Gemini (free AI Studio key), hand-rolled numpy retrieval, synthetic data only, run via adk web / adk run (not Vertex AI Search, RAG Engine, Gemini File Search)

**Version rule:** `architecture_version` above must equal the architecture spec's `version`. When the architecture changes, re-derive this file in the same proposal and bump both.

## 1. Structure and modularity

- `STRUCT-1` [P-DEP] Layers and their dependency direction are exactly those in architecture section 2. No import runs against the arrow.
- `STRUCT-2` [P-DEP] Modules are packaged and exposed as architecture section 3 says (`ARCH-MOD-2`). Other modules use only the public interface, never internals.
- `STRUCT-3` [P-RESP] Entry points (routes, handlers, commands, pages, jobs) only compose. No business rules, validation or data access inline.
- `STRUCT-4` [P-SEC] Code reserved for the trusted side (secrets, data stores, third-party SDKs) is never reachable from the untrusted side. Enforce with tooling where the stack allows it.
- `STRUCT-5` [P-REUSE] Before creating a component, helper or schema, search for an existing one and reuse or extend it. Extract shared code on the third real use, not speculatively.
- `STRUCT-6` [P-RESP] A new capability ships complete in its module: public interface, types, tests. Removing the module removes the capability cleanly.

## 2. Size and responsibility

- `SIZE-1` [P-RESP] Stay within the limits in architecture section 9. The function limits (`ARCH-LIM-3`, `ARCH-LIM-4`) are enforced by the linter (ruff `PLR0915`, `PLR0913`); the file limit (`ARCH-LIM-1`) is checked in review.
- `SIZE-2` [P-RESP] Limits are a smell detector. Split by responsibility, never by line count alone.
- `SIZE-3` [P-RESP] One reason to change per module. A file mixing rendering, fetching and validation must be split.
- `SIZE-4` [P-EDGE] Side effects sit at the edges; core logic is pure and unit-testable.

## 3. Types, boundaries and errors

- `TYPE-1` [P-BOUND] Use the strictest type checking the stack offers: mypy in strict mode on `backend/src`. No untyped escape hatches (`Any`, bare `# type: ignore`) or unexplained casts.
- `TYPE-2` [P-BOUND] Parse all external input once at the boundary (architecture section 4); pass typed values inward. One schema per payload, shared by both sides where both exist.
- `TYPE-3` [P-BOUND] Exported functions declare their return types.
- `ERR-1` [P-ERR] Errors are handled at the layer architecture section 6 names, never swallowed, and use its error shape.
- `ERR-2` [P-SEC] No secrets or personal data in logs, error messages, URLs or client bundles. This includes the audit record and the cost record (`ARCH-ERR-1`, `ARCH-EDGE-1`, `ARCH-CFG-1`): no customer names, emails or addresses, and no message text. Secrets only from the source in architecture section 7.
- `ERR-3` [P-ERR] Pipeline outcomes are the closed set in `ARCH-ERR-2` (A to E), each with its one observable output. No new outcome and no free-form fallback reply; an unexpected failure maps to the generic failure status of `ARCH-ERR-1`, not to a model-written answer. Tool statuses map to outcomes as `ARCH-ERR-1` states.
- `ERR-4` [P-SEC] A deterministic refusal (outcomes C and D of `ARCH-ERR-2`) is decided in code and is never overturned by a model or validator verdict. A verdict may only lower confidence or request a rewrite. Loop exit and the confidence band are computed in code.

## 4. Conventions

- `CONV-1` [P-CONFIG] Configuration, text and design values come from the sources in architecture section 7. No hard-coded copies of them. This includes the loop max iterations, loop-exit threshold, confidence weights, band thresholds and rewrite cap (`ARCH-CFG-1`): read in `config` with defaults, not constants.
- `CONV-2` [P-CONFIG] Naming and layout follow architecture sections 3 and 10.
- `CONV-3` [P-SCOPE] No new dependency without a one-line justification (size, maintenance, alternative considered) in the report.
- `CONV-4` [P-SCOPE] No dead code, commented-out code, or `TODO` without a tracked work item.

## 5. Tests and verification

- `TEST-1` [P-TEST] Every requirement or scenario touched has a test, and the test name quotes or references it.
- `TEST-2` [P-TEST] Test at the public interface, not internals. Cover the error path of every externally facing function. The pipeline decisions (precheck, routing, rubric coverage, confidence composite and band, outcome mapping to A-E, cost) have key-free unit tests with fake model outputs (`ARCH-TEST-1`).
- `TEST-3` [P-TEST] Before reporting done: lint, type-check, tests and build, each exactly as `process.yaml` (`stack.commands`) defines it, all pass. Show the commands and results. Do not substitute a weaker command for the type-check.
- `TEST-4` [P-TEST] Agent behavior has evals as architecture `ARCH-TEST-3` requires: every agent-behavior scenario maps to an eval case, and the eval command and pass rates are shown in the report next to the `TEST-3` results. Evals are live-only and are never run (nor any command that calls the model) until the owner has supplied the API key and says to run; until then report "authored, not run" and leave the task open. A failing eval fails the task.

## 6. Change hygiene and evolution

- `HYG-1` [P-SCOPE] Minimal diff: only what the work item needs. List worthwhile refactors in the report instead of doing them.
- `HYG-2` [P-SCOPE] One work item or chunk is one reviewable, independently verifiable commit's worth of change.
- `HYG-3` [P-SCOPE] Never edit generated files, lockfiles by hand, or files outside the work item's scope.
- `EVOL-1` [P-EVOLVE] Do not introduce a pattern, layer or dependency direction that the architecture spec does not approve. Raise a proposal instead.
- `EVOL-2` [P-SPEC] If existing code disagrees with the architecture, do not copy the old pattern. Follow the spec, and report the disagreement. Code covered by architecture section 11 (Migration) is exempt until its target version.

## 7. Agent pipeline and trust

- `AGENT-1` [P-SEC] Only the `retrieval` and `order` agents may be given tools (`ARCH-MOD-5`). Intake, validator and composer have none. No agent other than those two touches order data, and order data is reached only through a tool that calls the authorization choke point first (`ARCH-MOD-4`).
- `AGENT-2` [P-DEP] Delegation between agents is plain-Python routing in the deterministic orchestrator (`ARCH-LAYER-1`, section 10 patterns). No LLM-driven delegation: no `AgentTool`, transfer, or model-chosen `sub_agents`. Built-in tools are never mixed with function tools in one agent.
- `AGENT-3` [P-SEC] Sources, the confidence band and diagram blocks are written or verified by code from chunk metadata (section 10 patterns). The model never writes citations, the band or diagrams; model text containing them is replaced or rejected by code.
- `AGENT-4` [P-BOUND] Retrieved document text and every model-produced intermediate (rubric, verdict, rewritten query) are data only (`ARCH-BOUND-1`): passed as message content, parsed into typed models, never templated into instruction text and never obeyed as instructions. The raw user message passes the code precheck before any model call.
- `AGENT-5` [P-EDGE] Per-turn and per-session cost is recorded by code in `pipeline/cost` from the model's `usage_metadata` and the configured price table (`ARCH-CFG-1`), never estimated or reported by the model. `NOVAMART_SHOW_COST` hides display only; recording stays on. The record carries no PII (`ERR-2`).

## Exceptions

A deviation is allowed only with a comment `standards-exception(<RULE-ID>): <reason>` at the site and a line in the report. Reviewers fail unexplained deviations and accept justified ones.

## Developer self-check (paste into every report)

```
Standards self-check
- STRUCT: layers, public interfaces, entry points only compose ..... yes|no|n/a
- SIZE: within architecture limits, responsibilities separated ..... yes|no
- TYPE/ERR: boundary parsing, strict types, closed outcomes, refusals
  in code, no secrets or PII in logs (audit and cost too) ........... yes|no
- AGENT: tools only on retrieval/order, code routing, sources/band/
  diagrams/cost by code, model output treated as data .............. yes|no|n/a
- CONV: sources for config/text/design, reuse, dependency note ..... yes|no
- TEST: each scenario has a named test; lint+types+tests green ..... yes|no
- EVAL: scenarios have eval cases; authored, not run, or rates yes|no|n/a
- EVOL: no unapproved pattern; disagreements reported .............. yes|no
- Exceptions: <list or none>
```
