# Owner-run checklist (needs `GOOGLE_API_KEY`)

Tick each box together. Key-free state at time of writing: 766 tests pass, `ruff` clean, evalsets build, `run_evals.py --dry-run` = 31 cases, about 105 calls (plus about the same for `adk eval`).

Setup once (PowerShell, repo root, venv active): `backend\.env` holds the key and the two `FALSE` flags. For a low quota, use `$env:NOVAMART_MODEL = "gemini-3.5-flash-lite"`.

## A. Task 8.7: C case needs a question below the cosine threshold
- Probe found the dress-code question scores 0.657 (above 0.6), so it gave outcome E. Case swapped to "How do I reset my email password?" (0.562).
- [ ] `python backend/evals/run_evals.py --set quality --skip-adk --only question-below-the-cosine-threshold-email-password` returns PASS (intake could still route it out of scope as B; tell me if so).
- [ ] Then I tick 8.7.

## B. Task 9.1: fresh-clone check of the README
- [ ] In a clean folder or fresh clone, follow only the README setup, then `adk web backend/src` as `emp_store7`, and ask one policy question. It works.
- [ ] Note any step that was wrong or missing.

## C. Task 8.5: tuning (needs a full quality run)
- [ ] `python backend/evals/run_evals.py --set quality --skip-adk`; send me `backend/evals/results/` output.
- [ ] Re-run at three cosine thresholds (I will give the exact env or flag values once I see the first run).
- [ ] I write the tuning table and chosen defaults into `backend/evals/RESULTS.md`.

## D. Task 8.6: results summary
- [ ] `python backend/evals/run_evals.py` (full, with `adk eval`), results to me.
- [ ] I write every failure with a diagnosis, validator agreement (you hand-label a subset), calls and cost per question, and cost at 1,000 questions.

## E. Task 10.1: final run
- [ ] Unit tests, quality and security evals, and one demo per persona (`emp_store7`, `emp_store12`, `mgr_store7`, `regmgr_north`) from a clean environment, using `TEST_CASES.md` tests 1-10.
- [ ] Results match the summary from D.

Order: A, then C, D, E. B can happen any time.
