# backend-dev chunk 9 (tasks 9.1 to 9.4)

Verdict: DONE (no task ticked; orchestrator does that after the gates)

## Tasks
| Task | State |
|---|---|
| 9.1 | DONE. `README.md` (repo root). Links `backend/data/README.md` |
| 9.2 | DONE. Claims re-checked 2026-11-24; results in the Evidence section and in `docs/production_note.md` |
| 9.3 | DONE. `docs/production_note.md`: four sections, recommendation, fallback, revisit condition, identity spike, limits table including the combined-question limit |
| 9.4 | DONE. Secret scan, zero findings |

Tests: `backend/tests/test_docs_chunk9.py` (11 key-free tests).

## Evidence
- `ruff check backend`: All checks passed. `mypy --config-file backend/pyproject.toml backend/src`: no issues in 72 files. `pytest backend/tests`: 762 passed. `pip install -e backend`: success.
- `adk --help`, `adk run --help`, `adk web --help` ran from `backend/.venv` (no model call); `adk web [AGENTS_DIR]` and `adk run AGENT` forms match the README. Agent folder `backend/src/novamart_agent` has `__init__.py` and `agent.py` (`root_agent`).
- Page count method: no renderer used. Budget test `test_production_note_fits_one_page_budget`: at most 700 words and 60 lines (about one page at 10 pt, 0.75 in margins). Actual: 671 words including markup, 37 lines. A print-to-PDF check by the owner is still advisable.
- 9.2 sources (all read 2026-11-24):
  - Prices, aistudio.google.com/docs/pricing: gemini-3.6-flash $0.75 in / $3.75 out incl. thinking, promotional through 2026-12-31, then $1.50 / $7.50; gemini-3.5-flash-lite $0.30 / $2.50; gemini-embedding-001 $0.15 in. All equal `DEFAULT_PRICES` in `config.py:60`; no change needed. Test `test_production_note_prices_match_config` pins this.
  - Custom A2A registration (console or REST, you host it, Preview label), and user OAuth access or ID token sent in `Authorization`, forwarded by Cloud Run: docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-a2a-agent.
  - ACL set at data store creation (`aclEnabled`), "a one-time procedure": docs.cloud.google.com/gemini/enterprise/docs/identity. The page does NOT state it cannot be changed later, so design D9's "cannot be changed afterwards" is marked TBC in the note.
  - CMEK needs US or EU multi-region, not global; applied keys cannot be changed (versions rotate): docs.cloud.google.com/gemini/enterprise/docs/cmek.
  - Data use: unpaid AI Studio content used to improve products, human review possible; paid not: aistudio.google.com/docs/terms and the pricing page.
  - Marked TBC in the note: Gemini Enterprise seat pricing, residency for NovaMart's country, Gemini Enterprise's own data-use terms, passing the user token to code on Agent Runtime, whether the order API can validate the forwarded token, IAP as fallback, ACL changeability.
- 9.4: no scanner installed (gitleaks, trufflehog, detect-secrets absent). Regex scan (Google key prefix, PEM private key, AWS, GitHub, OpenAI-style, Slack, and `KEY/SECRET/TOKEN/PASSWORD = 16+ chars`): `git grep --untracked` on the work tree, `git grep --cached` on the index, and `git log --all -p` across 3 commits: 0 matches each. A positive control string matched, so the pattern works. `backend/.env` is untracked (`git ls-files` returns 0) and ignored (`.gitignore:1`). I did not open, print or search the contents of `backend/.env`. The scan covers only non-ignored files and history, so a key placed in an ignored file is not covered by design.

## Standards self-check
```
- STRUCT: layers, public interfaces, entry points only compose ..... n/a (docs and tests only)
- SIZE: within architecture limits, responsibilities separated ..... yes
- TYPE/ERR: boundary parsing, strict types, closed outcomes, refusals
  in code, no secrets or PII in logs (audit and cost too) ........... yes
- AGENT: ........................................................... n/a
- CONV: sources for config/text/design, reuse, dependency note ..... yes (no new dependency; prices read from config in the test)
- TEST: each scenario has a named test; lint+types+tests green ..... yes
- EVAL: scenarios have eval cases; authored, not run, or rates ..... n/a (no model call made)
- EVOL: no unapproved pattern; disagreements reported .............. yes
- Exceptions: none
```

## Open items
- design.md D9 says ACL "cannot be changed afterwards (VERIFY)"; the current docs only say "one-time procedure". Suggest the architect or PM keep it as VERIFY.
- Per-question cost at 1,000 questions needs the owner-run evals (task 10.1); the note states the formula, not a figure.
- `gemini-3.6-flash` pricing is promotional until 2026-12-31 (1.50 / 7.50 from 2027-01-01). `config.py` and `.env.example` comments already say so; update `DEFAULT_PRICES` on that date (owner decision).
- 9.1 says "verify a fresh clone follows it to a working session": the key-free parts (paths, persona table, env names, `adk` forms) are tested; a live session needs the key and is owner-run (10.1).
- Owner should print `docs/production_note.md` to PDF once to confirm one page (word and line budget only checked).
- `adk web` serves unauthenticated endpoints (its own help says so); the README states trusted-machine use.
