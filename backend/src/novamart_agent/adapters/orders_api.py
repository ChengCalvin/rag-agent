"""Order system stand-in: load the synthetic orders file (task 2.2; ARCH-EDGE-1).

The only module that reads order data. Read-only. The authorization choke point
(`security/guard`, chunk 3) must be called before any record leaves a tool (ARCH-MOD-4).
"""

import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from novamart_agent.errors import DataLoadError
from novamart_agent.models import ORDER_STATUSES, Customer, Order, OrderItem
from novamart_agent.parsing import (
    as_list,
    as_mapping,
    optional_date,
    require_date,
    require_int,
    require_str,
)


def _parse_item(raw: object, source: str) -> OrderItem:
    data = as_mapping(raw, f"{source} item")
    return OrderItem(
        sku=require_str(data, "sku", source),
        name=require_str(data, "name", source),
        category=require_str(data, "category", source),
        quantity=require_int(data, "quantity", source),
        condition=require_str(data, "condition", source),
    )


def _parse_customer(raw: object, source: str) -> Customer:
    data = as_mapping(raw, f"{source} customer")
    return Customer(
        name=require_str(data, "name", source),
        email=require_str(data, "email", source),
        address=require_str(data, "address", source),
    )


def _parse_order(raw: object, index: int) -> Order:
    source = f"orders.json[{index}]"
    data = as_mapping(raw, source)
    status = require_str(data, "status", source)
    if status not in ORDER_STATUSES:
        raise DataLoadError(f"{source}: unknown status")
    return Order(
        order_id=require_str(data, "order_id", source),
        store_id=require_str(data, "store_id", source),
        region=require_str(data, "region", source),
        status=status,
        ordered_date=require_date(data, "ordered_date", source),
        expected_delivery=optional_date(data, "expected_delivery", source),
        delivered_date=optional_date(data, "delivered_date", source),
        returned_date=optional_date(data, "returned_date", source),
        customer=_parse_customer(data.get("customer"), source),
        items=tuple(_parse_item(i, source) for i in as_list(data.get("items"), source)),
    )


class OrdersApi:
    """Read-only stand-in for the order system: lookup by id, nothing else (ARCH-EDGE-1).

    Offers no create, update or cancel. Authorization is not its job: callers reach `get` only
    through `OrderGuard.lookup` (ARCH-MOD-4).
    """

    def __init__(self, orders: tuple[Order, ...]) -> None:
        self._by_id: Mapping[str, Order] = MappingProxyType({o.order_id: o for o in orders})

    @classmethod
    def from_file(cls, path: Path) -> "OrdersApi":
        """Build the backend from the synthetic orders file."""
        return cls(load_orders(path))

    def get(self, order_id: str) -> Order | None:
        """Return the order with this id, or None."""
        return self._by_id.get(order_id)


def load_orders(path: Path) -> tuple[Order, ...]:
    """Load the orders file into typed orders; order ids must be unique."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # `from None`: JSONDecodeError.doc holds the whole file; never chain it.
        raise DataLoadError(f"{path.name}: not valid JSON") from None
    root = as_mapping(document, path.name)
    orders = tuple(
        _parse_order(raw, i) for i, raw in enumerate(as_list(root.get("orders"), path.name))
    )
    ids = [o.order_id for o in orders]
    if len(ids) != len(set(ids)):
        raise DataLoadError(f"{path.name}: duplicate order id")
    return orders
