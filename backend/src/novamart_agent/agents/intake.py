"""The intake agent: validate, classify and build the rubric. No tools (ARCH-MOD-5, D10)."""

from google.adk.agents import LlmAgent

from novamart_agent.agents._common import model_retry
from novamart_agent.agents.callbacks import make_usage_callback
from novamart_agent.agents.deps import ModelSpec
from novamart_agent.agents.schemas import RubricSchema
from novamart_agent.config import Settings
from novamart_agent.prompts import INTAKE_INSTRUCTION

NAME = "intake"


def build_intake(model: ModelSpec, settings: Settings) -> LlmAgent:
    """Intake: `output_schema` is the rubric; its reply is parsed again by code."""
    return LlmAgent(
        name=NAME,
        model=model,
        instruction=INTAKE_INSTRUCTION,
        output_schema=RubricSchema,
        after_model_callback=[make_usage_callback(NAME, settings.model)],
        retry_config=model_retry(settings),
    )
