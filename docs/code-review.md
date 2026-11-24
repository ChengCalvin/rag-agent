# Code review: novamart-rag-agent, chunk 9 (tasks 9.1-9.4)

Verdict: PASS (0 Blocker, 0 Major, 2 Minor). Standards v5 / architecture v7 match; `gates.fail_on` default `major`.

## Evidence
Project interpreter `backend/.venv/Scripts/python`. No model call; `backend/.env` not read.
- `ruff check backend`: All checks passed.
- `mypy --config-file backend/pyproject.toml backend/src`: no issues in 72 source files.
- `pytest backend/tests`: 762 passed.
- `pip install -e backend`: success.
- `docs/production_note.md`: 671 words, 37 lines (within the test budget of 700 / 60).
- Spec check (`production-note/spec.md`): four labelled sections (`production_note.md:7,12,17,23`); recommendation, reasons, **Fallback**, **Revisit** (line 5); identity spike with question, owners, fallback (line 18); unverified claims marked TBC (lines 10,13,18,19,20); limits table (lines 28-35) with simulated item and production replacement.
- Prices in note (line 10) equal `DEFAULT_PRICES` (`config.py:61-63`), pinned by `test_production_note_prices_match_config`.
- README: Python >=3.11 matches `pyproject.toml:9`; loop "max 2 passes" matches `config.py:103`; env names tested against `.env.example`; persona table tested against `users.json`.
- 9.4: `backend/.env` untracked (`git ls-files` returns 0) and ignored (`.gitignore:1`); developer's regex scan reported 0 matches. I did not re-scan history.
- Standards: no code in `src` changed (STRUCT/AGENT n/a); no new dependency; no TODO or dead code; test names reference spec scenarios (TEST-1); self-check is consistent with what I found.

## Findings
| Sev | Location | Rule | What | Suggested fix |
|---|---|---|---|---|
| Minor | `docs/production_note.md` (whole) | TEST-1 | The "one page" scenario is checked only by a word and line budget. No render was done, and 671 words plus a table and 5 headings may spill past one page at 10 pt. | Owner prints to PDF once (developer already lists this). If it spills, trim. |
| Minor | `backend/tests/test_docs_chunk9.py:97,105,116` | TEST-2 | Several tests assert exact prose strings (for example `"**Identity-propagation spike"`, `"Sources, all read"`). Editing wording breaks them. | Accept for now, or key them on headings only. |

## Pending migration
None applicable.

## Rules to add
None.
# Code review: novamart-rag-agent, chunk 8 (tasks 8.1-8.4), re-run after fix cycle 1

Verdict: PASS (0 Blocker, 0 Major, 0 Minor open). Standards v5 / architecture v7 match; `gates.fail_on` default `major`.

## Evidence

Commands run with the project interpreter `backend/.venv/Scripts/python.exe -m ...`. No model call made; `backend/.env` not read.
- `ruff check backend`: All checks passed.
- `mypy --config-file backend/pyproject.toml backend/src`: Success, no issues in 72 source files. The earlier `rag/index.py:28` error came from the system Python 3.13 (older numpy and ADK), not the project env.
- `pytest backend/tests`: 750 passed.

## Previous findings

| # | Was | Now | Evidence |
|---|---|---|---|
| 1 | Major, mypy red | Resolved | mypy green in the venv (above). The finding was an environment artifact. |
| 2 | Major, ERR-2 | Resolved | `--print_detailed_results` is gone from `adk_step.py` (the only remaining mention is a probe note string in `probe_agents.py:97` and the test asserting its absence at `tests/test_evals_runner.py:34`). `run_evals.py:69-77` runs with `capture_output=True`, keeps only `adk_record` (`{command, exit_code}`, `adk_step.py:40-42`) and writes `adk-<stamp>.json`. No `.txt` output is written. Test `test_run_adk_persists_no_reply_text` exists. |
| 3 | Minor, CONV-3 | Resolved | `pyproject.toml:22` declares `python-dotenv` with a justification comment. |
| 4 | Minor, exception ID | Resolved | `standards-exception(CONV-1)` in `run_evals.py:90`, `verify_models.py:19`, `check_adk_assumptions.py:43`. The fix report lists them. |
| 5 | Minor, facade logic | Resolved | `evalkit/case_set.py` (17 lines) holds `load_all_cases` and `CASE_FILES`. `evalkit/__init__.py` only re-exports. |
| 6 | Minor, mypy scope | Open item | Needs an architecture proposal; not a failure. |

New test `test_run_evals_without_a_key_returns_2_before_any_model_call` and the traceability tests are in the 750 passing. The largest evalkit file is `cases.py` at 158 lines (limit 300).

## Findings

None at or above minor.

## Pending migration (architecture section 11)

None in the chunk 8 diff. The `adk eval` Workflow-root question stays open (`design.md`, `adk-eval-workflow-root`).

## Rules to add (proposals; architecture change needed)

- `TYPE-5`: type-check `backend/evals` with mypy strict, or state the exclusion in the architecture.
- `ERR-5`: no file written by an eval or report tool stores raw model or tool output; only labelled figures.
- A rule for how owner-run eval scripts load `backend/.env` (currently covered by a `CONV-1` exception).

## Open items

- mypy does not cover `backend/evals` (about 1,200 lines in evalkit); needs a proposal.
- Spec edits under `openspec/changes/novamart-rag-agent/specs/` change behavior; the orchestrator should confirm owner approval in the ledger (operating model section 5).
- Evals are "authored, not run" (TEST-4): task 8.4 stays open until the owner supplies a key and says to run.
