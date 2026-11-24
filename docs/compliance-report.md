# Compliance review: chunk 5 "Order tools" (personal-data tag)

Reviewed 2026-11-24. Scope: `tools/get_order_status.py`, `tools/check_return_eligibility.py`, `tools/_guarded.py`, `adapters/orders_api.py`, `pipeline/eligibility.py`, `security/audit.py` (for log hygiene), and tests `test_tools_get_order_status.py`, `test_tools_check_return_eligibility.py`, `test_pipeline_eligibility.py`, `test_adapters_orders_api.py`. `backend/.env` not read. No model calls. Tests were read, not run. No law pages were opened this pass; privacy principles are a checklist framing (Assumption, not cited), not legal findings.

Verdict: PASS (0 P0 gaps; F1 from chunk 2 still pending for chunk 9; 3 P2 items).

## Evidence

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Order view minimised | Met | `get_order_status.py:20-31` returns only order_id, status, expected_delivery, store_id, items (name, quantity). Customer fields are omitted, not masked (`:4-5`). `test_tools_get_order_status.py:46-53` asserts the exact key set; `:102-115` asserts no customer name, email, address, "@" or "ZZ" in output for all orders across three personas. |
| 2 | Eligibility output within purpose | Met | `check_return_eligibility.py:65-79` returns order_id, verdict, reason code, policy id, policy parameters, reference date, days since delivery, per-item name/category/eligible/reason/window. All needed to explain the outcome; no customer fields. `test_tools_check_return_eligibility.py:171-182` checks output plus logs for personal data. |
| 3 | Customer record held in memory | Acceptable | `orders_api.py:35-41` parses name, email, address into `Customer`; they stay inside backend and guard and never cross the tool boundary. Data is synthetic. |
| 4 | Denial supports access limitation | Met | `_guarded.py:14-15` maps every non-allowed decision to None; both tools return the single `denied_result()` (`get_order_status.py:38`, `check_return_eligibility.py:97-98`). The guard runs before the policy is loaded, so a policy fault cannot unmask a denied order (test `:120`). Tests cover nonexistent, other store, other region, malformed, non-string, unknown role, no principal and throttle: all return identical `{"status": "not_found"}`. Tools take only `order_id`; a schema test checks no identity parameter. |
| 5 | Logs and audit avoid personal data | Met | `audit.py:1-5,38-49`: whitelisted short-code fields; order id is an HMAC-SHA256 with random per-process salt, truncated to 16 hex. Tool failure logs carry the exception class only (`get_order_status.py:40`, `check_return_eligibility.py:104,107`). `orders_api.py:88-90` uses `from None` so file content is not chained. Tests: `test_tools_get_order_status.py:118-140`, `test_tools_check_return_eligibility.py:171-182`. |
| 6 | Audit `caller` field | Acceptable now | Holds the persona `user_id` (synthetic). With real staff it would be personal data needing retention rules. |
| 7 | Read-only | Met | `orders_api.py:64-81` exposes `get` and `from_file` only; `test_tools_get_order_status.py:143-147` asserts the public surface. |
| 8 | Return parameters sourced from the policy doc | Met | `pipeline/eligibility.py:109-124` reads window, excluded categories, exceptions and conditions from front-matter; nothing hard-coded. Values live in `backend/data/docs/returns-policy.md:6-16`. Missing or wrongly typed parameters give `not_determinable` (fail closed). Result cites `policy_document_id` and `parameters_used`. |
| 9 | Synthetic policy not presented as real | Partially met (P2) | The doc says "All figures are synthetic" (`returns-policy.md:21`), but the tool result carries no synthetic marker and the docstring tells the model to explain from the parameters with no caveat. Audience is store staff (`audience: all_staff`) and it is a company policy, not a statutory right, so risk is low. See F2. |
| 10 | Carried-forward F1 (chunk 2) | Still pending | No root `README.md` exists (glob found only `backend/data/README.md`). `backend/.env.example` has no synthetic or real-data text (grep: no matches). Owner is task 9.1. |

Vendor context (verified in the chunk 2 section below; https://aistudio.google.com/docs/terms, fetched 2026-11-23): unpaid use lets Google use inputs and outputs to improve products, humans may read them, and users are told not to submit personal information. Because these tools strip customer fields before the model sees them, even a mistaken load of real orders would not send names, emails or addresses to Gemini through the tools. Text a user types into chat is not controlled by this chunk.

## Findings

| ID | Severity | Finding | Requirement / fix | Owner |
|---|---|---|---|---|
| F1 | P1 (carried to chunk 9) | Root README and `.env.example` still lack the "Synthetic data only" warning. | As in chunk 2 F1 below: never load real data; unpaid AI Studio terms and link; persona is not authentication. Not a blocker for chunk 5. | developer |
| F2 | P2 | Eligibility output does not mark the policy as synthetic, so an answer could read as a real return entitlement. | Add a fixed synthetic-policy note to `eligibility_result` or to the orchestrator's canned Sources footer, with a test. Where the disclaimer lives is a decision for the owner (production-note spec not checked). | developer |
| F3 | P2 | Audit `caller` is a persona id; becomes personal data if real staff are used. | Revisit before any non-synthetic use. | n/a |
| F4 | P2 | Log-hygiene tests search for seeded customer values only; no test that the raw order id is absent from audit lines. Assumption: order ids are business identifiers, not personal data. | Optional test. | qa |

Counts: Met 5, Acceptable 2, Partially met 1 (P2), carried 1 (P1), Needs legal review 0, P0 gaps 0.

## Open items

1. Task 9.1: F1 warning in root README and `.env.example`. Still pending.
2. Decide where the synthetic-policy disclaimer lives (F2).
3. If real data, real staff or a paid/Vertex route is ever used, redo the privacy review (PIPEDA, Quebec Law 25 incl. privacy impact assessment and out-of-Quebec transfer, GDPR if EU users). That needs legal review and was not researched here.
4. Tests were read, not executed, by this reviewer.

Dropped sources: none. No new web sources this pass.

This is a compliance checklist, not legal advice.

---

# Compliance review: chunk 2 "Synthetic data" (personal-data tag)

Change: `openspec/changes/novamart-rag-agent`. Reviewed 2026-11-23. Scope: `backend/data/**` (README, users.json, orders.json, 11 docs). The root README does not exist yet (task 9.1). `backend/.env` not read. No model calls.

Note on location: the caller asked for `docs/compliance-review.md`. The compliance-reviewer write scope allows only `docs/compliance-requirements.md` and `docs/compliance-report.md`, so this report is written here. Move it if you want the other name.

Verdict: PASS (0 P0 gaps; 1 requirement carried to chunk 9).

## Evidence

Files read: `docs/engineering-standards.md`, `proposal.md`, `specs/order-tools/spec.md`, `specs/access-control/spec.md`, `backend/data/README.md`, `users.json`, `orders.json`, `docs/customer-data-handling.md`, and a grep of `backend/data/docs`.

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Data marked synthetic | Met | `backend/data/README.md:3` "Everything here is invented for a prototype. There are no real people, customers, emails, addresses or policies." Docs carry "All figures are synthetic" (e.g. `returns-policy.md:21`, `customer-data-handling.md:10`); product docs say "synthetic example product". |
| 2 | Verifiably synthetic (no real PII) | Met for what is checkable | All 10 orders: emails use `example.com` / `example.test`; addresses use postcode prefix `ZZ`; names are invented compound surnames; phone `555-0142` and `novamart.example.com` in `store-operations.md:6`. No real-looking phone, URL or card numbers found by grep. Four personas in `users.json` use invented names. |
| 3 | Synthetic position stated in docs | Met for data folder; root README pending | `backend/data/README.md:3`; `architecture.md` ARCH-DRV-2 "synthetic data only"; access-control spec "SHALL use only synthetic data, and the documentation SHALL state that persona selection simulates, and is not, authentication"; `tasks.md:117` (9.1) requires the statement in README. |
| 4 | Persona is not authentication | Met | `backend/data/README.md:3`. |
| 5 | Data supports minimised views | Met | Each order has `customer.name`, `customer.email`, `customer.address` as separate fields, so masking or omission (order-tools "Customer data is minimised") and the log-hygiene search for seeded values (access-control "Log contents after a lookup") are both testable. README "Seeded personal data" documents this. Fields for the status view (status, expected_delivery, items) are present on all orders. |
| 6 | Licence / third-party | No issue found | Data is authored in-repo. Brand names "NovaMart", "NovaHub" etc. are invented; I did not run a trademark search (see open items). |
| 7 | Vendor data flow | Applies at run time | Free AI Studio terms (below). Data sent to Gemini are the synthetic docs, orders and user messages. |

### Free AI Studio terms (VERIFY item, now verified)

Source: "Gemini API Additional Terms of Service" page at https://aistudio.google.com/docs/terms (the old URL https://ai.google.dev/gemini-api/terms returned a 301 to it). Fetched 2026-11-23. Published/updated: no "last updated" shown; page shows "Effective March 23, 2026" (under 12 months, but check it is still current). Trust: High (the vendor's own terms, for facts about its service).

| Finding | Quote (verbatim) | Section | Status |
|---|---|---|---|
| Unpaid use lets Google use submitted content and responses to improve its products | "Google uses the content you submit to the Services and any generated responses to provide, improve, and develop" (sentence continues; opens "When you use Unpaid Services, including, for example, Google AI Studio and the unpaid quota on Gemini API,") | Unpaid Services > How Google Uses Your Data | Verified |
| Humans may read inputs and outputs | "To help with quality and improve our products, human reviewers may read, annotate, and process your API input and output." | Unpaid Services > How Google Uses Your Data | Verified |
| Terms tell users not to submit personal data | "Do not submit sensitive, confidential, or personal information to the Unpaid Services." | Unpaid Services > How Google Uses Your Data | Verified |

Caveats: the fetch tool summarises, and the first quote came split across segments, so the first row quotes the middle segment only. Whether these terms differ for EEA, UK or Swiss users was not checked (Unverified). Whether a paid tier or Vertex route changes this was not checked, and is outside this chunk.

Consequence: the "synthetic only" rule is not just good hygiene. Feeding real customer, employee or order data to the free key would send personal data to a vendor that says it may use it to improve products and have humans read it. That is where PIPEDA, Quebec Law 25 (transfer outside Quebec, privacy impact assessment) and GDPR would start to attach (Assumption: not researched this pass, because with synthetic data they do not attach).

## Findings

| ID | Severity | Finding | Requirement / fix | Owner |
|---|---|---|---|---|
| F1 | P1 (carried to chunk 9) | The synthetic-data warning lives only in `backend/data/README.md`. The root README (task 9.1) does not exist yet and a user starting with `adk web` may never open the data folder. | Task 9.1 README MUST include, near setup and the `.env` step, a "Synthetic data only" box: (a) all data is invented; (b) never load real customer, employee or order data or real documents, because the free AI Studio key is an unpaid service whose terms (link above) say Google may use inputs and outputs to improve products and humans may read them, and tell users not to submit personal information; (c) persona selection is not authentication. Acceptance: README contains these three statements and the terms link; the data README link is present. Also mirror (b) in `.env.example` comments. | developer |
| F2 | P2 | JSON data files cannot hold comments, so `orders.json` and `users.json` have no in-file synthetic marker. A copy detached from the README looks like real data. | Optional: add a top-level `"_synthetic": true` / `"_note"` key, if the loader tolerates it (loader not changed by me; check loader and tests first). | developer |
| F3 | P2 | Synthetic checks are by inspection and by convention (reserved-looking domains, `ZZ` prefix, `555` phone). Assumption: `example.com`, `.test`, `555-01xx` are reserved for documentation and `ZZ` is not a live postcode prefix; I did not open sources for these. | Optional: a small test asserting every email ends in `@example.com` or `@example.test`, and every address has the `ZZ` prefix, so a real record cannot slip in unnoticed. | developer / qa |
| F4 | P2 | `escalation_contact` in `store-operations.md` contains a phone and email (fictional) that the assistant will quote to users. | None needed; keep the `555-0142` / `example.com` form. Do not replace with a real support desk. | n/a |
| F5 | Info | Seeded customer values must never appear in logs, audit records or cost records (ERR-2). Not checked here (belongs to the logging chunk). | Verify in that chunk's gate. | code-reviewer / qa |

Counts: Met 5, carried to chunk 9 (F1) 1, optional hardening 3, Needs legal review 0.

## Open items

1. Chunk 9 (task 9.1): add the F1 warning to the root README and `.env.example` text. Not a blocker for chunk 2.
2. Check that the Google terms are still current when the README is written (page effective March 23, 2026).
3. Trademark: "NovaMart", "NovaHub", "NovaBook" etc. were not searched for collision with real marks. Low risk for a private prototype; take to a lawyer only if the project becomes public or a client deliverable.
4. If the prototype is ever pointed at real data or a paid or Vertex route, redo this review: privacy law, vendor DPA and data residency then apply and need legal review.
5. Dependency licences (`google-adk`, `google-genai`, `numpy`, `pytest`) are outside this chunk; not checked.

Sources: https://aistudio.google.com/docs/terms (redirected from https://ai.google.dev/gemini-api/terms). Dropped sources: none.

This is a compliance checklist, not legal advice.
