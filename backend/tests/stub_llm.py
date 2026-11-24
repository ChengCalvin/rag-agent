"""A scripted model for key-free tests of the whole graph (task 7.6 a, b).

`ScriptedLlm` is an ADK `BaseLlm` that returns the next scripted step on each call and counts
calls, so tests can assert exactly how many model calls a turn made. A step is a text reply
(`say`) or a tool call (`call`). A call beyond the script fails the test: an unexpected model call
(for example a summarising call after a tool result) is a bug, not something to absorb.
"""

import json
from collections.abc import AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

PROMPT_TOKENS = 100
CANDIDATE_TOKENS = 20
THOUGHT_TOKENS = 30


class UnexpectedModelCall(AssertionError):
    """The graph called a model more often than the test scripted."""


def say(text: str) -> LlmResponse:
    """A final text reply, with usage that includes thinking tokens."""
    part = types.Part(text=text)
    return _response(part)


def say_json(record: dict[str, object]) -> LlmResponse:
    """A text reply that is a JSON record (what an `output_schema` agent returns)."""
    return say(json.dumps(record))


def call(name: str, **args: object) -> LlmResponse:
    """A tool call."""
    part = types.Part(function_call=types.FunctionCall(name=name, args=dict(args)))
    return _response(part)


def call_together(*pairs: tuple[str, dict[str, object]]) -> LlmResponse:
    """Several tool calls in one model step (parallel function calling)."""
    parts = [types.Part(function_call=types.FunctionCall(name=n, args=a)) for n, a in pairs]
    return _response(*parts)


def _response(*parts: types.Part) -> LlmResponse:
    usage = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=PROMPT_TOKENS,
        candidates_token_count=CANDIDATE_TOKENS,
        thoughts_token_count=THOUGHT_TOKENS,
    )
    content = types.Content(role="model", parts=list(parts))
    return LlmResponse(content=content, usage_metadata=usage)


def _text_of(request: LlmRequest) -> str:
    parts = [p.text or "" for c in request.contents for p in (c.parts or [])]
    return "\n".join(parts)


class ScriptedLlm(BaseLlm):
    """Returns `script[i]` on call `i`; records what each call was sent."""

    script: list[LlmResponse] = []
    calls: int = 0
    requests: list[str] = []

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        index = self.calls
        self.calls += 1
        self.requests = [*self.requests, _text_of(llm_request)]
        if index >= len(self.script):
            raise UnexpectedModelCall(f"{self.model}: call {index + 1} was not scripted")
        yield self.script[index]


def scripted(label: str, *steps: LlmResponse) -> ScriptedLlm:
    """A model named `label` that will answer with `steps` in order."""
    return ScriptedLlm(model=label, script=list(steps), calls=0, requests=[])
