"""Root agent wiring. Tools, callbacks and prompts are added in later tasks."""

from google.adk.agents import Agent

from .config import load_settings

root_agent = Agent(
    name="novamart_assistant",
    model=load_settings().model,
    instruction="You are the NovaMart support assistant.",
)
