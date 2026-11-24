"""Small readers for what a function node receives (private to `agents/`)."""

from collections.abc import Callable

from google.adk import Context, Event
from google.adk.events.event_actions import EventActions
from google.genai import types

from novamart_agent.pipeline import STATE_USER_MESSAGE

# A function node: ADK binds `ctx` and `node_input` by name; both are read, nothing else.
NodeFunction = Callable[[Context, object], Event]


def message_text(raw: object) -> str:
    """The text of a node input: a string, or the text parts of a content (the user message)."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, types.Content):
        return "".join(p.text or "" for p in raw.parts or [])
    return ""


def user_message(state: object) -> str:
    """The raw user message stored by the first node of the turn ('' when absent)."""
    getter = getattr(state, "get", None)
    value = getter(STATE_USER_MESSAGE) if callable(getter) else None
    return value if isinstance(value, str) else ""


def routed(route: str, output: object = None) -> Event:
    """An event that carries a route value (and optionally the next node's input)."""
    return Event(output=output, actions=EventActions(route=route))
