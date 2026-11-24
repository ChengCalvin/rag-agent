# QA report: novamart-rag-agent, chunk 9 (tasks 9.1 to 9.4)

Date: 2026-11-24. Local, `backend/.venv`, no key, no model call. `backend/.env` never opened or printed. `adk run/web/eval`, `run_evals.py` and `probe_*.py` not run.

Verdict: PASS. No Blocker or Major finding. Two Minor observations.

| Check | Command / source | Result |
|---|---|---|
| Lint | `ruff check backend` | All checks passed |
| Typecheck | `mypy --config-file backend/pyproject.toml backend/src` | Success, 72 files |
| Tests | `pytest backend/tests -q` | 762 passed (incl. `test_docs_chunk9.py`, 12 doc tests) |
| Install | `pip install -e backend` | Success |
| README links/paths | `README.md` vs tree | `docs/production_note.md`, `backend/data/README.md`, `backend/.env.example`, `backend/evals/{build_evalsets,run_evals}.py`, `backend/evals/cases/`, layout dirs all exist; `adk.exe` in venv |
| Persona table | README vs `backend/data/users.json` | 4 personas, roles/stores/region match; scope claims match `backend/data/README.md:36-51` (regional manager north = stores 7, 12; NM-480201 is store 12) |
| Env vars | README vs `.env.example`, `config.py:268-286` | GOOGLE_API_KEY, both USE_* flags, NOVAMART_MODEL/EMBEDDING_MODEL/PRICE_TABLE/SHOW_COST/USER/SIMILARITY_THRESHOLD all exist; `.env` walk-up and "shell wins" match ADK `cli/utils/envs.py:53-78` and design D6 |
| Eval flags | README vs `run_evals.py:52-54` | `--set quality|security`, `--only`, `--skip-adk` exist; `build_evalsets.py` ran key-free, exit clean |
| Required statements | README | synthetic data (heading + reasons), "Persona is not authentication" (bold, no password/token), cost lower bound ("lower bound when errors occur"), `adk web` traces shown in full: all present. Bulk-order gap exists in `backend/data/README.md:28` and quality case `question-the-documents-are-silent-on-bulk-orders` |
| Cost line | README vs `pipeline/cost_line.py:3,11` | example shape and "cost unavailable" match |
| Production note | `docs/production_note.md` | four labelled sections (1-4); recommendation (hybrid) + fallback + revisit condition; identity spike with owners, exit test, fallback; limits table with combined order-and-policy row; claims carry [1]-[5] or TBC (seat pricing, residency, Gemini Enterprise terms, IAP, token pass-through); 671 words, under test budget of ~700 |
| Prices | note vs `config.py:60-64` | 3.6-flash 0.75/3.75 (promo, 1.50/7.50 from 2027-01-01), 3.5-flash-lite 0.30/2.50, embedding-001 0.15: match |
| Secrets, tracked tree | `git grep -nIE` AIza, sk-, ghp_, AKIA, private key, `GOOGLE_API_KEY=<value>`, quoted key/secret/token/password literals | 0 hits |
| Secrets, history | `git log --all -p -G<same>`, filtered to +/- lines | 0 hits; no `.env`, `.pem`, `.key` ever committed (`git log --all --name-only`) |
| `.env` hygiene | `git check-ignore -v backend/.env`; `git ls-files` | ignored by `.gitignore:1`; only `backend/.env.example` tracked (value empty); untracked-unignored files contain no secret patterns |

## Findings

| ID | Severity | Finding | Owner |
|---|---|---|---|
| F1 | Minor | "Renders to one page" (task 9.3) is proven only by a word-count heuristic (671 words incl. markup, budget ~700 in `test_docs_chunk9.py:18`), not by a real render. Margin is thin; a table-heavy render could spill. Owner should print once to confirm. | backend-dev |
| F2 | Minor | README "a fresh clone follows it to a working session" (task 9.1) cannot be proven key-free: the first model call, `adk web` session and embedding build need the owner's key. Static checks above pass; live check stays owner-gated. | owner |

## Open items

- Product claims in the note were not re-fetched by QA (no model/web scope here); they are sourced to Google pages read 2026-11-24 or marked TBC, which is what the spec requires. The gemini-3.6-flash promo price expires within about five weeks; re-check before use.
- `build_evalsets.py` was run to prove it is key-free; `backend/evals/` is wholly untracked so no diff is available, outputs are deterministic regenerations.
- Task ticks are orchestrator-owned; none changed by QA.

---

# QA report: novamart-rag-agent, chunk 8 (tasks 8.1 to 8.3; 8.4 authored not run, 8.5/8.6 not started)

Date: 2026-11-24. Local, `backend/.venv`, no network, no key, no model call. `backend/.env` not read. `adk eval/run/web`, `run_evals.py` and `probe_*.py` not run.

Verdict: PASS. No Blocker or Major finding. Two Minor spec-proof gaps (PM items 1, 2) and one Minor tooling finding (mypy cache). 8.4 stays unchecked in tasks.md (line 107), as required.

## Evidence

| Check | Command / source | Result |
|---|---|---|
| Lint | `backend/.venv/Scripts/ruff check backend` | All checks passed |
| Typecheck, clean cache | `mypy --config-file backend/pyproject.toml backend/src --cache-dir=<empty dir>` (run twice) | Success, 72 files |
| Typecheck, repo cache | same without `--cache-dir` | first run INTERNAL ERROR (mypy 2.4.1), then 3 reruns: `rag/index.py:28 no-any-return` (see F1) |
| Tests | `pytest backend/tests -q` | 746 passed in 21s |
| Build | `pip install -e backend -q` | exit 0 |
| Traceability | script over `specs/*/spec.md` vs `traceability.json` | 61 scenarios in specs, 61 mapped, 0 unmapped, 0 extra; every `cases` id exists in quality/security; every entry has `cases` or `covered_by`; `test_evals_traceability.py` passes |
| Quality set | `quality.json` | 18 cases (15-18 ok); types policy 3, product 3, order 5, refusal 5, combined 2 (all >= 2); `refusal_outcome` A..E once each (A out-of-order-number, B out-of-domain, C bulk-orders, D unknown-order, E partially-covered) |
| Security set | `security.json` | 12 cases, each with a "Pass only if..." condition (or explicit positive control for `manager-asks-the-same-question`) and 2-5 machine checks; none empty |
| No-key exit | `evals/run_evals.py:92-95` | `load_dotenv` then `if not GOOGLE_API_KEY: print(...); return 2` before `load_settings()`, `Runtime`, `run_all` or `run_adk`. Not executed: it loads `.env`, which I may not read and which could hold a key. Shell env has no GOOGLE/GEMINI variable. |

## Findings

| ID | Severity | Finding | Owner |
|---|---|---|---|
| F1 | Minor | `backend/.mypy_cache` gives a repeatable `index.py:28` error and one INTERNAL ERROR, while a clean cache passes cleanly twice. Stale or corrupted incremental cache, not a code defect. Delete `backend/.mypy_cache` and rerun; if it recurs, pin mypy or `np.divide` typing. | backend-dev |
| F2 | Minor | PM item 1 is REAL. Spec policy-retrieval:82 requires "no numeric confidence score"; case `answerable-policy-question-electronics-window` only matches `Confidence: (High\|Medium\|Low)`. Add a `reply_not_matches` for a number near "Confidence". | backend-dev |
| F3 | Minor | PM item 2 is REAL. order-tools:59 says eligibility needs no policy search and no band; `within-the-return-window-eligible` (and `category-exception-electronics-outside-window`) check neither `tool_not_called search_policy` nor `band_is none`. Only the order-status case does. | backend-dev |

## PM open items 1, 2, 3, 5

- Item 1: real gap (F2).
- Item 2: real gap (F3).
- Item 3: not a behaviour gap. The cap rule has key-free unit tests (`test_pipeline_confidence.py::test_required_criterion_cap_holds_the_band_at_low_whatever_the_sum`, `...::test_a_higher_composite_under_the_required_cap_...`). Only the traceability entry for "Uncovered required criterion caps the band" lists just the live case; add a `covered_by` line. Bookkeeping, no finding.
- Item 5: accept. `question-the-documents-are-silent-on-bulk-orders` asserts `agent_not_called` twice (validator and composer); the rewrite is produced by the validator, so a rewrite cannot occur without it. Indirect but sufficient.

## Open items

- 8.4 live run, 8.5, 8.6 are not done; no pass rates exist. Cases that may fail live: E, both combined cases, malformed turn of `denial-indistinguishable-from-not-found`, `poisoned-document`.
- PM items 7-9 (per-persona evalsets, `tool_trajectory_avg_score` with `ignore_args`, `Workflow` root under `adk eval`) are owner-run VERIFYs at the first live run.
- The no-key exit has no unit test (only static reading); consider one that monkeypatches `load_dotenv` and clears the key.

---

# QA report: novamart-rag-agent, chunk 7 Pipeline agents and orchestrator (tasks 7.1 to 7.6)

Date: 2026-11-24. Environment: local, `backend/.venv`, Windows. No network, no key, no model call; `backend/.env` not read. Real `Workflow` graph, callbacks, tools, guard and synthetic data under ADK's own runner, with scripted models (`stub_llm`) and a fake embedder. The owner-gated `adk run` checks of 7.2 to 7.6 were NOT run (no key, quota exhausted).

Verdict: PASS (key-free scope). No Blocker or Major finding. One Minor and three Info items. The `adk run` verifications remain open for the owner.

## Evidence

1. `ruff check backend` -> All checks passed. `mypy --config-file backend/pyproject.toml backend/src backend/tests/test_qa_chunk7.py` -> no issues (73 files). `pytest backend/tests` -> 662 passed, 0 failed (618 dev tests plus 44 of mine in `backend/tests/test_qa_chunk7.py`).
2. Denial parity (own test: 2 tools x cost flag on/off x 11 causes: nonexistent, out of scope, 9 malformed ids incl. fullwidth digits, trailing newline, path traversal, 400 digits, empty): identical reply text (`NOT_FOUND_REPLY` plus the cost line), identical whole-turn calls (intake 1 + order 1, nothing else), identical usage records and session total. Also identical when the model makes no tool call at all, and when one step mixes an ok status with a denied eligibility check (denial wins). The reply contains no order id, store or `@`.
3. No model call after a tool result: order (denied and ok) and retrieval (`ok` and `no_answer`) scripts with a spare model step never consume it. A retrieval agent that answers in text without a tool call ends in the generic failure with no validator or composer call. A retrieval agent that asks for `get_order_status` gets an ADK tool-not-found error and no order data.
4. Combined after-tool callback: usage order on a miss is chat(intake), chat(retrieval), embedding, chat(validator), chat(composer); `no_answer` on a miss records exactly one embedding; the same query again (cache hit) adds none; a failed search records none.
5. Loop: default bound 2 passes with a validator that always asks for a rewrite (third scripted step unused, composer called once, band Low); the bound follows `max_iterations` (1 and 3 tested); a high-confidence first pass exits at 1; extra `escalate`/`route` fields in a verdict have no effect; the second pass query is the validator rewrite, not the model's argument; the composer input holds the first (best) pass, not the worse second.
6. Routes: for each of `precheck`, `route_turn`, `after_order`, `after_retrieval`, `loop_decide`, the routed edge set equals the enum values exactly (none missing, none dangling); no sub-agents; only retrieval (1 tool) and order (2 tools) hold tools.
7. Code-built footers: composer text forging `Sources:`, `Confidence: High`, `Cost:` and a `Confidence - High` line yields exactly one code-built Sources, one band, one cost line. Invented diagrams (backtick and tilde fences) are stripped; prose kept.
8. Identity: an intake record with a `principal` field, tool args with `user_id`/`role`/`principal`, and a role-claim message leave the principal as the configured persona; the out-of-scope order is still denied uniformly.
9. Cost: for outcomes A, B, C, D, E (Low band) and an ordinary answer the line is present with the flag on and absent with it off, the body is otherwise identical, and the session total is recorded either way. Not-determinable (broken returns-policy metadata): canned text plus contact, no call after the tool, line on/off. Thinking tokens: each call 100 in / 20 candidate / 30 thought gives 50 out; the line shows `200 in / 100 out tokens` for two calls; price check `~$0.0002 this answer (1 call, 100 in / 50 out tokens)`, session `~$0.0004 over 2 questions`, "not billed" label on the first reply only. Precheck decline: 0 calls, `$0.00`.
10. State hygiene: a denied turn followed by a different-tool success turn is not poisoned (stored order results cleared per turn).
11. Task 7.1: grep of `prompts/` finds no day counts, categories, product or contact strings (ARCH-CFG-2); data-not-instruction, role-claim and disclosure wording is present in the instructions.
12. Mutation checks on a temp copy of `src`, `tests`, `data` (16 mutants; product code never edited in place), all killed by the full suite: retrieval halt removed, order halt removed, embedding recorded only on `ok`, cache hit still billed, loop bound ignored, composer gets last attempt, compose edge removed, thinking tokens dropped, diagram check disabled, no-result order not uniform, denial loses to ok mix, cost line dropped on denial, session total not updated when hidden, query hint not applied, order usage not captured, order results not cleared per turn. Two (denial vs ok mix, stale order results) survived the dev tests and my first draft; I added tests and re-ran: both killed. "Diagram check disabled" is not killed by my tests alone because `finish_reply` sanitises again (defence in depth); the dev suite kills it.

## DEVIATION check (after-tool callbacks halt on every tool status)

Safe. Halting on `ok` is what lets the retrieval agent write no text (the next node reads state) and hands the stored records to the composer on the order route; no model text from those agents can reach the user. No spec scenario requires a model call after an `ok` result; call counts only drop, and the cost line counts every call actually made (the rewrite scenario holds, tested). Unknown or error statuses fall to the generic failure reply. The one behavioural consequence is QA7-1.

## Findings

- QA7-1 (Minor): because the order agent halts on `ok`, a model that chains `get_order_status` and `check_return_eligibility` in two separate steps never reaches the second; the reply is composed from the first result and silently omits the return answer and its Sources. Reproduced by `test_deviation_sequential_order_tool_calls_stop_after_the_first_ok_result` (records current behaviour). The prompt tells the model to call both in one step, and parallel calls are handled (dev test). Not a spec violation. Owner-run `adk run` on a status-plus-return question should confirm Gemini calls them in parallel. Owner agent: backend-dev, optional.
- QA7-2 (Info): stored order results are keyed by tool name, so two lookups with the same tool in one step keep only the last. No denial leak (uniform text on any denial), but a mixed batch is judged by one result.
- QA7-3 (Info): a retrieval agent asking for a tool it does not hold costs one extra model call (ADK feeds the error back); no data leaks.
- QA7-4 (Info): live `adk run` behaviour, real `thoughts_token_count` billing and Gemini's parallel versus sequential function calling cannot be proven key-free.

## Open items

1. Owner-run `adk run` for 7.2 (policy, product, order, under-specified, out-of-scope), 7.3 (one rewrite, exhaustion), 7.4 (combined order-and-policy, unanswerable, product diagram), 7.5 re-run, 7.6 (cost line flag on/off, session total growth).
2. Decide whether QA7-1 needs a code change or only the live check.
3. No Notion tickets: this repo does not use Notion (CLAUDE.md). Write scope respected: only `backend/tests/test_qa_chunk7.py` and `docs/qa-report.md` changed.

## Standards self-check (tests I added)

Typed; ruff and mypy green; one `noqa: PLR0913` on a test helper and `type: ignore[arg-type]` where scripted steps are passed as `object`; each test names the behaviour it covers; no model call, no network, no secrets; mutation scripts live outside the repo.

---

# QA report: novamart-rag-agent, chunk 6 Pipeline logic (tasks 6.1 to 6.5), re-run

Date: 2026-11-24. Environment: local, `backend/.venv`, Windows. No network, no key, no model call; `backend/.env` not read. Re-run of the failed gate after backend-dev fixed QA6-1, QA6-2 and QA6-3.

Verdict: PASS. No Blocker or Major finding open. QA6-1 (Major), QA6-2 and QA6-3 (Minor) are verified fixed. Two new Info items.

## Evidence

1. `backend/.venv/Scripts/python -m ruff check backend` -> All checks passed. `-m mypy --config-file backend/pyproject.toml backend/src` -> Success: no issues found in 45 source files. `-m pytest backend/tests` -> 522 passed, 0 failed, 0 xfailed (no strict xfail markers remain; `test_pipeline_qa_chunk6.py` now has 3 plain passing regression tests for the fixed defects).
2. QA6-1 (tilde fence), own script through `sanitize_model_text` with a verified backtick diagram in the chunks. Invented diagram `X-->Y` is stripped in every form: `~~~`, `~~~~`, `~~~~~`, three-space indented `~~~`, backtick opener closed by tilde, tilde opener closed by backtick, unclosed tilde, CRLF tilde, a longer tilde opener with a shorter closer, and a tilde block wrapped in a backtick fence. A verified diagram is still kept verbatim in backtick form, in tilde form with a tilde chunk, and as a tilde reply block for a backtick chunk body. Surrounding prose ("Intro", "End") survives.
3. QA6-2 (footer variants): stripped: `Confidence - High`, en and em dash variants, `**Confidence** - High`, `> Confidence - High`, fullwidth `Sources:` and `Sources：`, zero-width inside or after `Sources`, bare `Sources`, `Confidence`, `Source - a.md`, `Cost - $1`. Prose kept: "The cost of shipping is $5", "Sources are listed below", "Confidence is key to trust", "Cost-saving tips", "Source code is private", "References to the policy apply".
4. QA6-3 (empty permitted corpus): driven through real `search_policy`, real index and a counting fake embedder (employee, manager-only docs): 1 real embedding call, `embedding_billed(result)` is now True (the tool exposes an explicit `embedded` field; billing no longer infers from `closest_titles`). The earlier matrix (blank, over-long, no principal, ok miss/hit, no_answer miss/hit) still bills exactly when a real call was made; an outage is not billed by design.
5. Regression pass over 6.1 to 6.5: the dev suite plus my earlier chunk 6 tests (config validation, precheck and routing, rubric fallback, composite/bands/loop/best attempt, assembly footers and sources, cost and session totals, denial parity) all pass in the 522. 
6. Mutation checks on a temp copy of `src`, `tests`, `data` (product code never edited in place), run against the full suite: tilde removed from the opener -> killed; `embedded` billing narrowed to `status == "ok"` -> killed; footer needs a colon -> killed; footer folding (NFKC, zero-width) removed -> killed; `search_policy` always reports `embedded: False` -> killed. A sixth mutation (closer ignores marker type) did not apply cleanly and was not run; mixed-marker behaviour was checked directly in item 2. My earlier mutation set (downgrade-only, required cap, best-attempt rules, loop exit, fence check, unpriced to 0, precheck rules, clarification cap) is covered by tests that still pass unchanged, so nothing was weakened.

## Findings

- QA6-1, QA6-2, QA6-3: FIXED and verified (Evidence 2 to 4).
- QA6-10 (Info): `Confidence High` and `Cost $0.5` (keyword followed by no colon, dash or end of line) are not stripped. They are prose-shaped; the code-built band and cost line are still the only authoritative ones. No action required.
- QA6-11 (Info): a prose line such as "Cost - effective returns are cheap" (keyword, spaced dash) is stripped as a footer. Rare false positive that only drops one line of model prose.
- QA6-4 to QA6-9 from the first run (Info) stand: the denial-parity dev test is a tautology (my own parity test covers it); thinking tokens have no testable boundary until chunk 7; D17 wording `$0.00 this answer (0 calls)`; inline backtick opener de-fences; precheck ignores zero-width characters; unusable intake falls back to `knowledge`.

## Open items

1. The chunk 7 gate must cover orchestrator-level denial parity (same call count and reply text for nonexistent, out-of-scope and malformed order ids) and thinking tokens summed into output.
2. No Notion tickets: this repo does not use Notion (CLAUDE.md). Write scope respected: only `docs/qa-report.md` changed this run.

---

# QA report: novamart-rag-agent, chunk 5 Order tools (tasks 5.1, 5.2)

Date: 2026-11-24. Environment: local, `backend/.venv`, Windows. No network, no key, no model call; the test fakes (`backend/tests/fakes.py`) and the real guard, adapter, rule and synthetic data. Verified against the task text and the order-tools and access-control scenarios, independently of the dev tests.

Verdict: PASS. No Blocker or Major finding. Two test gaps (rule survivors) found and closed with new tests; no product defect.

## Evidence

1. Independent script (scratchpad `qa5.py`, 247 checks, `SUMMARY fails: []`), calling the tools made by `make_get_order_status` / `make_check_return_eligibility`:
   - Permitted: own-store employee, manager, regional manager in region (both tools) return status ok.
   - Denied, all returning the identical full dict `{"status": "not_found"}` with no extra key: cross-store employee/manager, cross-region regional manager, unknown role, empty role, wrong-case role, no principal, empty session state, employee with no store, regional manager with no region, unknown order, and 18 malformed ids (trailing newline, spaces, lowercase prefix, fullwidth and Arabic-Indic digits, too short/long, NUL, empty, None, int, list, dict, bytes, lone surrogate alone and inside an id).
   - Throttle: after 5 denials a permitted lookup gives the same dict for both tools; interleaved allowed lookups do not reset it.
   - Before-tool callback path: unknown role and no principal return the same dict for both tools; the three known roles pass (None).
   - Schema (`FunctionTool._get_declaration`): both tools expose only `order_id` (required, string); no `tool_context` or identity field.
   - PII: all 10 seeded orders x 6 personas x 2 tools, plus 44k characters of captured log output (all loggers at level 1): none of the 10 names, name parts, emails, local parts or addresses appears; no `@` in any output.
2. `check_return_eligibility`, reference date 2026-11-23: NM-480101 eligible (within_window); NM-480102 not eligible (category_exception); NM-480202 outside_window; NM-480301 excluded_category; NM-480103 not_delivered; NM-480104 already_returned. Result carries `policy_document_id=returns-policy` and `parameters_used` (window 30, electronics 14, excluded, conditions).
3. Boundaries: electronics day 14 eligible, day 15 category_exception, day 30 category_exception, day 31 outside_window; general window day 30 eligible, day 31 outside_window; delivery day 0 eligible; reference date before delivery gives not_determinable.
4. Policy from a temp copy of the returns doc: window 7/exception 3 flips NM-480201; window 90 makes NM-480202 eligible; exception 25 makes NM-480102 eligible (not hard-coded). 13 broken variants (missing, string, negative, zero, float, bool window; negative and string exception; missing/scalar excluded list; missing exceptions; missing conditions; exception without category), a missing returns doc and an empty document set all return `{"status": "not_determinable"}` for NM-480101/102/301. With the same broken policies, a denied order and an unknown order still return `not_found` (no oracle).
5. `ruff check backend` -> All checks passed. `mypy --config-file backend/pyproject.toml backend/src` -> Success: no issues found in 30 source files. `pytest backend/tests` -> 303 passed (was 296 before my additions).
6. Mutation checks (each on a temp COPY of `src`, `tests`, `data`; scratchpad `qa5_mut.py`; baseline clean for both). "Dev suite" = existing tests incl. my additions below; "Before" notes where only the original dev tests were run.

| Mutation | Dev suite | My script |
|---|---|---|
| remove guard call (fetch directly) | killed | killed |
| guard returns order on denial (`guard.py`) | killed | survived (script does not inspect the guard's internal) |
| `guarded_order` ignores the decision | survived: equivalent mutant (guard already nulls the order on denial; the guard-level mutant above is killed). Defence in depth, not a gap | survived |
| off-by-one window (`<` for `<=`) | killed | killed |
| off-by-one general window in the exception branch | SURVIVED the original dev tests; killed by new test | killed |
| ignore category exception | killed | killed |
| hard-code window 30 | killed | killed |
| hard-code electronics 14 | SURVIVED the original dev tests; killed by new test | killed |
| email / address in order view | killed | killed |
| customer name in eligibility result | killed | killed |
| missing parameter defaults to 30 | killed | killed |
| negative window accepted | killed | killed |
| policy loaded before the guard (oracle) | killed | killed |
| undeterminable mapped to `error` | killed | killed |
| drop `parameters_used` / `policy_document_id` | killed | killed |
| extra key on the denial dict | killed | killed |
| exception text logged on failure | killed | survived (script never forces a failure; dev test covers it) |
| excluded categories ignored | killed | killed |

7. Added `backend/tests/test_tools_eligibility_boundaries.py` (7 cases): exception window read from the policy (3, 25 and 1 days) and reason code at each electronics window edge (14, 15, 30, 31). Fails against the two survivors above, passes on real code.

## Findings

- Info: the two survivors were test gaps only (reason code at the general-window edge for exception categories; exception window never varied). Closed.
- Info: the guard's order nulling and the tool-level `allowed` check are redundant by design; only a double mutation would leak, and no test needs to cover it.
- Info: `get_order_status` and `check_return_eligibility` are not yet wired onto an agent (chunk 7); the before-tool path was exercised with the real callback and a stand-in tool object, not a live ADK run.

## Open items

- Re-verify through a real ADK `Runner` (identity callback, before-tool callback, tool call) once chunk 7 wires the agents; the escalation contact and canned wording for `not_determinable` are also consumed there.
- The reference date is injected (`date.today` by default); chunk 7/eval should pin it so the seeded cases (dated for 2026-11-23) stay stable.

---

# QA report: novamart-rag-agent, chunk 4 Retrieval (tasks 4.1, 4.2, 4.3)

Date: 2026-11-24. Environment: local, `backend/.venv`, Windows. No model or embedding call (fake embedder in `backend/tests/fakes.py`); `backend/.env` not read. Verified against the literal task text and verify clauses, independently of the dev's tests.

Verdict: PASS. No Blocker or Major finding. One real test gap found (top-k taken before the audience filter was not caught by any test); closed with a new test.

## Evidence

1. Independent script (scratchpad `qa4_check.py`, real chunker/index/search/tool over `backend/data/docs`, 5 personas x 8 queries): all checks PASS, `SUMMARY fails: []`. Covered: manager-only docs (`manager-approvals`, `product-novabook-launch-briefing`) never appear (text, ids, titles, no_answer titles) for employee, unknown role (`contractor`), or no principal; both manager and regional_manager receive them; no_answer titles are 1..3, independent of threshold (threshold 0.99), clean for non-permitted personas and include restricted titles for a manager.
2. Cache: zero embed calls on rebuild; a different embedding model id re-embeds every chunk; 5 corrupted entries (invalid JSON, `[]`, non-numeric list) are misses, re-embedded exactly 5 times, no raise. `embedding_cache_hit` present in every result; False on miss, True on hit, and correct on no_answer (True when cached, False when not); error result also carries it (False).
3. Chunker: all 11 real docs chunk (44 chunks, no empty); the three product docs' fenced diagrams each land whole in exactly one chunk; a synthetic `# not heading` inside a fence is not a heading (headings `A`,`B`).
4. Tool: signature is `(query, tool_context)` only; blank, whitespace, None, int, list, dict, bytes, 200k-char, control/RTL/emoji and 5000-line queries never raise; an embedding outage returns `status: error` with `embedding_cache_hit: False`.
5. Escalation contact: read from `escalation_contact` front-matter of `store-operations`; a mutated copy in a temp dir returned the mutated text; blank, missing, non-string, null field and absent document all raise `EscalationContactError`.
6. Mutation checks (each on a temp COPY of `src`, scratchpad `qa4_mut.py`; baseline clean):

| Mutation | Result |
|---|---|
| drop audience filter | killed |
| audience filtered after ranking, top-k applied first (search.py) | SURVIVED the existing suite and my script; killed by the new test below |
| audience filtered only on output of `rank` (index.py) | equivalent mutant (cosine scores are independent per chunk), not a gap |
| ignore threshold | killed |
| cache key ignores model id | killed |
| closest titles unfiltered | killed |
| contact hard-coded | killed |
| `#` in fence treated as heading | killed |
| `embedding_cache_hit` always False | killed |
| corrupt cache entry raises | killed |

7. Added `backend/tests/test_rag_audience_order.py` (new file): a manager-only chunk that outscores a permitted one with `top_k=1` must not displace it for an employee. Fails against the top-k-before-filter mutant, passes on real code.
8. `ruff check backend` -> All checks passed. `mypy --config-file backend/pyproject.toml backend/src` -> Success: no issues found in 26 source files. `pytest backend/tests` -> 230 passed.

## Findings

- Minor: no maximum query length. A very long query is parsed and sent to the embedding API; a real over-limit failure maps to `status: error` (no raise), but it can cost a billed call. Not required by any spec scenario; consider a cap in a later chunk.
- Minor (observation): blank/non-string query and no-principal return `no_answer` with empty `closest_titles`, so case C for those has no titles to cite. Acceptable (nothing permitted to name) but chunk 5/7 must handle an empty list.
- Info: the "closest titles" lookup and `escalation_contact` exist and are tested, but nothing assembles case C yet, so "used by the code that assembles case C and order-eligibility cannot-determine replies" is not yet demonstrable end to end.

## Open items

- Wire `escalation_contact(documents)` at startup (load-time fail-fast) and consume it plus `closest_titles` in the case C and order "cannot determine" replies; re-verify when that code lands.
- Real-embedder behaviour (score scale vs the configured threshold, oversized input) is untested here by design; belongs to the eval chunk.

---

# QA report: novamart-rag-agent, chunk 3 re-audit of the rebuilt `test_security_guard.py` (tasks 3.2, 3.4)

Date: 2026-11-24. Environment: local, `backend/.venv`, Windows. No model call; `backend/.env` not read. Context: the file was emptied and rebuilt from memory, so it was judged against the access-control and order-tools spec scenarios and the 3.2/3.4 verify clauses, not against the old file.

Verdict: PASS. No Blocker or Major finding. The rebuilt file was mostly adequate but had five gaps (below); all are closed with added tests, and every non-equivalent mutant is now killed.

## Evidence

1. Baseline re-run against current code (audit-hash lone-surrogate fix and explicit per-role allowlist included): `qa3.py` -> 71 PASS, `failed: 0 total 71`; `qa3b.py` -> `same state obj True`, reasons `not_found, not_found, throttled`. Identical to the trusted baseline.
2. `ruff check .` -> All checks passed. `mypy --config-file pyproject.toml src` -> Success: no issues in 20 source files. `pytest tests -q` -> 183 passed (126 before my additions; +57 collected cases, all in `backend/tests/test_security_guard.py`).
3. Mutation checks: each mutant applied to a COPY of `guard.py` (or `callbacks.py`) in a temp directory with its own copy of `src`, `tests`, `data` (product code never edited in place; scratchpad `mut.py`). Run against the rebuilt file alone ("Before") and after my additions ("After", shown as the same run on the final file).

| Mutation | Before (rebuilt file) | After (with additions) |
|---|---|---|
| store check removed | killed | killed |
| region check removed | killed | killed |
| regional manager limited to own store (no wider scope) | killed | killed |
| unknown role treated as store-scoped | killed | killed |
| unknown role allowed (blanket) | killed | killed |
| store-less employee/manager allowed | SURVIVED (reason not asserted; denial came from a different path) | killed |
| store-less matches store-less order | SURVIVED | killed |
| region-less regional manager allowed | SURVIVED | killed |
| malformed check skipped | killed | killed |
| `match` instead of `fullmatch` (trailing text) | killed | killed |
| `$` anchor (trailing newline accepted) | killed | killed |
| `\d` (Unicode digits accepted) | killed | killed |
| case-insensitive `nm-` | killed | killed |
| whitespace stripped before match | killed | killed |
| non-string coerced with `str()` before match | SURVIVED (no object whose `str()` is a valid id) | killed |
| fetch called before id validation | killed (only for "NM-12") | killed (for all 25 malformed inputs) |
| throttle never triggers | killed | killed |
| throttle off by one (limit+1 and limit-1) | killed | killed |
| throttle evaluated after fetch | killed | killed |
| in-scope id passes after limit | killed | killed |
| allowed lookup resets the counter | killed | killed (plus interleaved test) |
| counter global instead of per session | killed | killed |
| malformed or not-found lookups not counted | killed | killed |
| `denied_result` differs (extra key) | killed | killed |
| `denied_result` returns a shared mutable dict | killed | killed |
| before-tool callback returns a different dict for one cause | not run before additions | killed |
| order returned on denial | killed | killed |
| no principal allowed | killed | killed |
| `authorize_tool` unknown role gets tools | survives | survives: equivalent mutant (`_check_principal` already denies an unknown role first), not a test gap |

## Per-scenario verdict on the rebuilt file

| Scenario / clause | Real assertion in rebuilt file? | Action |
|---|---|---|
| Cross-store request | Yes (`order is None`, not allowed) | none |
| Regional manager allow, other region denied | Yes, but only on 2 north orders and 1 south order | added full 10-order sweep |
| Unknown role deny | Yes, but one role (`intern`) and one order | added 6 role strings (`""`, `EMPLOYEE`, ` employee`, `admin`, `superadmin`) over 3 orders, with reason |
| Store-less employee/manager, region-less regional | Weak: only `allowed is False`, which a different denial path also produces | added `reason == "no_scope"` assertions |
| Identical denial vs not-found, full-dict equality | Weak: `denied_result() == {...}` only; no comparison across causes, and the callback path was untested for non-surrogate causes | added dict equality across no-principal, unknown-role, disallowed-tool and empty-tool-name causes through the before-tool callback, plus a test that the six guard reasons differ only internally and none returns data |
| Malformed id, no fetch | Weak: no-fetch checked for one id ("NM-12"); the list lacked NUL, leading newline, fullwidth digits, non-breaking hyphen, bytes, dict, bool, str-coercible object | added `HOSTILE_IDS` and a non-string object with a valid `str()`, run through the guard with a spy (reason `malformed_id`, zero fetches, counter +1) |
| Throttle after limit, in-scope id returns nothing, spy shows no fetch | Yes | none |
| Allowed lookups do not reset counter | Weak: one denial then one allow | added deny/allow interleaved up to the limit, then in-scope id returns nothing |
| Per-session counters | Yes but only one direction | added two-session test (second session unaffected, first still throttled), counter increments for out-of-scope, not-found and malformed, and forged counter values in state (-5, True, "7", 2.5, None) |
| Malformed validation lives only in the order tool | Yes: static check of `pipeline`, `agents`, `prompts` (intake and precheck code not yet written beyond stubs, so this is a source scan only) | none |

Constants: `LIMIT=3`, order ids `NM-480101/480201/480301` exist in the seeded `orders.json`, and the sweep tests read the seed data, so the constants are not weaker than the scenarios need.

## Findings

| # | Severity | Finding | Owner |
|---|---|---|---|
| G1 | Minor (closed) | Rebuilt tests did not prove reason `no_scope` for store-less/region-less principals; three mutants survived. Fixed with added tests. | qa |
| G2 | Minor (closed) | Non-string ids and several hostile strings were not exercised through the guard with a fetch spy. Fixed. | qa |
| G3 | Minor (closed) | No full-dict equality test across denial causes at the before-tool boundary. Fixed. | qa |
| F3 (carried) | Info | The real order tools do not exist yet (`tools/` is empty), so the "same dict for every denied `OrderAccess`" check and the signature check remain a chunk 5 item. | backend-dev, chunk 5 |
| F4 | Info | Mutant `authorize_tool` unknown-role allowlist fallback is unreachable (dead branch `ROLE_TOOL_ALLOWLIST.get(..., frozenset())` after `_check_principal`); harmless defence in depth. | none |

No bugs filed (Notion is not used for this repo).

## Open items

1. Chunk 5: map every denied `OrderAccess` (all six causes) to `denied_result()` at the real tool and compare full dicts; re-check that real tools take only `order_id`.
2. Chunk 4/5: when intake and precheck code exists, replace the source scan with a behavioural test that a malformed id is neither rejected nor rerouted.
3. Task 7.5: one run of the shared-state/throttle test against a real ADK `InMemorySessionService` session (state is a `State` object, not a dict), no model call.
4. The `test_security_guard.py` file has no git history; commit it so the next incident is recoverable.

---

# QA report: novamart-rag-agent, chunk 3 "Access control" (tasks 3.1 to 3.5)

Date: 2026-11-24. Environment: local, `backend/.venv`, Windows. No model call; `backend/.env` and keys not read. Verified independently of the dev tests with throwaway scripts (scratchpad `qa3.py`, `qa3b.py`) against the public interfaces `security/guard`, `callbacks`, `audit`, `principal` and `tests/fakes.py`, using the seeded `backend/data/orders.json` and `users.json`. Logging was captured on the root logger at level 1 (below DEBUG), so all loggers were covered.

Verdict: PASS (no Blocker or Major findings; 3 Minor/Info observations). 71 independent checks, 0 failed.

## Per-clause result

| Task / scenario | Check | Result |
|---|---|---|
| 3.1 / Role claimed in chat | The identity callback runs each turn and overwrites the principal: a forged `regional_manager` state replaced by `emp_store12`; a mid-session tamper (role set to regional_manager) is reset on the next turn | PASS |
| 3.1 / Role in tool args | Before-tool call with args `role=regional_manager, user_id=regmgr_north, store_id=store-7` leaves the state principal byte-identical, and a store-12 caller is still denied store-7 | PASS |
| 3.1 / unset or unknown `NOVAMART_USER` | `None` and `nobody` clear the principal; every consumer then denies | PASS |
| 3.1 / Tools take no identity parameters | Dev test inspects stand-in tools and the FunctionTool schema (`order_id` only). Real tools do not exist yet (see Open items) | PASS for the stand-in; real-tool check deferred |
| 3.2 / Cross-store | store-12 employee vs store-7 order: denied, `order is None`, reason `out_of_scope`; store-7 manager vs store-12 order denied | PASS |
| 3.2 / Own store | store-7 employee and manager get the store-7 order | PASS |
| 3.2 / Regional manager | Across all 10 seeded orders: allowed for the 7 `north` orders, denied for the 3 `south` orders (own region only) | PASS |
| 3.2 / Unknown role | `superadmin`, `""`, `EMPLOYEE`, `Employee`, `admin`, ` employee` all denied; no principal denied | PASS |
| 3.2 / Store-less | employee and manager with `store_id=None` denied (`no_scope`); regional manager with no region denied | PASS |
| 3.2 / Malformed id only in the order tool | 19 inputs (trailing/leading space, trailing/leading newline, lowercase `nm-`, `Nm-`, Arabic-Indic digits, fullwidth digits, 5 and 7 digits, no hyphen, NUL, empty, `None`, int, list, dict, SQL-ish text, non-breaking hyphen) all rejected as `malformed_id` with zero calls to the fetch; a valid id does fetch. Intake and precheck code does not exist yet, so "never rejects or reroutes" is a chunk 4/5 check | PASS (guard); see Open items |
| 3.2 / Identical denial vs not-found | `denied_result()` is `{"status": "not_found"}`, a fresh dict each call. The before-tool denial for unknown role, no principal, disallowed tool and empty tool name returns exactly that dict. The guard returns no data for nonexistent, out-of-scope, malformed, unknown-role, no-principal and throttled; the reason differs only in the internal `Decision`, which goes to the audit record only. The tool that turns an `OrderAccess` into the dict is chunk 5, so the end-to-end full-dict comparison cannot be run yet | PASS at the available boundary; see Open items |
| 3.3 / Before-tool allowlist skips the tool | Allowed tools (`get_order_status`, `search_policy`, `check_return_eligibility`) return `None`; `delete_order`, empty name, and any tool for an unknown role or no principal return the denial dict, which ADK uses as the result so the tool body never runs | PASS |
| 3.3 / No PII in logs | 50 caller-by-order combinations over all 10 orders (employee 7, employee 12, regional, unknown role, no principal) through both the before-tool callback and the guard, plus `repr()` of every order and access, plus customer name, email and address passed as the order id: 160 log lines. Searched case-insensitively for every seeded full name, email, address, first name and email local part: 0 matches. Raw order ids also absent; `order_ref` is a 16-hex keyed HMAC, differs per salt, stable per salt | PASS |
| 3.4 / Probing throttled | Limit 3: three out-of-scope lookups, then the fourth and later return `throttled` with no order and no fetch call; an in-scope id after the limit also returns nothing. Allowed lookups in between do not reset the counter. A forged negative counter in state is treated as 0, not as a bypass | PASS |
| 3.5 / Helper reuse | `fakes.py` is imported by `test_security_identity`, `test_security_guard`, `test_security_audit` (3.1 to 3.3). `shared_state_contexts(principal, 3)` gives three contexts over one state dict: same principal for all, and the denied counter is shared (denied, denied, throttled across three "agents"). Independent contexts have independent state | PASS |

## Evidence
1. `backend/.venv/Scripts/ruff.exe check .` (in backend) -> All checks passed.
2. `mypy --config-file pyproject.toml src` (in backend, same config as requested) -> Success: no issues found in 20 source files.
3. `python -m pytest tests -q` -> 118 passed in 0.68s.
4. `python -I qa3.py` -> 71 PASS lines, 0 FAIL ("failed: 0 total 71"); `qa3b.py` multi-agent output: `same state obj True`, reasons `not_found, not_found, throttled`.
5. Code refs: id regex `guard.py:42` (`fullmatch`, ASCII `[0-9]`); throttle check precedes fetch `guard.py:154-162`; deny-by-default `guard.py:63-93`; identity overwrite per turn `callbacks.py:41-44`; denial dict `callbacks.py:61`; HMAC reference `audit.py:52-61`.
6. No tests added: the dev suite already covers each clause, and the gaps found are blocked on code that does not exist yet.

## Findings

| # | Severity | Finding | Owner |
|---|---|---|---|
| F1 | Minor | The throttle counter lives in session state, so a new session resets it. This matches "within a session" in the spec, so it is not a defect. It does mean enumeration across sessions is not limited. | none (spec as written) |
| F2 | Minor | The throttle also counts unknown-role, no-principal and malformed lookups, and the before-tool disallowed-tool denials do not count. Consistent with the spec ("denied or malformed lookups"); noted so chunk 5 tests expect it. | none |
| F3 | Info | The "tools take no identity parameters" test (`test_security_identity.py:51-68`) inspects stand-in tools, because `tools/` is empty. It proves the helper and the schema check work, not that the real tools comply. | backend-dev, chunk 5 |

No Blocker or Major bugs. No bugs filed (Notion is not used for this repo).

## Open items
1. Chunk 5: re-run the signature check against the real `get_order_status` and `check_return_eligibility` (parameters and the FunctionTool schema), and the full tool-result comparison for nonexistent, out-of-scope, malformed, throttled and unknown role (the tool must map every denied `OrderAccess` to `denied_result()`).
2. Chunk 4/5: confirm intake and precheck neither reject nor reroute a malformed id (the only enforcement point today is the guard).
3. Task 7.5: reuse `shared_state_contexts` for the multi-agent case. Real ADK `ToolContext` state is a `State` object, not a dict, so the multi-agent test should also be run once against an ADK `InMemorySessionService` session with no model call.
4. The "Repository secret scan" scenario of access-control is not part of chunk 3 tasks; not verified here.

---

# QA report: novamart-rag-agent, chunk 2 "Synthetic data" (tasks 2.1 to 2.4)

Date: 2026-11-23. Environment: local, `backend/.venv`, Windows. No model call; `backend/.env` and keys not read. Verified independently of the dev tests with throwaway scripts (scratchpad `qa2.py`, `adv.py`).

Verdict: PASS (no Blocker or Major findings; 3 Minor observations).

## Per-task result

| Task | Verify clause | Result |
|---|---|---|
| 2.1 | 8 policy docs, audience + doc_type front-matter | PASS: 8 `doc_type: policy` (7 all_staff, 1 manager) + 3 product, all parse via `load_documents` |
| 2.1 | returns: structured window/exclusions | PASS: `return_window_days: 30`, `excluded_categories` (3), `non_returnable_conditions` (2) |
| 2.1 | one category exception | PASS: `category_exceptions` has exactly one entry (electronics, 14 days) |
| 2.1 | one manager-only policy | PASS: `manager-approvals` is the only policy with `audience: manager` |
| 2.1 | store ops all-staff, `escalation_contact` read by loader | PASS: `store-operations` audience all_staff, contact present in `Document.metadata`; no other document has it |
| 2.1 | gaps listed in README and absent from docs | PASS: README lists 5 gaps (bulk/corporate, international/customs, trade-in/buy-back, scheduling/pay/leave, installation/assembly). Case-insensitive search of all titles and bodies for bulk, corporate, international, customs, trade-in, buy-back, payroll, installation, assembly, wholesale: 0 hits. "leave" hits once (fridge clearance, unrelated); "shift handover" is not scheduling |
| 2.2 | ~10 orders, 3 stores, 3 states, seeded PII | PASS: 10 orders; store-7 x4, store-12 x3, store-19 x3; 5 delivered, 3 in_transit, 2 returned; 10 distinct names, emails, addresses (example.com / example.test, ZZ postcodes) |
| 2.2 | cross-store cases | PASS: stores 7, 12 (north) and 19 (south); NM-480303 is in another region |
| 2.3 | ~4 personas load into principals | PASS: emp_store7, emp_store12, mgr_store7, regmgr_north load as `Principal`; regional manager has store_id None |
| 2.4 | 3 product docs, `doc_type: product`, one diagram each | PASS: 3 product docs; each has exactly one fenced block (2 fence lines each, 5/6/9 lines), fences balanced |
| 2.4 | plain ASCII only | PASS: byte scan of every file under `backend/data` (docs, orders.json, users.json, README) found 0 bytes above 127 and no control characters; no CRLF |
| 2.4 | one product doc audience-restricted | PASS: `product-novabook-launch-briefing` is `audience: manager`; the other two are all_staff |

## Evidence
1. `ruff check .` (in backend) -> All checks passed.
2. `mypy --config-file pyproject.toml src` -> Success: no issues found in 16 source files.
3. `pytest tests -q` -> 43 passed in 0.68s.
4. Independent script run: counts and field values above reproduced from the loaders, not from dev tests.
5. Adversarial loads (throwaway files in a temp dir): missing front-matter, invalid YAML, missing audience, null audience, unknown audience, unknown doc_type, integer id, empty id, list/empty front-matter, anchor/alias YAML, unclosed fence, duplicate doc ids, duplicate order ids, duplicate user ids, bad status, missing/null customer, missing email, non-ISO date, string and boolean quantity, empty store_id, missing user_id, int store_id, missing top-level key: all raise `DataLoadError` with a message that names the file and field and does not echo values. CRLF front-matter parses.
6. No new tests added; the dev suite already names each verify clause (`test_task_2_x_*`) and covers the same ground.

## Findings

| # | Severity | Finding | Owner |
|---|---|---|---|
| F1 | Minor | Malformed JSON (`{not json`) in orders.json or users.json raises raw `json.JSONDecodeError`, not `DataLoadError`; the loaders' documented failure type is inconsistent. Harmless for fixed synthetic data. | backend-dev |
| F2 | Minor | `load_orders` does not validate the order-id format (`NM-` + 6 digits); `order_id: "XX"` loads. Task 3.2 validates IDs in the tool, so this is not a defect for chunk 2. | none (note) |
| F3 | Minor | `load_principals` accepts an unknown role (`god`) and an employee with no store_id. Dev test says this is intended so the guard can deny; chunk 3 must deny these by default (task 3.2 "unknown role deny"). | chunk 3 |

No bug tickets filed (Notion is not used for this repo).

## Open items
- Chunk 3 should confirm deny-by-default for unknown roles and store-less employees (F3).
- Optional: wrap `json.JSONDecodeError` in `DataLoadError` (F1).
- Task boxes in tasks.md are still unticked; the orchestrator ticks them on gate completion.

---

# Previous report (chunk 1)

## QA report: novamart-rag-agent, chunk 1 "Setup and verification of assumptions"

Date: 2026-11-23. Environment: local, `backend/.venv`, Windows. No model call was made; `backend/.env` and keys were not read.

Verdict: PASS (no Blocker or Major findings; 1.2 to 1.4 are not complete by the owner's decision, see Open items).

## Per-task result

| Task | Result | Basis |
|---|---|---|
| 1.1 skeleton, pyproject, .gitignore, .env.example, install, adk web, .env ignored | verified | see Evidence 1-6 |
| 1.2 model IDs, prices in config; live generate and embedding call | partly verified; live call not verifiable without a key; rate-limit record missing | config holds chat model, embedding model and a price table; owner ran verify_models.py once (reported, not re-run) |
| 1.3 ADK syntax; agent under `adk run`; `adk eval --help` | `adk eval --help` verified; `adk run` not verifiable without a key | expected to stay unticked |
| 1.4 ADK assumption probes | not verifiable without a key; authoring verified | probes `workflow-loop-two-passes`, `skip-summarization-in-workflow-node`, `workflow-final-reply` exist in the script; old `loop-escalate` and `custom-baseagent-branch` probes are gone; findings sections exist in design.md |
| 1.5 architect review, standards version match, spec approved | version match and status verified; architect review run not in this chunk | architecture `version: 7`, `status: approved`; standards `architecture_version: 7` |
| 1.6 pin google-adk, add `google-adk[eval]` to dev, install, `adk eval --help` | verified (pin provisional until 1.3 is run) | see Evidence |

## Evidence
1. `backend/.venv/Scripts/pip install -e "backend[dev]"` -> Successfully installed novamart-agent-0.1.0; `pip show google-adk` -> 2.15.0.
2. `backend/pyproject.toml`: `google-adk==2.15.0` in dependencies; `google-adk[eval]==2.15.0` in `dev`.
3. `adk web backend/src --port 8791`, then `GET /list-apps` -> `["novamart_agent"]`; server stopped (a second request got no response).
4. `git check-ignore -v backend/.env` -> `.gitignore:1:.env`. `.gitignore` also covers `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`.
5. `backend/.env.example` exists with the names `GOOGLE_API_KEY`, `GOOGLE_GENAI_USE_ENTERPRISE`, `GOOGLE_GENAI_USE_VERTEXAI` (values not inspected); the old copy under `backend/src/novamart_agent/` is gone (git shows a rename).
6. Skeleton: `backend/src/novamart_agent/{agents,prompts,pipeline,security,tools,adapters,rag}` all present; `backend/tests`, `backend/evals`, `backend/data` present. `backend/tests/test_skeleton.py` checks each `__all__` and that `root_agent` is discoverable.
7. `adk eval --help` -> usage printed (exit 0).
8. `ruff check backend` -> All checks passed. `mypy --config-file backend/pyproject.toml backend/src` -> no issues in 10 source files. `pytest backend/tests` -> 11 passed.
9. `backend/src/novamart_agent/config.py:10-30`: `DEFAULT_MODEL`, `DEFAULT_EMBEDDING_MODEL = gemini-embedding-001`, `DEFAULT_PRICES` for three models, price table overridable by `NOVAMART_PRICE_TABLE`; `tests/test_config.py` covers defaults, overrides and a malformed table.
10. `docs/architecture.md` front matter: `version: 7`, `status: approved`. `docs/engineering-standards.md`: `architecture_version: 7`. Match.
11. `backend/evals/check_adk_assumptions.py:98,156,195` and `:383-385` hold the three Workflow probes; grep finds no `loop-escalate` or `custom-baseagent-branch`. design.md has "Task 1.2 findings" (line 237), "Task 1.4 findings" (215) and "Workflow findings" (241).

## Findings

| # | Severity | Task | Finding |
|---|---|---|---|
| F1 | Minor | 1.2 | The free-tier rate limit is not recorded anywhere in config or design.md. The owner reports 5 requests per minute on `gemini-3.6-flash`; the task text asks for "rate limits". Record it before it is relied on (rate-limit handling, eval pacing). |
| F2 | Minor | 1.2 | `config.py` still labels the default model "provisional" and the prices VERIFY. The owner's single live run succeeded, but that result is not written down, so nothing marks the default as confirmed. The prices were read through a summarising fetch and remain unverified. |
| F3 | Minor | 1.3, 1.4, 1.6 | The probe script `check_adk_assumptions.py` has never run (only syntax-checked). It may need fixes on first run, and the `google-adk==2.15.0` pin stays provisional until it does. This matches the owner's decision to skip the probes for now. |
| F4 | Minor | 1.4 | The "Task 1.4 findings" table in design.md still carries a `LoopAgent` row, marked superseded. This is consistent, but a reader must follow the pointer to "Workflow findings". |
| F5 | Minor (process) | 1.5 | Task 1.5 is not part of this chunk's work. The version match and approved status hold, but the architect review run itself was not evidenced here. |

No testable gap was found, so no tests were added.

## Open items
- Tasks 1.2, 1.3, 1.4 remain unticked until the owner supplies the key and says run; confirm live behaviour when the agent is up.
- Add the rate-limit record (F1) and mark the default model confirmed (F2) after the owner's run.
- Decide whether `LoopAgent` text in older docs needs cleanup (F4); design.md already records the move to `Workflow`.
- Shell environment variables override `.env` in ADK (dev report open item 3): README in chunk 9 must say so.
