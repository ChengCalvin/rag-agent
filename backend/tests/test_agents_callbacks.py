"""Tasks 7.3, 7.4, 7.6: the ADK callbacks, called directly with fake contexts (no model).

The combined after-tool callback ordering, the query-hint override, the order halt, usage capture
with thinking tokens, and the diagram check. Fakes duck-type the parts of ADK contexts used.
"""

from pathlib import Path
from types import SimpleNamespace

from google.adk.models.llm_response import LlmResponse
from google.genai import types

from fakes import FakeTool
from novamart_agent.agents.callbacks import (
    make_diagram_check_callback,
    make_order_after_tool,
    make_query_hint_callback,
    make_retrieval_after_tool,
    make_usage_callback,
)
from novamart_agent.config import Settings
from novamart_agent.models import Criterion, RetrievedChunk, Route, Rubric, Verdict
from novamart_agent.pipeline import (
    STATE_ATTEMPTS,
    STATE_ORDER_RESULTS,
    STATE_QUERY_HINT,
    STATE_RETRIEVAL,
    STATE_USAGE,
    LoopInputs,
    RetrievalResult,
    attempts_to_state,
    loop_step,
)
from world import make_settings

SETTINGS: Settings = make_settings(Path("."), None, True)


class LoggedState(dict[str, object]):
    """A state dict that remembers the order of its writes."""

    def __init__(self) -> None:
        super().__init__()
        self.writes: list[str] = []

    def __setitem__(self, key: str, value: object) -> None:
        self.writes.append(key)
        super().__setitem__(key, value)


class FakeActions:
    """Logs into the same write list when `skip_summarization` is set."""

    def __init__(self, writes: list[str]) -> None:
        self._writes = writes
        self._skip = False

    @property
    def skip_summarization(self) -> bool:
        return self._skip

    @skip_summarization.setter
    def skip_summarization(self, value: bool) -> None:
        self._writes.append("skip_summarization")
        self._skip = value


class FakeContext:
    def __init__(self) -> None:
        self.state = LoggedState()
        self.actions = FakeActions(self.state.writes)


def no_answer(*, embedded: bool) -> dict[str, object]:
    return {
        "status": "no_answer",
        "embedding_cache_hit": not embedded,
        "embedded": embedded,
        "closest_titles": [],
    }


# --------------------------------------------- the combined retrieval after-tool


def test_retrieval_after_tool_records_the_embedding_estimate_first_then_halts() -> None:
    """One combined callback: the embedding record, then the stored result, then the halt."""
    context = FakeContext()
    callback = make_retrieval_after_tool(SETTINGS)
    returned = callback(
        FakeTool("search_policy"), {"query": "xylophone zebra"}, context, no_answer(embedded=True)  # type: ignore[arg-type]
    )
    assert returned is None
    assert context.state.writes == [STATE_USAGE, STATE_RETRIEVAL, "skip_summarization"]
    records = context.state[STATE_USAGE]
    assert isinstance(records, list)
    assert [r["kind"] for r in records] == ["embedding"]  # a no_answer on a miss is still costed
    assert context.actions.skip_summarization is True


def test_retrieval_after_tool_adds_no_embedding_record_on_a_cache_hit_but_still_halts() -> None:
    context = FakeContext()
    make_retrieval_after_tool(SETTINGS)(
        FakeTool("search_policy"), {"query": "q words"}, context, no_answer(embedded=False)  # type: ignore[arg-type]
    )
    assert STATE_USAGE not in context.state
    assert context.state[STATE_RETRIEVAL] == no_answer(embedded=False)
    assert context.actions.skip_summarization is True


def test_retrieval_after_tool_costs_the_query_that_was_actually_embedded() -> None:
    """The before-tool hint overwrites the query argument in place, so the estimate uses it."""
    context = FakeContext()
    context.state[STATE_QUERY_HINT] = "x" * 40
    args: dict[str, object] = {"query": "short"}
    make_query_hint_callback()(FakeTool("search_policy"), args, context)  # type: ignore[arg-type]
    make_retrieval_after_tool(SETTINGS)(
        FakeTool("search_policy"), args, context, no_answer(embedded=True)  # type: ignore[arg-type]
    )
    records = context.state[STATE_USAGE]
    assert isinstance(records, list)
    assert records[0]["input_tokens"] == 40 // SETTINGS.pipeline.embedding_chars_per_token


# ------------------------------------------------------------- query hint


def test_the_query_hint_overwrites_the_query_argument_in_place() -> None:
    context = FakeContext()
    context.state[STATE_QUERY_HINT] = "better words"
    args: dict[str, object] = {"query": "model words"}
    assert make_query_hint_callback()(FakeTool("search_policy"), args, context) is None  # type: ignore[arg-type]
    assert args == {"query": "better words"}


def test_no_hint_leaves_the_model_query_and_other_tools_are_untouched() -> None:
    context = FakeContext()
    args: dict[str, object] = {"query": "model words"}
    make_query_hint_callback()(FakeTool("search_policy"), args, context)  # type: ignore[arg-type]
    assert args == {"query": "model words"}
    context.state[STATE_QUERY_HINT] = "hint"
    other: dict[str, object] = {"order_id": "NM-480101"}
    make_query_hint_callback()(FakeTool("get_order_status"), other, context)  # type: ignore[arg-type]
    assert other == {"order_id": "NM-480101"}


# -------------------------------------------------------------- order halt


def test_order_after_tool_keeps_each_result_by_tool_name_and_halts() -> None:
    context = FakeContext()
    callback = make_order_after_tool()
    callback(FakeTool("get_order_status"), {}, context, {"status": "ok"})  # type: ignore[arg-type]
    callback(
        FakeTool("check_return_eligibility"),  # type: ignore[arg-type]
        {},
        context,  # type: ignore[arg-type]
        {"status": "ok", "policy_document_id": "returns-policy"},
    )
    stored = context.state[STATE_ORDER_RESULTS]
    assert isinstance(stored, dict)
    assert set(stored) == {"get_order_status", "check_return_eligibility"}
    assert stored["check_return_eligibility"]["policy_document_id"] == "returns-policy"
    assert context.actions.skip_summarization is True


# ------------------------------------------------------------ usage capture


def response(
    usage: types.GenerateContentResponseUsageMetadata | None, *, partial: bool = False
) -> LlmResponse:
    content = types.Content(role="model", parts=[types.Part(text="x")])
    return LlmResponse(content=content, usage_metadata=usage, partial=partial)


def test_usage_capture_sums_thinking_tokens_into_output() -> None:
    context = SimpleNamespace(state={})
    usage = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=1000, candidates_token_count=200, thoughts_token_count=300
    )
    assert make_usage_callback("composer", "m")(context, response(usage)) is None  # type: ignore[arg-type]
    assert context.state[STATE_USAGE] == [
        {
            "kind": "chat",
            "agent": "composer",
            "model_id": "m",
            "input_tokens": 1000,
            "output_tokens": 500,
        }
    ]


def test_usage_capture_ignores_a_response_without_usage_and_a_partial_one() -> None:
    context = SimpleNamespace(state={})
    callback = make_usage_callback("a", "m")
    usage = types.GenerateContentResponseUsageMetadata(prompt_token_count=1)
    assert callback(context, response(None)) is None  # type: ignore[arg-type]
    assert callback(context, response(usage, partial=True)) is None  # type: ignore[arg-type]
    assert STATE_USAGE not in context.state


def test_usage_records_hold_counts_only_never_message_text() -> None:
    context = SimpleNamespace(state={})
    usage = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=5, candidates_token_count=5
    )
    make_usage_callback("a", "m")(context, response(usage))  # type: ignore[arg-type]
    assert set(context.state[STATE_USAGE][0]) == {
        "kind", "agent", "model_id", "input_tokens", "output_tokens"
    }


# ----------------------------------------------------------- diagram check


def test_the_diagram_check_keeps_a_block_from_the_best_attempt_and_strips_others() -> None:
    chunk_text = "Diagram:\n```\n+--+\n|ok|\n+--+\n```"
    chunk = RetrievedChunk("doc", "H", "doc.md", "product", chunk_text, 0.9)
    rubric = Rubric(Route.KNOWLEDGE, "product", (Criterion("c", True),))
    retrieval = RetrievalResult("ok", False, False, (chunk,), ())
    inputs = LoopInputs(rubric, Verdict((True,), 0.9, None), retrieval, 0.2)
    step = loop_step((), inputs, SETTINGS.pipeline)
    context = SimpleNamespace(state={STATE_ATTEMPTS: attempts_to_state(step.attempts)})
    reply = "Text.\n```\n+--+\n|ok|\n+--+\n```\n```\nINVENTED\n```\nSources:\n- Fake (x.md)"
    changed = make_diagram_check_callback()(context, response_with(reply))  # type: ignore[arg-type]
    assert changed is not None
    text = changed.content.parts[0].text  # type: ignore[union-attr]
    assert "|ok|" in text
    assert "INVENTED" not in text
    assert "Sources" not in text


def test_with_no_attempts_every_block_is_stripped_the_order_route_has_none_to_cite() -> None:
    context = SimpleNamespace(state={})
    changed = make_diagram_check_callback()(context, response_with("Hi\n```\nDRAWN\n```"))  # type: ignore[arg-type]
    assert changed is not None
    assert "DRAWN" not in changed.content.parts[0].text  # type: ignore[union-attr]


def response_with(text: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))
