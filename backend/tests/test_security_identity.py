"""Task 3.1: identity is set by the application and read from state by tools only."""

import inspect
from collections.abc import Callable
from pathlib import Path

import pytest
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import FunctionTool

from fakes import FakeToolContext, fake_tool_context, shared_state_contexts
from novamart_agent.config import load_settings
from novamart_agent.models import STATE_PRINCIPAL, Principal
from novamart_agent.security import (
    load_principals,
    principal_from_state,
    principal_to_state,
    resolve_principal,
)
from novamart_agent.security.callbacks import make_identity_callback

IDENTITY_NAMES = {"user", "user_id", "store", "store_id", "role", "principal", "region", "caller"}


def whoami_tool(tool_context: FakeToolContext) -> dict[str, str | None]:
    """A stand-in data tool: identity comes from the tool context only."""
    principal = principal_from_state(tool_context.state)
    return {"caller": principal.user_id if principal else None}


def lookup_stub(order_id: str, tool_context: FakeToolContext) -> dict[str, str | None]:
    """A stand-in order tool: the only model-visible parameter is the order id."""
    return {"order_id": order_id, **whoami_tool(tool_context)}


@pytest.fixture()
def callback_for(
    monkeypatch: pytest.MonkeyPatch, data_dir: Path
) -> Callable[[str | None], Callable[[CallbackContext], None]]:
    def build(user: str | None) -> Callable[[CallbackContext], None]:
        if user is None:
            monkeypatch.delenv("NOVAMART_USER", raising=False)
        else:
            monkeypatch.setenv("NOVAMART_USER", user)
        monkeypatch.setenv("NOVAMART_DATA_DIR", str(data_dir))
        return make_identity_callback(load_settings())

    return build


def test_task_3_1_tool_reads_the_principal_from_the_tool_context(
    principals: dict[str, Principal],
) -> None:
    ctx = fake_tool_context(principals["emp_store12"])
    assert whoami_tool(ctx) == {"caller": "emp_store12"}


def test_tools_take_no_identity_parameters(principals: dict[str, Principal]) -> None:
    for fn in (whoami_tool, lookup_stub):
        assert not IDENTITY_NAMES & set(inspect.signature(fn).parameters)


def test_tools_take_no_identity_parameters_in_the_model_visible_schema() -> None:
    declaration = FunctionTool(lookup_stub)._get_declaration()
    assert declaration is not None
    schema = declaration.parameters_json_schema
    assert isinstance(schema, dict)
    assert set(schema["properties"]) == {"order_id"}


def test_task_3_1_before_agent_callback_sets_the_novamart_user_persona(
    callback_for: Callable[[str | None], Callable[[CallbackContext], None]],
) -> None:
    ctx = fake_tool_context(None)
    callback_for("regmgr_north")(ctx)  # type: ignore[arg-type]  # test double, not the ADK type
    principal = principal_from_state(ctx.state)
    assert principal is not None
    assert (principal.user_id, principal.role, principal.region) == (
        "regmgr_north",
        "regional_manager",
        "north",
    )


def test_role_claimed_in_chat_leaves_access_unchanged(
    callback_for: Callable[[str | None], Callable[[CallbackContext], None]],
) -> None:
    """Scenario 'Role claimed in chat': a state value written by anything else is overwritten."""
    ctx = FakeToolContext(state={STATE_PRINCIPAL: {"user_id": "x", "role": "regional_manager"}})
    callback_for("emp_store7")(ctx)  # type: ignore[arg-type]  # test double, not the ADK type
    principal = principal_from_state(ctx.state)
    assert principal is not None and principal.role == "employee"


@pytest.mark.parametrize("user", [None, "nobody"])
def test_unset_or_unknown_persona_clears_identity(
    callback_for: Callable[[str | None], Callable[[CallbackContext], None]], user: str | None
) -> None:
    ctx = fake_tool_context(None)
    ctx.state[STATE_PRINCIPAL] = {"user_id": "stale", "role": "manager"}
    callback_for(user)(ctx)  # type: ignore[arg-type]  # test double, not the ADK type
    assert principal_from_state(ctx.state) is None


def test_principal_round_trips_through_state(principals: dict[str, Principal]) -> None:
    for principal in principals.values():
        assert principal_from_state(fake_tool_context(principal).state) == principal


@pytest.mark.parametrize(
    "raw", [None, "emp_store7", [], {}, {"role": "employee"}, {"user_id": 1, "role": "employee"}]
)
def test_malformed_state_yields_no_principal(raw: object) -> None:
    assert principal_from_state({STATE_PRINCIPAL: raw}) is None  # type: ignore[arg-type]  # malformed on purpose


def test_resolve_principal_unset_and_unknown(principals: dict[str, Principal]) -> None:
    assert resolve_principal(None, principals) is None
    assert resolve_principal("nobody", principals) is None
    assert principal_to_state(None) is None


def test_principal_reaches_every_context_sharing_the_session_state(
    principals: dict[str, Principal],
) -> None:
    """Reusable by task 7.5: sub-agents of one orchestrator read the same principal."""
    contexts = shared_state_contexts(principals["mgr_store7"], 3)
    assert {whoami_tool(c)["caller"] for c in contexts} == {"mgr_store7"}


@pytest.fixture(scope="module")
def principals(data_dir: Path) -> dict[str, Principal]:
    return load_principals(data_dir / "users.json")
