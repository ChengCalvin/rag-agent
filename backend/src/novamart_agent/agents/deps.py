"""What the orchestrator is built from, and how the real one is assembled (task 7.2, LAYER-1).

`PipelineDeps` is the seam tests use: a fake search and a fake clock go in, the same graph comes
out. `build_deps` is the production assembly: documents, the read-only order stub behind the one
guard, the audit logger, and a search that builds its index on first use (no key at import).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from google.adk.models.base_llm import BaseLlm

from novamart_agent.adapters import OrdersApi
from novamart_agent.config import Settings
from novamart_agent.models import Document
from novamart_agent.rag import (
    Embedder,
    GenaiEmbeddingClient,
    LazyPolicySearch,
    PolicySearch,
    SearchService,
    build_policy_search,
    load_documents,
)
from novamart_agent.security import AuditLogger, OrderGuard

ModelSpec = str | BaseLlm
CACHE_DIR_NAME = ".cache"  # under the data dir; git-ignored


@dataclass(frozen=True)
class AgentModels:
    """The model of each agent. A string is a model ID; tests pass a scripted `BaseLlm`."""

    intake: ModelSpec
    retrieval: ModelSpec
    validator: ModelSpec
    order: ModelSpec
    composer: ModelSpec

    @classmethod
    def uniform(cls, model: ModelSpec) -> "AgentModels":
        """The same model for every agent."""
        return cls(model, model, model, model, model)


@dataclass(frozen=True)
class PipelineDeps:
    """Everything the graph needs from outside it."""

    settings: Settings
    documents: tuple[Document, ...]
    search: SearchService
    guard: OrderGuard
    audit: AuditLogger
    today: Callable[[], date]


def build_deps(settings: Settings) -> PipelineDeps:
    """The production dependencies. Reads local files only: no network, no key."""
    documents = load_documents(settings.data_dir / "docs")
    orders = OrdersApi.from_file(settings.data_dir / "orders.json")
    audit = AuditLogger()
    guard = OrderGuard(orders.get, audit, settings.denied_lookup_limit)
    cache_dir = settings.data_dir / CACHE_DIR_NAME

    def build_search() -> PolicySearch:
        embedder = Embedder(GenaiEmbeddingClient(), settings.embedding_model, cache_dir)
        return build_policy_search(documents, embedder, settings)

    search = LazyPolicySearch(build_search, settings.max_query_chars)
    return PipelineDeps(settings, documents, search, guard, audit, date.today)
