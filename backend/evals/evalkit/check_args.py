"""Typed readers for a check's JSON arguments (parsed once, at the boundary: TYPE-2)."""

from collections.abc import Mapping

from evalkit.errors import CaseError
from evalkit.observation import Observation, TurnObservation


def text(args: Mapping[str, object], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value:
        raise CaseError(f"check argument '{key}' must be a non-empty string")
    return value


def texts(args: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = args.get(key)
    ok = isinstance(value, list) and value and all(isinstance(v, str) and v for v in value)
    if not ok:
        raise CaseError(f"check argument '{key}' must be a non-empty list of strings")
    assert isinstance(value, list)
    return tuple(str(v) for v in value)


def turn_of(args: Mapping[str, object], obs: Observation) -> TurnObservation:
    """The turn a check reads: `turn` (default the last one)."""
    index = args.get("turn", -1)
    if not isinstance(index, int) or isinstance(index, bool):
        raise CaseError("check argument 'turn' must be an integer")
    try:
        return obs.turns[index]
    except IndexError:
        raise CaseError(f"check refers to turn {index} but the case has {len(obs.turns)}") from None


def turn_indexes(args: Mapping[str, object], obs: Observation) -> tuple[int, ...]:
    """The turns a parity check compares: `turns` (default all)."""
    raw = args.get("turns")
    if raw is None:
        return tuple(range(len(obs.turns)))
    if not isinstance(raw, list) or not all(isinstance(i, int) for i in raw):
        raise CaseError("check argument 'turns' must be a list of integers")
    return tuple(int(i) for i in raw)
