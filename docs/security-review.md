# Security review: chunk 7 "Pipeline agents and orchestrator" (tags api, auth)

Change: openspec/changes/novamart-rag-agent. Reviewer: security-reviewer. Date: 2026-11-24.
Verdict: **PASS** (0 Critical, 0 High, 1 Medium, 3 Low, 2 Info). Notion is not used in this repo and there are no Critical/High findings, so no tickets.

Scope: agents/ (orchestrator, nodes_*, callbacks, deps, the five agents, reply), pipeline/ (state keys, messages, routing, cost, retrieval_result, sources), prompts/, rag/lazy.py, tools/search_policy.py, config.py, security/callbacks.py.

## Scanners
- gitleaks, semgrep, pip-audit: not installed (no module in backend/.venv). Replaced by grep for key patterns (`AIza...`, `sk-...`, `GOOGLE_API_KEY=value`) over the tree: no hits outside `.env.example` (names only). No dependency audit ran, so dependency risk is unassessed. checkov/tfsec: n/a.
- `backend/.env` not read; `git check-ignore` confirms it is ignored (`.gitignore:1`) and not tracked. `.adk/session.db` has no key pattern.
- `ruff check`: clean. `mypy src`: no issues in 72 files. `pytest -q`: 618 passed.

## Findings
**Medium**
- M1. `backend/src/novamart_agent/.adk/session.db` (650 KB, untracked) is not git-ignored (`git check-ignore` returns nothing). It is the adk web/run session store: events, state (persona name, role, store), user messages, tool results. Data is synthetic, but one `git add -A` would commit it. Fix: add `.adk/` to `.gitignore`. Owner: backend-dev.

**Low**
- L1. Retry amplification and cost understatement (`agents/_common.py:12-18`). `exceptions=["ClientError","ServerError"]` retries every 4xx (400, 401, 403, 404) as well as 429; 4 attempts with 8/16/32 s waits per node (about 56 s blocked). Worst case per turn: intake 4 + retrieval 8 + validator 8 + composer 4 = 24 chat calls (max_iterations 2) plus embeddings. Failed attempts are not counted (D17), so the cost line understates. Order-agent retries re-run only a call that failed before any tool ran (the turn halts at the tool), so the denied-lookup throttle is not inflated. Fix: retry only 429/5xx, or cap attempts at 2, and note the undercount.
- L2. `make_order_after_tool` keys results by tool name (`agents/callbacks.py`). A message naming two orders overwrites the earlier result, so the answer covers one order and depends on call order. No leak: a denied or nonexistent order gives the same not-found either way. Integrity/UX only.
- L3. Uniform denial depends on the model in one place. Denied, nonexistent and malformed ids are identical in code (same `{"status":"not_found"}`, same `NOT_FOUND_REPLY`, same route, same call count: intake plus order, no composer). That holds only if intake routes to `order` and the order agent calls the tool; precheck deliberately never inspects ids. If a model sent a malformed id to clarify, its call count and reply would differ. That reveals nothing about existence or scope. Unverified without model calls; chunk 8 evals should cover it.

**Info**
- I1. Persona selection (`NOVAMART_USER`) is simulated auth (accepted in architecture). adk web has no auth and its session API lets a local client write state. The principal is overwritten by the first node every turn, but `denied_lookups` could be reset by a client. Local dev only.
- I2. Retrieved text, the rubric and rewrites remain prompt-injection surfaces for the validator and composer. Both have no tools, get JSON-as-data, and Sources, notes and cost are built by code. The residual is a manipulated answer body, not a data or authorization breach.

## Evidence
- Identity. `inject_identity` is the first node after START (`orchestrator.py` chain). It writes the principal from `settings.user` resolved against `users.json` at build time (`security/callbacks.py:34-45`). No message, document or model output reaches it. No agent sets `output_key` (grep), so model output is never written to state. The tools take only `query` or `order_id`, and `principal_from_state` fails closed. Role claims in a message reach only intake as data and the precheck patterns.
- Guard on every path. The guard runs inside both order tools (chunk 5). The new after-tool callbacks run after the tool, store the result, set `skip_summarization` and return None (no replacement response, no tool call). The halt applies to every status, so no model sees a result or writes cause-dependent wording. Before-tool order: allowlist and audit first, then the hint, so a denied call never gets the override.
- Templating. No `{` or `}` in any instruction (grep over `prompts/`), so ADK state-key templating cannot fire. Untrusted text goes only as JSON message content (`pipeline/messages.py`). The hint callback rewrites only `query`, from a rewrite already capped (200 chars) and cleaned; `parse_query` cleans it again and the search is still audience-filtered. The hint is cleared each turn (`fresh_turn_state`).
- Manager-only content. `CosineIndex.rank` filters by audience before ranking (`rag/index.py:42`) and `closest_titles` comes from that filtered ranking (`rag/search.py:58-60`). The validator and composer see only filtered chunks, so rewrites, Sources (catalog lookup by id of filtered chunks) and the "You might mean" titles cannot carry manager-only titles.
- Cost and state. Usage records hold token counts only. The cost line has the same shape for every denial cause; denied and nonexistent orders both end after 2 calls.
- Logs. The only log calls in reviewed code are class-name-only warnings in the three tools. Audit is whitelisted and keyed (chunk 5). Node errors carry state key names, never values (`pipeline/state_codec.py`).
- adk web traces. User-visible: own persona (state delta), intake rubric (paraphrase of their own message), validator verdict and rewrite, retrieved chunks (audience-filtered), order tool results (guard-authorised, no customer PII), composer text (sanitised by the after-model callback). No restricted title, manager-only chunk or rubric rule text is in state or events. Accepted.

## Open items
1. Fix M1 (add `.adk/` to `.gitignore`) before the next commit.
2. Decide on L1 (narrow retry to 429/5xx).
3. Chunk 8 evals: assert the same reply and cost-line shape for denied, nonexistent and malformed ids with real model calls (L3).
4. Install gitleaks, semgrep and pip-audit for the next gate.

---

# Security review: chunk 5 "Order tools" (tags api, personal-data)

Change: openspec/changes/novamart-rag-agent. Reviewer: security-reviewer. Date: 2026-11-24.
Verdict: **PASS** (0 Critical, 0 High, 0 Medium, 4 Low, 2 Info).

Scope: adapters/orders_api.py, pipeline/eligibility.py, tools/get_order_status.py, tools/check_return_eligibility.py, tools/_guarded.py, errors.py, models.py, parsing.py, and the guard path they depend on (security/guard.py, decision.py, audit.py, principal.py), plus tests.

## Scanners
- gitleaks, semgrep, pip-audit: not installed. Replaced with grep and manual reading. No dependency audit was run, so dependency risk is unassessed.
- checkov/tfsec: not applicable (no Terraform).
- `backend/.env` was not read. `git check-ignore` confirms `.env` is ignored (`.gitignore:1`).
- Notion: not used in this repo (CLAUDE.md). No Critical/High findings, so no tickets were needed.

## Evidence
- ARCH-MOD-4, bypass search. `grep OrdersApi|orders_api|_by_id|\.get(order` over backend/ shows `OrdersApi` is used only in `adapters/` and tests. `_by_id` is private to `orders_api.py:72,81`. No `src/` module other than the guard calls the fetch. `OrderGuard(fetch, ...)` is built only in tests, and `tests/fakes.py:98` passes `backend.get`. `agents/` holds only `__init__.py`, so there is no production wiring yet (see open items).
- Both tools reach order data only through `guarded_order` (`tools/_guarded.py:14`). It returns the order only when `access.decision.allowed`. `OrderGuard._decide` (`guard.py:182-197`) puts the order in `OrderAccess` only when `authorize_order` allows.
- IDOR across store and region.
  - Order ids must match `NM-[0-9]{6}` by `fullmatch` (`guard.py:46,71`). That rejects trailing newline, spaces, Unicode digits, lowercase and non-str types. Lookup is by exact dict key.
  - Employees and managers need `store_id` equal to the order's store. Regional managers need `region` equal to the order's region. Missing scope, unknown role and no principal are denied (`guard.py:90-103`).
  - The tools take no identity parameter. I confirmed with ADK 1.18.0 that the model-visible declaration exposes only `order_id`, for both tools.
- Existence oracle.
  - Every denial (nonexistent, out of scope, malformed, no principal, unknown role, throttled) maps to `None`, then to a fresh `{"status": "not_found"}` (`guard.py:76-79`, `get_order_status.py:38`, `check_return_eligibility.py:97-98`).
  - In `check_return_eligibility` the guard runs before the policy load, clock read and rule evaluation (`:96-101`). A broken or mutated policy cannot make denied and permitted orders look different, and denied orders never get `not_determinable`, `error`, reason codes or `days_since_delivery`.
  - The throttle counter rises on every denial and is not reset by allowed lookups (`guard.py:176-177`), so enumeration is capped. Audit reasons go to the audit log only.
  - Timing differences (dict miss vs scope compare) are microseconds and not visible through an LLM tool channel. Not rated.
- PII.
  - `order_status_view` returns status, order id, expected delivery, store id and item name/quantity (`get_order_status.py:20-31`). `check_return_eligibility` returns the verdict, the policy parameters and, per item, name, category, eligibility, reason and window. Neither returns customer name, email or address, SKU, condition or dates other than expected delivery.
  - `Customer` fields are `repr=False` (`models.py:89-91`).
  - The tools log only the exception class name (`get_order_status.py:40`, `check_return_eligibility.py:104,107`), with no `exc_info` and no message. Exception messages carry field names only (`errors.py`, `parsing.py`). `from None` on JSON errors prevents file content from leaking.
  - The audit record is whitelisted. Order ids appear only as an HMAC-SHA256 reference with a per-process random salt (`audit.py:52-63`).
  - Status `error` and `not_determinable` carry no detail beyond the status string.
- Mutation. `OrdersApi` exposes only `get`, over a `MappingProxyType`. `Order`, `OrderItem` and `Customer` are frozen dataclasses with a tuple of items. `ReturnPolicy` is frozen and built from copies (`_str_tuple` returns a new tuple). Nothing writes to `Document.metadata`.
- Clock. `evaluate_return` is pure and takes `today`. The only clock input is the `today` parameter of `make_check_return_eligibility`, which defaults to `date.today`. No environment or config override exists (grep for `NOVAMART_*DATE|CLOCK|TODAY` found nothing). Tests inject a date.
- Dates. `delivered_date` after the reference date, or missing on a delivered order, raises `OrderDataError`, so the result is `not_determinable` (fail closed, `eligibility.py:157-160`). A delivered order with no items does the same. "returned" and "not delivered" orders return order-level reasons without a date calculation.
- Policy typing. `_positive_int` rejects bool, float, string and values below 1 (`eligibility.py:75-78`). A missing or wrongly typed parameter raises `PolicyParametersError`, which gives `not_determinable`.
- Injection. Policy front-matter and order fields (item name, category) reach the model only as JSON data fields in the result. No string is concatenated into instructions by this code. The tool docstrings are static. A grep of `data/orders.json` for instruction-like words found none.
- Tests. `python -m pytest -q` in backend: 291 passed, 3 failed. The three failures are the "no identity parameter in the model-visible schema" tests (see L4). The suite covers uniform denial for every cause, throttle uniformity, malformed ids never reaching the fetch, no PII in output or logs, undeterminable policy not unmasking a denied order, injected clock, generic error on failure, and a read-only backend.

## Findings

| # | Severity | Location | Finding | Impact | Recommended fix | Owner |
|---|----------|----------|---------|--------|-----------------|-------|
| L1 | Low | `pipeline/eligibility.py:132-142`, `_str_tuple` (:81-84) | Category and condition matching is exact and case-sensitive. Policy values are not normalized. A front-matter value like `Gift_Cards` or one with a trailing space does not match `gift_cards`, so an excluded or exception category silently falls to the general window (fail open). | Wrong "eligible" answer from a data typo. Not exploitable by the model or a user. | Normalize (strip, lower) on both sides when loading, or reject non-canonical values with `PolicyParametersError`. | backend-developer |
| L2 | Low | `pipeline/eligibility.py:75-78,87-99` | No upper bound on `window_days`. Duplicate `category_exceptions` entries resolve silently to the first (`exception_for`). | A mistaken policy edit (for example 3000) makes everything eligible with no signal. Needs write access to policy documents. | Cap the window at a sane maximum and reject duplicate categories. | backend-developer |
| L3 | Low | `tools/check_return_eligibility.py:115`, `date.today` | The reference date is the server's local date, not a fixed business timezone. | A one-day skew near midnight or across timezones can flip a boundary-day result. | Use a configured timezone for the default clock. | backend-developer |
| L4 | Low | `tests/test_security_identity.py`, `tests/test_tools_get_order_status.py:156-159`, `tests/test_tools_check_return_eligibility.py` | Three schema tests fail in this environment. Installed google-adk is 1.18.0 and `pyproject.toml:11` pins 2.15.0. On 1.18.0, `parameters_json_schema` is `None`. I confirmed manually that the declaration `parameters.properties` is `['order_id']` only, so the control holds. | The regression guard for "no identity parameter" is not running green, so a future identity parameter could be missed until the environment matches the pin. | Align the environment to the pin (or the pin to the environment) and rerun. Make the test tolerant of both schema APIs. | backend-developer |
| I1 | Info | `security/guard.py:160-180` | A throttled session also denies permitted orders, with the same uniform dict. This is correct for oracle resistance but is a self-inflicted denial of service within a session. | None security-relevant. | Accept. | n/a |
| I2 | Info | `tools/get_order_status.py:29` | `store_id` is returned for allowed orders. For employees and managers it equals their own store. For regional managers it reveals which store in the region, which is within their scope. | None. | Accept. | n/a |

Accepted Low and Info risks: L1 to L4, I1, I2, subject to the open items below.

## Open items
1. Production wiring does not exist yet (`agents/` is empty). In chunk 6, confirm that:
   - the fetch passed to `OrderGuard` is `OrdersApi.get` and only the guard holds it;
   - `make_check_return_eligibility` is called without a `today` override;
   - `AuditLogger` is constructed without a fixed salt;
   - the before-tool callback sets the principal from the application, not from user input.
2. Dependency audit (pip-audit) is still not run. Install it, or run it in CI, before the release gate.
3. Resolve L4 (ADK version drift) so the identity-parameter tests run green.
4. Whether session state (`principal`, `denied_lookups`) can be written from outside the application via `adk web` is chunk 3 and chunk 6 scope. It was not re-verified here.
