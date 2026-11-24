"""Agent-level probes: clone, 429 retry, adk eval note (OWNER-RUN ONLY; no real model call)."""

from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.workflow import START, RetryConfig, Workflow
from google.genai import errors, types

from probe_support import (
    FAIL,
    INCONCLUSIVE,
    content_text,
    halt_after_tool,
    lookup,
    passfail,
    recorder,
    report,
    run,
)

# ------------------------------------------------------ callbacks survive clone


async def probe_clone_callbacks() -> None:
    """Model-free: LlmAgent.clone is what the single_turn node path may run (D1 note)."""
    seen: dict[str, Any] = {}
    agent = LlmAgent(
        name="orig",
        model="gemini-probe",
        tools=[lookup],
        after_tool_callback=halt_after_tool,
        before_model_callback=recorder(seen, "orig"),
    )
    clone = agent.clone({"name": "copy"})
    kept = {
        "before_model_callback": clone.before_model_callback == agent.before_model_callback,
        "after_tool_callback": clone.after_tool_callback == agent.after_tool_callback,
        "tools": [getattr(t, "__name__", getattr(t, "name", "?")) for t in clone.tools],
    }
    ok = kept["before_model_callback"] and kept["after_tool_callback"] and "lookup" in kept["tools"]
    report("callbacks-survive-clone", passfail(bool(ok)), f"{kept} (attribute level, no call)")


# ------------------------------------------------------------- retry on 429 path


class Flaky429(BaseLlm):
    """Fake model: first call raises a 429 ClientError, later calls answer `ok`."""

    attempts: int = 0

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self.attempts += 1
        if self.attempts == 1:
            raise errors.ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}})
        part = types.Part(text="ok")
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


async def probe_retry_429() -> None:
    fake = Flaky429(model="fake-flaky")
    retry = RetryConfig(
        max_attempts=3, initial_delay=0.01, max_delay=0.05, jitter=0.0, exceptions=["ClientError"]
    )
    agent = LlmAgent(name="flaky", model=fake, instruction="Say ok.", retry_config=retry)
    try:
        events = await run(Workflow(name="retry_probe", edges=[(START, agent)]), {}, "go")
    except Exception as exc:  # noqa: BLE001 - the probe reports whatever ADK does
        report("retry-config-429", FAIL, f"attempts={fake.attempts} raised {type(exc).__name__}")
        return
    answered = any("ok" in content_text(e.content) for e in events)
    errored = [e.error_code for e in events if e.error_code]
    report(
        "retry-config-429",
        passfail(fake.attempts >= 2 and answered),
        f"model attempts={fake.attempts} (expect 2) answered_after_retry={answered} "
        f"error_events={errored}. FAIL with attempts=1 means ADK turned the 429 into an error "
        "event before the node retry could see it (then ARCH-ERR-1 needs a different wording).",
    )


# ------------------------------------------------------------- adk eval on Workflow


def probe_adk_eval() -> None:
    report(
        "adk-eval-workflow-root",
        INCONCLUSIVE,
        "not run by this script (needs an evalset and model calls). Authored command: "
        "`adk eval backend/src/novamart_agent backend/evals/<evalset>.json "
        "--print_detailed_results` once the Workflow root exists; PASS if it loads the root and "
        "scores, else D7 falls back to the custom runner reading tool calls from events.",
    )
