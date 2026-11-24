"""ADK callbacks of the pipeline agents (LAYER-1; tasks 7.3, 7.4, 7.6).

They only adapt ADK to pure functions: usage capture and the diagram check (after-model), the
query-hint override (before-tool), and the two after-tool callbacks that store a tool result in
state and end the agent's turn at it with no further model call (`skip_summarization`, D13).
The identity and allowlist callbacks are in `security/callbacks.py`.
"""

from collections.abc import Callable

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from novamart_agent.config import Settings
from novamart_agent.models import TOOL_SEARCH_POLICY
from novamart_agent.pipeline import (
    STATE_ATTEMPTS,
    STATE_ORDER_RESULTS,
    STATE_QUERY_HINT,
    STATE_RETRIEVAL,
    STATE_USAGE,
    TokenCounts,
    attempts_from_state,
    best_attempt,
    chat_usage_record,
    embedding_estimate,
    sanitize_model_text,
    with_usage,
)

AfterModelCallback = Callable[[CallbackContext, LlmResponse], LlmResponse | None]
BeforeToolCallback = Callable[[BaseTool, dict[str, object], ToolContext], dict[str, object] | None]
AfterToolCallback = Callable[
    [BaseTool, dict[str, object], ToolContext, dict[str, object]], dict[str, object] | None
]


def make_usage_callback(agent_name: str, model_id: str) -> AfterModelCallback:
    """After-model callback: add this call's token usage to the turn's list in state.

    Counts only a complete response that carries `usage_metadata`; a failed call returns none
    and is not counted (D17). Thinking tokens are summed into output by `chat_usage_record`.
    Only counts are stored, never text (ERR-2).
    """

    def capture_usage(
        callback_context: CallbackContext, llm_response: LlmResponse
    ) -> LlmResponse | None:
        meta = llm_response.usage_metadata
        if meta is None or llm_response.partial:
            return None
        counts = TokenCounts(
            meta.prompt_token_count, meta.candidates_token_count, meta.thoughts_token_count
        )
        record = chat_usage_record(agent_name, model_id, counts)
        state = callback_context.state
        state[STATE_USAGE] = with_usage(state.get(STATE_USAGE), record)
        return None

    return capture_usage


def make_diagram_check_callback() -> AfterModelCallback:
    """After-model callback on the composer: strip model-written footers and any fenced block
    that is not in the best attempt's chunks (the order route has none, so none survives)."""

    def check_reply(
        callback_context: CallbackContext, llm_response: LlmResponse
    ) -> LlmResponse | None:
        content = llm_response.content
        if llm_response.partial or content is None or not content.parts:
            return None
        attempts = attempts_from_state(callback_context.state.get(STATE_ATTEMPTS))
        texts = [c.text for c in best_attempt(attempts).chunks] if attempts else []
        parts = [
            part.model_copy(update={"text": sanitize_model_text(part.text, texts)})
            if part.text and not part.thought
            else part
            for part in content.parts
        ]
        return llm_response.model_copy(
            update={"content": content.model_copy(update={"parts": parts})}
        )

    return check_reply


def make_query_hint_callback() -> BeforeToolCallback:
    """Before-tool callback: overwrite the `search_policy` query with the validator's rewrite.

    Mutates the argument dict in place (ADK passes the same dict to the tool), so the model does
    not choose the argument twice. The hint is already length-capped and cleaned (parse_verdict).
    """

    def apply_hint(
        tool: BaseTool, args: dict[str, object], tool_context: ToolContext
    ) -> dict[str, object] | None:
        hint = tool_context.state.get(STATE_QUERY_HINT)
        if tool.name == TOOL_SEARCH_POLICY and isinstance(hint, str) and hint.strip():
            args["query"] = hint
        return None

    return apply_hint


def make_retrieval_after_tool(settings: Settings) -> AfterToolCallback:
    """The one combined after-tool callback of the retrieval agent (D13, D17).

    In this order: record the query-embedding estimate (only when the result says an embedding
    call was billed, so a `no_answer` on a cache miss is still costed and a cache hit adds
    nothing), store the result for the next node, then end the agent's turn at the result. The
    agent writes no text: the next node reads state and routes on the status.
    """

    def record_and_halt(
        tool: BaseTool,
        args: dict[str, object],
        tool_context: ToolContext,
        tool_response: dict[str, object],
    ) -> dict[str, object] | None:
        estimate = embedding_estimate(
            tool_response,
            args.get("query"),
            settings.embedding_model,
            settings.pipeline.embedding_chars_per_token,
        )
        state = tool_context.state
        if estimate is not None:
            state[STATE_USAGE] = with_usage(state.get(STATE_USAGE), estimate)
        state[STATE_RETRIEVAL] = dict(tool_response)
        tool_context.actions.skip_summarization = True
        return None

    return record_and_halt


def make_order_after_tool() -> AfterToolCallback:
    """After-tool callback of the order agent: keep each tool's structured result in state, by
    tool name, and end the turn at the result (no summarising call, so no cause-dependent
    wording can reach the user, D13). The policy id for Sources is read from here, not from
    anything the model wrote (AG-41)."""

    def store_and_halt(
        tool: BaseTool,
        args: dict[str, object],
        tool_context: ToolContext,
        tool_response: dict[str, object],
    ) -> dict[str, object] | None:
        state = tool_context.state
        stored = state.get(STATE_ORDER_RESULTS)
        results = dict(stored) if isinstance(stored, dict) else {}
        results[tool.name] = dict(tool_response)
        state[STATE_ORDER_RESULTS] = results
        tool_context.actions.skip_summarization = True
        return None

    return store_and_halt
