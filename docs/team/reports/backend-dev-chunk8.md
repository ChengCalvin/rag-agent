# backend-dev report: chunk 8 (Evaluation), tasks 8.1 to 8.4

Verdict: DONE (8.1, 8.2, 8.3 complete and checked; 8.4 authored, not run, left unchecked; the tuning and results-summary tasks after it need live runs and were not started)

## Tasks

| Task | State |
|---|---|
| 8.1 spec scenarios | DONE, checked. New requirements and scenarios in `policy-retrieval`, `order-tools`, `agent-evaluation`; traceability test passes |
| 8.2 quality cases | DONE, checked. 18 cases in `backend/evals/cases/quality.json` |
| 8.3 security cases | DONE, checked. 12 cases in `backend/evals/cases/security.json` |
| 8.4 runner | AUTHORED, NOT RUN, unchecked (live-only, no key; ARCH-TEST-3, TEST-4). Pure and content-check logic is unit-tested key-free |
| tuning and results summary | Not started, unchecked (need live runs; out of scope here) |

### 8.1 spec changes (`openspec/changes/novamart-rag-agent/specs/`)
- `policy-retrieval`: scenario "Answerable product question"; requirements "Under-specified questions get exactly one clarifying question" (scenarios "Order number missing", "Clarification asked only once"), "No evidence is refused, weak coverage is answered with a caveat" (C against E: "No evidence names the contact and permitted titles", "Weak coverage answers with Low band"), "Confidence is shown as a band written by code" ("Band shown on a document answer", "Uncovered required criterion caps the band").
- `order-tools`: requirements "Order questions skip the validation loop" ("Order shortcut") and "A message mixing order and policy parts is answered by the order path only" ("Combined question known limitation"); scenario "Malformed identifier costs the same as a nonexistent one" (the existing "Malformed identifier" scenario already states the uniform not-found text, no follow-up, no lookup).
- `agent-evaluation`: quality set now 15 to 18 cases with exactly one per outcome A to E ("Coverage of refusal outcomes"); security set extended (injection through document and through rubric/rewrite, denial parity, probing, request to change an order; scenarios "Injection cases", "Denial parity case"); new requirements "Every behavior scenario maps to an eval case" ("Traceability map") and "Results record calls and cost per question" ("Cost recorded per case").
- Mapping: `backend/evals/cases/traceability.json` maps all 61 scenarios in the change to case ids or to a named test/document with a reason. `backend/tests/test_evals_traceability.py` fails if a scenario is unmapped, a case id is unknown, a `covered_by` path is missing, or a case maps to nothing.

### 8.2 quality cases (18)
policy 3, product 3, order 5 (status, eligible, category exception, regional manager, clarification once), combined 2 (labelled `known_limitation`; pass = order part right, no `search_policy`, reply says "cannot answer the policy part"), refusal 5 (A order number missing, B out-of-domain, C bulk orders, D unknown order, E partially covered warranty question). Types: answerable 6, order 5, combined 2, refusal 5.

### 8.3 security cases (12)
cross-store (with nonexistent-order parity), role claim caught by precheck, role claim passing precheck, poisoned document (fixture `backend/evals/fixtures/poisoned-courier-memo/`, copied into a scratch data dir at run time; shipped corpus untouched), rubric/rewrite injection, PII in logs (DEBUG capture of all loggers plus `log_contains audit` so an empty capture cannot pass), manager-only policy (employee, plus manager positive control), manager-only product briefing, denial parity (cross-store, nonexistent, malformed in one session: same text, same model-call count and agent path, validator and composer never ran), sequential probing (7 lookups, limit 5), request to change an order. Each `expected` starts "Pass only if" (or "Positive control") and is backed by objective checks.

### 8.4 runner (authored, not run)
`backend/evals/evalkit/` (small modules, largest 158 lines): `cases` (typed parse at load), `checks*` (20 objective check kinds, no model grading), `observation` (outcome letters from code state and layout), `grade`, `summary`, `render`, `write_results`, `adk_evalset`/`adk_step` (ADK trajectory evalsets and commands), `events`, `drive` (live; the only model-calling module), `corpus`, `seeded`, `log_capture`. Entry points: `backend/evals/run_evals.py` (live; exits 2 before any model call if `GOOGLE_API_KEY` is unset) and `backend/evals/build_evalsets.py` (key-free). Writes per-set `.md` and `.json` to `backend/evals/results/` (gitignored): per-case results, overall pass rate, calls and cost per question, cost at 1,000 questions, every failure listed; no reply text or customer values are written (ERR-2).

## Evidence

Run from repo root with `backend/.venv` (google-adk 2.15.0). No model, network or key was used; `backend/.env` exists but was never loaded or read.

```
$ backend/.venv/Scripts/ruff check backend
All checks passed!
$ backend/.venv/Scripts/mypy --config-file backend/pyproject.toml backend/src
Success: no issues found in 72 source files
$ backend/.venv/Scripts/python -m pytest backend/tests -q
746 passed in 36.22s            (662 before this chunk; 84 new, all key-free)
$ backend/.venv/Scripts/python -m pip install -e backend
Successfully installed novamart-agent-0.1.0
```

New tests (84), named after scenarios: `test_evals_cases.py` (coverage of question types, coverage of refusal outcomes A to E once each, combined question known limitation, every security category, and that each case's expectations agree with the shipped documents, canned wording and `precheck`), `test_evals_checks.py` (every check kind passes and fails; unknown kind or bad argument raises, never passes), `test_evals_report.py` (per-case results, pass rate, every failure listed, calls and cost per question, unavailable cost never zero, no reply text or customer data in results files), `test_evals_adk.py` (generated evalsets equal the files on disk; parsed by ADK's `EvalSet`/`EvalConfig`; trajectory metric alone), `test_evals_traceability.py`, `test_evals_support.py` (seeded values, log capture, fixture corpus, event reading), `test_evals_driver_turn.py`. The last one runs the REAL orchestrator with scripted models and grades eight shipped cases (A, B, C, D, E outcome, precheck decline, cross-store parity, order shortcut) through the real `run_turn`, so the checks are proven to agree with the pipeline.

Task verify conditions: 8.1 `test_evals_traceability.py` (10 tests) every scenario maps; 8.2 `test_coverage_of_question_types_*` and `test_coverage_of_refusal_outcomes_*`; 8.3 `test_every_security_case_has_a_pass_condition_*` and `test_security_set_covers_every_required_category`.

## ADK eval check against adk.dev and the installed 2.15.0 (mismatches with the design)

1. D7 says evalsets seed the persona through `session_input.state`. The orchestrator's first node overwrites the principal every turn from `NOVAMART_USER`, so seeding state cannot select a persona. Evalsets are therefore generated per persona and `adk eval` is run once per persona with `NOVAMART_USER` set; state stays empty. Design D7 should be amended.
2. adk.dev documents only `tool_trajectory_avg_score` (exact) and `response_match_score` (ROUGE, applied by default if no criteria). Exact args cannot match a model-written `search_policy` query. google-adk 2.15.0 has `match_type` (`EXACT`, `IN_ORDER`, `ANY_ORDER`) and `ignore_args` on the criterion, not on the page. Configs use the trajectory metric alone, `ignore_args: true`, `IN_ORDER` for tool cases and `EXACT` for no-tool cases.
3. adk.dev documents no results file for `adk eval`, only `--print_detailed_results` to the console. The runner stores each command's raw output and exit code; parsing scores from it is a VERIFY item at the first live run.
4. Whether `adk eval` loads a `Workflow` root is still open (`adk-eval-workflow-root`). The custom runner reads tool calls from events regardless, which is the fallback D7 names.
5. Multi-turn and fixture-corpus cases are not exported to ADK (one expected tool list cannot say which turn made which call); the custom runner covers them.

## Standards self-check

```
Standards self-check
- STRUCT: layers, public interfaces, entry points only compose ..... yes (evals sit outside the layers and import only public names of src packages; no src change)
- SIZE: within architecture limits, responsibilities separated ..... yes (largest file 158 lines; ruff PLR0913/PLR0915/C901 clean)
- TYPE/ERR: boundary parsing, strict types, closed outcomes, refusals
  in code, no secrets or PII in logs (audit and cost too) ........... yes (cases parsed once at load; outcome letters from code state; results hold no reply text or customer values; failures name a value label only)
- AGENT: tools only on retrieval/order, code routing and loop exit,
  sources/band/diagrams/cost by code, model output treated as data,
  no deprecated ADK API ............................................ yes (cost read from recorded usage, not model text; no LoopAgent; no src change)
- CONV: sources for config/text/design, reuse, dependency note ..... yes (canned wording and prices imported, not copied; no new dependency; `python-dotenv` already used by the probes and shipped with ADK)
- TEST: each scenario has a named test; lint+types+tests green ..... yes (ruff, mypy, 746 pytest, pip install -e all green)
- EVAL: scenarios have eval cases; authored, not run, or rates ..... yes: every scenario maps to a case or a stated reason; AUTHORED, NOT RUN, no pass rates
- EVOL: no unapproved pattern; disagreements reported .............. yes (D7 mismatches above)
- Exceptions: standards-exception(ARCH-CFG-1) on `load_dotenv` in `run_evals.py`, same as the existing owner-run probes
```

## Open items

1. Scope flag: `docs/team/guardrails.yaml` gives backend-dev no write access to `openspec/**` or `docs/team/**`. I edited three spec files and `tasks.md` (8.1 to 8.3 checked) and wrote this report because the delegation instructed it. `check_scope.py` will flag them; the orchestrator should accept them or have the product-manager re-apply the spec text. `pyproject.toml` (deps scope) got one line: pytest `pythonpath = ["src", "evals"]`.
2. 8.4 and the two live-run tasks after it stay open. Owner-run: `python backend/evals/run_evals.py` (all cases, then the ADK step), `--set`, `--only <id>`, `--skip-adk`; regenerate evalsets with `python backend/evals/build_evalsets.py`.
3. Cases that may fail live and must be reported honestly, not tuned away: E (weak coverage depends on validator and rubric behavior), the two combined cases (depend on intake flagging the policy part), `denial-indistinguishable-from-not-found` turn "10x2" (intake could ask a clarification instead of routing to `order`), `poisoned-document` (requires retrieval to surface the memo; its `cites` check makes a non-retrieval fail rather than pass vacuously).
4. Return-window answers use a pinned reference date of 2026-11-23 (`drive.REFERENCE_DATE`, from `backend/data/README.md`); the poisoned-document case builds a scratch copy of `backend/data` under `backend/evals/results/scratch` (gitignored).
5. Free-tier rate limits: the runner runs cases sequentially with no throttling; about 19 quality turns plus 25 security turns at 1 to 6 model calls each. Add backoff if 429s appear (agent nodes already retry).
6. Design.md D7 should record the persona and `ignore_args` findings above; I did not edit `design.md`.
7. Possible refactor, not done: `Case.adk_expected_tools` derives pinned tools from `tool_called` checks; an explicit field would be clearer if more kinds are added.

## Fix cycle 1

Verdict: DONE (8.4 stays unchecked; nothing live was run).

1. mypy: not reproduced. `backend/.venv/Scripts/python.exe -m mypy --config-file backend/pyproject.toml backend/src` is green with the repo cache, with a clean `--cache-dir`, and after deleting the stale `backend/.mypy_cache` (deleted; rebuilt green). The `index.py:28` no-any-return only appeared under the system Python 3.13 (older numpy and ADK 1.18), not the project venv. No typing change made.
2. ERR-2: `--print_detailed_results` removed from `evalkit/adk_step.py`; `run_evals.run_adk` no longer writes `adk-*.txt`. The new `adk_record` keeps only `{command, exit_code}` in `adk-<stamp>.json`. Test: `tests/test_evals_runner.py::test_run_adk_persists_no_reply_text` (plus flag-absent and record-shape tests).
3. `python-dotenv` declared in the `dev` extra of `backend/pyproject.toml`.
4. The exception comments (`run_evals.py`, `verify_models.py`, `check_adk_assumptions.py`) now cite `standards-exception(CONV-1)`.
5. `load_all_cases` and `CASE_FILES` moved to `evalkit/case_set.py`; `evalkit/__init__.py` re-exports only.
6. Cases: numeric-confidence `reply_not_matches` added to answerable-policy-question-electronics-window; `tool_not_called search_policy` and `band_is none` added to within-the-return-window-eligible and category-exception-electronics-outside-window. The "Uncovered required criterion caps the band" traceability entry is now `covered_by` the two named tests in `test_pipeline_confidence.py`; its id was added to the allow-list in `test_evals_traceability.py` (behavior scenarios otherwise need an eval case).
7. `test_run_evals_without_a_key_returns_2_before_any_model_call` added (key env cleared, `load_dotenv` stubbed, model path stubbed to fail).

Results: `ruff check backend` pass; mypy 72 files no issues; pytest 750 passed; `pip install -e backend` ok.

Open items: mypy does not cover `backend/evals` and no standards rule governs eval-script dotenv loading (both need an architecture proposal; not done). Case-file edits change what the owner-run eval checks; still authored, not run.
