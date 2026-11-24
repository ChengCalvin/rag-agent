<!-- product-team:begin -->
## Product team

- Process: `docs/team/process.yaml` (config) and `docs/team/operating-model.md` (policy, roles, handoffs; diagrams in `docs/team/process-diagrams.md`). Edit the config, then run `setup-workflow` in sync mode.
- Workflow: OpenSpec; specs and tasks live in `openspec/specs` and `openspec/changes`. Notion is not used for this repo.
- Architecture spec: `docs/architecture.md` drives the code; standards in `docs/engineering-standards.md` derive from it and are binding; `code-reviewer` cites rule IDs. Change the architecture only by proposal.
- Guardrails: `docs/team/guardrails.yaml` sets each agent's write scope and return shape; the orchestrator verifies both after every delegation (`docs/team/tools/`).
- Pinned stack: Python, Google ADK, Gemini (free AI Studio key), hand-rolled numpy retrieval, synthetic data only, run via adk web / adk run (not Vertex AI Search, RAG Engine, Gemini File Search). Agents must not change it.
<!-- product-team:end -->
