"""QA gap test (chunk 4): the audience filter applies BEFORE ranking and top-k.

A manager-only chunk that outscores every permitted chunk must not use up a top-k slot for an
employee: the employee still gets the best permitted chunk, and no restricted title appears.
"""

from pathlib import Path

from fakes import (
    EMPLOYEE_STORE7,
    MANAGER_STORE7,
    FakeEmbeddingClient,
    build_fake_search,
    retrieval_settings,
)
from novamart_agent.security import permitted_audiences


def _doc(doc_id: str, title: str, audience: str, body: str) -> str:
    return (
        f"---\nid: {doc_id}\ntitle: {title}\ndoc_type: policy\naudience: {audience}\n---\n\n"
        f"# {title}\n\n{body}\n"
    )


def test_restricted_chunk_does_not_take_a_top_k_slot_from_a_permitted_one(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "secret.md").write_text(
        _doc("secret", "Secret Plans", "manager", "zebra zebra zebra quartz quartz"),
        encoding="utf-8",
    )
    (docs / "open.md").write_text(
        _doc("open", "Open Guide", "all_staff", "zebra quartz and other unrelated filler words"),
        encoding="utf-8",
    )
    search = build_fake_search(
        docs, tmp_path / "cache", FakeEmbeddingClient(), retrieval_settings(threshold=0.1, top_k=1)
    )

    query = "zebra zebra zebra quartz quartz"
    employee = search.search(query, permitted_audiences(EMPLOYEE_STORE7))
    manager = search.search(query, permitted_audiences(MANAGER_STORE7))

    assert [h.chunk.doc_id for h in employee.hits] == ["open"]
    assert employee.closest_titles == ("Open Guide",)
    assert [h.chunk.doc_id for h in manager.hits] == ["secret"]
