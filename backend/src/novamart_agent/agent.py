"""Root agent wiring only: the orchestrator `Workflow` that adk web and adk run load."""

from .agents import AgentModels, build_deps, build_orchestrator
from .config import load_settings

_settings = load_settings()

root_agent = build_orchestrator(build_deps(_settings), AgentModels.uniform(_settings.model))
