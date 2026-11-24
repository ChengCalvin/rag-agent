"""Hook logic for automatic audit capture (SubagentStop, Stop). Never blocks and never raises.

Self-contained like audit_lib.py (copied to docs/team/tools/ by setup-workflow). The hook scripts in
plugins/product-team/hooks/scripts are thin wrappers around `run_hook`.

Hook stdin is JSON: session_id, transcript_path, cwd, and for SubagentStop agent_id, agent_type and
agent_transcript_path.
"""
import json
import sys
from pathlib import Path

import audit_lib as al

PRICES = Path(__file__).resolve().parent / "prices.yaml"


class NoOp(Exception):
    """Nothing to record (no ledger dir, no resolvable change, nothing new). Silent."""


def find_repo(cwd):
    """Nearest parent of cwd that has a docs/team/audit directory."""
    p = Path(cwd or ".").resolve()
    for d in (p, *p.parents):
        if (d / "docs" / "team" / "audit").is_dir():
            return d
    raise NoOp("no ledger directory")


def resolve(data):
    repo = find_repo(data.get("cwd"))
    change = al.active_change(repo)
    if not change:
        raise NoOp("no active change")
    return repo, change


def _readable(path):
    if not path or not Path(path).is_file():
        raise NoOp("transcript not readable")
    return path


def record_subagent(data):
    repo, change = resolve(data)
    agent_type = data.get("agent_type") or ""
    if not agent_type.startswith("product-team:"):
        raise NoOp("not a product-team agent")
    agent_id = data.get("agent_id")
    if not agent_id:
        raise NoOp("no agent id")
    path = data.get("agent_transcript_path")
    if not path or not Path(path).is_file():
        path, _ = al.find_subagent(agent_id)
    tokens = al.transcript_tokens(_readable(path))
    if not tokens:
        raise NoOp("subagent used no tokens")
    skill, via, run = "", [], ""
    main = data.get("transcript_path")
    if main and Path(main).is_file():
        windows = al.skill_windows(main)
        skill, via = al.skill_at(windows, al.now())
        w = al.window_at(windows, al.now())
        run = w["start"] if w else ""
    agent = agent_type.split(":")[-1]
    stage = al.default_stage(skill, agent)
    prices = al.load_prices(PRICES)
    evs = al.read_events(repo, change)
    ev = {"type": "step", "stage": stage, "stage_source": "hook", "phase": al.PHASES[stage],
          "round": al.next_round(evs, stage), "agent": agent, "agent_id": agent_id, "chunk": None, "tasks": [],
          "description": None, "tokens": tokens, "cost_usd": al.cost_usd(tokens, prices),
          "price_table": prices.get("version"), "skill": skill, "skill_run": run, "via": via, "source": "hook"}
    return al.append(repo, change, ev, dedupe=f"agent:{agent_id}")


def record_turn(data):
    """Append main-session tokens since the ledger's watermark for this session, one event per skill window."""
    repo, change = resolve(data)
    sid, path = data.get("session_id"), _readable(data.get("transcript_path"))
    if not sid:
        raise NoOp("no session id")
    watermark = max((e["until"] for e in al.read_events(repo, change)
                     if e.get("type") == "skill_usage" and e.get("session_id") == sid and e.get("until")),
                    key=al._parse_ts, default=None)
    groups, last = al.windowed_usage(path, after=watermark)
    prices = al.load_prices(PRICES)
    out = []
    for g in groups:
        if not sum(sum(t.values()) for t in g["tokens"].values()):
            continue  # zero-token turns write nothing
        ev = {"type": "skill_usage", "skill": g["skill"], "skill_run": g["skill_run"], "via": g["via"],
              "session_id": sid, "until": last, "tokens": g["tokens"], "cost_usd": al.cost_usd(g["tokens"], prices),
              "price_table": prices.get("version"), "source": "hook"}
        out.append(al.append(repo, change, ev, dedupe=f"usage:{sid}:{last}:{g['skill_run']}"))
    return out


def run_hook(fn):
    """Read hook JSON from stdin, call fn(data). Always returns 0: an audit tool must not break an agent run."""
    try:
        fn(json.load(sys.stdin))
    except NoOp:
        pass
    except Exception as e:  # noqa: BLE001
        print(f"audit hook: {type(e).__name__}: {e}", file=sys.stderr)
    return 0
