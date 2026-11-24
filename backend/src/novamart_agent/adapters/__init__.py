"""Integration adapters: the orders_api stub.

Public names are exposed here (ARCH-MOD-2); other packages import only these.
"""

from novamart_agent.adapters.orders_api import OrdersApi, load_orders

__all__: list[str] = ["OrdersApi", "load_orders"]
