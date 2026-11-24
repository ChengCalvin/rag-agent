"""The three model-facing tools, one per file (ARCH-MOD-3).

Public names are exposed here (ARCH-MOD-2); other packages import only these.
"""

from novamart_agent.tools._types import ToolContextLike
from novamart_agent.tools.check_return_eligibility import (
    EligibilityDeps,
    make_check_return_eligibility,
    run_check_return_eligibility,
)
from novamart_agent.tools.get_order_status import (
    make_get_order_status,
    order_status_view,
    run_get_order_status,
)
from novamart_agent.tools.search_policy import (
    make_search_policy,
    parse_query,
    run_search_policy,
)

__all__: list[str] = [
    "EligibilityDeps",
    "ToolContextLike",
    "make_check_return_eligibility",
    "make_get_order_status",
    "make_search_policy",
    "order_status_view",
    "parse_query",
    "run_check_return_eligibility",
    "run_get_order_status",
    "run_search_policy",
]
