"""Read tool calls and the reply out of ADK events (pure over event objects; no model)."""

from collections.abc import Iterable

from google.adk import Event
from google.genai import types

from evalkit.observation import ToolCall


def tool_calls(events: Iterable[Event]) -> tuple[ToolCall, ...]:
    """Every function call in the events, in order."""
    calls: list[ToolCall] = []
    for event in events:
        for call in event.get_function_calls():
            args = tuple(sorted((k, str(v)) for k, v in (call.args or {}).items()))
            calls.append(ToolCall(call.name or "", args))
    return tuple(calls)


def content_text(content: types.Content | None) -> str:
    return "".join(p.text or "" for p in (content.parts if content and content.parts else []))


def final_reply(events: Iterable[Event]) -> str:
    """The text of the last non-user event that carries text: the assembled reply."""
    text = ""
    for event in events:
        if event.author != "user":
            candidate = content_text(event.content)
            if candidate and not event.get_function_calls():
                text = candidate
    return text
