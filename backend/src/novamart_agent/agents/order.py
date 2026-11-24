"""The order agent: the only holder of the two order tools besides the guard (ARCH-MOD-5)."""

from google.adk.agents import LlmAgent

from novamart_agent.agents._common import model_retry
from novamart_agent.agents.callbacks import make_order_after_tool, make_usage_callback
from novamart_agent.agents.deps import ModelSpec, PipelineDeps
from novamart_agent.prompts import ORDER_INSTRUCTION
from novamart_agent.security.callbacks import make_before_tool_callback
from novamart_agent.tools import make_check_return_eligibility, make_get_order_status

NAME = "order"


def build_order(model: ModelSpec, deps: PipelineDeps) -> LlmAgent:
    """Order agent: the tools call the guard first; the after-tool callback halts at the result."""
    settings = deps.settings
    return LlmAgent(
        name=NAME,
        model=model,
        instruction=ORDER_INSTRUCTION,
        tools=[
            make_get_order_status(deps.guard),
            make_check_return_eligibility(deps.guard, deps.documents, deps.today),
        ],
        before_tool_callback=[make_before_tool_callback(deps.audit)],
        after_tool_callback=make_order_after_tool(),
        after_model_callback=[make_usage_callback(NAME, settings.model)],
        retry_config=model_retry(settings),
    )
