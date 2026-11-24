# backend-dev report, chunk 1 (novamart-rag-agent), tasks 1.1, 1.2, 1.3, 1.4, 1.6

Verdict: DONE (1.1 and 1.6 done; 1.2, 1.3, 1.4 authored, not run; 1.6 provisional until 1.3 is owner-run). No model call was made and no API key was read or requested.

## Tasks
- 1.1 done. Skeleton per D8: `agents/ prompts/ pipeline/` added; `security/ tools/ adapters/ rag/` existed; each `__init__.py` declares `__all__` (ARCH-MOD-2); `backend/tests`, `backend/evals`, `backend/data/docs` present. `.env.example` moved by `git mv` to `backend/.env.example` with `GOOGLE_API_KEY`, `GOOGLE_GENAI_USE_ENTERPRISE=FALSE`, `GOOGLE_GENAI_USE_VERTEXAI=FALSE`. `.env` ignored. Files: `backend/.env.example`, `backend/src/novamart_agent/{agents,prompts,pipeline}/__init__.py`, `backend/tests/test_skeleton.py`.
- 1.2 authored, not run. `backend/src/novamart_agent/config.py` now holds chat model (provisional default `gemini-3.6-flash`), embedding model (`gemini-embedding-001`), `show_cost`, and a price table (`DEFAULT_PRICES`, env-overridable via `NOVAMART_PRICE_TABLE`), all marked VERIFY. Live script: `backend/evals/verify_models.py` (one generate call, one embedding call). Doc-read findings in design.md "Task 1.2 findings". Rate limits: not published per model on the docs page; owner-run item.
- 1.3 authored, not run. `backend/evals/check_adk_assumptions.py` header lists the `adk run backend/src/novamart_agent` and `adk eval --help` commands. `adk eval --help` ran (no model call) and works. adk.dev not fetched directly; ADK facts come from the installed 2.15.0 source.
- 1.4 authored, not run. Probe script `backend/evals/check_adk_assumptions.py`; source-read results recorded in design.md ("Task 1.4 findings"), each marked source-read / doc / owner-run needed.
- 1.6 done, provisional. `google-adk==2.15.0` (installed version) and `google-adk[eval]==2.15.0` in `dev`; `pip install -e backend[dev]` succeeds; `adk eval --help` runs. Pin stays provisional until 1.3 is owner-run.

Dependency: google-adk[eval] (dev extra only). Reason: `adk eval` needs it (D7). Size: pulls pandas, rouge_score, google-cloud-aiplatform and others, dev-only. Alternative: custom eval runner only, rejected because ARCH-TEST-3 requires `adk eval`. `python-dotenv` is imported by the owner-run scripts but comes in transitively via google-adk.

## Evidence
- `ruff check backend` -> All checks passed!
- `mypy --config-file backend/pyproject.toml backend/src` -> Success: no issues found in 10 source files
- `pytest backend/tests` -> 11 passed
- `pip install -e backend[dev]` -> Successfully installed novamart-agent-0.1.0 (exit 0)
- `adk eval --help` -> usage printed, exit 0
- `adk web backend/src --port 8765` then `GET /list-apps` -> `["novamart_agent"]` (no key, no model call; server stopped)
- `git check-ignore -v backend/.env` -> `.gitignore:1:.env`
- Source facts, `backend/.venv/Lib/site-packages/google/adk`: `agents/loop_agent.py:60-66,121` (LoopAgent deprecated; exits on escalate); `agents/llm_agent.py:468-474` (output_schema works with tools); `flows/llm_flows/tools/_caller.py:~535,~630,~712` (same args dict reaches callback and tool); `events/event.py:303-325` and `flows/llm_flows/base_llm_flow.py:~300` (skip_summarization ends the turn); `cli/utils/envs.py:53-90` (shell vars win over `.env`).
- Pricing/model IDs read from `aistudio.google.com/docs/pricing` through a summarising fetch on 2026-11-23; unverified, hence VERIFY.

## Standards self-check
```
Standards self-check
- STRUCT: layers, public interfaces, entry points only compose ..... yes
- SIZE: within architecture limits, responsibilities separated ..... yes
- TYPE/ERR: boundary parsing, strict types, closed outcomes, refusals
  in code, no secrets or PII in logs (audit and cost too) ........... yes
- AGENT: tools only on retrieval/order, code routing, sources/band/
  diagrams/cost by code, model output treated as data .............. n/a
- CONV: sources for config/text/design, reuse, dependency note ..... yes
- TEST: each scenario has a named test; lint+types+tests green ..... yes
- EVAL: scenarios have eval cases; authored, not run, or rates ..... yes (probe scripts authored, not run; no scenario evals in this chunk)
- EVOL: no unapproved pattern; disagreements reported .............. yes
- Exceptions: none
```

## Open items
1. Owner decision: ADK 2.15.0 marks `LoopAgent` deprecated in favour of `Workflow`. D1/D11/architecture use `LoopAgent`. Recommend accepting it on the pinned version for the prototype.
2. Deviation recorded: `output_schema` and tools can coexist in ADK 2.15.0 (D1 assumed not). No design change: ARCH-MOD-5 forbids tools on intake/validator by rule.
3. Shell variables override `.env` in ADK: an ambient `GOOGLE_GENAI_USE_ENTERPRISE=TRUE` is not cancelled by `.env.example`. README (chunk 9) must say so.
4. Owner-run needed (key + go-ahead): `python backend/evals/verify_models.py`, `python backend/evals/check_adk_assumptions.py`, `adk run backend/src/novamart_agent`; then confirm/replace default model, free-tier rate limits, usage fields, embedding token counts, and re-verify prices. `gemini-3.6-flash` price changes on 2027-01-01 (0.75/3.75 to 1.50/7.50).
5. The probe script was only syntax-checked, never executed, so it may need small fixes on first owner run.
6. Task 1.5 (architect) untouched. Task checkboxes not ticked. `docs/architecture.md` says sub-package `config` is a module, consistent with `config.py`.
7. Files changed outside the pure write-scope list: `backend/evals/*.py` (eval scripts), design.md Open Questions (as instructed), this report. Worktree also holds pre-existing uncommitted changes from before this chunk; nothing was committed.
