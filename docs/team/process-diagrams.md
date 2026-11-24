# Process diagrams: how the pieces connect and where handoffs happen

Handoffs are numbered H1-H10. Each is a point where work, a decision or an artifact passes from one party to another, and each has a check that must pass before the next party starts.

## 1. Who talks to whom (star, not mesh)

Subagents cannot spawn subagents and do not talk to each other. Every handoff goes through the orchestrator, and the payload travels as a file in the repo, never as chat history.

```
                        ┌──────────────────────────┐
                        │  OWNER (human)           │
                        │  approves spec, stack,   │
                        │  chunk boundaries, prod  │
                        └─────────────┬────────────┘
                          H1,H4,H8,H10│ approvals / reports
                                      ▼
   docs/team/process.yaml    ┌──────────────────────────┐   framework state
   (config, read each ──────►│  ORCHESTRATOR            │◄─────────────────┐
   delegation)               │  main Claude session     │  tasks, status,  │
                             │  assigns, gates, loops   │  archive         │
                             └──┬─────┬─────┬─────┬─────┘                  │
              delegation prompt │     │     │     │ verdict + evidence     │
              (preamble)        │     │     │     │                        │
        ┌───────────┬───────────┘     │     │     └──────────┬─────────────┤
        ▼           ▼                 ▼     ▼                ▼             │
   ┌────────┐  ┌────────┐       ┌────────┐ ┌────────┐   ┌─────────────┐    │
   │ SPEC   │  │ DESIGN │       │ BUILD  │ │ BUILD  │   │ GATES       │    │
   │ PM     │  │ arch / │       │front-  │ │back-   │   │ code-review │    │
   │        │  │ ux     │       │end-dev │ │end-dev │   │ qa, a11y,   │    │
   │        │  │        │       │        │ │        │   │ security,   │    │
   │        │  │        │       │        │ │        │   │ compliance, │    │
   │        │  │        │       │        │ │        │   │ ux          │    │
   └───┬────┘  └───┬────┘       └───┬────┘ └───┬────┘   └──────┬──────┘    │
       │writes     │writes          │writes    │writes         │writes     │
       ▼           ▼                ▼          ▼               ▼           │
   ┌──────────────────────────────────────────────────────────────────┐    │
   │ REPO: spec · design · tasks · src/ · tests · docs/*-report.md    │────┘
   │ (the only channel between agents)                                │
   └──────────────────────────────────────────────────────────────────┘
```

## 2. Lifecycle with handoffs

```
 OWNER idea
    │
    │ H1  request ──► orchestrator: pick PM, pass idea + constraints
    ▼
┌─────────┐  H2  spec ready (proposal + scenarios)         ┌─────────────┐
│1 SPECIFY├──────────────────────────────────────────────►│ OWNER       │
│  PM     │◄────────── changes requested ─────────────────│ approves    │
└─────────┘                                                └──────┬──────┘
                                                                  │ approved spec
                                              ┌───────────────────┴─────────────┐
                                              ▼                                 ▼
                                   ┌──────────────────┐            stack change / server state /
                                   │2 DESIGN          │            new look? ──yes──► architect / ux-designer
                                   │ layout + contract│            (owner approves, H3)
                                   └────────┬─────────┘
                                            │ H3  design ready (module layout, contract, visual direction)
                                            ▼
                                   ┌──────────────────┐
                                   │3 PLAN            │  chunk map: owner:, tags:, gates:
                                   │ PM / orchestrator│  every scenario maps to a task
                                   └────────┬─────────┘
                                            │ H4  plan approved by owner (chunk map)
                                            ▼
        ┌──────────────────────── per chunk, repeats ────────────────────────┐
        │                                                                     │
        │  ┌──────────┐ H5 delegation  ┌───────────┐ H6 DONE + self-check    │
        │  │ORCHESTR. ├───────────────►│4 BUILD    ├──────────────┐          │
        │  │          │                │ owner: dev│              │          │
        │  └────▲─────┘                └───────────┘              ▼          │
        │       │                                          ┌────────────┐    │
        │       │ H7 findings (FAIL, ≤ N cycles)           │5 VERIFY    │    │
        │       └──────────────────────────────────────────┤ gate agents│    │
        │                                                  └─────┬──────┘    │
        │                                                        │ H8 verdicts (all PASS)
        │                                                        ▼          │
        │                                                  ┌────────────┐    │
        │                                                  │6 ACCEPT    │    │
        │                                                  │ OWNER      │    │
        │                                                  └─────┬──────┘    │
        └────────────────────────────────────────────────────────┼──────────┘
                                          next chunk ◄───────────┤ yes
                                                                 │ all chunks done
                                                                 ▼
                                   ┌──────────────────┐  H9 accepted code on main
                                   │7 RELEASE         │◄──────────────────────
                                   │ devops-engineer  │
                                   └────────┬─────────┘
                                            │ H10 production approval (always the owner)
                                            ▼
                                   ┌──────────────────┐
                                   │8 ARCHIVE         │  sync delta specs into main specs,
                                   │ orchestrator     │  close the change
                                   └──────────────────┘
```

## 3. One chunk, step by step (sequence)

```
 OWNER      ORCHESTRATOR         OWNER AGENT        GATE AGENTS          REPO / FRAMEWORK
   │             │               (frontend/backend)  (reviewer, qa, ...)
   │             │ read process.yaml, chunk tags ──────────────────────────►│ tasks.md
   │             │ "you are here" diagram                                   │
   │◄────────────┤                                                          │
   │             │ H5 delegation prompt                                     │
   │             ├─────────────────►│ read operating-model, standards,      │
   │             │                  │ CLAUDE.md, spec scenarios ◄───────────┤
   │             │                  │ state layer / module / interface    │
   │             │                  │ build + tests ───────────────────────►│ src/, tests/
   │             │                  │ run lint · types · tests · build      │
   │             │ H6 DONE: verdict + evidence + standards self-check       │
   │             │◄─────────────────┤                                       │
   │             │ evidence missing? ──► back to owner agent                │
   │             │                                                          │
   │             │ gates = always + by_tag(chunk.tags)                      │
   │             ├──────────────────────────────────►│ code-reviewer: diff vs standards
   │             ├──────────────────────────────────►│ qa-engineer: scenarios
   │             ├──────────────────────────────────►│ + a11y / security / ... by tag
   │             │                                   │ write docs/*-report.md ───►│
   │             │ H8 verdicts + findings (rule IDs, file:line)             │
   │             │◄──────────────────────────────────┤                      │
   │             │                                                          │
   │             │  any finding ≥ fail_on? ──yes──► H7 findings to owner agent
   │             │                                  fix → re-run ONLY failed gate
   │             │                                  (max_fix_cycles, then stop)
   │             │  all PASS ──► tick tasks ────────────────────────────────►│ tasks.md
   │  chunk report: verdict per gate, evidence                               │
   │◄────────────┤                                                          │
   │ H8 "go"     │                                                          │
   ├────────────►│ next chunk                                               │
```

## 4. Handoff register

| # | From | To | Artifact (where it lives) | Must contain | Check before proceeding |
|---|---|---|---|---|---|
| H1 | Owner | Orchestrator | The request (chat) | Goal, constraints, what is out of scope | Orchestrator restates scope; ambiguity goes back to the owner |
| H2 | Product manager | Owner | Proposal and scenarios (spec folder) | Requirements, Given/When/Then scenarios, out of scope | Owner approval; every scenario is testable |
| H3 | Architect / UX / orchestrator | Planner | Design (design file) | ASCII change diagram, placement in the architecture (layer, module, public interface), data and API contract, visual direction if the look changes | Stack unchanged, or owner approved the change |
| H4 | Planner | Owner | Chunk map in the tasks file | Per chunk: `owner:`, `tags:`, `gates:`, tasks, dependencies | Each chunk is buildable, verifiable and committable alone; every scenario maps to a task; owner approves |
| H5 | Orchestrator | Owner agent | Delegation prompt (preamble from `process.yaml`) | Change path, chunk tasks and scenarios, files to read first, pinned stack and exclusions, source of truth, green commands, scope limit, required return | Agent restates the module layout before coding |
| H6 | Owner agent | Orchestrator | Report plus the code diff | Verdict (DONE/BLOCKED), commands run and results, standards self-check, open items | Evidence present; self-check present; lint, types, tests, build green |
| H7 | Orchestrator | Owner agent | Findings from a failed gate | Findings with rule IDs and `file:line`, which gate failed | Only the failed gate is re-run; cycle count under the cap |
| H8 | Gate agents | Orchestrator, then Owner | `docs/*-report.md` and verdicts | PASS/FAIL, evidence, findings table, severity | No finding at or above `fail_on`; owner confirms the chunk boundary |
| H9 | Orchestrator | devops-engineer | Accepted commits on the main branch | Change path, environments, rollback plan | All chunks accepted; CI green |
| H10 | devops-engineer | Owner | Deploy plan and smoke-test result | What will deploy, rollback, result | Explicit owner approval in the current conversation; cannot be configured away |

## 5. How the configuration reaches the agents

```
 docs/team/process.yaml ──(validate_process.py)──► OK / ERROR list
        │
        │  setup-workflow renders (install or sync)
        ├────────────► framework rules home ──► delegation preamble, gate rules,
        │               OpenSpec: openspec/config.yaml            fix-loop cap,
        │               Spec Kit: constitution.md                 owner/tags/gates format
        │               Notion:   CLAUDE.md block
        │               plain:    docs/workflow.md
        ├────────────► CLAUDE.md managed block ──► pointers + pinned stack
        └────────────► docs/team/operating-model.md  (copied; policy)
                       docs/engineering-standards.md (copied; rule IDs)

 At run time:   orchestrator reads rules home + process.yaml
                    └─► builds each H5 delegation prompt
                           └─► agent reads operating-model + standards + CLAUDE.md
                                  └─► agent returns H6 (dev) or H8 (gate) in the required shape
```

## 6. Worked example: chunk "Contact form" (tags: forms, api, personal-data, ui)

```
 H4 chunk map line:
   Chunk 3: Contact form  owner: backend-dev (+ frontend-dev sub-chunk 3b)
   tags: forms, api, personal-data, ui
   gates = always[code-reviewer, qa-engineer]
         + forms[security-compliance]
         + api[security-compliance]
         + personal-data[security-compliance, compliance-reviewer]
         + ui[accessibility-tester]
         = code-reviewer, qa-engineer, security-compliance, compliance-reviewer, accessibility-tester

 3a  backend-dev  ──H6──►  schema (shared), service, email adapter, handler  ─┐
                                                                              ├─► orchestrator
 3b  frontend-dev ──H6──►  form UI using the same schema, tests              ─┘
         (3b starts after 3a, because the schema and contract come from 3a)

 Gates run on the combined diff, in parallel (read-only, each writes its own report):

   code-reviewer ─► STRUCT-3 handler only composes? TYPE-2 one shared schema? ──┐
   qa-engineer ───► scenarios: invalid email, honeypot, send failure ──────────┤
   security ──────► input validation, secrets only in env, rate limiting ──────┤──► H8
   compliance ────► consent text, retention, third parties named ──────────────┤
   accessibility ─► labels, errors announced, keyboard flow ───────────────────┘

   one FAIL (Major) ──H7──► owner agent fixes ──► re-run that gate only ──► PASS
   all PASS ──► chunk report to owner ──► owner "go" ──► next chunk
```

## 7. The chain that drives the code

```
 PRINCIPLES  docs/team/principles.md      stack-neutral, change with the plugin
     │ interpreted by
     ▼
 ARCHITECTURE SPEC  docs/architecture.md  version N, owner-approved ◄── proposal (H3-style):
     │ derives                              layers, modules, limits, patterns     version bump,
     ▼                                      migration table                       migration plan
 STANDARDS  docs/engineering-standards.md  architecture_version = N, rules cite [P-...]
     │ read first by
     ▼
 AGENTS ──► CODE ──► code-reviewer (fails new code that breaks version N; lists legacy scope as pending migration)
```

## 8. After every delegation: guardrail verification

```
 owner agent returns (H6)                 gate agent returns (H8)
        │                                        │
        ▼                                        ▼
 ┌────────────────────────────────────────────────────────────────┐
 │ ORCHESTRATOR runs, before accepting anything:                  │
 │   check_scope.py     agent changed only files in its allowlist │
 │   validate_return.py verdict token, sections, evidence, tasks, │
 │                      findings consistent, rule IDs real        │
 └──────────────┬──────────────────────────────┬──────────────────┘
        all pass │                              │ any violation
                 ▼                              ▼
      continue: gates (H8) or accept     treated as a FAILED GATE for that agent
                                         ──► back to the agent with the output (H7)
                                         ──► max_fix_cycles, then stop and report to the owner
```
