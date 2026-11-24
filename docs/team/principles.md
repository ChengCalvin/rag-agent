# Principles (stack-neutral, rarely change)

The top of the chain that drives code:

```
 PRINCIPLES (this file, stack-neutral)
      │ interpreted for the project by
      ▼
 ARCHITECTURE SPEC (docs/architecture.md, versioned, owner-approved)  ◄── changed only by proposal (P-EVOLVE)
      │ derives
      ▼
 ENGINEERING STANDARDS (docs/engineering-standards.md, rule IDs, each traced to a principle)
      │ enforced by
      ▼
 AGENTS + REVIEW + LINT  ──►  CODE
```

Code never defines the standard. If code and architecture disagree, the code is wrong, or a proposal is raised to change the architecture (`P-SPEC`, `P-EVOLVE`). Existing code is not precedent.

Each principle has an ID. Standards rules cite them as `[P-XXX]`, and the check fails on an unknown ID.

| ID | Principle | Why | What a reviewer looks for |
|---|---|---|---|
| `P-RESP` | Each module has one reason to change. Keep presentation, orchestration, business rules, data access, validation and integrations apart. | Small, testable, replaceable parts | A module doing two jobs; entry points containing logic |
| `P-DEP` | Dependencies point one way, from higher layers to lower. Modules talk only through their public interface. | Changes stay local; no cycles | Imports against the layer direction; reaching into another module's internals |
| `P-BOUND` | External input is parsed once, at the edge, into typed values. The inside trusts the types. | One place to get validation right | Unparsed input flowing inward; the same rule checked in several places |
| `P-EDGE` | Side effects (I/O, time, randomness, environment) live at the edges behind adapters; the core is pure. | Testability and swappable integrations | Core logic calling a third-party SDK or reading env directly |
| `P-REUSE` | Reuse before creating. Extract shared code on proven repetition, not speculation. | Less duplication, less premature abstraction | New code duplicating something that exists; shared code with one user |
| `P-ERR` | Errors are handled deliberately and shaped consistently. Nothing is swallowed. | Predictable failure, debuggable systems | Empty catches; ad-hoc error shapes |
| `P-SEC` | Secrets and personal data are never exposed: not in logs, URLs, client bundles or error messages. Least privilege everywhere. | Safety and legal duty | Sensitive values in logs or client code; broad permissions |
| `P-TEST` | Every requirement or scenario in the spec is traceable to a test, written against public interfaces. | Proof that the spec is met | A scenario with no test; tests of internals only |
| `P-SCOPE` | Change only what the work item requires. List adjacent improvements instead of making them. | Reviewable, reversible changes | Unrelated edits; new dependencies without justification |
| `P-CONFIG` | Configuration, secrets, user-facing text and design values each have one designated source. | No scattered constants | Hard-coded values that the architecture assigns to a source |
| `P-SPEC` | The spec leads. Requirements and architecture are the source; code follows them. | Intent stays authoritative | Behaviour or structure with no spec behind it |
| `P-EVOLVE` | Architecture and standards change only by versioned proposal, with a migration plan for existing code. | Improvement without drift or breakage | A new pattern introduced with no approved proposal |

## How principles scale

- Add a principle only when a recurring failure cannot be expressed as a rule under an existing one. Principles are versioned with the plugin; projects do not edit them.
- Projects improve by changing the **architecture spec** (section 11 of its template governs migration), then re-deriving the standards. See `operating-model.md`, "Evolving the architecture".
