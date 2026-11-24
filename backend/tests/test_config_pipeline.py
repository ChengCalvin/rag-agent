"""Task 6.1: pipeline settings are configuration, validated at load (ARCH-CFG-1, CONV-1).

The shipped defaults are checked against the invariants only (weights sum to 1, band thresholds
ordered, `max_iterations` is 2), never against the design's numbers (AG-15).
"""

import math
import os

import pytest

from novamart_agent.config import (
    BandThresholds,
    ConfidenceWeights,
    PipelineSettings,
    load_settings,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [n for n in os.environ if n.startswith("NOVAMART_")]:
        monkeypatch.delenv(name)


def test_shipped_defaults_load_and_satisfy_the_invariants() -> None:
    pipeline = load_settings().pipeline
    w = pipeline.weights
    assert math.isclose(w.coverage + w.score + w.llm, 1.0, abs_tol=1e-6)
    assert 0.0 < pipeline.bands.medium < pipeline.bands.high <= 1.0
    assert pipeline.max_iterations == 2
    assert 0.0 < pipeline.loop_exit_threshold <= 1.0
    assert pipeline.rewrite_max_chars >= 1
    assert pipeline.clarification_cap >= 1


def test_dataclass_defaults_are_the_loaded_defaults() -> None:
    assert load_settings().pipeline == PipelineSettings()


def test_valid_overrides_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOVAMART_MAX_ITERATIONS", "3")
    monkeypatch.setenv("NOVAMART_LOOP_EXIT_THRESHOLD", "0.9")
    monkeypatch.setenv("NOVAMART_WEIGHT_COVERAGE", "0.4")
    monkeypatch.setenv("NOVAMART_WEIGHT_SCORE", "0.4")
    monkeypatch.setenv("NOVAMART_WEIGHT_LLM", "0.2")
    monkeypatch.setenv("NOVAMART_BAND_MEDIUM", "0.4")
    monkeypatch.setenv("NOVAMART_BAND_HIGH", "0.8")
    monkeypatch.setenv("NOVAMART_REWRITE_MAX_CHARS", "120")
    monkeypatch.setenv("NOVAMART_CLARIFICATION_CAP", "2")
    pipeline = load_settings().pipeline
    assert pipeline.max_iterations == 3
    assert pipeline.loop_exit_threshold == 0.9
    assert (pipeline.weights.coverage, pipeline.weights.score) == (0.4, 0.4)
    assert (pipeline.bands.medium, pipeline.bands.high) == (0.4, 0.8)
    assert (pipeline.rewrite_max_chars, pipeline.clarification_cap) == (120, 2)


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("NOVAMART_WEIGHT_LLM", "0.5", "sum to 1"),  # 0.5 + 0.3 + 0.5
        ("NOVAMART_WEIGHT_COVERAGE", "1.5", "NOVAMART_WEIGHT_COVERAGE"),
        ("NOVAMART_WEIGHT_SCORE", "heavy", "NOVAMART_WEIGHT_SCORE"),
        ("NOVAMART_BAND_MEDIUM", "0.9", "medium < high"),  # medium above the default high
        ("NOVAMART_BAND_HIGH", "0.4", "medium < high"),  # high below the default medium
        ("NOVAMART_BAND_HIGH", "high", "NOVAMART_BAND_HIGH"),
        ("NOVAMART_LOOP_EXIT_THRESHOLD", "0", "exit threshold"),
        ("NOVAMART_LOOP_EXIT_THRESHOLD", "2", "NOVAMART_LOOP_EXIT_THRESHOLD"),
        ("NOVAMART_MAX_ITERATIONS", "0", "NOVAMART_MAX_ITERATIONS"),
        ("NOVAMART_MAX_ITERATIONS", "two", "NOVAMART_MAX_ITERATIONS"),
        ("NOVAMART_REWRITE_MAX_CHARS", "-5", "NOVAMART_REWRITE_MAX_CHARS"),
        ("NOVAMART_CLARIFICATION_CAP", "0", "NOVAMART_CLARIFICATION_CAP"),
    ],
)
def test_bad_pipeline_values_fail_at_load(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str, message: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=message):
        load_settings()


def test_invalid_values_fail_when_built_directly() -> None:
    with pytest.raises(ValueError):
        ConfidenceWeights(0.5, 0.5, 0.5)
    with pytest.raises(ValueError):
        BandThresholds(medium=0.8, high=0.8)
    with pytest.raises(ValueError):
        PipelineSettings(max_iterations=0)
