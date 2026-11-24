"""The retrieval agent: one `search_policy` call per pass (ARCH-MOD-5, D11, D13)."""

from google.adk.agents import LlmAgent

from novamart_agent.agents._common import model_retry
from novamart_agent.agents.callbacks import (
    make_query_hint_callback,
    make_retrieval_after_tool,
    make_usage_callback,
)
from novamart_agent.agents.deps import ModelSpec, PipelineDeps
from novamart_agent.prompts import RETRIEVAL_INSTRUCTION
from novamart_agent.security.callbacks import make_before_tool_callback
from novamart_agent.tools import make_search_policy

NAME = "retrieval"


def build_retrieval(model: ModelSpec, deps: PipelineDeps) -> LlmAgent:
    """Retrieval: the allowlist and audit callback runs before the hint override, and one
    combined after-tool callback records the embedding estimate then halts."""
    settings = deps.settings
    return LlmAgent(
        name=NAME,
        model=model,
        instruction=RETRIEVAL_INSTRUCTION,
        tools=[make_search_policy(deps.search)],
        before_tool_callback=[make_before_tool_callback(deps.audit), make_query_hint_callback()],
        after_tool_callback=make_retrieval_after_tool(settings),
        after_model_callback=[make_usage_callback(NAME, settings.model)],
        retry_config=model_retry(settings),
    )
