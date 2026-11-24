---
version: 2
architecture_version: 2
---

# Engineering standards (derived rules)

Derived from `docs/architecture.md` (which interprets `docs/team/principles.md` for this project). Every agent that writes or reviews code reads this file first. It is binding.

**Chain:** principles -> architecture spec -> these rules -> code. The code never defines a rule. Each rule shows its principle `[P-...]`; the numbers, paths and layer names it refers to live in the architecture spec, so changing the architecture changes the rules without editing every agent.

**Precedence:** this file > project `CLAUDE.md` > plugin defaults. The pinned stack always wins over a conflicting rule; note the exception in the report.

**Stack (pinned):** Python, Google ADK, Gemini (free AI Studio key), hand-rolled numpy retrieval, synthetic data only, run via adk web / adk run (not Vertex AI Search, RAG Engine, Gemini File Search)

**Version rule:** `architecture_version` above must equal the architecture spec's `version`. When the architecture changes, re-derive this file in the same proposal and bump both.

## 1. Structure and modularity

- `STRUCT-1` [P-DEP] Layers and their dependency direction are exactly those in architecture section 2. No import runs against the arrow.
- `STRUCT-2` [P-DEP] Modules are packaged and exposed as architecture section 3 says. Other modules use only the public interface, never internals.
- `STRUCT-3` [P-RESP] Entry points (routes, handlers, commands, pages, jobs) only compose. No business rules, validation or data access inline.
- `STRUCT-4` [P-SEC] Code reserved for the trusted side (secrets, data stores, third-party SDKs) is never reachable from the untrusted side. Enforce with tooling where the stack allows it.
- `STRUCT-5` [P-REUSE] Before creating a component, helper or schema, search for an existing one and reuse or extend it. Extract shared code on the third real use, not speculatively.
- `STRUCT-6` [P-RESP] A new capability ships complete in its module: public interface, types, tests. Removing the module removes the capability cleanly.

## 2. Size and responsibility

- `SIZE-1` [P-RESP] Stay within the limits in architecture section 9.
- `SIZE-2` [P-RESP] Limits are a smell detector. Split by responsibility, never by line count alone.
- `SIZE-3` [P-RESP] One reason to change per module. A file mixing rendering, fetching and validation must be split.
- `SIZE-4` [P-EDGE] Side effects sit at the edges; core logic is pure and unit-testable.

## 3. Types, boundaries and errors

- `TYPE-1` [P-BOUND] Use the strictest type checking the stack offers. No untyped escape hatches or unexplained casts.
- `TYPE-2` [P-BOUND] Parse all external input once at the boundary (architecture section 4); pass typed values inward. One schema per payload, shared by both sides where both exist.
- `TYPE-3` [P-BOUND] Exported functions declare their return types.
- `ERR-1` [P-ERR] Errors are handled at the layer architecture section 6 names, never swallowed, and use its error shape.
- `ERR-2` [P-SEC] No secrets or personal data in logs, error messages, URLs or client bundles. Secrets only from the source in architecture section 7.

## 4. Conventions

- `CONV-1` [P-CONFIG] Configuration, text and design values come from the sources in architecture section 7. No hard-coded copies of them.
- `CONV-2` [P-CONFIG] Naming and layout follow architecture sections 3 and 10.
- `CONV-3` [P-SCOPE] No new dependency without a one-line justification (size, maintenance, alternative considered) in the report.
- `CONV-4` [P-SCOPE] No dead code, commented-out code, or `TODO` without a tracked work item.

## 5. Tests and verification

- `TEST-1` [P-TEST] Every requirement or scenario touched has a test, and the test name quotes or references it.
- `TEST-2` [P-TEST] Test at the public interface, not internals. Cover the error path of every externally facing function.
- `TEST-3` [P-TEST] Before reporting done: lint, type-check, tests and build (as `process.yaml` defines them) all pass. Show the commands and results.
- `TEST-4` [P-TEST] Agent behavior has evals as architecture `ARCH-TEST-3` requires: every agent-behavior scenario maps to an eval case, and the eval command and pass rates are shown in the report next to the `TEST-3` results. Evals are live-only and are never run (nor any command that calls the model) until the owner has supplied the API key and says to run; until then report "authored, not run" and leave the task open. A failing eval fails the task.

## 6. Change hygiene and evolution

- `HYG-1` [P-SCOPE] Minimal diff: only what the work item needs. List worthwhile refactors in the report instead of doing them.
- `HYG-2` [P-SCOPE] One work item or chunk is one reviewable, independently verifiable commit's worth of change.
- `HYG-3` [P-SCOPE] Never edit generated files, lockfiles by hand, or files outside the work item's scope.
- `EVOL-1` [P-EVOLVE] Do not introduce a pattern, layer or dependency direction that the architecture spec does not approve. Raise a proposal instead.
- `EVOL-2` [P-SPEC] If existing code disagrees with the architecture, do not copy the old pattern. Follow the spec, and report the disagreement. Code covered by architecture section 11 (Migration) is exempt until its target version.

## Exceptions

A deviation is allowed only with a comment `standards-exception(<RULE-ID>): <reason>` at the site and a line in the report. Reviewers fail unexplained deviations and accept justified ones.

## Developer self-check (paste into every report)

```
Standards self-check
- STRUCT: layers, public interfaces, entry points only compose ..... yes|no|n/a
- SIZE: within architecture limits, responsibilities separated ..... yes|no
- TYPE/ERR: boundary parsing, typed, no secrets in logs ............ yes|no
- CONV: sources for config/text/design, reuse, dependency note ..... yes|no
- TEST: each scenario has a named test; lint+types+tests green ..... yes|no
- EVAL: scenarios have eval cases; authored, not run, or rates yes|no|n/a
- EVOL: no unapproved pattern; disagreements reported .............. yes|no
- Exceptions: <list or none>
```
