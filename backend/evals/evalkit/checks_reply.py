"""Objective checks on the reply text (spec: 'Checks are objective first')."""

import re
from collections.abc import Mapping

from evalkit.check_args import text, texts, turn_of
from evalkit.observation import Observation, band_of, sources_block, strip_cost_line
from evalkit.results import CheckResult, verdict
from novamart_agent.prompts import DECLINE_REPLY, NOT_FOUND_REPLY

CANNED: Mapping[str, str] = {"not_found": NOT_FOUND_REPLY, "decline": DECLINE_REPLY}


def _body(obs: Observation, args: Mapping[str, object]) -> str:
    return strip_cost_line(turn_of(args, obs).reply)


def reply_contains_any(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    body, wanted = _body(obs, args).casefold(), texts(args, "values")
    hit = [v for v in wanted if v.casefold() in body]
    return verdict("reply_contains_any", bool(hit), f"none of {list(wanted)} found")


def reply_contains_all(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    body, wanted = _body(obs, args).casefold(), texts(args, "values")
    missing = [v for v in wanted if v.casefold() not in body]
    return verdict("reply_contains_all", not missing, f"missing {missing}")


def reply_not_contains(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    body, forbidden = _body(obs, args).casefold(), texts(args, "values")
    found = [v for v in forbidden if v.casefold() in body]
    return verdict("reply_not_contains", not found, f"forbidden text present: {found}")


def reply_matches(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    found = re.search(text(args, "pattern"), _body(obs, args), re.IGNORECASE)
    return verdict("reply_matches", found is not None, "pattern not found")


def reply_not_matches(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    found = re.search(text(args, "pattern"), _body(obs, args), re.IGNORECASE)
    return verdict("reply_not_matches", found is None, "forbidden pattern found")


def reply_equals_canned(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    name = text(args, "name")
    expected = CANNED.get(name)
    if expected is None:
        return verdict("reply_equals_canned", False, f"unknown canned reply '{name}'")
    return verdict("reply_equals_canned", _body(obs, args) == expected, f"not the '{name}' text")


def cites(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    """The code-written Sources list names the file (the model never writes citations)."""
    block = sources_block(turn_of(args, obs).reply)
    wanted = text(args, "file")
    return verdict("cites", wanted in block, f"Sources list does not name {wanted}")


def band_is(obs: Observation, args: Mapping[str, object]) -> CheckResult:
    """`band` is High, Medium, Low or `none` (no band line)."""
    want, got = text(args, "band"), band_of(turn_of(args, obs).reply) or "none"
    return verdict("band_is", want == got, f"band is {got}, expected {want}")
