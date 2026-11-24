"""Workflow probes: loop, skip-summarization, final reply (OWNER-RUN ONLY)."""

from typing import Any

from google.adk import Context, Event
from google.adk.agents import LlmAgent
from google.adk.workflow import START, Workflow
from google.genai import types

from probe_support import (
    FAIL,
    INCONCLUSIVE,
    PASS,
    content_text,
    halt_after_tool,
    lookup,
    passfail,
    recorder,
    report,
    run,
)

# ---------------------------------------------------- workflow-loop-two-passes


def make_loop_workflow(model: str, seen: dict[str, Any]) -> Workflow:
    """seed -> retrieval -> validator -> decide -(retry)-> retrieval | -(done)-> finish."""
    retrieval = LlmAgent(
        name="retrieval",
        model=model,
        before_model_callback=recorder(seen, "retrieval"),
        instruction="Reply with exactly the one word you are given, in UPPERCASE, nothing else.",
    )
    validator = LlmAgent(
        name="validator",
        model=model,
        before_model_callback=recorder(seen, "validator"),
        instruction="Reply with exactly the one word you are given, in lowercase, nothing else.",
    )

    def seed() -> Event:
        return Event(output="ALPHA", state={"passes": 0})

    def decide(ctx: Context, node_input: Any) -> Event:
        passes = int(ctx.state.get("passes", 0)) + 1
        seen["decide_inputs"] = [*seen.get("decide_inputs", []), str(node_input)]
        if passes < 2:
            return Event(output="BETA", route="retry", state={"passes": passes})
        return Event(output=str(node_input), route="done", state={"passes": passes})

    def finish(node_input: Any) -> str:
        seen["finished_with"] = str(node_input)
        return f"finished {node_input}"

    edges = [(START, seed, retrieval, validator, decide, {"retry": retrieval, "done": finish})]
    return Workflow(name="loop_probe", edges=edges)  # type: ignore[arg-type]


def judge_loop(seen: dict[str, Any]) -> tuple[str, str]:
    retrieval, validator = seen.get("retrieval", []), seen.get("validator", [])
    detail = (
        f"passes={len(seen.get('decide_inputs', []))} retrieval_calls={len(retrieval)} "
        f"validator_calls={len(validator)} finished_with={seen.get('finished_with')!r}"
    )
    if len(retrieval) != 2 or len(validator) != 2:
        return FAIL, f"expected 2 passes of each agent; {detail}"
    stale = [t for t in (retrieval[1], validator[1]) if "ALPHA" in t.upper() and "BETA" not in t]
    if "BETA" not in retrieval[1]:
        return FAIL, f"pass-2 retrieval did not receive the new input BETA; {detail}"
    if "ALPHA" in retrieval[1].upper() or "ALPHA" in validator[1].upper() or stale:
        return FAIL, (
            "pass 2 still carries pass-1 content (stale history): set include_contents='none' "
            f"on retrieval and validator and pass every input through the node; {detail}"
        )
    return PASS, f"pass 2 saw only BETA, state counter persisted, exit after 2 passes; {detail}"


async def probe_loop(model: str) -> None:
    seen: dict[str, Any] = {}
    await run(make_loop_workflow(model, seen), {}, "go")
    status, detail = judge_loop(seen)
    report("workflow-loop-two-passes", status, detail)


# ------------------------------------------- skip-summarization-in-workflow-node


async def probe_skip_summarization(model: str) -> None:
    seen: dict[str, Any] = {}
    agent = LlmAgent(
        name="halting",
        model=model,
        tools=[lookup],
        after_tool_callback=halt_after_tool,
        before_model_callback=recorder(seen, "halting"),
        instruction="Call lookup with query 'x' exactly once. Do not answer afterwards.",
    )

    def successor(ctx: Context, node_input: Any) -> str:
        seen["successor_ran"] = True
        seen["state_result"] = ctx.state.get("tool_result")
        seen["node_input"] = repr(node_input)
        return "after"

    events = await run(Workflow(name="skip_probe", edges=[(START, agent, successor)]), {}, "search")
    ok = (
        seen.get("successor_ran") is True
        and seen.get("model_calls") == 1
        and (seen.get("state_result") or {}).get("status") == "no_answer"
    )
    report(
        "skip-summarization-in-workflow-node",
        passfail(ok),
        f"model_calls={seen.get('model_calls')} (expect 1) "
        f"successor_ran={seen.get('successor_ran')} "
        f"state_result={seen.get('state_result')} successor_node_input={seen.get('node_input')} "
        f"events={len(events)}",
    )


# ----------------------------------------------------------- workflow-final-reply


def reply_as_content() -> types.Content:
    return types.Content(role="model", parts=[types.Part(text="REPLY-CONTENT")])


def reply_as_output() -> str:
    return "REPLY-OUTPUT"


def cli_view(events: list[Event]) -> str:
    """What `adk run` prints: only event.content text (cli/cli.py `run_interactively`)."""
    return " / ".join(t for e in events if (t := content_text(e.content)))


async def probe_final_reply() -> None:
    """Model-free: runs two one-node workflows and mimics what `adk run` prints."""
    shown: dict[str, str] = {}
    outputs: dict[str, str] = {}
    for label, func in (("content", reply_as_content), ("output", reply_as_output)):
        events = await run(Workflow(name=f"reply_{label}", edges=[(START, func)]), {}, "hi")
        shown[label] = cli_view(events)
        outputs[label] = repr([e.output for e in events if e.output is not None])
    content_shows = "REPLY-CONTENT" in shown["content"]
    output_shows = "REPLY-OUTPUT" in shown["output"]
    report(
        "workflow-final-reply",
        PASS if content_shows else INCONCLUSIVE,
        f"adk-run view: Content-return shown={content_shows}, "
        f"str/output-return shown={output_shows}"
        f"; outputs seen {outputs}. Use Event(content=...) for the user-facing reply if only "
        "Content shows. adk web chat rendering not testable here: type one line into "
        "`adk web` against a Workflow with each form and note which appears (owner eyes).",
    )
