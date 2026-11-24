"""Probes that call the configured model or embedding endpoint (OWNER-RUN ONLY)."""

from typing import Any

from google import genai
from google.adk.agents import LlmAgent
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from novamart_agent.config import load_settings
from probe_support import (
    APP,
    INCONCLUSIVE,
    PASS,
    Verdict,
    content_text,
    lookup,
    passfail,
    report,
    run,
)


def mutate_args(tool: Any, args: dict[str, Any], tool_context: Any) -> None:
    """before_tool_callback: overwrite the model's argument in place."""
    args["query"] = "MUTATED"
    tool_context.state["seen_args"] = dict(args)


def keep_usage(callback_context: Any, llm_response: LlmResponse) -> None:
    """after_model_callback: keep usage_metadata on the session state for inspection."""
    usage = llm_response.usage_metadata
    if usage is not None:
        callback_context.state["usage"] = usage.model_dump(exclude_none=True)


async def probe_tool_and_usage(model: str) -> None:
    agent = LlmAgent(
        name="t",
        model=model,
        instruction="Call lookup with query 'x', then answer.",
        tools=[lookup],
        before_tool_callback=mutate_args,
        after_model_callback=keep_usage,
    )
    service = InMemorySessionService()
    await service.create_session(app_name=APP, user_id="u", session_id="s")
    runner = Runner(agent=agent, app_name=APP, session_service=service)
    msg = types.Content(role="user", parts=[types.Part(text="search")])
    async for _ in runner.run_async(user_id="u", session_id="s", new_message=msg):
        pass
    state = (await service.get_session(app_name=APP, user_id="u", session_id="s")).state  # type: ignore[union-attr]
    args, usage = state.get("seen_args") or {}, state.get("usage")
    report("before-tool-arg-mutation", passfail(args.get("query") == "MUTATED"), f"args={args}")
    fields = ("prompt_token_count", "candidates_token_count", "thoughts_token_count")
    present = bool(usage) and all(f in usage for f in fields[:2])
    report(
        "usage-metadata",
        PASS if present else INCONCLUSIVE,
        f"last call usage={usage} (D17 sums thoughts_token_count into output; "
        f"thoughts present={bool(usage) and fields[2] in usage})",
    )


async def probe_schema_and_template(model: str) -> None:
    both = LlmAgent(
        name="s",
        model=model,
        instruction="Return ok true. Call lookup first.",
        tools=[lookup],
        output_schema=Verdict,
        output_key="verdict",
    )
    events = await run(both, {}, "go")
    report(
        "output-schema-with-tools",
        passfail(any(e.get_function_calls() for e in events)),
        "tool call seen alongside output_schema",
    )
    reader = LlmAgent(name="r", model=model, instruction="Repeat this secret exactly: {secret}")
    replies = await run(reader, {"secret": "PINEAPPLE"}, "go")
    text = "".join(content_text(e.content) for e in replies)
    report("instruction-templating", passfail("PINEAPPLE" in text), "state value rendered")


async def probe_embedding_tokens() -> None:
    client = genai.Client()
    result = await client.aio.models.embed_content(
        model=load_settings().embedding_model,
        contents="return window for opened items",
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    stats = [e.statistics for e in (result.embeddings or [])]
    counted = any(s is not None and getattr(s, "token_count", None) for s in stats)
    report(
        "embedding-token-counts",
        PASS if counted else INCONCLUSIVE,
        f"metadata={result.metadata} statistics={stats} (none: keep D17 estimate path)",
    )
