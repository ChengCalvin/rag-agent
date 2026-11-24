"""A search service built on first use (task 7.2, ARCH-EDGE-1).

Building the index embeds every chunk (one billed call each on a cold cache). Importing the
agent package must need no key and no network, so `adk web` can list the agent and tests can
import it; the index is therefore built when the first search runs. A failure while building
propagates to `run_search_policy`, which maps it to the generic error status, and the next search
tries again. No ADK imports.
"""

from collections.abc import Callable

from novamart_agent.rag.search import PolicySearch, SearchResult


class LazyPolicySearch:
    """Builds the real `PolicySearch` on the first `search` call and reuses it afterwards."""

    def __init__(self, build: Callable[[], PolicySearch], max_query_chars: int) -> None:
        self._build = build
        self._search: PolicySearch | None = None
        self._max_query_chars = max_query_chars

    @property
    def max_query_chars(self) -> int:
        """The longest query embedded (from configuration; known without building)."""
        return self._max_query_chars

    def search(self, query: str, audiences: frozenset[str]) -> SearchResult:
        """Search for a caller with `audiences`, building the index first if needed."""
        if self._search is None:
            self._search = self._build()
        return self._search.search(query, audiences)
