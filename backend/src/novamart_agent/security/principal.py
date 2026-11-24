"""Persona loading: users.json into typed principals (task 2.3; ARCH-BOUND-1 c).

Persona selection simulates authentication and is not authentication. Resolving the active
persona and converting it to and from session state is here (task 3.1); the ADK callback that
writes it is `security/callbacks.py`. No ADK imports (LAYER-3).
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from novamart_agent.errors import DataLoadError
from novamart_agent.models import STATE_PRINCIPAL, Principal
from novamart_agent.parsing import as_list, as_mapping, optional_str, require_str


def _parse_principal(raw: object, index: int) -> Principal:
    source = f"users.json[{index}]"
    data = as_mapping(raw, source)
    return Principal(
        user_id=require_str(data, "user_id", source),
        name=require_str(data, "name", source),
        role=require_str(data, "role", source),
        store_id=optional_str(data, "store_id", source),
        region=optional_str(data, "region", source),
    )


def load_principals(path: Path) -> dict[str, Principal]:
    """Load personas keyed by `user_id`; ids must be unique."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # `from None`: JSONDecodeError.doc holds the whole file; never chain it.
        raise DataLoadError(f"{path.name}: not valid JSON") from None
    root = as_mapping(document, path.name)
    principals: dict[str, Principal] = {}
    for index, raw in enumerate(as_list(root.get("users"), path.name)):
        principal = _parse_principal(raw, index)
        if principal.user_id in principals:
            raise DataLoadError(f"{path.name}: duplicate user_id")
        principals[principal.user_id] = principal
    return principals


class SessionState(Protocol):
    """The part of ADK session state used here (`State.get`, `State.__setitem__`).

    A plain dict satisfies it too, so pure code and tests need no ADK object.
    """

    def get(self, key: str, default: object = None, /) -> object: ...

    def __setitem__(self, key: str, value: object, /) -> None: ...


def resolve_principal(user_id: str | None, principals: Mapping[str, Principal]) -> Principal | None:
    """Return the persona selected by `NOVAMART_USER`, or None when unset or unknown."""
    if user_id is None:
        return None
    return principals.get(user_id)


def principal_to_state(principal: Principal | None) -> dict[str, str | None] | None:
    """JSON-safe form stored in session state; None clears the identity (deny by default)."""
    if principal is None:
        return None
    return {
        "user_id": principal.user_id,
        "name": principal.name,
        "role": principal.role,
        "store_id": principal.store_id,
        "region": principal.region,
    }


def _opt_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def principal_from_state(state: SessionState) -> Principal | None:
    """Read the principal a tool acts for, or None when absent or malformed (deny by default)."""
    raw = state.get(STATE_PRINCIPAL)
    if not isinstance(raw, dict):
        return None
    user_id, role = raw.get("user_id"), raw.get("role")
    if not isinstance(user_id, str) or not isinstance(role, str):
        return None
    return Principal(
        user_id=user_id,
        name=_opt_str(raw.get("name")) or "",
        role=role,
        store_id=_opt_str(raw.get("store_id")),
        region=_opt_str(raw.get("region")),
    )
