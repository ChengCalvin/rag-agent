"""Builds the real orchestrator graph with scripted models and runs turns (tasks 7.2 to 7.6).

Everything is real except the models (scripted, no key), the embedding client (a fake hashed
bag of words) and the clock. Turns run under ADK's own runner, so the graph, the function nodes,
the callbacks and the routes are what `adk run` executes.
"""

import asyncio
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.workflow import Workflow
from google.genai import types

from fakes import FakeEmbeddingClient, build_fake_search, build_order_guard, retrieval_settings
from novamart_agent.agents import AgentModels, PipelineDeps, build_orchestrator
from novamart_agent.config import ModelPrice, Settings
from novamart_agent.models import Document
from novamart_agent.rag import load_documents
from novamart_agent.security import AuditLogger
from stub_llm import ScriptedLlm, scripted

CHAT_MODEL = "stub-model"
EMBEDDING_MODEL = "emb-1"
APP = "test"
TODAY = date(2026, 11, 23)


@dataclass(frozen=True)
class Scripts:
    """One scripted model per agent; an unused agent gets an empty script (any call fails)."""

    intake: ScriptedLlm
    retrieval: ScriptedLlm
    validator: ScriptedLlm
    order: ScriptedLlm
    composer: ScriptedLlm

    def calls(self) -> int:
        """Model calls made so far, over all five agents."""
        return sum(m.calls for m in self.all())

    def all(self) -> tuple[ScriptedLlm, ...]:
        return (self.intake, self.retrieval, self.validator, self.order, self.composer)


@dataclass(frozen=True)
class Turn:
    """The reply text and the session state after one turn."""

    reply: str
    state: dict[str, object]


@dataclass
class World:
    """A built graph plus the pieces tests inspect."""

    workflow: Workflow
    settings: Settings
    embedder: FakeEmbeddingClient
    service: InMemorySessionService

    def run(self, *messages: str) -> list[Turn]:
        """Run the messages as consecutive turns of one session."""
        return asyncio.run(self._run(messages))

    async def _run(self, messages: tuple[str, ...]) -> list[Turn]:
        await self.service.create_session(app_name=APP, user_id="u", session_id="s", state={})
        runner = Runner(node=self.workflow, app_name=APP, session_service=self.service)
        turns: list[Turn] = []
        for text in messages:
            message = types.Content(role="user", parts=[types.Part(text=text)])
            events = [
                e
                async for e in runner.run_async(user_id="u", session_id="s", new_message=message)
            ]
            session = await self.service.get_session(app_name=APP, user_id="u", session_id="s")
            state = dict(session.state) if session else {}
            replies = [e for e in events if e.content and e.content.parts and e.author != "user"]
            last = replies[-1].content if replies and replies[-1].content else None
            turns.append(Turn(_text(last), state))
        return turns


def rubric_json(
    route: str,
    criteria: tuple[tuple[str, bool], ...] = (("answer the question", True),),
    *,
    doc_type: str | None = None,
    slots: tuple[str, ...] = (),
) -> dict[str, object]:
    """An intake record as the model would return it."""
    return {
        "route": route,
        "doc_type": doc_type,
        "criteria": [{"text": t, "required": r, "unanswered_policy": False} for t, r in criteria],
        "missing_slots": list(slots),
    }


def flag_unanswered_policy(record: dict[str, object]) -> dict[str, object]:
    """The record with every criterion flagged as an unanswered policy part."""
    criteria = record["criteria"]
    assert isinstance(criteria, list)
    return {**record, "criteria": [{**c, "unanswered_policy": True} for c in criteria]}


def verdict_json(
    coverage: tuple[bool, ...], confidence: float, rewrite: str | None = None
) -> dict[str, object]:
    """A validator record as the model would return it."""
    record: dict[str, object] = {"coverage": list(coverage), "llm_confidence": confidence}
    if rewrite is not None:
        record["rewritten_query"] = rewrite
    return record


def unused(label: str) -> ScriptedLlm:
    """A model that must never be called."""
    return scripted(label)


def _text(content: types.Content | None) -> str:
    return "".join(p.text or "" for p in (content.parts if content and content.parts else []))


def make_settings(data_dir: Path, user: str | None, show_cost: bool) -> Settings:
    """Retrieval settings plus the stub chat model, its price and the persona."""
    base = retrieval_settings(EMBEDDING_MODEL)
    prices = {CHAT_MODEL: ModelPrice(1.0, 2.0), EMBEDDING_MODEL: ModelPrice(0.1, 0.0)}
    return replace(
        base, model=CHAT_MODEL, user=user, show_cost=show_cost, data_dir=data_dir, prices=prices
    )


@dataclass(frozen=True)
class WorldOptions:
    """What varies between tests: the persona, the cost flag and the documents."""

    user: str | None = "emp_store7"
    show_cost: bool = True
    documents: tuple[Document, ...] | None = None


def make_deps(
    data_dir: Path, cache_dir: Path, options: WorldOptions = WorldOptions()
) -> tuple[PipelineDeps, FakeEmbeddingClient]:
    """Real documents, orders, guard and search; a fake embedding client and a fixed clock."""
    settings = make_settings(data_dir, options.user, options.show_cost)
    client = FakeEmbeddingClient()
    search = build_fake_search(data_dir / "docs", cache_dir, client, settings)
    docs = options.documents or load_documents(data_dir / "docs")
    deps = PipelineDeps(
        settings, docs, search, build_order_guard(data_dir), AuditLogger(b"t"), lambda: TODAY
    )
    return deps, client


def build_world(
    scripts: Scripts, data_dir: Path, cache_dir: Path, options: WorldOptions = WorldOptions()
) -> World:
    """The real graph over the synthetic data with scripted models."""
    deps, client = make_deps(data_dir, cache_dir, options)
    models = AgentModels(
        scripts.intake, scripts.retrieval, scripts.validator, scripts.order, scripts.composer
    )
    return World(build_orchestrator(deps, models), deps.settings, client, InMemorySessionService())
