"""Settings loaded once from the environment (the only module that reads it, ARCH-CFG-1)."""

import json
import math
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")

# PipelineSettings field name -> environment variable, for the integer-valued tuning values.
_PIPELINE_INT_VARS: dict[str, str] = {
    "max_iterations": "NOVAMART_MAX_ITERATIONS",
    "rewrite_max_chars": "NOVAMART_REWRITE_MAX_CHARS",
    "clarification_cap": "NOVAMART_CLARIFICATION_CAP",
    "max_message_chars": "NOVAMART_MAX_MESSAGE_CHARS",
    "rubric_max_criteria": "NOVAMART_RUBRIC_MAX_CRITERIA",
    "criterion_max_chars": "NOVAMART_CRITERION_MAX_CHARS",
    "embedding_chars_per_token": "NOVAMART_EMBEDDING_CHARS_PER_TOKEN",
    "model_retry_attempts": "NOVAMART_MODEL_RETRY_ATTEMPTS",
    "model_retry_delay_seconds": "NOVAMART_MODEL_RETRY_DELAY_SECONDS",
}

# Defaults from design D6 candidates; task 1.2 (owner-run, tasks.md) confirms or replaces them.
# Both IDs answered a live call on the free AI Studio key on 2026-11-24 (task 1.2). Free-tier rate
# limits are shown per key in AI Studio, not published per model; they are not recorded here.
DEFAULT_MODEL = "gemini-3.6-flash"
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"


# backend/data, next to backend/src (ARCH-MOD-1); override with NOVAMART_DATA_DIR.
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
# Where the documents are shown to be in a Sources list (a display label: `adk web` cannot open
# local files, design D15). Override with NOVAMART_DOCS_PATH_LABEL when the data dir moves.
DEFAULT_DOCS_PATH_LABEL = "backend/data/docs"
# Denied or malformed order lookups allowed per session before it is throttled (task 3.4).
DEFAULT_DENIED_LOOKUP_LIMIT = 5
# Retrieval gate (design D4). VERIFY: the threshold is a starting value for gemini-embedding-001
# cosine scores; it is tuned on the eval set (tasks chunk 8), not proven.
DEFAULT_SIMILARITY_THRESHOLD = 0.6
DEFAULT_TOP_K = 3
# Longest policy-search query embedded; longer ones are answered no_answer without a call.
DEFAULT_MAX_QUERY_CHARS = 500


@dataclass(frozen=True)
class ModelPrice:
    """USD per million tokens. An embedding model has output 0.0."""

    input_per_m: float
    output_per_m: float


# VERIFY: every figure below was read from the AI Studio pricing page on 2026-11-23 (paid tier,
# standard). The gemini-3.6-flash rate is promotional until 2026-12-31 and becomes 1.50 / 7.50 on
# 2027-01-01. Re-check against the published page before relying on the cost line (design D17).
# A model ID with no entry means "cost unavailable", never 0.
DEFAULT_PRICES: dict[str, ModelPrice] = {
    "gemini-3.6-flash": ModelPrice(0.75, 3.75),
    "gemini-3.5-flash-lite": ModelPrice(0.30, 2.50),
    "gemini-embedding-001": ModelPrice(0.15, 0.0),
}


@dataclass(frozen=True)
class ConfidenceWeights:
    """Weights of the three composite inputs (design D12). They must sum to 1."""

    coverage: float = 0.5
    score: float = 0.3
    llm: float = 0.2

    def __post_init__(self) -> None:
        parts = (self.coverage, self.score, self.llm)
        if any(not 0.0 <= p <= 1.0 for p in parts):
            raise ValueError("confidence weights must each be between 0 and 1")
        if not math.isclose(sum(parts), 1.0, abs_tol=1e-6):
            raise ValueError("confidence weights must sum to 1")


@dataclass(frozen=True)
class BandThresholds:
    """Composite at or above `high` is High, at or above `medium` is Medium, else Low."""

    medium: float = 0.5
    high: float = 0.75

    def __post_init__(self) -> None:
        if not 0.0 < self.medium < self.high <= 1.0:
            raise ValueError("band thresholds must satisfy 0 < medium < high <= 1")


@dataclass(frozen=True)
class PipelineSettings:
    """Pipeline tuning values (ARCH-CFG-1, D11, D12). Defaults are build-time starting values,
    tuned on the eval set (task 8.5); they are configuration, not constants (CONV-1)."""

    loop_exit_threshold: float = 0.7
    weights: ConfidenceWeights = field(default_factory=ConfidenceWeights)
    bands: BandThresholds = field(default_factory=BandThresholds)
    max_iterations: int = 2
    rewrite_max_chars: int = 200
    clarification_cap: int = 1
    max_message_chars: int = 2000
    rubric_max_criteria: int = 6
    criterion_max_chars: int = 200
    embedding_chars_per_token: int = 4
    # Attempts per agent node on a model failure (ARCH-ERR-1) and the first wait between them,
    # doubling each time. The free tier limits requests per minute, so the waits (8, 16, 32
    # seconds) must be long enough to outlast a per-minute window.
    model_retry_attempts: int = 4
    model_retry_delay_seconds: int = 8

    def __post_init__(self) -> None:
        if not 0.0 < self.loop_exit_threshold <= 1.0:
            raise ValueError("loop exit threshold must be between 0 (exclusive) and 1")
        counts = (
            self.max_iterations,
            self.rewrite_max_chars,
            self.clarification_cap,
            self.max_message_chars,
            self.rubric_max_criteria,
            self.criterion_max_chars,
            self.embedding_chars_per_token,
            self.model_retry_attempts,
            self.model_retry_delay_seconds,
        )
        if any(c < 1 for c in counts):
            raise ValueError("pipeline counts and length caps must be at least 1")


@dataclass(frozen=True)
class Settings:
    """Runtime configuration."""

    model: str
    embedding_model: str
    show_cost: bool
    user: str | None = None
    data_dir: Path = DEFAULT_DATA_DIR
    denied_lookup_limit: int = DEFAULT_DENIED_LOOKUP_LIMIT
    prices: dict[str, ModelPrice] = field(default_factory=dict)
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    top_k: int = DEFAULT_TOP_K
    max_query_chars: int = DEFAULT_MAX_QUERY_CHARS
    docs_path_label: str = DEFAULT_DOCS_PATH_LABEL
    pipeline: PipelineSettings = field(default_factory=PipelineSettings)


def _parse_prices(raw: str | None) -> dict[str, ModelPrice]:
    """Parse NOVAMART_PRICE_TABLE: JSON {"model-id": [input_per_m, output_per_m]}."""
    if not raw:
        return dict(DEFAULT_PRICES)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("NOVAMART_PRICE_TABLE must be a JSON object")
    table: dict[str, ModelPrice] = {}
    for model_id, pair in parsed.items():
        try:
            table[str(model_id)] = ModelPrice(float(pair[0]), float(pair[1]))
        except (TypeError, ValueError, IndexError, KeyError) as exc:
            raise ValueError(
                f"NOVAMART_PRICE_TABLE entry {model_id!r} must be [input_per_m, output_per_m] "
                "with two numbers"
            ) from exc
    return table


def _parse_positive_int(name: str, raw: str | None, default: int) -> int:
    """Parse an environment value that must be an integer of at least 1."""
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer") from None
    if value < 1:
        raise ValueError(f"{name} must be at least 1")
    return value


def _parse_threshold(raw: str | None) -> float:
    """Parse NOVAMART_SIMILARITY_THRESHOLD: a number between 0 and 1 inclusive."""
    if raw is None or not raw.strip():
        return DEFAULT_SIMILARITY_THRESHOLD
    try:
        value = float(raw)
    except ValueError:
        raise ValueError("NOVAMART_SIMILARITY_THRESHOLD must be a number") from None
    if not 0.0 <= value <= 1.0:
        raise ValueError("NOVAMART_SIMILARITY_THRESHOLD must be between 0 and 1")
    return value


def _parse_unit_float(name: str, raw: str | None, default: float) -> float:
    """Parse an environment value that must be a number in [0, 1]."""
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number") from None
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return value


def _named(name: str, build: Callable[[], T]) -> T:
    """Run a validating constructor and name the environment group in any failure."""
    try:
        return build()
    except ValueError as exc:
        raise ValueError(f"{name}: {exc}") from None


def _load_pipeline(env: Mapping[str, str]) -> PipelineSettings:
    """Read the pipeline tuning values; every default comes from the dataclasses (CONV-1)."""
    base = PipelineSettings()
    ints = {
        name: _parse_positive_int(var, env.get(var), getattr(base, name))
        for name, var in _PIPELINE_INT_VARS.items()
    }

    def unit(var: str, default: float) -> float:
        return _parse_unit_float(var, env.get(var), default)

    weights = _named(
        "NOVAMART_WEIGHT_*",
        lambda: ConfidenceWeights(
            coverage=unit("NOVAMART_WEIGHT_COVERAGE", base.weights.coverage),
            score=unit("NOVAMART_WEIGHT_SCORE", base.weights.score),
            llm=unit("NOVAMART_WEIGHT_LLM", base.weights.llm),
        ),
    )
    bands = _named(
        "NOVAMART_BAND_*",
        lambda: BandThresholds(
            medium=unit("NOVAMART_BAND_MEDIUM", base.bands.medium),
            high=unit("NOVAMART_BAND_HIGH", base.bands.high),
        ),
    )
    threshold = unit("NOVAMART_LOOP_EXIT_THRESHOLD", base.loop_exit_threshold)
    return _named(
        "pipeline settings",
        lambda: PipelineSettings(
            loop_exit_threshold=threshold,
            weights=weights,
            bands=bands,
            max_iterations=ints["max_iterations"],
            rewrite_max_chars=ints["rewrite_max_chars"],
            clarification_cap=ints["clarification_cap"],
            max_message_chars=ints["max_message_chars"],
            rubric_max_criteria=ints["rubric_max_criteria"],
            criterion_max_chars=ints["criterion_max_chars"],
            embedding_chars_per_token=ints["embedding_chars_per_token"],
            model_retry_attempts=ints["model_retry_attempts"],
            model_retry_delay_seconds=ints["model_retry_delay_seconds"],
        ),
    )


def load_settings() -> Settings:
    """Read settings from environment variables."""
    env = os.environ
    return Settings(
        model=env.get("NOVAMART_MODEL", DEFAULT_MODEL),
        embedding_model=env.get("NOVAMART_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        show_cost=env.get("NOVAMART_SHOW_COST", "true").strip().lower() != "false",
        user=(env.get("NOVAMART_USER") or "").strip() or None,
        data_dir=Path(env.get("NOVAMART_DATA_DIR") or DEFAULT_DATA_DIR),
        denied_lookup_limit=_parse_positive_int(
            "NOVAMART_DENIED_LOOKUP_LIMIT",
            env.get("NOVAMART_DENIED_LOOKUP_LIMIT"),
            DEFAULT_DENIED_LOOKUP_LIMIT,
        ),
        prices=_parse_prices(env.get("NOVAMART_PRICE_TABLE")),
        similarity_threshold=_parse_threshold(env.get("NOVAMART_SIMILARITY_THRESHOLD")),
        top_k=_parse_positive_int("NOVAMART_TOP_K", env.get("NOVAMART_TOP_K"), DEFAULT_TOP_K),
        max_query_chars=_parse_positive_int(
            "NOVAMART_MAX_QUERY_CHARS",
            env.get("NOVAMART_MAX_QUERY_CHARS"),
            DEFAULT_MAX_QUERY_CHARS,
        ),
        docs_path_label=(env.get("NOVAMART_DOCS_PATH_LABEL") or "").strip().rstrip("/")
        or DEFAULT_DOCS_PATH_LABEL,
        pipeline=_load_pipeline(env),
    )
