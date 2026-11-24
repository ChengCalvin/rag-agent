# Operating model: how the product team works inside a spec-driven repo

Think of this as a small IT department. The **spec framework** (OpenSpec, Spec Kit, ...) is the ticketing and documentation system. The **agents** are staff with fixed roles. The **main session** is the department lead who assigns work, never does the specialist work, and reports to the **owner** (the human). `docs/team/process.yaml` is the department's configuration; this file is the policy it implements.

## 1. People and roles

| Role | Who | Accountable for | Never does |
|---|---|---|---|
| Owner | the human | Approves specs, stack changes, chunk boundaries, production deploys, anything outward-facing | |
| Orchestrator | main Claude session | Reads `process.yaml`, assigns chunks, runs gates, enforces the fix loop, reports, keeps framework state current | Writes product code or specs content that belongs to a specialist; picks a stack |
| Product manager | `product-manager` | Spec: problem, scope, requirements, scenarios, task breakdown | Writes code; expands scope silently |
| Architect | `architect` | Stack/tier decisions, data model, API contract, module layout for new capabilities, standards file | Re-picks a pinned stack; "future-proofs" |
| UX designer | `ux-designer` | Visual direction, design spec, review of built UI against the chosen design | Implements UI |
| Frontend dev | `frontend-dev` | UI code, component tests, UI bugs | Invents API endpoints; touches server code |
| Backend dev | `backend-dev` | API, data, integrations, server tests, server bugs | Changes the contract without telling the orchestrator |
| Code reviewer | `code-reviewer` | Standards and modularity verdict on a diff | Fixes code |
| QA engineer | `qa-engineer` | Behaviour verdict against spec scenarios; E2E tests | Fixes product code |
| Accessibility tester | `accessibility-tester` | Accessibility verdict at the project's WCAG level | Fixes product code |
| Security | `security-compliance` | Vulnerability and data-protection verdict | Fixes product code |
| Compliance | `compliance-reviewer` | Legal/regulatory requirements checklist (not legal advice) | Gives legal advice |
| DevOps | `devops-engineer` | CI/CD, environments, deploy, rollback, monitoring | Deploys production without owner approval |
| Platform | `platform-engineer` | Cloud infrastructure, Large tier only | |

Subagents cannot spawn subagents. Everything is delegated from the orchestrator, and agents hand off through files in the repo, never through chat history.

## 2. The SDD lifecycle (stages, owners, exit criteria)

```
 1 SPECIFY ──► 2 DESIGN ──► 3 PLAN ──► 4 BUILD ──► 5 VERIFY ──► 6 ACCEPT ──► 7 RELEASE ──► 8 ARCHIVE
   PM           arch/ux      PM/orch    dev(owner)   gate agents    owner       devops        orch
   │             │            │          └─────────────┬────────────┘            │
   owner         owner        owner       per chunk, repeats; fix loop ≤ N        owner approves prod
   approves      approves*    approves    (stages 4-6 loop per chunk)
   * only when the design changes the stack, adds server state, or changes how pages look
```

| # | Stage | Owner agent | Inputs | Output (in the framework) | Exit criteria |
|---|---|---|---|---|---|
| 1 | Specify | product-manager | Owner's idea or request | Proposal + requirements with Given/When/Then scenarios | Owner approved; out-of-scope listed; each scenario testable |
| 2 | Design | architect (only if triggered, see `engage`), ux-designer (if visual), else the orchestrator drafts from the owner's constraints | Approved spec, pinned stack | Design: ASCII change diagram, where the work sits in the architecture (layer, module, public interface per `STRUCT-1/2`), data/API contract, visual direction | Stack unchanged or owner approved the change; layout named; contract written |
| 3 | Plan | product-manager (or orchestrator) | Spec + design | Chunks: each has `owner:`, `gates:`, tasks, dependencies; ASCII chunk map | Each chunk independently buildable/verifiable/committable; every scenario maps to a task |
| 4 | Build | frontend-dev / backend-dev / devops-engineer / ux-designer per `owner:` | One chunk, standards, pinned stack | Code + tests + standards self-check, one commit's worth | Lint, type-check, tests, build green; self-check attached |
| 5 | Verify | gate agents (section 4) | Chunk diff + its scenarios | One verdict per gate with evidence | All gates PASS, or fix loop exhausted (then stop) |
| 6 | Accept | owner | Gate verdicts | Confirmation to continue | Owner says go (unless `autonomy.confirm_chunk_boundary: false`) |
| 7 | Release | devops-engineer | Accepted chunks on the main branch | Deployed environment, smoke test result | Owner approval for production (always, see section 6) |
| 8 | Archive | orchestrator | Completed change | Delta specs synced into main specs; change archived; status updated | Specs reflect shipped behaviour; no open tasks |

Stages 4-6 repeat per chunk. Stages 1-3 repeat per change, never per chunk.

## 3. Handoff contract: what each agent receives and returns

Diagrams, the numbered handoff register (H1-H10) and a worked example are in `process-diagrams.md`.

Every delegation (rendered from `process.yaml` into the framework's config) carries: change/feature path, chunk and tasks with scenarios, "read `CLAUDE.md` and `docs/engineering-standards.md` first (binding)", the pinned stack and exclusions, the source of truth, scope limit, and the required return.

Every agent returns:
1. **Verdict:** PASS or FAIL (devs: DONE or BLOCKED).
2. **Evidence:** commands run and results, `file:line` references, test names.
3. **Standards self-check** (dev agents) or **findings table with rule IDs** (reviewers).
4. **Open items:** blockers, contract changes, refactors worth doing later.

A verdict without evidence is treated as FAIL by the orchestrator.

## 4. Gates: who verifies what

Each chunk carries `tags:` (what it touches); `process.yaml` maps tags to gate agents. Defaults:

| Gate | Agent | Runs when |
|---|---|---|
| standards | code-reviewer | any code changed |
| behaviour | qa-engineer | always |
| security | security-compliance | tag `forms`, `api`, `auth`, `secrets`, or `personal-data` |
| accessibility | accessibility-tester | tag `ui` |
| design | ux-designer | tag `look` |
| compliance | compliance-reviewer | tag `privacy` or `legal` |

Gate agents are read-only on product code. They write only their own report file. The owner agent never grades its own work.

**Fix loop:** FAIL goes back to the chunk's owner agent with the findings; re-run only the failed gate; at most `autonomy.max_fix_cycles` (default 3), then stop and report open findings to the owner.

## 5. Write permissions (who may change what)

| Path or artifact | May write | Everyone else |
|---|---|---|
| Spec and requirements | product-manager (owner approves) | read-only |
| Design, ADR, `docs/engineering-standards.md` | architect (owner approves) | read-only; propose changes in the report |
| Product source and its tests | frontend-dev, backend-dev (within the chunk's scope) | read-only |
| E2E and a11y tests | qa-engineer, accessibility-tester | read-only |
| Review/report files (`docs/code-review.md`, `qa-report.md`, `security-review.md`, `accessibility-report.md`) | their own agent | read-only |
| CI, deploy config, environments | devops-engineer, platform-engineer | read-only |
| Framework state (task ticks, archive, status) | orchestrator only | read-only |
| `docs/team/process.yaml`, framework config | `setup-workflow` / owner | read-only |

## 6. Escalation and human approvals

Stop and ask the owner (do not guess) when:
- the work would change the pinned stack or add server state not in the spec (route to `architect`, owner approves);
- an agent needs an endpoint, field or behaviour the spec and contract do not define;
- a requirement is ambiguous or contradicts another;
- the fix loop is exhausted;
- a new dependency is proposed (`approvals` in `process.yaml` decides if this needs the owner or only a report line);
- anything outward-facing or hard to reverse: production deploy, sending messages, spending money, deleting data.

Production deploy always needs the owner's explicit approval in the current conversation; this cannot be configured away.

## 7. Framework mapping

How the generic model lands in each framework is in `adapters/*.md`. Configuration lives once, in `docs/team/process.yaml`; adapters render it into the framework's own config so nothing is typed twice. Re-run `setup-workflow` in sync mode after editing `process.yaml`.

| Concept | OpenSpec | Spec Kit | Notion | Plain markdown |
|---|---|---|---|---|
| Spec | `proposal.md` + `specs/` | `spec.md` | Specs DB (PRD) | `docs/specs/*.md` |
| Design | `design.md` | `plan.md` | Specs DB (ADR) | `docs/plan.md` |
| Chunk + tasks | `tasks.md` | `tasks.md` | Tickets DB | `docs/tasks.md` |
| Rules/preamble home | `openspec/config.yaml` | `.specify/memory/constitution.md` | repo `CLAUDE.md` | `docs/workflow.md` |
| Archive | `openspec archive` | merge `specs/` into main, close feature | set Idea to Done | move to `docs/archive/` |

## 8. Evolving the architecture and standards

```
 principles (plugin) ──► ARCHITECTURE SPEC (project, versioned) ──► STANDARDS (derived) ──► CODE
                                 ▲                                       │
                  proposal ──────┘  (owner approves, version bump,       └─ code-reviewer + agents + lint enforce
                                     migration plan, standards re-derived)
```

- The architecture spec drives the code. Code that disagrees is a defect, or the trigger for a proposal. It is never the new standard (`EVOL-2`).
- A change is a proposal that bumps the architecture `version`, adds a change-log row and a Migration row, and re-derives the standards in the same change. `check_process.py` fails while their versions differ.
- Migration scope: code in a legacy scope is reported as pending migration, not failed, until its target version. New or changed code must conform immediately.
- Principles are stack-neutral and change only with the plugin.

## 9. Guardrails: keeping each agent on track

Each agent's limits are data in `docs/team/guardrails.yaml` (defaults in the plugin, editable per project). The orchestrator verifies them after every delegation, before a gate runs:

| Mechanism | Prevents | Verified by |
|---|---|---|
| Write allowlist per agent (`may_write`) | an agent editing files outside its role | `check_scope.py` on the git diff plus untracked files |
| Protected files (team config, architecture, standards, `CLAUDE.md`, framework rules) | an agent rewriting its own rules | `check_scope.py` |
| Return shape (verdict token, required sections) | free-form, unverifiable answers | `validate_return.py` |
| Evidence rule | a PASS or DONE with no commands or `file:line` | `validate_return.py` |
| Task accounting (`--tasks`) | doing unassigned work, or silently skipping assigned work | `validate_return.py` |
| Findings consistency (gates) | PASS with a Major finding, FAIL with no finding, invented rule IDs | `validate_return.py` |
| Dependency gate | adding a dependency without a justification line | `check_scope.py` plus the report |
| Stop conditions and attempt cap | improvising around a blocker | agent text; BLOCKED needs a reason (`validate_return.py`) |
| Tool restrictions in agent frontmatter | read-only agents using write tools | the plugin's agent definitions |

A violation counts as a failed gate for that agent. The output goes back to it, and the fix loop applies (`autonomy.max_fix_cycles`).

Limits of this design: the scope check sees what changed on disk, not what an agent ran. A command with no file effect (a deploy, a network call) is covered only by the stop conditions and by `approvals`, which the agent text states and the orchestrator must enforce. A runtime hook that blocks writes as they happen would close more of that gap; it depends on the hook payload identifying the subagent, which has not been verified.

## 10. Audit trail

Every delegation is recorded by the orchestrator in `docs/team/audit/<change>.jsonl` (see the `audit-trail` skill): agent, stage, refinement round, tokens and API-equivalent cost, files added/modified/deleted, gate results per spec scenario, and every decision with who made it (`owner`, `owner-delegated`, `agent:<name>`). Cost is additive across refinements and reported per phase (explore, execute, verify, release). `audit.py check` fails on a broken hash chain, a skipped scenario, a step with no tokens, or an agent deciding a spec, stack change or production deploy. Only the orchestrator writes the ledger; an owner decision must quote the owner's words.
