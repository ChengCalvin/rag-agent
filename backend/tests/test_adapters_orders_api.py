"""Task 2.2: synthetic orders load and include cross-store cases."""

import json
import re
from pathlib import Path

import pytest

from novamart_agent.adapters import load_orders
from novamart_agent.errors import DataLoadError
from novamart_agent.models import Order


@pytest.fixture(scope="module")
def orders(data_dir: Path) -> tuple[Order, ...]:
    return load_orders(data_dir / "orders.json")


def test_task_2_2_ten_orders_load_with_unique_well_formed_ids(
    orders: tuple[Order, ...],
) -> None:
    assert len(orders) == 10
    assert all(re.fullmatch(r"NM-\d{6}", o.order_id) for o in orders)


def test_task_2_2_orders_span_three_stores_and_all_three_states(
    orders: tuple[Order, ...],
) -> None:
    assert {o.store_id for o in orders} == {"store-7", "store-12", "store-19"}
    assert {o.status for o in orders} == {"delivered", "in_transit", "returned"}


def test_task_2_2_cross_store_and_cross_region_cases_exist(orders: tuple[Order, ...]) -> None:
    assert len({o.region for o in orders}) == 2
    assert {o.store_id for o in orders if o.region == "north"} == {"store-7", "store-12"}


def test_task_2_2_every_order_has_seeded_distinctive_name_email_and_address(
    orders: tuple[Order, ...],
) -> None:
    for values in (
        [o.customer.name for o in orders],
        [o.customer.email for o in orders],
        [o.customer.address for o in orders],
    ):
        assert len(set(values)) == len(orders)
    assert all(re.search(r"@example\.(com|test)$", o.customer.email) for o in orders)
    assert all("ZZ " in o.customer.address for o in orders)


def test_task_2_2_synthetic_data_guard_example_emails_and_zz_postcodes(
    orders: tuple[Order, ...],
) -> None:
    for o in orders:
        assert o.customer.email.endswith(("@example.com", "@example.test"))
        assert re.search(r"\bZZ \d+$", o.customer.address)


def test_task_2_2_malformed_json_raises_data_load_error_without_file_content(
    tmp_path: Path,
) -> None:
    path = tmp_path / "orders.json"
    path.write_text('{"orders": [ "SECRET-VALUE" ', encoding="utf-8")
    with pytest.raises(DataLoadError, match="orders.json") as info:
        load_orders(path)
    assert "SECRET-VALUE" not in str(info.value)
    assert info.value.__cause__ is None
    assert info.value.__suppress_context__


def test_task_2_2_state_dates_are_consistent(orders: tuple[Order, ...]) -> None:
    for o in orders:
        if o.status == "in_transit":
            assert o.delivered_date is None
            assert o.expected_delivery is not None
        else:
            assert o.delivered_date is not None
        assert (o.returned_date is not None) == (o.status == "returned")


def test_task_2_2_order_repr_does_not_expose_customer_pii(orders: tuple[Order, ...]) -> None:
    text = repr(orders)
    for o in orders:
        for value in (o.customer.name, o.customer.email, o.customer.address):
            assert value not in text


def test_loader_rejects_unknown_status_without_echoing_values(tmp_path: Path) -> None:
    path = tmp_path / "orders.json"
    path.write_text(
        json.dumps({"orders": [{"order_id": "NM-1", "status": "lost"}]}), encoding="utf-8"
    )
    with pytest.raises(DataLoadError, match="unknown status") as info:
        load_orders(path)
    assert "NM-1" not in str(info.value)


def test_loader_rejects_missing_customer_field(tmp_path: Path, data_dir: Path) -> None:
    raw = json.loads((data_dir / "orders.json").read_text(encoding="utf-8"))
    del raw["orders"][0]["customer"]["email"]
    path = tmp_path / "orders.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(DataLoadError, match="email"):
        load_orders(path)
