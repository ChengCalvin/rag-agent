"""Build the data directory a case runs against (the shipped data, plus a fixture document)."""

import shutil
from pathlib import Path


def prepare_data_dir(base: Path, fixture_dir: Path | None, scratch: Path) -> Path:
    """`base` itself, or a copy of it in `scratch` with the fixture's files added to `docs/`.

    The copy keeps the embedding cache (`.cache`), so unchanged documents are not re-embedded.
    The shipped corpus is never modified.
    """
    if fixture_dir is None:
        return base
    if scratch.exists():
        shutil.rmtree(scratch)
    shutil.copytree(base, scratch)
    for document in sorted(fixture_dir.glob("*.md")):
        shutil.copy2(document, scratch / "docs" / document.name)
    return scratch
