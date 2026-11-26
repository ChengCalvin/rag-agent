"""Chunk 9: README claims that can be checked without a key.

Covers task 9.1 (every path and command in the README exists, required warnings) and task 9.4.
The production note is a planning document, not part of the code, so no test reads it.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
README = (REPO / "README.md").read_text(encoding="utf-8")


def test_readme_local_links_and_paths_exist() -> None:
    """9.1: every local link and every backticked repo path in the README exists."""
    targets = set(re.findall(r"\]\(([^)#]+)\)", README))
    targets |= set(re.findall(r"`((?:backend|docs|openspec)/[\w./-]+)`", README))
    targets |= set(re.findall(r"python (backend/[\w./-]+\.py)", README))
    local = {t for t in targets if not t.startswith("http")}
    assert local
    missing = [t for t in sorted(local) if not (REPO / t.rstrip("/")).exists()]
    # backend/data/.cache is created at run time and is git-ignored.
    assert [m for m in missing if ".cache" not in m] == []


def test_readme_persona_table_matches_users_json() -> None:
    """9.1: the persona table lists exactly the personas in users.json."""
    users = json.loads((REPO / "backend/data/users.json").read_text(encoding="utf-8"))["users"]
    ids = {u["user_id"] for u in users}
    rows = re.findall(r"^\| `(\w+)` \|", README, flags=re.MULTILINE)
    listed = set(rows) - {"NOVAMART_USER"}  # the header cell of the persona table
    assert listed == ids


def test_readme_env_names_are_in_env_example() -> None:
    """9.1: each environment variable the README names is documented in .env.example."""
    example = (REPO / "backend/.env.example").read_text(encoding="utf-8")
    names = set(re.findall(r"`?\b((?:NOVAMART|GOOGLE)_[A-Z_]+)\b", README))
    assert names
    assert [n for n in sorted(names) if n not in example] == []


def test_readme_states_required_warnings() -> None:
    """9.1: synthetic data, not-authentication, lower-bound cost and trace statements."""
    text = README.lower()
    assert "synthetic" in text
    assert "not authentication" in text
    assert "lower bound" in text
    assert "full event trace" in text
    assert "adk web backend/src" in README
    assert "backend/data/README.md" in README
    assert "pip install -e" in README and "backend[dev]" in README


def test_env_file_is_gitignored() -> None:
    """9.4: backend/.env is git-ignored."""
    lines = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in [line.strip() for line in lines]
