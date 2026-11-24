#!/usr/bin/env python3
"""Validate an agent's returned report against its guardrails.

Usage: python validate_return.py --agent NAME [--tasks 1.1,1.2] [--repo DIR] FILE|-
  FILE|-   the agent's report (use - for stdin)
  --tasks  the task IDs the agent was assigned; the report must account for exactly these
Exit 0 = valid, 1 = problems, 2 = cannot run.
"""
import argparse
import sys
from pathlib import Path

import guardrails_lib as gl


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--agent", required=True)
    ap.add_argument("--tasks")
    ap.add_argument("--repo", default=".")
    a = ap.parse_args(argv)
    try:
        cfg, g = gl.load_all(a.repo)
        text = sys.stdin.read() if a.report == "-" else Path(a.report).read_text(encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"cannot run: {e}")
        return 2
    tasks = [t.strip() for t in a.tasks.split(",") if t.strip()] if a.tasks else None
    errs = gl.validate_return(a.agent, text, cfg, g, a.repo, tasks)
    for e in errs:
        print(f"INVALID RETURN: {e}")
    print(f"{a.agent}: " + ("valid" if not errs else f"{len(errs)} problem(s); treat as FAIL and send back"))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
