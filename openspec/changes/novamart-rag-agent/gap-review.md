# Gap review: novamart-rag-agent

**Verdict: AMBER**
Reviewed together: novamart-rag-agent
Artifact hash: `5addb9169fee52fc799e7ed2019130e42d5451a8dcc5fcdd96935a99d4979952`

Stopped because: only_decisions

## Rounds

- Round 1: 0 blocking, 5 open decisions, 5 auto-fixes
- Round 2: 2 blocking, 4 open decisions, 0 auto-fixes

Dropped findings: 1

- AG-42: quote missing: text not found at openspec/changes/novamart-rag-agent/tasks.md:93

## Findings

### OQ-1 (ambiguity, clarifying, decision, open)

Open question left unresolved: How does Gemini Enterprise pass end-user identity to an A2A-registered agent? A production spike item for the note, not a prototype task.

> - How does Gemini Enterprise pass end-user identity to an A2A-registered agent? A production spike item for the note, not a prototype task. Kept open by owner decision (2026-11-23); no prototype task depends on it.  
> `openspec/changes/novamart-rag-agent/design.md:190`

**Question:** Design of 'novamart-rag-agent' leaves this open: How does Gemini Enterprise pass end-user identity to an A2A-registered agent? A production spike item for the note, not a prototype task. Kept open by owner decision (2026-11-23); no prototype task de How should it be settled?

- (recommended) **Decide it now**: Choose an answer now and record it in the design, so no task waits on it.
- **Keep it open**: Leave it open and mark the dependent tasks as not startable until it is answered.

### AG-40 (coverage, blocking, decision, open)

The cost callback must skip cache hits, but search_policy's result is specified without any cache-hit indicator, and nothing owns the ordering of the two after-tool callbacks on retrieval (halt for no_answer, embedding estimate).

> The callback adds the record only when the result is not a cache hit, so cache hits cost nothing.  
> `openspec/changes/novamart-rag-agent/design.md:156`
> Implement `search_policy` returning chunks, document IDs, section headings, file paths, `doc_type` and scores, or `no_answer` below the configurable threshold  
> `openspec/changes/novamart-rag-agent/tasks.md:61`
> An after-tool callback on those two agents recognises the status, stores the result in state, and sets the tool context's `skip_summarization`  
> `openspec/changes/novamart-rag-agent/design.md:134`

**Question:** The retrieval agent needs an after-tool callback that appends a query-embedding cost estimate unless the query embedding was a cache hit. The search_policy result in task 4.2 carries only chunks, ids, headings, paths, doc_type and scores, so the callback cannot tell a hit from a miss. A second after-tool callback on the same agent halts the turn on no_answer, and the no_answer path still embeds the query and so still costs money. How should the cache-hit signal reach the callback, and who owns the order and combination of the two callbacks on retrieval?

- (recommended) **Cache-hit flag in tool result, one combined callback**: search_policy returns an extra embedding_cache_hit field (set by the rag embedder, no ADK import) in every result including no_answer. One combined after-tool callback on retrieval records the embedding estimate first, then does the halt. Add it to 4.2 and 7.3/7.6 verification.
- **Embedder records hit/miss in per-turn state**: The embedder records hit/miss in a per-turn structure that the callback reads, instead of a field in the model-visible tool result.

### AG-41 (behavior, blocking, decision, open)

On a normal (successful) eligibility result nothing stores the policy document id where the orchestrator can read it; the halt callback stores only the deterministic statuses, yet D15 has the orchestrator build the order-route Sources entry from that id.

> On the order route there are no retrieved chunks: code builds the Sources entry from the policy document id returned by `check_return_eligibility`  
> `openspec/changes/novamart-rag-agent/design.md:145`
> For `no_answer` (C), `not_found` (D) and `not_determinable` (F) that extra call must not happen. An after-tool callback on those two agents recognises the status, stores the result in state  
> `openspec/changes/novamart-rag-agent/design.md:134`
> the orchestrator appends the order-route Sources entry from the 6.4 loader  
> `openspec/changes/novamart-rag-agent/tasks.md:94`

**Question:** On the order route the orchestrator must append a Sources entry from the policy document id that check_return_eligibility returns. The only callback described as storing tool results in state acts on no_answer, not_found and not_determinable, so for a successful eligibility result the id is only inside the order agent's model conversation. How does the orchestrator obtain the id without trusting model-written text?

- (recommended) **Order after-tool callback stores success result in state**: The order agent's after-tool callback also stores the structured eligibility result (policy id and parameters) in state on success; the orchestrator reads it from state. Extend D15 and 7.4 with a test that the id comes from the tool result, not model output.
- **Orchestrator parses order agent events**: The orchestrator reads the tool response event from the order agent's emitted events.

### AG-43 (ambiguity, clarifying, decision, open)

Denial parity is tested on the order agent alone, but the spec and D17 promise equal call counts on the whole turn; a malformed id could be routed by intake to the clarify route (case A) rather than reach the order tool, which would change the call count.

> Ask exactly one question, end the turn. At most one clarification per user question (counter in state), then proceed with best effort or decline.  
> `openspec/changes/novamart-rag-agent/design.md:125`
> A malformed id is rejected the same way, with no lookup.  
> `openspec/changes/novamart-rag-agent/design.md:128`
> both replies show the same call count and the same code-produced text  
> `openspec/changes/novamart-rag-agent/specs/cost-reporting/spec.md:52`

**Question:** Intake can route to clarify when an order id is missing; a malformed id such as '10x2' is neither clearly missing nor valid. Where is a malformed id rejected: by intake or precheck (before the order agent, so a different call count from a nonexistent order), or only inside the order tool (so the whole turn has the same calls as a nonexistent order)? And should the 7.6 parity test run the full orchestrated turn, not only the order agent?

- (recommended) **Reject malformed id in the order tool only**: Intake never treats a malformed id as missing; it routes to order, the tool rejects it. Parity test runs the full orchestrator with a stub model for all three causes and compares whole-turn call counts.
- **Decide all denials in code before intake**: Reject malformed ids in code before intake and make the non-malformed denials match that call count by also deciding them in code (changes the specified tool-halt design).

## Readiness

- 1. Setup and verification of assumptions: ready
- 2. Synthetic data: ready
- 3. Access control: ready
- 4. Retrieval: blocked (tasks 4.2 wait on AG-40)
- 5. Order tools: ready
- 6. Pipeline logic (pure, no ADK imports): blocked (tasks 6.4 wait on AG-41)
- 7. Pipeline agents and orchestrator: blocked (tasks 7.3, 7.4, 7.6 wait on AG-40, AG-41, AG-43)
- 8. Evaluation: ready
- 9. Documentation and production note: ready
- 10. Final check: ready

## Auto-fixes applied

- AG-4: `openspec/changes/novamart-rag-agent/tasks.md`: `current architecture version (v5)` -> `current architecture version (v6)`
- AG-5: `openspec/changes/novamart-rag-agent/proposal.md`: `One root agent with three tools:` -> `A staged pipeline of single-purpose agents (design D1) with three tools:`
- AG-13: `openspec/changes/novamart-rag-agent/design.md`: `be set at build and tuned in task 8.4; no task waits.` -> `be set at build and tuned in task 8.5; no task waits.`
- AG-19: `openspec/changes/novamart-rag-agent/proposal.md`: `- `production-note`: the one-page production plan for NovaMart on Google's enterprise stack.` -> `- `production-note`: the one-page production plan for NovaMart on Google's enterprise stack.
- `cost-reporting`: per-answer and per-session cost computed by code from recorded usage, shown behind a flag.`
- AG-24: `openspec/changes/novamart-rag-agent/design.md`: `Run it before `docs/architecture.md` v4 is approved.` -> `Run it before `docs/architecture.md` (currently v6) is approved.`
