"""Agent wiring: the five agents and the orchestrator `Workflow` graph (ARCH-LAYER-1).

Public names are exposed here (ARCH-MOD-2); other packages import only these.
"""

from novamart_agent.agents.deps import AgentModels, ModelSpec, PipelineDeps, build_deps
from novamart_agent.agents.orchestrator import ORCHESTRATOR_NAME, build_orchestrator

__all__: list[str] = [
    "ORCHESTRATOR_NAME",
    "AgentModels",
    "ModelSpec",
    "PipelineDeps",
    "build_deps",
    "build_orchestrator",
]
