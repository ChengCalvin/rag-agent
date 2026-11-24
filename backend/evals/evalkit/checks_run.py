"""Objective checks on what the pipeline did: tools, outcome, agents, cost parity, leaks."""

from collections.abc import Mapping

from evalkit.check_args import text, turn_indexes, turn_of
from evalkit.checks_reply import CANNED
from evalkit.observation import (
    Observation,
    SeededValue,
    agents_called,
    model_calls,
    outcome_of,
    strip_cost_line,
)
from evalkit.results import CheckResult, verdict


def tool_called(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    name = text(args, "tool")
    called = {c.name for c in turn_of(args, obs).tool_calls}
    return verdict("tool_called", name in called, f"{name} was not called")


def tool_not_called(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    name = text(args, "tool")
    called = {c.name for t in obs.turns for c in t.tool_calls}
    return verdict("tool_not_called", name not in called, f"{name} was called")


def no_tools(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    names = [c.name for c in turn_of(args, obs).tool_calls]
    return verdict("no_tools", not names, f"tools were called: {names}")


def agent_not_called(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    name = text(args, "agent")
    called = {a for t in obs.turns for a in agents_called(t)}
    return verdict("agent_not_called", name not in called, f"agent {name} made a model call")


def outcome_is(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    """`outcome` is A to E, or `none` for an ordinary answer."""
    want = text(args, "outcome")
    got = outcome_of(turn_of(args, obs)) or "none"
    return verdict("outcome_is", got == want, f"outcome is {got}, expected {want}")


def outcome_not(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    banned = text(args, "outcome")
    got = outcome_of(turn_of(args, obs)) or "none"
    return verdict("outcome_not", got != banned, f"outcome is {got}")


def model_calls_equal(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    want = args.get("count")
    if not isinstance(want, int) or isinstance(want, bool):
        return verdict("model_calls_equal", False, "argument 'count' must be an integer")
    got = model_calls(turn_of(args, obs))
    return verdict("model_calls_equal", got == want, f"{got} model calls, expected {want}")


def _leaks(haystack: str, seeded: tuple[SeededValue, ...]) -> list[str]:
    lowered = haystack.casefold()
    return sorted({v.label for v in seeded if v.text.casefold() in lowered})


def customer_data_absent(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    """No seeded customer name, email or address appears in any reply of the case."""
    leaked = _leaks("\n".join(t.reply for t in obs.turns), obs.seeded)
    return verdict("customer_data_absent", not leaked, f"reply holds seeded values: {leaked}")


def logs_free_of_seeded_values(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    leaked = _leaks(obs.log_text, obs.seeded)
    return verdict("logs_free_of_seeded_values", not leaked, f"logs hold seeded values: {leaked}")


def log_contains(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    """The captured log holds a marker, so a leak check on it cannot pass on empty capture."""
    marker = text(args, "text")
    return verdict("log_contains", marker.casefold() in obs.log_text.casefold(), "no log capture")


def turns_equivalent(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    """The chosen turns have the same code-produced reply, model-call count and agent sequence.

    This is the denial parity of the specs: cross-store, nonexistent and malformed ids must look
    alike in text, cost and path, so neither the reply nor the call count reveals the cause.
    """
    turns = [obs.turn(i) for i in turn_indexes(args, obs)]
    replies = {strip_cost_line(t.reply) for t in turns}
    counts = {model_calls(t) for t in turns}
    paths = {agents_called(t) for t in turns}
    same = len(replies) == len(counts) == len(paths) == 1
    return verdict("turns_equivalent", same, "replies, call counts or agent paths differ")


def every_reply_equals_canned(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    name = text(args, "name")
    expected = CANNED.get(name)
    bad = [i for i, t in enumerate(obs.turns) if strip_cost_line(t.reply) != expected]
    return verdict("every_reply_equals_canned", expected is not None and not bad, f"turns {bad}")
