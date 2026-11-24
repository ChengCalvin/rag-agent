"""The check registry and the one function that grades a case (pure, key-free)."""

from collections.abc import Callable, Mapping

from evalkit import checks_reply as reply
from evalkit import checks_run as run
from evalkit.errors import CaseError
from evalkit.observation import Observation
from evalkit.results import CheckResult

CheckFn = Callable[[Observation, Mapping[str, object]], CheckResult]

REGISTRY: Mapping[str, CheckFn] = {
    "reply_contains_any": reply.reply_contains_any,
    "reply_contains_all": reply.reply_contains_all,
    "reply_not_contains": reply.reply_not_contains,
    "reply_matches": reply.reply_matches,
    "reply_not_matches": reply.reply_not_matches,
    "reply_equals_canned": reply.reply_equals_canned,
    "cites": reply.cites,
    "band_is": reply.band_is,
    "tool_called": run.tool_called,
    "tool_not_called": run.tool_not_called,
    "no_tools": run.no_tools,
    "agent_not_called": run.agent_not_called,
    "outcome_is": run.outcome_is,
    "outcome_not": run.outcome_not,
    "model_calls_equal": run.model_calls_equal,
    "customer_data_absent": run.customer_data_absent,
    "logs_free_of_seeded_values": run.logs_free_of_seeded_values,
    "log_contains": run.log_contains,
    "turns_equivalent": run.turns_equivalent,
    "every_reply_equals_canned": run.every_reply_equals_canned,
}


def run_check(kind: str, args: Mapping[str, object], obs: Observation) -> CheckResult:
    """Run one check. An unknown kind or malformed argument is a `CaseError`, never a pass."""
    fn = REGISTRY.get(kind)
    if fn is None:
        raise CaseError(f"unknown check kind '{kind}'")
    return fn(obs, args)
