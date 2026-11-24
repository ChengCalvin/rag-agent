"""Task 2.3: synthetic personas load into principals."""

import json
from pathlib import Path

import pytest

from novamart_agent.adapters import load_orders
from novamart_agent.errors import DataLoadError
from novamart_agent.models import KNOWN_ROLES, Principal
from novamart_agent.security import load_principals


@pytest.fixture(scope="module")
def principals(data_dir: Path) -> dict[str, Principal]:
    return load_principals(data_dir / "users.json")


def test_task_2_3_four_personas_load_into_principals(principals: dict[str, Principal]) -> None:
    assert set(principals) == {"emp_store7", "emp_store12", "mgr_store7", "regmgr_north"}
    assert all(p.user_id == key for key, p in principals.items())
    assert all(p.role in KNOWN_ROLES for p in principals.values())


def test_task_2_3_personas_cover_two_stores_a_manager_and_a_regional_manager(
    principals: dict[str, Principal],
) -> None:
    employees = [p for p in principals.values() if p.role == "employee"]
    assert len({p.store_id for p in employees}) == 2
    assert sum(p.role == "manager" for p in principals.values()) == 1
    regional = principals["regmgr_north"]
    assert regional.role == "regional_manager"
    assert regional.store_id is None
    assert regional.region == "north"


def test_task_2_3_every_store_persona_has_orders_in_another_store(
    principals: dict[str, Principal], data_dir: Path
) -> None:
    stores = {o.store_id for o in load_orders(data_dir / "orders.json")}
    for p in principals.values():
        if p.store_id is not None:
            assert stores - {p.store_id}


def test_loader_rejects_duplicate_user_id(tmp_path: Path) -> None:
    user = {"user_id": "a", "name": "A", "role": "employee", "store_id": "s", "region": "r"}
    path = tmp_path / "users.json"
    path.write_text(json.dumps({"users": [user, user]}), encoding="utf-8")
    with pytest.raises(DataLoadError, match="duplicate"):
        load_principals(path)


def test_loader_keeps_unknown_role_so_the_guard_can_deny_it(tmp_path: Path) -> None:
    user = {"user_id": "a", "name": "A", "role": "intern", "store_id": "s", "region": None}
    path = tmp_path / "users.json"
    path.write_text(json.dumps({"users": [user]}), encoding="utf-8")
    assert load_principals(path)["a"].role == "intern"


def test_task_2_3_malformed_json_raises_data_load_error_without_file_content(
    tmp_path: Path,
) -> None:
    path = tmp_path / "users.json"
    path.write_text('{"users": [ "SECRET-VALUE" ', encoding="utf-8")
    with pytest.raises(DataLoadError, match="users.json") as info:
        load_principals(path)
    assert "SECRET-VALUE" not in str(info.value)
    assert info.value.__cause__ is None
    assert info.value.__suppress_context__


def test_loader_rejects_missing_role(tmp_path: Path) -> None:
    path = tmp_path / "users.json"
    path.write_text(json.dumps({"users": [{"user_id": "a", "name": "A"}]}), encoding="utf-8")
    with pytest.raises(DataLoadError, match="role"):
        load_principals(path)
