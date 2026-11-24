"""Tasks 2.1 and 2.4: synthetic policy and product documents parse (TEST-1 names the clause)."""

from pathlib import Path

import pytest

from novamart_agent.errors import DataLoadError
from novamart_agent.models import Document
from novamart_agent.rag import fenced_blocks, load_documents, parse_document

FENCE = "`" * 3
GAP_TOPICS = [
    "bulk or corporate orders",
    "international shipping and customs",
    "trade-in and buy-back",
    "employee scheduling, pay and leave",
    "installation and assembly services",
]
GAP_WORDS = ["bulk", "corporate", "customs", "trade-in", "buy-back", "payroll", "assembly service"]


@pytest.fixture(scope="module")
def documents(data_dir: Path) -> tuple[Document, ...]:
    return load_documents(data_dir / "docs")


def _by_type(documents: tuple[Document, ...], doc_type: str) -> list[Document]:
    return [d for d in documents if d.doc_type == doc_type]


def test_task_2_1_eight_policy_documents_parse_with_audience_and_doc_type(
    documents: tuple[Document, ...],
) -> None:
    policies = _by_type(documents, "policy")
    assert len(policies) == 8
    assert {d.audience for d in policies} == {"all_staff", "manager"}


def test_task_2_1_returns_document_has_structured_window_and_exclusions(
    documents: tuple[Document, ...],
) -> None:
    returns = next(d for d in documents if d.doc_id == "returns-policy")
    assert returns.metadata["return_window_days"] == 30
    assert returns.metadata["excluded_categories"] == [
        "gift_cards",
        "perishable_food",
        "custom_orders",
    ]


def test_task_2_1_returns_document_has_one_category_exception(
    documents: tuple[Document, ...],
) -> None:
    returns = next(d for d in documents if d.doc_id == "returns-policy")
    assert returns.metadata["category_exceptions"] == [
        {"category": "electronics", "window_days": 14}
    ]


def test_task_2_1_exactly_one_policy_document_is_manager_only(
    documents: tuple[Document, ...],
) -> None:
    restricted = [d.doc_id for d in _by_type(documents, "policy") if d.audience == "manager"]
    assert restricted == ["manager-approvals"]


def test_task_2_1_store_operations_contact_field_is_read_and_audience_is_all_staff(
    documents: tuple[Document, ...],
) -> None:
    store_ops = next(d for d in documents if d.doc_id == "store-operations")
    assert store_ops.audience == "all_staff"
    contact = store_ops.metadata["escalation_contact"]
    assert isinstance(contact, str)
    assert "store-support@novamart.example.com" in contact


def test_task_2_1_only_store_operations_carries_an_escalation_contact(
    documents: tuple[Document, ...],
) -> None:
    holders = [d.doc_id for d in documents if "escalation_contact" in d.metadata]
    assert holders == ["store-operations"]


def test_task_2_1_deliberate_gaps_are_listed_in_readme_and_absent_from_documents(
    documents: tuple[Document, ...], data_dir: Path
) -> None:
    readme = (data_dir / "README.md").read_text(encoding="utf-8").lower()
    assert all(topic in readme for topic in GAP_TOPICS)
    corpus = " ".join(d.body.lower() for d in documents)
    assert not any(word in corpus for word in GAP_WORDS)


def test_task_2_4_three_product_documents_each_hold_one_intact_ascii_diagram(
    documents: tuple[Document, ...],
) -> None:
    products = _by_type(documents, "product")
    assert len(products) == 3
    for doc in products:
        blocks = fenced_blocks(doc.body)
        assert len(blocks) == 1, doc.doc_id
        assert blocks[0].strip() != ""
        assert all(ch == "\n" or 0x20 <= ord(ch) <= 0x7E for ch in blocks[0]), doc.doc_id


def test_task_2_4_diagram_fences_are_balanced(documents: tuple[Document, ...]) -> None:
    for doc in _by_type(documents, "product"):
        assert doc.body.count(FENCE) == 2, doc.doc_id


def test_task_2_4_one_product_document_has_audience_restriction(
    documents: tuple[Document, ...],
) -> None:
    restricted = [d.doc_id for d in _by_type(documents, "product") if d.audience == "manager"]
    assert restricted == ["product-novabook-launch-briefing"]


def test_loader_rejects_document_without_front_matter(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text("# No header\n", encoding="utf-8")
    with pytest.raises(DataLoadError, match="front-matter"):
        parse_document(bad)


def test_loader_rejects_unknown_audience(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text(
        "---\nid: x\ntitle: X\ndoc_type: policy\naudience: everyone\n---\nbody\n", encoding="utf-8"
    )
    with pytest.raises(DataLoadError, match="audience"):
        parse_document(bad)


def test_loader_rejects_duplicate_document_ids(tmp_path: Path) -> None:
    text = "---\nid: same\ntitle: T\ndoc_type: policy\naudience: all_staff\n---\nbody\n"
    (tmp_path / "a.md").write_text(text, encoding="utf-8")
    (tmp_path / "b.md").write_text(text, encoding="utf-8")
    with pytest.raises(DataLoadError, match="duplicate"):
        load_documents(tmp_path)


def test_fenced_blocks_rejects_unclosed_fence() -> None:
    with pytest.raises(DataLoadError, match="unclosed"):
        fenced_blocks("text\n" + FENCE + "\n+--+\n")
