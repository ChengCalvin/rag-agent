"""Run one case through the real orchestrator under ADK's runner (LIVE: calls the model).

Never imported by the key-free tests' code paths that execute it; the pure pieces it uses
(`events`, `observation`, `cost`) are tested on their own. Each case gets a fresh session and a
fresh graph built for its persona, so the throttle counter and the clarification counter start
at zero. The reference date is pinned to the one the synthetic orders were written for
(`backend/data/README.md`), so return-window answers do not drift with the calendar.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from evalkit.cases import Case
from evalkit.corpus import prepare_data_dir
from evalkit.events import final_reply, tool_calls
from evalkit.log_capture import capture_logs
from evalkit.observation import Observation, SeededValue, TurnObservation
from novamart_agent.agents import AgentModels, build_deps, build_orchestrator
from novamart_agent.config import ModelPrice, Settings
from novamart_agent.pipeline import (
    STATE_ATTEMPTS,
    STATE_FINAL_KIND,
    STATE_USAGE,
    attempts_from_state,
    compute_turn_cost,
    parse_usage_records,
)

REFERENCE_DATE = date(2026, 11, 23)
APP = "novamart_eval"
USER_ID = "eval"


@dataclass(frozen=True)
class Runtime:
    """What every case shares: configuration, where fixtures and scratch space are, seeded data."""

    settings: Settings
    fixtures_dir: Path
    scratch_dir: Path
    seeded: tuple[SeededValue, ...]


def _fixture_dir(case: Case, runtime: Runtime) -> Path | None:
    return runtime.fixtures_dir / case.fixture if case.fixture else None


@dataclass(frozen=True)
class LiveSession:
    """A runner and the ids of the session it runs in (tests pass their own scripted graph)."""

    runner: Runner
    service: InMemorySessionService
    app: str = APP
    user: str = USER_ID
    session_id: str = APP


async def run_turn(
    live: LiveSession, message: str, prices: Mapping[str, ModelPrice]
) -> TurnObservation:
    """Send one message, then read the reply, tool calls and recorded usage of that turn."""
    content = types.Content(role="user", parts=[types.Part(text=message)])
    events = [
        e
        async for e in live.runner.run_async(
            user_id=live.user, session_id=live.session_id, new_message=content
        )
    ]
    session = await live.service.get_session(
        app_name=live.app, user_id=live.user, session_id=live.session_id
    )
    state = dict(session.state) if session else {}
    usage = parse_usage_records(state.get(STATE_USAGE))
    kind = state.get(STATE_FINAL_KIND)
    return TurnObservation(
        message=message,
        reply=final_reply(events),
        tool_calls=tool_calls(events),
        final_kind=kind if isinstance(kind, str) else None,
        usage=usage,
        cost=compute_turn_cost(usage, prices),
        attempts=attempts_from_state(state.get(STATE_ATTEMPTS)),
    )


async def run_case(case: Case, runtime: Runtime) -> Observation:
    """Run every turn of the case in one session and capture logs and usage."""
    data_dir = prepare_data_dir(
        runtime.settings.data_dir,
        _fixture_dir(case, runtime),
        runtime.scratch_dir / case.case_id,
    )
    settings = replace(runtime.settings, user=case.persona, data_dir=data_dir)
    deps = replace(build_deps(settings), today=lambda: REFERENCE_DATE)
    workflow = build_orchestrator(deps, AgentModels.uniform(settings.model))
    service = InMemorySessionService()
    await service.create_session(app_name=APP, user_id=USER_ID, session_id=APP, state={})
    live = LiveSession(Runner(node=workflow, app_name=APP, session_service=service), service)
    turns: list[TurnObservation] = []
    with capture_logs() as lines:
        for message in case.turns:
            turns.append(await run_turn(live, message, settings.prices))
    return Observation(tuple(turns), "\n".join(lines), runtime.seeded)
