"""Run the quality and security evals LIVE (OWNER-RUN ONLY: needs GOOGLE_API_KEY; ARCH-TEST-3).

Agents author this runner but never run it (HYG, TEST-4): every case calls the real model.
From the repo root, with `backend/.env` filled in:

    python backend/evals/run_evals.py                      # both sets, plus the ADK step
    python backend/evals/run_evals.py --set security --skip-adk
    python backend/evals/run_evals.py --only unknown-order-not-found

Outputs, in `backend/evals/results/`: per set `<set>-<stamp>.md` and `.json` (per-case results,
overall pass rate, model calls and cost per question) and, unless `--skip-adk`, one
`adk-<stamp>.json` listing each `adk eval` command with its exit code (no output is stored).
Without a key it prints a message and exits 2 before any model call.
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from evalkit import (
    CaseResult,
    adk_commands,
    adk_record,
    failed_run,
    grade_case,
    load_all_cases,
    select_cases,
    summarize,
    write_results,
)
from evalkit.cases import Case
from evalkit.drive import Runtime, run_case
from evalkit.seeded import load_seeded_values
from novamart_agent.config import load_settings

EVALS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVALS_DIR.parent
AGENT_DIR = BACKEND_DIR / "src" / "novamart_agent"
RESULTS_DIR = EVALS_DIR / "results"
NO_KEY = 2


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the NovaMart evals (live, needs a key).")
    parser.add_argument("--set", choices=["quality", "security"], default=None)
    parser.add_argument("--only", action="append", default=[], help="a case id (repeatable)")
    parser.add_argument("--skip-adk", action="store_true", help="skip the `adk eval` step")
    return parser.parse_args(argv)


async def run_all(cases: tuple[Case, ...], runtime: Runtime) -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in cases:
        try:
            results.append(grade_case(case, await run_case(case, runtime)))
        except Exception as exc:  # noqa: BLE001 - one broken case must not hide the others
            results.append(failed_run(case, type(exc).__name__))
        print(f"{'PASS' if results[-1].passed else 'FAIL'} {case.case_id}", flush=True)
    return results


def run_adk(only_set: str | None, stamp: str) -> None:
    """Run each `adk eval` command with its persona; keep only its exit code (ERR-2: no output)."""
    records: list[dict[str, object]] = []
    for command in adk_commands(EVALS_DIR / "evalsets", AGENT_DIR, only_set):
        env = {**os.environ, "NOVAMART_USER": command.persona}
        done = subprocess.run(command.argv, env=env, capture_output=True, text=True, check=False)
        records.append(adk_record(command, done.returncode))
    out = RESULTS_DIR / f"adk-{stamp}.json"
    out.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")


def report(results: list[CaseResult], stamp: str) -> None:
    for set_name in sorted({r.set_name for r in results}):
        part = [r for r in results if r.set_name == set_name]
        summary = summarize(set_name, part)
        write_results(RESULTS_DIR, stamp, part, summary)
        print(f"{set_name}: {summary.passed}/{summary.total} passed ({summary.pass_rate:.0%})")


async def main(argv: list[str]) -> int:
    args = parse_args(argv)
    # standards-exception(CONV-1): owner-run eval scripts load backend/.env before config
    load_dotenv(BACKEND_DIR / ".env")
    if not os.environ.get("GOOGLE_API_KEY"):
        print("GOOGLE_API_KEY is not set; the evals are live-only. Nothing was run.")
        return NO_KEY
    settings = load_settings()
    runtime = Runtime(
        settings,
        EVALS_DIR / "fixtures",
        RESULTS_DIR / "scratch",
        load_seeded_values(settings.data_dir / "orders.json"),
    )
    cases = select_cases(load_all_cases(EVALS_DIR / "cases"), args.set, tuple(args.only))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    results = await run_all(cases, runtime)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report(results, stamp)
    if not args.skip_adk:
        run_adk(args.set, stamp)
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
