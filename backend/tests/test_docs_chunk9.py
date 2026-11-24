"""Chunk 9: README and production note claims that can be checked without a key.

Covers spec scenarios of `production-note` (required topics present, length limit, recommendation
stated, identity risk named, unverified claims marked, limits section) and task 9.1 (every path and
command in the README exists).
"""

import json
import re
from pathlib import Path

from novamart_agent.config import DEFAULT_PRICES

REPO = Path(__file__).resolve().parents[2]
README = (REPO / "README.md").read_text(encoding="utf-8")
NOTE = (REPO / "docs" / "production_note.md").read_text(encoding="utf-8")

# One page at 10 pt with 0.75 in margins holds about 700 words including markup.
NOTE_WORD_BUDGET = 700
NOTE_LINE_BUDGET = 60


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


def test_production_note_has_four_labelled_sections() -> None:
    """Required topics present: each of the four topics has its own heading."""
    headings = re.findall(r"^## (.+)$", NOTE, flags=re.MULTILINE)
    for topic in (
        "Gemini Enterprise or custom build",
        "real data",
        "Security and governance",
        "Evaluating and monitoring",
    ):
        assert any(topic in h for h in headings), topic


def test_production_note_fits_one_page_budget() -> None:
    """Length limit: the note stays inside the word and line budget for one page."""
    assert len(NOTE.split()) <= NOTE_WORD_BUDGET
    assert len(NOTE.splitlines()) <= NOTE_LINE_BUDGET


def test_production_note_states_recommendation_and_fallback() -> None:
    """Recommendation stated: architecture, reasons, fallback, and when it would change."""
    assert "**Recommendation: hybrid.**" in NOTE
    assert "**Fallback**" in NOTE
    assert "**Revisit**" in NOTE


def test_production_note_names_identity_spike_with_owner_and_fallback() -> None:
    """Identity risk named: the question, who must answer it, and the fallback."""
    spike = NOTE.split("**Identity-propagation spike")[1].split("\n- ")[0]
    assert "order API" in spike
    assert "Owners:" in spike
    assert "Fallback" in spike


def test_production_note_lists_limits_including_combined_questions() -> None:
    """Limits section: simulated parts, their replacement, and the combined-question limit."""
    limits = NOTE.split("## Prototype limits")[1]
    assert "Persona" in limits and "not authentication" in limits
    assert "Orders in a JSON file" in limits
    assert "Combined order-and-policy" in limits


def test_production_note_marks_unverified_claims_and_cites_sources() -> None:
    """Unverified claim: marked TBC; verified claims carry a dated source."""
    assert NOTE.count("TBC") >= 5
    assert "2026-11-24" in NOTE
    for n in range(1, 6):
        assert f"[{n}] " in NOTE.split("Sources, all read")[1]


def test_production_note_prices_match_config() -> None:
    """9.2: the token prices quoted in the note equal the config price table."""
    flash = DEFAULT_PRICES["gemini-3.6-flash"]
    lite = DEFAULT_PRICES["gemini-3.5-flash-lite"]
    emb = DEFAULT_PRICES["gemini-embedding-001"]
    assert f"${flash.input_per_m:.2f} in / ${flash.output_per_m:.2f} out" in NOTE
    assert f"${lite.input_per_m:.2f} / ${lite.output_per_m:.2f}" in NOTE
    assert f"${emb.input_per_m:.2f} in" in NOTE
