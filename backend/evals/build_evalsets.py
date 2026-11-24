"""Regenerate `backend/evals/evalsets/` from `cases/*.json` (key-free; no model call).

    python backend/evals/build_evalsets.py
"""

import shutil
import sys
from pathlib import Path

from evalkit import evalset_files, load_all_cases

EVALS_DIR = Path(__file__).resolve().parent


def main() -> int:
    target = EVALS_DIR / "evalsets"
    if target.exists():
        shutil.rmtree(target)
    for relative, content in evalset_files(load_all_cases(EVALS_DIR / "cases")).items():
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
