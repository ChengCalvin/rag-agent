"""Task 6.4: code-side output assembly: Sources from chunk metadata, the band footer, the
verbatim fenced-block check, and the order-route Sources entry (D15, AGENT-3)."""

from pathlib import Path

import pytest

from novamart_agent.config import DEFAULT_DOCS_PATH_LABEL
from novamart_agent.errors import ToolResultError
from novamart_agent.models import ConfidenceBand, DocumentRef, RetrievedChunk, SourceEntry
from novamart_agent.pipeline import (
    ReplyParts,
    assemble_reply,
    order_sources,
    parse_retrieval_result,
    policy_sources,
    sanitize_model_text,
)
from novamart_agent.prompts import SYNTHETIC_POLICY_NOTE, order_route_notes
from novamart_agent.rag import build_catalog, load_documents

FENCE = "`" * 3
DIAGRAM = "+-----+\n| Hub |\n+-----+"
CHUNK_TEXT = f"## Setup\nConnect it.\n\n{FENCE}\n{DIAGRAM}\n{FENCE}\n"
CATALOG = {
    "novahub-speaker": DocumentRef("NovaHub Speaker Guide", "product-novahub-speaker.md"),
    "returns-policy": DocumentRef("Returns Policy", "returns-policy.md"),
}
LABEL = DEFAULT_DOCS_PATH_LABEL


def chunk(doc_id: str = "novahub-speaker", heading: str = "Setup") -> RetrievedChunk:
    return RetrievedChunk(doc_id, heading, "x.md", "product", CHUNK_TEXT, 0.9)


# --- Sources from chunk metadata ----------------------------------------------------------------


def test_sources_come_from_chunk_metadata_and_the_catalog_with_heading_and_path() -> None:
    entries = policy_sources([chunk()], CATALOG, LABEL)
    path = "backend/data/docs/product-novahub-speaker.md"
    assert entries == (SourceEntry("NovaHub Speaker Guide", path, "Setup"),)


def test_the_sources_path_label_is_passed_in_not_hard_coded() -> None:
    (entry,) = policy_sources([chunk()], CATALOG, "elsewhere/docs")
    assert entry.path == "elsewhere/docs/product-novahub-speaker.md"
    (order_entry,) = order_sources("returns-policy", CATALOG, "elsewhere/docs")
    assert order_entry.path == "elsewhere/docs/returns-policy.md"


def test_sources_are_deduplicated_and_keep_distinct_sections() -> None:
    entries = policy_sources([chunk(), chunk(), chunk(heading="Reset")], CATALOG, LABEL)
    assert [e.heading for e in entries] == ["Setup", "Reset"]


def test_a_fabricated_citation_is_impossible_unknown_ids_get_no_entry() -> None:
    assert policy_sources([chunk("made-up-policy")], CATALOG, LABEL) == ()


def test_model_written_sources_and_confidence_lines_are_removed_from_the_reply() -> None:
    text = (
        "The window is 30 days.\n\nSources:\n- Fake Policy (fake.md)\n- Other (o.md)\n\n"
        "**Confidence**: High\nCost: $0.00"
    )
    cleaned = sanitize_model_text(text, [])
    assert cleaned == "The window is 30 days."
    reply = assemble_reply(
        ReplyParts(cleaned, policy_sources([chunk()], CATALOG, LABEL), ConfidenceBand.MEDIUM)
    )
    assert "Fake Policy" not in reply
    assert reply.count("Sources:") == 1
    assert "NovaHub Speaker Guide" in reply


def test_assembled_reply_has_body_sources_band_and_cost_in_order() -> None:
    reply = assemble_reply(
        ReplyParts(
            "Answer.",
            (SourceEntry("Returns Policy", "backend/data/docs/returns-policy.md", "Window"),),
            ConfidenceBand.HIGH,
            ("A note.",),
            "Cost: $0.00 this answer (0 calls)",
        )
    )
    assert reply.split("\n\n") == [
        "Answer.",
        "A note.",
        'Sources:\n- Returns Policy, section "Window" (backend/data/docs/returns-policy.md)',
        "Confidence: High",
        "Cost: $0.00 this answer (0 calls)",
    ]


def test_a_reply_with_no_sources_band_or_cost_is_just_the_body() -> None:
    assert assemble_reply(ReplyParts("  Hello  ")) == "Hello"


# --- fenced blocks must be verbatim ------------------------------------------------------------


def test_a_model_invented_diagram_is_stripped() -> None:
    reply = f"Here is the layout.\n\n{FENCE}\n+--+\n|ZZ|\n+--+\n{FENCE}\n\nDone."
    cleaned = sanitize_model_text(reply, [CHUNK_TEXT])
    assert "ZZ" not in cleaned
    assert FENCE not in cleaned
    assert cleaned == "Here is the layout.\n\nDone."


def test_a_diagram_that_appears_verbatim_in_a_chunk_is_kept_unchanged() -> None:
    reply = f"Wiring:\n\n{FENCE}\n{DIAGRAM}\n{FENCE}\n"
    assert sanitize_model_text(reply, [CHUNK_TEXT]) == f"Wiring:\n\n{FENCE}\n{DIAGRAM}\n{FENCE}"


def test_a_slightly_altered_diagram_is_stripped() -> None:
    altered = DIAGRAM.replace("Hub", "Hab")
    reply = f"{FENCE}\n{altered}\n{FENCE}"
    assert sanitize_model_text(reply, [CHUNK_TEXT]) == ""


def test_a_language_tagged_fence_with_verbatim_content_is_kept() -> None:
    reply = f"{FENCE}text\n{DIAGRAM}\n{FENCE}"
    assert DIAGRAM in sanitize_model_text(reply, [CHUNK_TEXT])


def test_an_unclosed_fence_is_stripped_to_the_end() -> None:
    reply = f"Intro.\n{FENCE}\n{DIAGRAM}\nstill going"
    assert sanitize_model_text(reply, [CHUNK_TEXT]) == "Intro."


def test_no_retrieved_chunks_means_every_block_is_stripped() -> None:
    assert sanitize_model_text(f"{FENCE}\n{DIAGRAM}\n{FENCE}", []) == ""


def test_footer_words_inside_a_verified_diagram_are_not_stripped() -> None:
    inner = "Cost: label\n+--+"
    chunk_text = f"{FENCE}\n{inner}\n{FENCE}"
    assert inner in sanitize_model_text(chunk_text, [chunk_text])


# --- order-route Sources ----------------------------------------------------------------------


def test_order_route_resolves_a_known_policy_id_to_title_and_path_without_a_heading() -> None:
    (entry,) = order_sources("returns-policy", CATALOG, LABEL)
    assert entry == SourceEntry("Returns Policy", "backend/data/docs/returns-policy.md", None)
    reply = assemble_reply(ReplyParts("Eligible.", (entry,)))
    assert "- Returns Policy (backend/data/docs/returns-policy.md)" in reply
    assert "section" not in reply


@pytest.mark.parametrize("policy_id", ["not-a-document", "", None, 7, ["returns-policy"]])
def test_order_route_unknown_or_missing_id_gives_no_entry_and_no_crash(policy_id: object) -> None:
    entries = order_sources(policy_id, CATALOG, LABEL)
    assert entries == ()
    assert "Sources" not in assemble_reply(ReplyParts("Status: delivered.", entries))


def test_loader_resolves_real_document_ids_to_title_and_file_name_only(data_dir: Path) -> None:
    catalog = build_catalog(load_documents(data_dir / "docs"))
    ref = catalog["returns-policy"]
    assert ref.file_name == "returns-policy.md"
    assert ref.title
    assert set(vars(ref)) == {"title", "file_name"}  # no heading, no text
    (entry,) = order_sources("returns-policy", catalog, LABEL)
    assert entry.path == "backend/data/docs/returns-policy.md"
    assert entry.heading is None


# --- notes: synthetic policy (compliance F2) and limitation -------------------------------------


def test_synthetic_policy_note_is_appended_on_the_eligibility_route_only() -> None:
    notes = order_route_notes(eligibility=True, flags_unanswered_policy=False)
    with_note = assemble_reply(ReplyParts("Eligible.", notes=notes))
    assert SYNTHETIC_POLICY_NOTE in with_note
    status_only = order_route_notes(eligibility=False, flags_unanswered_policy=False)
    assert status_only == ()


def test_limitation_sentence_follows_the_note_when_the_rubric_flags_a_policy_part() -> None:
    notes = order_route_notes(eligibility=True, flags_unanswered_policy=True)
    assert len(notes) == 2 and notes[0] == SYNTHETIC_POLICY_NOTE


# --- tool result parsing -----------------------------------------------------------------------


def test_parse_retrieval_result_types_ok_and_no_answer_results() -> None:
    ok = parse_retrieval_result(
        {
            "status": "ok",
            "embedding_cache_hit": True,
            "chunks": [
                {
                    "text": "t",
                    "document_id": "returns-policy",
                    "section_heading": "Window",
                    "file_path": "returns-policy.md",
                    "doc_type": "policy",
                    "score": 0.8,
                }
            ],
        }
    )
    assert ok.embedding_cache_hit is True and ok.chunks[0].document_id == "returns-policy"
    assert ok.embedded is False
    miss = parse_retrieval_result(
        {"status": "no_answer", "embedded": True, "closest_titles": ["A"]}
    )
    assert miss.chunks == () and miss.closest_titles == ("A",) and not miss.embedding_cache_hit
    assert miss.embedded is True


@pytest.mark.parametrize(
    "bad", [{}, {"status": "ok"}, {"status": "ok", "chunks": [1]}, {"status": "ok", "chunks": [{}]}]
)
def test_parse_retrieval_result_rejects_a_wrong_shape(bad: dict[str, object]) -> None:
    with pytest.raises(ToolResultError):
        parse_retrieval_result(bad)


def test_pipeline_is_pure_no_adk_no_same_layer_or_upward_imports() -> None:
    """ARCH-LAYER-3: `pipeline/` imports only shared (LAYER-4) code, never ADK, `rag`, `tools`,
    `prompts` or `security`; it reads no environment and no clock."""
    src = Path(__file__).resolve().parent.parent / "src" / "novamart_agent" / "pipeline"
    banned = ("google", "novamart_agent.rag", "novamart_agent.tools", "novamart_agent.prompts")
    for path in src.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for name in banned:
            assert f"import {name}" not in text and f"from {name}" not in text, path.name
        assert "os.environ" not in text and "datetime.now" not in text, path.name
