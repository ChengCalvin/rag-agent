"""Eval kit support pieces (task 8.4): seeded values, log capture, fixture corpus, event reading.
Key-free."""

import logging
from pathlib import Path

from google.adk import Event
from google.genai import types

from evalkit.corpus import prepare_data_dir
from evalkit.events import final_reply, tool_calls
from evalkit.log_capture import capture_logs
from evalkit.seeded import load_seeded_values

EVALS = Path(__file__).resolve().parent.parent / "evals"


def test_seeded_values_cover_every_order_name_email_and_address(data_dir: Path) -> None:
    values = load_seeded_values(data_dir / "orders.json")
    labels = {v.label for v in values}
    assert len(values) == 30 and "NM-480101.email" in labels and "NM-480303.address" in labels
    assert any(v.text == "ottoline.thrushwick@example.test" for v in values)


def test_log_capture_sees_every_logger_at_debug_and_restores_the_root_level() -> None:
    root = logging.getLogger()
    before = root.level
    with capture_logs() as lines:
        logging.getLogger("novamart.audit").info("audit one")
        logging.getLogger("google_adk.deep").debug("debug two")
    assert any("audit one" in line for line in lines)
    assert any("debug two" in line for line in lines)
    assert root.level == before
    assert not [h for h in root.handlers if type(h).__name__ == "_Collector"]


def test_the_fixture_corpus_is_a_copy_and_the_shipped_data_is_never_changed(
    data_dir: Path, tmp_path: Path
) -> None:
    shipped = sorted(p.name for p in (data_dir / "docs").glob("*.md"))
    fixture = EVALS / "fixtures" / "poisoned-courier-memo"
    copy = prepare_data_dir(data_dir, fixture, tmp_path / "scratch")
    assert copy != data_dir
    assert (copy / "docs" / "poisoned-courier-memo.md").is_file()
    assert (copy / "orders.json").is_file() and (copy / "users.json").is_file()
    assert sorted(p.name for p in (data_dir / "docs").glob("*.md")) == shipped
    assert prepare_data_dir(data_dir, None, tmp_path / "unused") == data_dir


def _event(author: str, *parts: types.Part) -> Event:
    return Event(author=author, content=types.Content(role="model", parts=list(parts)))


def test_tool_calls_and_the_final_reply_are_read_from_events() -> None:
    call = types.Part(function_call=types.FunctionCall(name="search_policy", args={"query": "q"}))
    events = [
        _event("user", types.Part(text="hello")),
        _event("retrieval", call),
        _event("retrieval", types.Part(text="tool chatter")),
        _event("novamart_assistant", types.Part(text="Final answer.")),
    ]
    assert [c.name for c in tool_calls(events)] == ["search_policy"]
    assert tool_calls(events)[0].args == (("query", "q"),)
    assert final_reply(events) == "Final answer."
    assert final_reply([]) == "" and tool_calls([]) == ()
