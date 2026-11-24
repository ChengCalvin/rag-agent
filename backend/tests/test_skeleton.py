"""Task 1.1 / ARCH-MOD-2: skeleton packages exist and expose a public interface."""

import importlib

import pytest

PACKAGES = ["agents", "prompts", "pipeline", "security", "tools", "adapters", "rag"]


@pytest.mark.parametrize("name", PACKAGES)
def test_subpackage_exposes_public_names_list(name: str) -> None:
    """Each sub-package declares __all__ in __init__.py (ARCH-MOD-2)."""
    module = importlib.import_module(f"novamart_agent.{name}")
    assert isinstance(module.__all__, list)


def test_root_agent_is_discoverable_by_adk() -> None:
    """adk web backend/src lists the agent: the package exposes root_agent via agent."""
    module = importlib.import_module("novamart_agent")
    assert module.agent.root_agent.name == "novamart_assistant"
