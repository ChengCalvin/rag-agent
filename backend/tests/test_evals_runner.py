"""Eval runner CLI, key-free: no key exits 2 before any model call; adk output is never stored."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import run_evals
from evalkit import AdkCommand, adk_commands, adk_record

EVALS = Path(__file__).resolve().parent.parent / "evals"
REPLY = "Order NM-480103 for Jane Doe, 12 Elm St, is in transit"


def test_run_evals_without_a_key_returns_2_before_any_model_call(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(run_evals, "load_dotenv", lambda *_a, **_k: False)

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("the model path was reached without a key")

    monkeypatch.setattr(run_evals, "load_settings", boom)
    monkeypatch.setattr(run_evals, "run_all", boom)
    assert asyncio.run(run_evals.main(["--skip-adk"])) == run_evals.NO_KEY == 2
    assert "Nothing was run" in capsys.readouterr().out


def test_adk_eval_commands_do_not_ask_for_detailed_results() -> None:
    for command in adk_commands(EVALS / "evalsets", Path("agent_dir"), None):
        assert "--print_detailed_results" not in command.argv


def test_adk_record_keeps_only_the_command_and_exit_code() -> None:
    record = adk_record(AdkCommand("in_order/x.evalset.json", "emp_store7", ("adk",)), 1)
    assert record == {"command": "in_order/x.evalset.json", "exit_code": 1}


def test_run_adk_persists_no_reply_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    done = SimpleNamespace(returncode=0, stdout=REPLY, stderr=REPLY)
    monkeypatch.setattr(run_evals.subprocess, "run", lambda *_a, **_k: done)
    monkeypatch.setattr(run_evals, "RESULTS_DIR", tmp_path)
    run_evals.run_adk(None, "stamp")
    files = list(tmp_path.iterdir())
    assert [f.name for f in files] == ["adk-stamp.json"]  # no per-command output file
    text = files[0].read_text(encoding="utf-8")
    assert "Jane" not in text and "Elm St" not in text and "in transit" not in text
    assert all(set(r) == {"command", "exit_code"} for r in json.loads(text))
