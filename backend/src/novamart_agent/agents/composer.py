"""The composer agent: write the reply body from the best attempt or the order records.

No tools (ARCH-MOD-5). Its text passes the diagram check in the after-model callback; Sources,
the band and the cost line are added by code afterwards (AGENT-3).
"""

from google.adk.agents import LlmAgent

from novamart_agent.agents._common import model_retry
from novamart_agent.agents.callbacks import make_diagram_check_callback, make_usage_callback
from novamart_agent.agents.deps import ModelSpec
from novamart_agent.config import Settings
from novamart_agent.prompts import COMPOSER_INSTRUCTION

NAME = "composer"


def build_composer(model: ModelSpec, settings: Settings) -> LlmAgent:
    """Composer: usage is counted first, then the check (a callback list stops at the first
    one that returns a response, so the counting one returns nothing)."""
    return LlmAgent(
        name=NAME,
        model=model,
        instruction=COMPOSER_INSTRUCTION,
        after_model_callback=[
            make_usage_callback(NAME, settings.model),
            make_diagram_check_callback(),
        ],
        retry_config=model_retry(settings),
    )
