"""Field readers shared by the data loaders (LAYER-4, TYPE-2).

Each reader takes an untrusted mapping parsed from YAML or JSON and returns a typed value or
raises `DataLoadError`. Error messages carry the source name and the field name, never the value.
"""

from collections.abc import Mapping
from datetime import date

from novamart_agent.errors import DataLoadError


def as_mapping(value: object, source: str) -> Mapping[str, object]:
    """Return `value` as a string-keyed mapping or raise."""
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise DataLoadError(f"{source}: expected an object")
    return value


def as_list(value: object, source: str) -> list[object]:
    """Return `value` as a list or raise."""
    if not isinstance(value, list):
        raise DataLoadError(f"{source}: expected a list")
    return value


def require_str(data: Mapping[str, object], key: str, source: str) -> str:
    """Return a non-empty string field or raise."""
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DataLoadError(f"{source}: field '{key}' must be a non-empty string")
    return value


def optional_str(data: Mapping[str, object], key: str, source: str) -> str | None:
    """Return a string field, or None when absent or null."""
    if data.get(key) is None:
        return None
    return require_str(data, key, source)


def require_int(data: Mapping[str, object], key: str, source: str) -> int:
    """Return an integer field (booleans are rejected) or raise."""
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise DataLoadError(f"{source}: field '{key}' must be an integer")
    return value


def optional_date(data: Mapping[str, object], key: str, source: str) -> date | None:
    """Return an ISO date field (YYYY-MM-DD), or None when absent or null."""
    raw = optional_str(data, key, source)
    if raw is None:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise DataLoadError(f"{source}: field '{key}' must be an ISO date") from None


def require_date(data: Mapping[str, object], key: str, source: str) -> date:
    """Return an ISO date field or raise."""
    value = optional_date(data, key, source)
    if value is None:
        raise DataLoadError(f"{source}: field '{key}' must be an ISO date")
    return value
