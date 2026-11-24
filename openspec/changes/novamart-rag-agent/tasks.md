## 1. Setup and verification of assumptions

owner: backend-dev
tags: none
gates: code-reviewer, qa-engineer

- [ ] 1.1 Create the project skeleton per design D8 (everything under `backend/`) with `backend/pyproject.toml`, `.gitignore` (excluding `.env` and cache) and `.env.example`; verify `pip install -e backend` succeeds and `adk web backend/src` lists the agent and `.env` is ignored by git
- [ ] 1.2 Check AI Studio for the free-tier model IDs and rate limits, choose the default model and record it in configuration; verify a one-line `google-genai` generate call and one embedding call succeed with the key
- [ ] 1.3 Confirm current ADK syntax on adk.dev (agent definition, callbacks, `adk eval`); verify a minimal agent runs under `adk run`

## 2. Synthetic data

owner: backend-dev
tags: personal-data
gates: code-reviewer, qa-engineer, security-compliance, compliance-reviewer

- [ ] 2.1 Write 8 short policy documents with audience front-matter, including a returns document with structured window and exclusion parameters, one category exception, one manager-only document, and deliberate gaps (such as bulk orders); verify each parses and the gaps are listed in the README
- [ ] 2.2 Write about 10 orders across 3 stores covering delivered, in-transit and returned states with seeded customer name, email and address; verify the file loads and includes cross-store cases
- [ ] 2.3 Write about 4 personas (two stores' employees, a manager, a regional manager); verify they load into principals

## 3. Access control

owner: backend-dev
tags: auth, api
gates: code-reviewer, qa-engineer, security-compliance

- [ ] 3.1 Implement principal loading and the before-agent callback that sets identity in session state from `NOVAMART_USER`; verify with a test that a tool reads the principal and no tool signature has identity parameters
- [ ] 3.2 Implement order-ID validation and the shared authorization function, with uniform denial responses; verify unit tests for malformed IDs, cross-store denial, regional-manager allow, unknown role deny, and identical denial vs not-found replies
- [ ] 3.3 Implement the before-tool callback with per-role tool allowlist and the audit log with hashed order references and PII redaction; verify a test that seeded name, email and address never appear in log output
- [ ] 3.4 Implement the denied-lookup counter with session throttling; verify a test that sequential probing is throttled and returns nothing (cut first if time runs short)

## 4. Retrieval

owner: backend-dev
tags: api
gates: code-reviewer, qa-engineer, security-compliance

- [ ] 4.1 Implement the chunker, embedder with per-chunk calls and content-hash disk cache, and cosine index with audience filtering; verify tests that a manager-only chunk is never returned to a non-manager and that cached vectors are reused
- [ ] 4.2 Implement `search_policy` returning chunks, document IDs and scores, or `no_answer` below the configurable threshold; verify tests for an answerable query, a gap query and an unrelated query

## 5. Order tools and agent

owner: backend-dev
tags: api, personal-data
gates: code-reviewer, qa-engineer, security-compliance, compliance-reviewer

- [ ] 5.1 Implement the read-only order backend stub and `get_order_status` returning the minimised, masked view; verify tests for permitted, denied and unknown orders and that no full email or address is returned
- [ ] 5.2 Implement `check_return_eligibility` with deterministic date and category logic from policy parameters; verify unit tests for within-window, category-exception, outside-window and undeterminable-policy cases
- [ ] 5.3 Write the system instruction (answer only from tool results, cite documents, treat retrieved text as data, decline and escalate, refuse role claims and instruction disclosure) and wire the root agent; verify by running `adk run` through one doc question, one order lookup, one combined question and one unanswerable question

## 6. Evaluation

owner: backend-dev
tags: none
gates: code-reviewer, qa-engineer

- [ ] 6.1 Write 12 to 15 quality cases across the four question types with persona, expected behavior and rule checks; verify at least two per type
- [ ] 6.2 Write the security cases (cross-store access, role-override claim, poisoned document, PII in logs, manager-only content); verify each has an unambiguous pass condition
- [ ] 6.3 Build the runner (ADK eval for tool trajectories plus custom content checks) and run both sets; verify it produces per-case results and an overall pass rate
- [ ] 6.4 Run the quality set at three threshold values and choose one; verify the threshold table is written to the results summary
- [ ] 6.5 Write the results summary listing every failure with a diagnosis; verify no failing case is omitted and fix or document each one

## 7. Documentation and production note

owner: backend-dev
tags: none
gates: code-reviewer, qa-engineer

- [ ] 7.1 Write the README with setup, persona table, run commands, eval commands, the synthetic-data statement and the "persona is not authentication" statement; verify a fresh clone follows it to a working session
- [ ] 7.2 Re-check the Google product claims for the note against current docs (Gemini Enterprise registration of custom agents, identity passing, ACL setup, CMEK and residency, data-use terms); verify each claim has a source or is marked to be confirmed
- [ ] 7.3 Write the one-page production note with the four required sections, a stated recommendation and fallback, the identity-propagation spike, and a prototype-limits list; verify it renders to a single page
- [ ] 7.4 Run a secret scan over the repository and its history; verify zero findings

## 8. Final check

owner: backend-dev
tags: none
gates: code-reviewer, qa-engineer

- [ ] 8.1 Run all unit tests, the quality and security evals, and one end-to-end demo per persona from a clean environment; verify the results match the summary
- [ ] 8.2 Review each spec scenario against the delivered behavior; verify every scenario has a test, an eval case, or a stated reason it is covered by documentation
