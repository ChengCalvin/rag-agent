"""The seeded customer values to look for in replies and logs (from the synthetic orders)."""

import json
from pathlib import Path

from evalkit.errors import CaseError
from evalkit.observation import SeededValue

_FIELDS = ("name", "email", "address")


def load_seeded_values(orders_path: Path) -> tuple[SeededValue, ...]:
    """Name, email and address of every seeded order, labelled by order id and field only."""
    document = json.loads(orders_path.read_text(encoding="utf-8"))
    values: list[SeededValue] = []
    for order in document.get("orders", []):
        customer = order.get("customer")
        if not isinstance(customer, dict):
            raise CaseError(f"{orders_path.name}: an order has no customer record")
        for field in _FIELDS:
            text = customer.get(field)
            if isinstance(text, str) and text:
                values.append(SeededValue(f"{order.get('order_id')}.{field}", text))
    return tuple(values)
