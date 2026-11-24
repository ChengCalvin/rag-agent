"""Task 6.4: the fence scanner of the output check (D15, QA6-1, QA6-7) and its parity with the
document loader's fence predicate (STRUCT-5: two scanners must agree on what a fence is)."""

import pytest

from novamart_agent.pipeline import sanitize_model_text
from novamart_agent.pipeline.fences import block_keys, split_fences
from novamart_agent.rag.documents import fenced_blocks, is_fence_line

TICKS = "`" * 3
TILDES = "~" * 3
DIAGRAM = "+-----+\n| Hub |\n+-----+"
CHUNK = f"## Setup\n\n{TICKS}\n{DIAGRAM}\n{TICKS}\n"
INVENTED = "graph TD\n  X-->Y"


def san(reply: str) -> str:
    return sanitize_model_text(reply, [CHUNK])


# --- parity with rag.documents ------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [TICKS, f"{TICKS}mermaid", f"  {TICKS}", f"{TICKS}x ", "plain text", "", "`one` tick", "``two"],
)
def test_both_scanners_agree_on_what_a_backtick_fence_line_is(line: str) -> None:
    pipeline_sees_fence = any(s.is_fence for s in split_fences(line))
    assert pipeline_sees_fence == is_fence_line(line)


def test_both_scanners_agree_on_the_blocks_of_a_shared_document() -> None:
    text = f"Intro\n{TICKS}text\n{DIAGRAM}\n{TICKS}\nMiddle\n{TICKS}\nsecond\n{TICKS}\nEnd\n"
    assert block_keys(text) == set(fenced_blocks(text)) == {DIAGRAM, "second"}


# --- tilde and nested fences (QA6-1) -------------------------------------------------------------


def test_a_model_invented_tilde_fenced_diagram_is_stripped() -> None:
    assert san(f"Layout:\n{TILDES}mermaid\n{INVENTED}\n{TILDES}\nDone.") == "Layout:\nDone."


def test_a_tilde_fenced_diagram_is_kept_only_when_verbatim_in_a_chunk() -> None:
    tilde_chunk = f"{TILDES}\n{DIAGRAM}\n{TILDES}"
    reply = f"See:\n{TILDES}\n{DIAGRAM}\n{TILDES}"
    assert sanitize_model_text(reply, [tilde_chunk]) == reply
    assert sanitize_model_text(reply, []) == "See:"


def test_a_longer_tilde_fence_closes_only_on_an_equal_or_longer_run() -> None:
    reply = f"A\n~~~~\nx\n{TILDES}\nstill inside\n~~~~\nB"
    assert san(reply) == "A\nB"


def test_a_tilde_marker_does_not_close_a_backtick_fence() -> None:
    reply = f"A\n{TICKS}\nx\n{TILDES}\nstill inside\n{TICKS}\nB"
    assert san(reply) == "A\nB"


def test_a_four_backtick_wrapper_strips_the_whole_block_with_a_verified_diagram() -> None:
    wrapped = f"A\n````\n{TICKS}\n{DIAGRAM}\n{TICKS}\n````\nB"
    cleaned = san(wrapped)
    assert cleaned == "A\nB"
    assert "Hub" not in cleaned


def test_an_inline_fence_opener_strips_the_whole_block_and_leaks_nothing() -> None:
    cleaned = san(f"see {TICKS}mermaid\n{INVENTED}\n{TICKS}\nafter")
    assert "X-->Y" not in cleaned and cleaned == "after"


def test_an_inline_opener_around_a_verified_diagram_is_still_stripped() -> None:
    assert san(f"look {TICKS}\n{DIAGRAM}\n{TICKS}\nafter") == "after"


def test_an_indented_fence_of_up_to_three_spaces_is_a_fence() -> None:
    assert san(f"A\n   {TICKS}\n{INVENTED}\n   {TICKS}\nB") == "A\nB"


def test_a_one_line_code_span_is_plain_text() -> None:
    assert san(f"Run {TICKS}ls{TICKS} now") == f"Run {TICKS}ls{TICKS} now"


# --- footer lines (QA6-2) ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "Confidence - High",
        "Confidence – High",
        "Sources：",
        "Sources： a.md",
        "Sources​",
        "Sou​rces:",
        "**Sources**​:",
        "Ｃonfidence: High",
        "Cost - $0.01",
    ],
)
def test_footer_lines_are_removed_after_normalising_width_and_zero_width_characters(
    line: str,
) -> None:
    assert san(f"Answer.\n{line}\nTail") == "Answer.\nTail"


@pytest.mark.parametrize(
    "line", ["Cost-effective options exist.", "The cost of shipping is $5.", "Sources are below."]
)
def test_prose_that_only_starts_with_a_footer_word_is_kept(line: str) -> None:
    assert san(f"Answer.\n{line}") == f"Answer.\n{line}"
