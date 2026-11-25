"""Task 8.5 helper: replay recorded composite inputs under other weights, T and band cut-offs.

No key, no model call. Reads the `attempts` a quality run recorded and labels each case from its
id: answerable (a correct answer is expected) or weak (documents do not cover it: must be Low).
Usage: python backend/evals/tune_confidence.py backend/evals/results/quality-<stamp>.json
"""

import itertools
import json
import sys
from pathlib import Path

WEAK_HINTS = ("silent-on", "partially-covered")


def load(path: Path) -> tuple[list[list[tuple[float, ...]]], list[list[tuple[float, ...]]]]:
    """(answerable, weak): per case, the (coverage, score, llm, required_uncovered) of each pass."""
    answerable: list[list[tuple[float, ...]]] = []
    weak: list[list[tuple[float, ...]]] = []
    for case in json.loads(path.read_text(encoding="utf-8"))["cases"]:
        passes = [
            (a[4], a[5], a[6], float(a[3])) for turn in case["turns"] for a in turn["attempts"]
        ]
        if not passes:
            continue
        is_weak = any(h in case["case_id"] for h in WEAK_HINTS)
        (weak if is_weak else answerable).append(passes)
    return answerable, weak


def composite(p: tuple[float, ...], w: tuple[float, float, float]) -> float:
    return w[0] * p[0] + w[1] * p[1] + w[2] * p[2]


def gap(answerable, weak, w):  # type: ignore[no-untyped-def]
    """Lowest answerable first pass and highest weak pass, raw composites (T compares these)."""
    low = min(composite(c[0], w) for c in answerable)
    high = max(composite(p, w) for c in weak for p in c)
    return low, high


def main() -> int:
    answerable, weak = load(Path(sys.argv[1]))
    print(f"{len(answerable)} answerable cases, {len(weak)} weak cases")
    rows = []
    steps = [i / 10 for i in range(0, 11)]
    for a, b in itertools.product(steps, steps):
        if a + b <= 1.0 + 1e-9:
            w = (a, b, round(1.0 - a - b, 10))
            low, high = gap(answerable, weak, w)
            rows.append((low - high, w, low, high))
    rows.sort(reverse=True)
    print("\nbest weights (coverage, score, llm) by gap between answerable min and weak max:")
    for margin, w, low, high in rows[:6]:
        print(f"  {w}: answerable min {low:.2f}, weak max {high:.2f}, gap {margin:.2f}")
    current = (0.6, 0.2, 0.2)
    low, high = gap(answerable, weak, current)
    print(
        f"\ncurrent {current}: answerable min {low:.2f}, weak max {high:.2f}, gap {low - high:.2f}"
    )
    mid = (low + high) / 2
    print(f"safe T / medium range under current weights: ({high:.2f}, {low:.2f}); mid {mid:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
