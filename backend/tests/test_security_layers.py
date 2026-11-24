"""Layer rules for access control (ARCH-LAYER-3, ARCH-CFG-1) and its new settings."""

from pathlib import Path

import pytest

from novamart_agent.config import DEFAULT_DENIED_LOOKUP_LIMIT, load_settings

SECURITY = Path(__file__).resolve().parent.parent / "src" / "novamart_agent" / "security"


def test_only_callbacks_py_imports_adk() -> None:
    """LAYER-3 files (principal, guard, audit, decision) have no ADK imports."""
    for path in SECURITY.glob("*.py"):
        imports_adk = "google.adk" in path.read_text(encoding="utf-8")
        assert imports_adk == (path.name == "callbacks.py"), path.name


def test_only_config_reads_the_environment() -> None:
    src = SECURITY.parent
    for path in src.rglob("*.py"):
        if path.name != "config.py":
            text = path.read_text(encoding="utf-8")
            assert "os.environ" not in text and "getenv" not in text, path.name


def test_settings_defaults_for_identity_and_throttle(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("NOVAMART_USER", "NOVAMART_DATA_DIR", "NOVAMART_DENIED_LOOKUP_LIMIT"):
        monkeypatch.delenv(name, raising=False)
    settings = load_settings()
    assert settings.user is None
    assert settings.denied_lookup_limit == DEFAULT_DENIED_LOOKUP_LIMIT
    assert (settings.data_dir / "users.json").is_file()


def test_settings_read_user_and_limit_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NOVAMART_USER", " emp_store7 ")
    monkeypatch.setenv("NOVAMART_DENIED_LOOKUP_LIMIT", "2")
    settings = load_settings()
    assert settings.user == "emp_store7" and settings.denied_lookup_limit == 2


@pytest.mark.parametrize("raw", ["0", "-1", "many"])
def test_invalid_throttle_limit_is_rejected(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("NOVAMART_DENIED_LOOKUP_LIMIT", raw)
    with pytest.raises(ValueError):
        load_settings()
