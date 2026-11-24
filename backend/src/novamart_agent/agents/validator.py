"""The validator agent: judge rubric coverage of the retrieved chunks. No tools (D11)."""

from google.adk.agents import LlmAgent

from novamart_agent.agents._common import model_retry
from novamart_agent.agents.callbacks import make_usage_callback
from novamart_agent.agents.deps import ModelSpec
from novamart_agent.agents.schemas import VerdictSchema
from novamart_agent.config import Settings
from novamart_agent.prompts import VALIDATOR_INSTRUCTION

NAME = "validator"


def build_validator(model: ModelSpec, settings: Settings) -> LlmAgent:
    """Validator: its verdict can only lower confidence or ask for a rewrite (ERR-4)."""
    return LlmAgent(
        name=NAME,
        model=model,
        instruction=VALIDATOR_INSTRUCTION,
        output_schema=VerdictSchema,
        after_model_callback=[make_usage_callback(NAME, settings.model)],
        retry_config=model_retry(settings),
    )
