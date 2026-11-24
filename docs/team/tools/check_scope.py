#!/usr/bin/env python3
"""Check that an agent changed only what its guardrails allow.

Usage: python check_scope.py --agent NAME [--base REF] [--report FILE] [--files a b ...] [repo]
  --base    compare the working tree with this ref (default HEAD: everything uncommitted).
            Use the commit before the delegation when the agent committed its work.
  --files   check these paths instead of asking git.
Exit 0 = in scope, 1 = violations, 2 = cannot run.
"""
import argparse
import sys
from pathlib import Path

import guardrails_lib as gl


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--agent", required=True)
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("--report")
    ap.add_argument("--files", nargs="*")
    a = ap.parse_args(argv)
    try:
        cfg, g = gl.load_all(a.repo)
        files = a.files if a.files is not None else gl.changed_files(a.repo, a.base)
        report = Path(a.report).read_text(encoding="utf-8") if a.report else None
    except Exception as e:  # noqa: BLE001
        print(f"cannot run: {e}")
        return 2
    errs = gl.scope_violations(a.agent, files, cfg, g, report)
    for e in errs:
        print(f"OUT OF SCOPE: {e}")
    print(f"{a.agent}: {len(files)} changed file(s), " + ("IN SCOPE" if not errs else f"{len(errs)} violation(s)"))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
