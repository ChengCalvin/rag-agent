#!/usr/bin/env python3
"""Audit trail CLI. Run by the orchestrator, never by an agent.

  begin                          print a snapshot id; call before delegating
  use       --change X                     mark X as the active change for hooks (docs/team/audit/ACTIVE)
  step      --stage S --agent A --before SNAP (--agent-id ID | --transcript FILE [--since TS --until TS]) [--skill NAME]
  scenarios --chunk C --ids S1,S2          register the spec scenarios a chunk must cover
  gate      --chunk C --gate G --agent A --results FILE.json [--agent-id ID]
  decision  --by owner|owner-delegated|agent:NAME --kind K --question Q --choice X [--quote TEXT]
  check                                    exit 1 on errors
  report    [--write]                      markdown to stdout, or docs/team/audit/<change>.md
Common: --repo DIR (default .), --change ID.
"""
import argparse
import json
import sys
from pathlib import Path

import audit_lib as al

PRICES = Path(__file__).resolve().parent / "prices.yaml"


def build_parser():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["begin", "use", "step", "scenarios", "gate", "decision", "check", "report"])
    for name in ("--repo", "--change", "--stage", "--agent", "--chunk", "--tasks", "--before", "--agent-id",
                 "--transcript", "--since", "--until", "--projects-dir", "--ids", "--gate", "--results", "--by",
                 "--question", "--options", "--choice", "--ref", "--quote", "--skill"):
        ap.add_argument(name)
    ap.set_defaults(repo=".", kind="other", rationale="")
    ap.add_argument("--kind")
    ap.add_argument("--rationale")
    ap.add_argument("--write", action="store_true")
    return ap


def cmd_step(a, evs):
    if a.stage not in al.PHASES:
        print(f"--stage must be one of {sorted(al.PHASES)}")
        return 2
    path, meta = a.transcript, {}
    if a.agent_id:
        path, meta = al.find_subagent(a.agent_id, a.projects_dir)
    if not path:
        print("cannot find the transcript; pass --agent-id or --transcript")
        return 2
    prices = al.load_prices(PRICES)
    tokens = al.transcript_tokens(path, a.since, a.until)
    ev = {"type": "step", "stage": a.stage, "phase": al.PHASES[a.stage], "round": al.next_round(evs, a.stage),
          "agent": a.agent or meta.get("agentType", "orchestrator"), "chunk": a.chunk,
          "tasks": a.tasks.split(",") if a.tasks else [], "description": meta.get("description"),
          "tokens": tokens, "cost_usd": al.cost_usd(tokens, prices), "price_table": prices.get("version")}
    skill, via, run = a.skill or "", [], ""
    if not a.skill and a.transcript:  # a main-session transcript: the skill active at the end of the slice
        windows = al.skill_windows(a.transcript)
        at = a.until or al.now()
        skill, via = al.skill_at(windows, at)
        w = al.window_at(windows, at)
        run = w["start"] if w else ""
    ev.update({"skill": skill, "skill_run": run, "via": via})
    if a.before:
        ev["files"] = al.file_delta(a.repo, a.before, al.snapshot(a.repo))
    e = al.append(a.repo, a.change, ev)
    print(f"recorded step {e['seq']}: {e['agent']} {a.stage} round {e['round']} cost {e['cost_usd']}")
    return 0


def cmd_gate(a, evs):
    results = json.loads(Path(a.results).read_text(encoding="utf-8"))
    exp = next((e["ids"] for e in reversed(evs) if e["type"] == "scenarios" and e["chunk"] == a.chunk), None)
    errs = al.validate_results(results, exp)
    for m in errs:
        print(f"INVALID GATE: {m}")
    if errs:
        print("not recorded; send back to the gate agent")
        return 1
    ev = {"type": "gate", "chunk": a.chunk, "gate": a.gate, "agent": a.agent, "results": results}
    if a.agent_id:
        path, _ = al.find_subagent(a.agent_id, a.projects_dir)
        ev["commands"] = al.tool_commands(path) if path else None
    al.append(a.repo, a.change, ev)
    print(f"recorded gate {a.gate}: {sum(r['result'] == 'pass' for r in results)}/{len(results)} pass")
    return 0


def cmd_decision(a, evs):
    if a.by in al.DECIDERS and not a.quote:
        print("an owner decision needs --quote with the owner's actual message")
        return 1
    if not a.by or not (a.by in al.DECIDERS or a.by.startswith("agent:")):
        print("--by must be owner, owner-delegated or agent:<name>")
        return 2
    al.append(a.repo, a.change, {
        "type": "decision", "decided_by": a.by, "kind": a.kind, "question": a.question,
        "options": a.options.split("|") if a.options else [], "choice": a.choice,
        "rationale": a.rationale, "ref": a.ref or "", "quote": a.quote})
    print("recorded decision")
    return 0


def cmd_check(a, evs):
    errs, warns = al.check(evs)
    for w in warns:
        print(f"warn: {w}")
    for e in errs:
        print(f"ERROR: {e}")
    print("OK" if not errs else f"{len(errs)} error(s)")
    return 1 if errs else 0


def cmd_report(a, evs):
    md = al.report(evs, a.change)
    if a.write:
        p = al.ledger_path(a.repo, a.change).with_suffix(".md")
        p.write_text(md, encoding="utf-8", newline="\n")
        print(f"wrote {p}")
    else:
        print(md)
    return 0


def main(argv):
    a = build_parser().parse_args(argv)
    try:
        if a.cmd == "begin":
            print(al.snapshot(a.repo))
            return 0
        if not a.change:
            print("--change is required")
            return 2
        if a.cmd == "use":
            print(f"active change: {a.change} ({al.set_active(a.repo, a.change)})")
            return 0
        evs = al.read_events(a.repo, a.change)
        if a.cmd == "scenarios":
            al.append(a.repo, a.change, {"type": "scenarios", "chunk": a.chunk, "ids": a.ids.split(",")})
            print("registered")
            return 0
        return {"step": cmd_step, "gate": cmd_gate, "decision": cmd_decision,
                "check": cmd_check, "report": cmd_report}[a.cmd](a, evs)
    except Exception as e:  # noqa: BLE001
        print(f"cannot run: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
