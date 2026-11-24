"""Shared helpers for the ADK assumption probes (OWNER-RUN ONLY; see check_adk_assumptions.py)."""

from typing import Any, Callable

from google.adk import Event
from google.adk.models.llm_request import LlmRequest
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.workflow import Workflow
from google.genai import types
from pydantic import BaseModel

APP = "probe"
PASS, FAIL, INCONCLUSIVE = "PASS", "FAIL", "INCONCLUSIVE"


def report(check: str, status: str, detail: str) -> None:
    print(f"{check} {status} {detail}", flush=True)


def passfail(ok: bool) -> str:
    return PASS if ok else FAIL


async def run(root: Any, state: dict[str, Any], text: str) -> list[Event]:
    """Run one turn on a Workflow (node root) or an agent and return all events."""
    service = InMemorySessionService()
    await service.create_session(app_name=APP, user_id="u", session_id="s", state=state)
    if isinstance(root, Workflow):
        runner = Runner(node=root, app_name=APP, session_service=service)
    else:
        runner = Runner(agent=root, app_name=APP, session_service=service)
    message = types.Content(role="user", parts=[types.Part(text=text)])
    return [e async for e in runner.run_async(user_id="u", session_id="s", new_message=message)]


def content_text(content: types.Content | None) -> str:
    return "".join(p.text or "" for p in (content.parts if content and content.parts else []))


def request_text(request: LlmRequest) -> str:
    return " | ".join(content_text(c) for c in request.contents)


def recorder(seen: dict[str, Any], name: str) -> Callable[..., None]:
    """before_model_callback: count the call and keep what the model was sent."""

    def before_model(callback_context: Any, llm_request: LlmRequest) -> None:
        seen["model_calls"] = seen.get("model_calls", 0) + 1
        seen.setdefault(name, []).append(request_text(llm_request))

    return before_model


def lookup(query: str) -> dict[str, str]:
    """Return a canned no_answer result."""
    return {"status": "no_answer", "query": query}


def halt_after_tool(tool: Any, args: dict[str, Any], tool_context: Any, tool_response: Any) -> None:
    """after_tool_callback: store the result in state, end the node's turn at no_answer."""
    tool_context.state["tool_result"] = dict(tool_response)
    if tool_response.get("status") == "no_answer":
        tool_context.actions.skip_summarization = True


class Verdict(BaseModel):
    """Output schema probe."""

    ok: bool
