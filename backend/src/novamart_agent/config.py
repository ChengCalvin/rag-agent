"""Settings loaded once from the environment (the only module that reads it)."""

import os
from dataclasses import dataclass

# Provisional default from design D6 candidates; task 1.2 confirms or replaces it.
DEFAULT_MODEL = "gemini-3.6-flash"


@dataclass(frozen=True)
class Settings:
    """Runtime configuration."""

    model: str


def load_settings() -> Settings:
    """Read settings from environment variables."""
    return Settings(model=os.environ.get("NOVAMART_MODEL", DEFAULT_MODEL))
