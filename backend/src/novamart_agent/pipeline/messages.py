"""Message content handed to the validator and composer agents (tasks 7.3, 7.4, D15, D16).

Untrusted text (the rubric, retrieved chunks, tool results, the user's words) goes in as one JSON
record of message content, never into instruction text, so it is data and not instructions
(AGENT-4). Diagram blocks are extracted by code from the cited chunks and handed over to be
included unchanged; the model never draws one (AGENT-3).
"""

import json
from collections.abc import Mapping, Sequence

from novamart_agent.models import DOC_TYPES, RetrievedChunk, Rubric
from novamart_agent.pipeline.fences import split_fences


def _dump(record: Mapping[str, object]) -> str:
    return json.dumps(record, ensure_ascii=False, indent=2)


def _chunk_record(chunk: RetrievedChunk) -> dict[str, object]:
    return {"id": chunk.document_id, "section": chunk.heading, "text": chunk.text}


def validator_message(rubric: Rubric, chunks: Sequence[RetrievedChunk]) -> str:
    """The record the validator judges: numbered criteria and the retrieved chunks."""
    return _dump(
        {
            "criteria": [
                {"number": i + 1, "text": c.text, "required": c.required}
                for i, c in enumerate(rubric.criteria)
            ],
            "retrieved_chunks": [_chunk_record(c) for c in chunks],
        }
    )


def diagram_blocks(chunks: Sequence[RetrievedChunk]) -> tuple[str, ...]:
    """Every closed fenced block of the chunks, fences included, in order, without repeats."""
    blocks: list[str] = []
    for chunk in chunks:
        for segment in split_fences(chunk.text):
            if segment.is_fence and segment.closed and not segment.inline:
                block = "\n".join(segment.lines)
                if block not in blocks:
                    blocks.append(block)
    return tuple(blocks)


def answer_doc_type(rubric: Rubric, chunks: Sequence[RetrievedChunk]) -> str:
    """`policy` or `product`: the rubric's type when valid, else the first chunk's, else policy."""
    if rubric.doc_type is not None and rubric.doc_type in DOC_TYPES:
        return rubric.doc_type
    for chunk in chunks:
        if chunk.doc_type in DOC_TYPES:
            return chunk.doc_type
    return "policy"


def knowledge_composer_message(
    question: str, rubric: Rubric, chunks: Sequence[RetrievedChunk]
) -> str:
    """The record for a policy or product answer, built from the best attempt's chunks."""
    return _dump(
        {
            "question": question,
            "doc_type": answer_doc_type(rubric, chunks),
            "criteria": [c.text for c in rubric.criteria],
            "evidence": [_chunk_record(c) for c in chunks],
            "diagrams": list(diagram_blocks(chunks)),
        }
    )


def order_composer_message(question: str, results: Mapping[str, Mapping[str, object]]) -> str:
    """The record for an order answer: the guarded tool results of this turn."""
    return _dump({"question": question, "doc_type": "order", "order_records": dict(results)})
