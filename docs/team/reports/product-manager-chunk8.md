# product-manager report: chunk 8, task 8.1 (spec side)

Verdict: READY

## Evidence

- Reviewed `specs/policy-retrieval`, `specs/order-tools`, `specs/agent-evaluation` against design D12 to D15 and `backend/evals/cases/{quality,security,traceability}.json`.
- Tightened (written by me, in scope):
  - `policy-retrieval/spec.md`: clarification is "no tool, no retrieval"; "Clarification asked only once" now states the testable outcome (the follow-up reply is not another clarification: best-effort or decline); E scenario states "which part is not covered" and "Low band", not the C refusal; band requirement now names the layout (Sources then `Confidence: <band>`), no numeric score, and that clarification, decline, C and order replies carry no band.
  - `order-tools/spec.md`: malformed id is rejected inside the order tool only (D13 D, AG-43); parity scenario adds same agent path; label is the exact `From order records.` (canned.py:41); combined sentence must contain "cannot answer the policy part" (canned.py:21).
  - `agent-evaluation/spec.md`: "exactly one case labelled with each outcome A to E" (a second case, `clarification-asked-only-once`, also asserts A on turn 0, so "expected outcome of exactly one case" was false); combined scenario adds "no policy search called" and drops the awkward wording.
- `tasks.md`: already in the required state, no change needed: 8.1, 8.2, 8.3 `[x]`; 8.4, 8.5, 8.6 `[ ]`. Verify conditions hold: 8.1 traceability test; 8.2 and 8.3 case tests (below).
- Commands (repo root, `backend/.venv`): `pytest backend/tests/test_evals_traceability.py backend/tests/test_evals_cases.py -q` gives `38 passed in 0.97s` after my edits.
- Every new requirement maps in `traceability.json`: Order number missing (`order-number-missing-asks-one-question`), Clarification once (`clarification-asked-only-once`), No evidence (`question-the-documents-are-silent-on-bulk-orders`), Weak coverage and cap (`partially-covered-question-low-band`), Band (`answerable-policy-question-electronics-window`), Order shortcut (`permitted-order-status-and-order-shortcut`), Combined (`combined-question-known-limitation-*`), Malformed (`denial-indistinguishable-from-not-found`).
- Scope: I wrote only under `openspec/changes/novamart-rag-agent/specs/` and this report. design.md, architecture.md, backend/ untouched.

## Open items

Traceability and case mismatches (backend-dev; files read-only for me):
1. Band scenario says "no numeric confidence score"; case `answerable-policy-question-electronics-window` only checks the `Confidence: (High|Medium|Low)` line. Add a `reply_not_matches` for a numeric score, or the clause is unproven.
2. Order requirement says an eligibility answer needs no `search_policy` and no band. `within-the-return-window-eligible` checks neither; add `tool_not_called search_policy` and `band_is none`.
3. "Uncovered required criterion caps the band" and "band not written by a model" are mapped only to a live case that may fail for other reasons. Add a `covered_by` unit test (the cap rule in `pipeline/confidence`) as a second mapping.
4. `clarification-asked-only-once` checks only "turn 1 is not outcome A"; weaker than the requirement ("proceeds best-effort or declines"). Acceptable, but the case also asserts A on turn 0, so it is a second A-labelled case by assertion; `refusal_outcome` labelling keeps the "exactly one" rule true.
5. C requirement says no query rewrite is attempted; no scenario or case check asserts it (`question-the-documents-are-silent-on-bulk-orders` checks validator and composer not called). Add a no-rewrite check (model-call count) or accept as unit-test only.
6. Cases that may fail live (from backend-dev): E, both combined cases, malformed turn in `denial-indistinguishable-from-not-found`, `poisoned-document`. 8.4 is authored, not run; no pass rates exist.

D7 findings for the architect/owner (design.md not edited by me):
7. Persona seeding via `session_input.state` cannot work: the orchestrator's first node overwrites the principal each turn from `NOVAMART_USER`. Evalsets must be generated per persona, with `adk eval` run once per persona with `NOVAMART_USER` set.
8. The trajectory metric must compare tool names only: use `tool_trajectory_avg_score` alone with `ignore_args: true` (`IN_ORDER` for tool cases, `EXACT` for no-tool cases), because a model-written `search_policy` query cannot match exactly. `match_type` and `ignore_args` are in google-adk 2.15.0 but not on adk.dev (backend-dev's report).
9. Whether `adk eval` loads a `Workflow` root is still open (`adk-eval-workflow-root`); the custom runner reading events is the fallback. Parsing scores from `adk eval` console output is a VERIFY at the first live run.

Scope note: backend-dev edited these specs and tasks.md out of its write scope; the text is now authored by product-manager, so `check_scope.py` should accept the spec files from this report onward.
