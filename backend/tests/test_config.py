"""Task 1.2: model IDs and prices are configuration (ARCH-CFG-1, design D6 and D17)."""

import pytest

from novamart_agent.config import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_MODEL,
    load_settings,
)


def test_defaults_are_provisional_ids_and_show_cost_on(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("NOVAMART_MODEL", "NOVAMART_EMBEDDING_MODEL", "NOVAMART_SHOW_COST"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("NOVAMART_PRICE_TABLE", raising=False)
    settings = load_settings()
    assert settings.model == DEFAULT_MODEL
    assert settings.embedding_model == DEFAULT_EMBEDDING_MODEL == "gemini-embedding-001"
    assert settings.show_cost is True
    assert settings.embedding_model in settings.prices


def test_env_overrides_model_ids_and_hides_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOVAMART_MODEL", "m-x")
    monkeypatch.setenv("NOVAMART_SHOW_COST", "false")
    monkeypatch.setenv("NOVAMART_PRICE_TABLE", '{"m-x": [1, 2]}')
    settings = load_settings()
    assert settings.model == "m-x"
    assert settings.show_cost is False
    assert settings.prices["m-x"].output_per_m == 2.0
    assert "gemini-embedding-001" not in settings.prices


def test_malformed_price_table_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOVAMART_PRICE_TABLE", "[1]")
    with pytest.raises(ValueError):
        load_settings()


@pytest.mark.parametrize("table", ['{"m": [1]}', '{"m": ["a", "b"]}', '{"m": 5}', '{"m": null}'])
def test_malformed_price_pair_names_the_entry(monkeypatch: pytest.MonkeyPatch, table: str) -> None:
    monkeypatch.setenv("NOVAMART_PRICE_TABLE", table)
    with pytest.raises(ValueError, match="'m'"):
        load_settings()


def test_retrieval_threshold_and_top_k_have_defaults_and_env_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NOVAMART_SIMILARITY_THRESHOLD", raising=False)
    monkeypatch.delenv("NOVAMART_TOP_K", raising=False)
    settings = load_settings()
    assert (settings.similarity_threshold, settings.top_k) == (0.6, 3)
    monkeypatch.setenv("NOVAMART_SIMILARITY_THRESHOLD", "0.75")
    monkeypatch.setenv("NOVAMART_TOP_K", "5")
    settings = load_settings()
    assert (settings.similarity_threshold, settings.top_k) == (0.75, 5)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("NOVAMART_SIMILARITY_THRESHOLD", "high"),
        ("NOVAMART_SIMILARITY_THRESHOLD", "1.5"),
        ("NOVAMART_TOP_K", "0"),
        ("NOVAMART_TOP_K", "three"),
        ("NOVAMART_MAX_QUERY_CHARS", "0"),
        ("NOVAMART_MAX_QUERY_CHARS", "long"),
    ],
)
def test_invalid_retrieval_settings_fail_loudly(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        load_settings()
