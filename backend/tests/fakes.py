"""Pure test helpers for access control (task 3.5), reusable by task 7.5.

`fake_tool_context` builds a stand-in for ADK's `ToolContext`/`CallbackContext` that carries a
principal in session state, exactly as the identity callback writes it. No ADK objects, no model.
`shared_state_contexts` returns several contexts over ONE state dict, which is how sub-agents of
one orchestrator see the session (design D16), for the multi-agent identity test in task 7.5.
"""

import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from novamart_agent.adapters import OrdersApi
from novamart_agent.config import Settings
from novamart_agent.errors import EmbeddingError
from novamart_agent.models import STATE_PRINCIPAL, Principal
from novamart_agent.rag import Embedder, PolicySearch, build_policy_search, load_documents
from novamart_agent.security import AuditLogger, OrderGuard, principal_to_state

EMPLOYEE_STORE7 = Principal("emp_store7", "Test Employee", "employee", "store-7", "north")
EMPLOYEE_STORE12 = Principal("emp_store12", "Test Employee", "employee", "store-12", "north")
MANAGER_STORE7 = Principal("mgr_store7", "Test Manager", "manager", "store-7", "north")
REGIONAL_NORTH = Principal("regmgr_north", "Test Regional", "regional_manager", None, "north")
UNKNOWN_ROLE_PRINCIPAL = Principal("temp_1", "Test Temp", "contractor", "store-7", "north")


@dataclass
class FakeToolContext:
    """Duck-types the `.state` access that tools and callbacks use."""

    state: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FakeTool:
    """Duck-types the `.name` access that the before-tool callback uses."""

    name: str


def fake_tool_context(principal: Principal | None) -> FakeToolContext:
    """A context whose state holds `principal` (or an explicit None identity)."""
    return FakeToolContext(state={STATE_PRINCIPAL: principal_to_state(principal)})


def shared_state_contexts(principal: Principal | None, count: int) -> list[FakeToolContext]:
    """`count` contexts that share one state dict, like agents of one orchestrator."""
    first = fake_tool_context(principal)
    return [first] + [FakeToolContext(state=first.state) for _ in range(count - 1)]


class FakeEmbeddingClient:
    """Deterministic embedder stand-in for retrieval tests: no network, no key (task 4.1).

    A text becomes a hashed bag of its words (4+ letters), so texts sharing words are close
    and texts sharing none score exactly 0. It records every call so tests can count them.
    """

    DIMENSIONS = 4096

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.fail = fail

    def embed(self, model: str, task_type: str, text: str) -> list[float]:
        self.calls.append((model, task_type, text))
        if self.fail:
            raise EmbeddingError("fake embedding outage")
        vector = [0.0] * self.DIMENSIONS
        for word in re.findall(r"[a-z]{4,}", text.lower()):
            vector[zlib.crc32(word.encode()) % self.DIMENSIONS] += 1.0
        return vector


def retrieval_settings(model: str = "emb-1", threshold: float = 0.2, top_k: int = 3) -> Settings:
    """Settings for retrieval tests; fake-embedder scores are small, so the threshold is low."""
    return Settings(
        model="chat-model",
        embedding_model=model,
        show_cost=False,
        similarity_threshold=threshold,
        top_k=top_k,
    )


def build_fake_search(
    docs_dir: Path, cache_dir: Path, client: FakeEmbeddingClient, settings: Settings
) -> PolicySearch:
    """The real chunker, index and search over the synthetic documents, with a fake client."""
    embedder = Embedder(client, settings.embedding_model, cache_dir)
    return build_policy_search(load_documents(docs_dir), embedder, settings)


def build_order_guard(data_dir: Path, limit: int = 5) -> OrderGuard:
    """The real guard over the real synthetic orders through the read-only adapter (task 5.1)."""
    backend = OrdersApi.from_file(data_dir / "orders.json")
    return OrderGuard(backend.get, AuditLogger(b"test-salt"), limit)
