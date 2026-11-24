"""Audit trail logic: append-only hash-chained ledger, cost from transcripts, file deltas from git trees.

Self-contained (PyYAML + git only) so render copies it to docs/team/tools/.
Ledger: docs/team/audit/<change>.jsonl. Never edited; corrections are new events.
"""
import glob
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import yaml

# stage -> phase. "explore" is thinking/planning spend, "execute" is building and fixing.
PHASES = {
    "explore": "explore", "specify": "explore", "propose": "explore", "design": "explore", "plan": "explore",
    "build": "execute", "fix": "execute",
    "verify": "verify",
    "release": "release", "archive": "release",
}
OWNER_ONLY_KINDS = {"spec", "stack_change", "production_deploy"}
DECIDERS = ("owner", "owner-delegated")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ledger_path(repo, change):
    return Path(repo) / "docs" / "team" / "audit" / f"{change}.jsonl"


# ---------- ledger ----------

def _hash(ev):
    body = {k: v for k, v in ev.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def read_events(repo, change):
    p = ledger_path(repo, change)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


class LockTimeout(RuntimeError):
    pass


@contextmanager
def _lock(ledger, timeout=10.0, stale=60.0):
    """Portable exclusive lock: create-exclusive file next to the ledger, retry until timeout, steal if stale."""
    lp = ledger.with_suffix(".lock")
    lp.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.close(os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except (FileExistsError, PermissionError):  # Windows reports a file mid-delete as PermissionError
            try:
                if time.time() - os.path.getmtime(lp) > stale:
                    os.unlink(lp)
                    continue
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise LockTimeout(f"could not lock {lp}")
            time.sleep(0.02)
    try:
        yield
    finally:
        try:
            os.unlink(lp)
        except OSError:
            pass


def append(repo, change, ev, dedupe=None):
    """Append one hash-chained event under an exclusive lock. With `dedupe`, an event carrying the same key is
    not appended again (returns None), so a hook that fires twice records once."""
    p = ledger_path(repo, change)
    with _lock(p):
        evs = read_events(repo, change)
        if dedupe and any(e.get("dedupe") == dedupe for e in evs):
            return None
        if dedupe:
            ev = {**ev, "dedupe": dedupe}
        ev = {"seq": len(evs) + 1, "ts": now(), "change": change, **ev, "prev": evs[-1]["hash"] if evs else ""}
        ev["hash"] = _hash(ev)
        with p.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(ev, sort_keys=True, ensure_ascii=False) + "\n")
    return ev


def verify_chain(evs):
    errs, prev = [], ""
    for i, e in enumerate(evs, 1):
        if e.get("seq") != i:
            errs.append(f"event {i}: seq is {e.get('seq')}")
        if e.get("prev") != prev:
            errs.append(f"event {i}: chain broken (prev hash mismatch); the ledger was edited or reordered")
        if e.get("hash") != _hash(e):
            errs.append(f"event {i}: content does not match its hash; the ledger was edited")
        prev = e.get("hash", "")
    return errs


def next_round(evs, stage):
    """Refinements are additive: each new step in the same stage is the next round, never a replacement."""
    return 1 + sum(1 for e in evs if e["type"] == "step" and e.get("stage") == stage)


# ---------- cost ----------

def load_prices(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def price_for(prices, model):
    best = None
    for prefix, p in (prices.get("models") or {}).items():
        if (model or "").startswith(prefix) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, p)
    return best[1] if best else None


def cost_usd(tokens_by_model, prices):
    """tokens_by_model: {model: {in,out,cache_read,cache_write_5m,cache_write_1h}}. None if any model is unpriced."""
    total = 0.0
    for model, t in tokens_by_model.items():
        p = price_for(prices, model)
        if p is None:
            return None
        total += sum(t.get(k, 0) * p[k] for k in ("in", "out", "cache_read", "cache_write_5m", "cache_write_1h")) / 1e6
    return round(total, 6)


def _parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _usage_lines(path):
    """Yield (line_no, timestamp, message_id, model, tokens) per assistant usage record. Malformed lines are
    skipped, so a half-written transcript never breaks a caller."""
    for n, line in enumerate(Path(path).read_text(encoding="utf-8", errors="replace").splitlines()):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        m = d.get("message") or {}
        u = m.get("usage")
        if d.get("type") != "assistant" or not isinstance(u, dict):
            continue
        cc = u.get("cache_creation") or {}
        w1h = cc.get("ephemeral_1h_input_tokens", 0)
        w5m = cc.get("ephemeral_5m_input_tokens", u.get("cache_creation_input_tokens", 0) - w1h)
        yield n, d.get("timestamp"), m.get("id") or f"line{n}", m.get("model") or "unknown", {
            "in": u.get("input_tokens", 0), "out": u.get("output_tokens", 0),
            "cache_read": u.get("cache_read_input_tokens", 0), "cache_write_5m": w5m, "cache_write_1h": w1h}


def _add_tokens(out, model, t):
    acc = out.setdefault(model, dict.fromkeys(t, 0))
    for k, v in t.items():
        acc[k] += v


def transcript_tokens(path, since=None, until=None):
    """Sum usage across a transcript (optionally a time slice). Streaming writes the same message more than
    once, so keep the last usage seen per message id."""
    by_id = {}
    for _n, ts, mid, model, t in _usage_lines(path):
        if ts and ((since and _parse_ts(ts) < _parse_ts(since)) or (until and _parse_ts(ts) > _parse_ts(until))):
            continue
        by_id[mid] = (model, t)
    out = {}
    for model, t in by_id.values():
        _add_tokens(out, model, t)
    return out


# ---------- skill windows ----------

# Slash commands that are not skills; they must not open a window.
BUILTIN_COMMANDS = {
    "clear", "help", "compact", "model", "config", "exit", "quit", "resume", "login", "logout", "status", "cost",
    "context", "memory", "agents", "mcp", "permissions", "doctor", "plugin", "hooks", "ide", "fast", "rewind",
    "export", "copy", "theme", "vim", "add-dir", "usage", "terminal-setup", "statusline", "effort"}
_CMD_RE = re.compile(r"<command-name>\s*/?([^<\s]+)\s*</command-name>")


def _norm_skill(name):
    return (name or "").strip().lstrip("/")


def _user_text(d):
    """(text, is_tool_result) of a user line."""
    c = (d.get("message") or {}).get("content")
    if isinstance(c, str):
        return c, False
    parts, result = [], False
    for b in c or []:
        if isinstance(b, dict):
            if b.get("type") == "tool_result":
                result = True
            elif b.get("type") == "text":
                parts.append(b.get("text") or "")
    return "\n".join(parts), result


def skill_windows(path):
    """Skill windows of a main-session transcript, in order.

    A window opens at a user slash command, or at the first `Skill` call after a user prompt, and closes when
    the next window opens. A `Skill` call made inside an open window with no new user prompt in between is
    nested: it goes in the outer window's `via`, never a window of its own."""
    windows, pending, last_ts = [], False, None

    def open_window(name, ts, by):
        if windows:
            windows[-1]["end"] = ts
        windows.append({"skill": name, "start": ts, "end": None, "invoked_by": by, "via": []})

    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        ts = d.get("timestamp") or last_ts
        last_ts = ts
        if not ts:
            continue
        kind = d.get("type")
        if kind == "user" and not d.get("isMeta"):
            text, is_result = _user_text(d)
            if is_result:
                continue
            pending = True
            m = _CMD_RE.search(text)
            if m and _norm_skill(m.group(1)) not in BUILTIN_COMMANDS:
                open_window(_norm_skill(m.group(1)), ts, "user")
                pending = False
        elif kind == "assistant":
            c = (d.get("message") or {}).get("content")
            for b in c if isinstance(c, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Skill":
                    name = _norm_skill((b.get("input") or {}).get("skill"))
                    if not name:
                        continue
                    if pending or not windows:
                        open_window(name, ts, "user" if pending else "model")
                        pending = False
                    else:
                        windows[-1]["via"].append({"skill": name, "ts": ts})
    return windows


def window_at(windows, ts):
    if not ts:
        return None
    t = _parse_ts(ts) if isinstance(ts, str) else ts
    for w in windows:
        if _parse_ts(w["start"]) <= t and (w["end"] is None or t < _parse_ts(w["end"])):
            return w
    return None


def skill_at(windows, ts):
    """(outer skill name or "", names of nested skills called so far in that window)."""
    w = window_at(windows, ts)
    if not w:
        return "", []
    t = _parse_ts(ts) if isinstance(ts, str) else ts
    return w["skill"], [v["skill"] for v in w["via"] if _parse_ts(v["ts"]) <= t]


def windowed_usage(path, after=None, windows=None):
    """Main-session tokens after `after` (exclusive), split per skill window.
    Returns ([{skill, skill_run, via, tokens}], last_timestamp)."""
    windows = skill_windows(path) if windows is None else windows
    by_id = {}
    for _n, ts, mid, model, t in _usage_lines(path):
        if after and ts and _parse_ts(ts) <= _parse_ts(after):
            continue
        by_id[mid] = (ts, model, t)
    groups, last = {}, None
    for ts, model, t in by_id.values():
        if ts and (last is None or _parse_ts(ts) > _parse_ts(last)):
            last = ts
        w = window_at(windows, ts)
        g = groups.setdefault(w["start"] if w else "", {
            "skill": w["skill"] if w else "", "skill_run": w["start"] if w else "", "via": [], "tokens": {}})
        _add_tokens(g["tokens"], model, t)
    for g in groups.values():
        w = next((w for w in windows if w["start"] == g["skill_run"]), None)
        if w:
            g["via"] = [v["skill"] for v in w["via"]
                        if (not after or _parse_ts(v["ts"]) > _parse_ts(after)) and (not last or _parse_ts(v["ts"]) <= _parse_ts(last))]
    return sorted(groups.values(), key=lambda g: g["skill_run"]), last


# ---------- active change ----------

CHANGE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def set_active(repo, change):
    if not CHANGE_ID.fullmatch(change or ""):
        raise ValueError(f"not a valid change id: {change!r}")
    p = Path(repo) / "docs" / "team" / "audit" / "ACTIVE"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(change + "\n", encoding="utf-8", newline="\n")
    return p


def active_change(repo):
    """The explicit ACTIVE marker, else the sole non-archived OpenSpec change, else None (unresolved)."""
    repo = Path(repo)
    marker = repo / "docs" / "team" / "audit" / "ACTIVE"
    if marker.is_file():
        lines = marker.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        if lines and CHANGE_ID.fullmatch(lines[0].strip()):
            return lines[0].strip()
    d = repo / "openspec" / "changes"
    if d.is_dir():
        names = [p.name for p in d.iterdir() if p.is_dir() and p.name != "archive" and not p.name.startswith(".")]
        if len(names) == 1:
            return names[0]
    return None


# ---------- default stage for hook-recorded steps ----------

AGENT_STAGE = {
    "product-manager": "propose", "architect": "design", "ux-designer": "design",
    "backend-dev": "build", "frontend-dev": "build", "devops-engineer": "build", "platform-engineer": "build",
    "qa-engineer": "verify", "accessibility-tester": "verify", "security-compliance": "verify",
    "compliance-reviewer": "verify", "code-reviewer": "verify"}
SKILL_STAGE = {
    "opsx:explore": "explore", "openspec-explore": "explore",
    "opsx:propose": "propose", "openspec-propose": "propose",
    "opsx:archive": "archive", "openspec-archive-change": "archive",
    "product-team:deploy-prod": "release", "deploy-prod": "release"}


def default_stage(skill, agent):
    """Best guess at a stage when a hook records a step; the caller marks it `stage_source: hook`."""
    if skill in SKILL_STAGE:
        return SKILL_STAGE[skill]
    return AGENT_STAGE.get((agent or "").split(":")[-1], "build")


def find_subagent(agent_id, projects_dir=None):
    root = projects_dir or os.path.join(os.path.expanduser("~"), ".claude", "projects")
    hits = glob.glob(os.path.join(root, "*", "*", "subagents", f"agent-{agent_id}.jsonl"))
    if not hits:
        return None, {}
    meta = {}
    mp = hits[0][:-len(".jsonl")] + ".meta.json"
    if os.path.exists(mp):
        meta = json.loads(Path(mp).read_text(encoding="utf-8"))
    return hits[0], meta


def tool_commands(path, limit=200):
    """Tool calls an agent actually made, so 'I ran the E2E suite' can be checked against what ran."""
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        c = (d.get("message") or {}).get("content")
        if d.get("type") != "assistant" or not isinstance(c, list):
            continue
        for b in c:
            if b.get("type") == "tool_use":
                inp = b.get("input") or {}
                out.append(f"{b.get('name')}: {str(inp.get('command') or inp.get('file_path') or inp.get('url') or '')[:160]}")
    return out[:limit]


# ---------- file deltas (git tree snapshots) ----------

def _git(repo, *args, env=None):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def snapshot(repo):
    """Tree hash of the whole working tree (tracked + untracked, honours .gitignore), via a throwaway index."""
    fd, idx = tempfile.mkstemp(prefix="audit-index-")
    os.close(fd)
    os.unlink(idx)
    env = {**os.environ, "GIT_INDEX_FILE": idx}
    try:
        _git(repo, "add", "-A", "--", ".", env=env)
        return _git(repo, "write-tree", env=env).strip()
    finally:
        if os.path.exists(idx):
            os.unlink(idx)


def file_delta(repo, before, after):
    status = {}
    for line in _git(repo, "diff-tree", "-r", "--name-status", "--no-renames", before, after).splitlines():
        s, _, p = line.partition("\t")
        status[p] = {"A": "added", "M": "modified", "D": "deleted"}.get(s[:1], s)
    files = []
    for line in _git(repo, "diff-tree", "-r", "--numstat", "--no-renames", before, after).splitlines():
        a, d, p = line.split("\t", 2)
        files.append({"path": p, "status": status.get(p, "modified"),
                      "added": 0 if a == "-" else int(a), "removed": 0 if d == "-" else int(d)})
    return sorted(files, key=lambda f: f["path"])


# ---------- checks ----------

def validate_results(results, expected_ids=None):
    errs = []
    for r in results:
        if r.get("result") not in ("pass", "fail", "not_run"):
            errs.append(f"{r.get('id')}: result must be pass, fail or not_run")
        elif r["result"] == "pass" and not r.get("evidence"):
            errs.append(f"{r['id']}: pass needs evidence (command, test name or file:line)")
        elif r["result"] == "not_run" and not r.get("reason"):
            errs.append(f"{r['id']}: not_run needs a reason")
    if expected_ids is not None:
        have = {r.get("id") for r in results}
        errs += [f"{sid}: missing from the gate results" for sid in expected_ids if sid not in have]
    return errs


def check(evs):
    errs, warns = verify_chain(evs), []
    expected, latest_gate = {}, {}
    for e in evs:
        t = e["type"]
        if t in ("step", "skill_usage"):  # `skill` is optional: ledgers written before skill attribution have none
            label = "step" if t == "step" else "skill usage"
            if not e.get("tokens"):
                errs.append(f"event {e['seq']}: {label} has no token record")
            elif e.get("cost_usd") is None:
                warns.append(f"event {e['seq']}: {e.get('agent') or e.get('skill') or 'main session'} {label} is unpriced (model not in prices.yaml); tokens are still recorded")
        if t == "decision":
            if e.get("decided_by", "").startswith("agent:") and e.get("kind") in OWNER_ONLY_KINDS:
                errs.append(f"event {e['seq']}: '{e['kind']}' decided by {e['decided_by']}; only the owner may decide this")
            if e.get("decided_by") in DECIDERS and not e.get("quote"):
                errs.append(f"event {e['seq']}: owner decision with no quoted message")
        if t == "scenarios":
            expected[e["chunk"]] = list(e["ids"])
        if t == "gate":
            latest_gate[(e["chunk"], e["gate"])] = e
    for (chunk, gate), g in latest_gate.items():
        got = {r["id"] for r in g["results"]}
        errs += [f"gate {gate} on chunk {chunk}: scenario {sid} has no result (skipped)"
                 for sid in expected.get(chunk, []) if sid not in got]
    for chunk in expected:
        if not any(c == chunk for c, _ in latest_gate):
            warns.append(f"chunk {chunk}: scenarios registered but no gate has reported yet")
    return errs, warns


# ---------- report ----------

def _sum(rows):
    return {"cost": round(sum(r.get("cost_usd") or 0 for r in rows), 4),
            "tokens": sum(sum(t.values()) for r in rows for t in (r.get("tokens") or {}).values()),
            "unpriced": sum(1 for r in rows if r.get("cost_usd") is None)}


ADHOC = "(no skill / ad hoc)"


def skill_totals(evs):
    """Spend per skill over steps and main-session usage. Unrounded, so the rows sum exactly to the total."""
    out = {}
    for e in evs:
        if e["type"] not in ("step", "skill_usage"):
            continue
        g = out.setdefault(e.get("skill") or ADHOC, {"runs": set(), "steps": 0, "tokens": 0, "cost": 0.0, "unpriced": 0})
        if e["type"] == "step":
            g["steps"] += 1
        if e.get("skill_run"):
            g["runs"].add(e["skill_run"])
        g["tokens"] += sum(sum(t.values()) for t in (e.get("tokens") or {}).values())
        g["cost"] += e.get("cost_usd") or 0
        g["unpriced"] += e.get("cost_usd") is None
    for g in out.values():
        g["runs"] = len(g["runs"]) or 1
    return out


def _skill_section(evs, total_cost):
    totals = skill_totals(evs)
    order = sorted(totals, key=lambda k: (k == ADHOC, -totals[k]["cost"], k))
    L = ["", "## Spend by skill", "", "| Skill | Runs | Steps | Tokens | Cost | % of total |", "|---|---|---|---|---|---|"]
    for k in order:
        g = totals[k]
        pct = 100 * g["cost"] / total_cost if total_cost else 0
        cost = f"${g['cost']:.2f}" + (f" ({g['unpriced']} unpriced)" if g["unpriced"] else "")
        runs = "-" if k == ADHOC else g["runs"]
        L.append(f"| {k} | {runs} | {g['steps']} | {g['tokens']:,} | {cost} | {pct:.1f}% |")
    for k in order:
        rows = [e for e in evs if e["type"] in ("step", "skill_usage") and (e.get("skill") or ADHOC) == k]
        L += ["", f"### {k}", "", "| Round | Stage | Agent | Tokens | Cost |", "|---|---|---|---|---|"]
        for s in (r for r in rows if r["type"] == "step"):
            stage = s["stage"] + (" (inferred)" if s.get("stage_source") == "hook" else "")
            cost = "unpriced" if s.get("cost_usd") is None else f"${s['cost_usd']:.2f}"
            L.append(f"| {s['round']} | {stage} | {s['agent']} | {_sum([s])['tokens']:,} | {cost} |")
        use = [r for r in rows if r["type"] == "skill_usage"]
        if use:
            u = _sum(use)
            cost = f"${u['cost']:.2f}" + (f" ({u['unpriced']} unpriced)" if u["unpriced"] else "")
            L.append(f"| - | - | orchestrator overhead | {u['tokens']:,} | {cost} |")
        nested = {}
        for r in rows:
            for v in r.get("via") or []:
                nested[v] = nested.get(v, 0) + 1
        if nested:
            L += ["", "Nested skills: " + ", ".join(f"`{n}` x{c}" for n, c in sorted(nested.items()))]
    return L


def report(evs, change):
    steps = [e for e in evs if e["type"] == "step"]
    usage = [e for e in evs if e["type"] == "skill_usage"]
    tot = _sum(steps + usage)
    L = [f"# Audit: {change}", "",
         "Dollar figures are API-equivalent estimates (tokens x `prices.yaml`), not billing.", "",
         f"**Total:** ${tot['cost']:.2f} across {len(steps)} steps"
         + (f" and {len(usage)} main-session usage records" if usage else "") + f", {tot['tokens']:,} tokens"
         + (f" ({tot['unpriced']} unpriced)" if tot["unpriced"] else ""), "",
         "## Spend by phase (additive across refinements)", "", "| Phase | Steps | Tokens | Cost |", "|---|---|---|---|"]
    for ph in ("explore", "execute", "verify", "release"):
        rows = [s for s in steps if s.get("phase") == ph]
        if rows:
            s = _sum(rows)
            L.append(f"| {ph} | {len(rows)} | {s['tokens']:,} | ${s['cost']:.2f} |")
    if usage:
        s = _sum(usage)
        L.append(f"| orchestrator overhead | {len(usage)} | {s['tokens']:,} | ${s['cost']:.2f} |")
    L += _skill_section(evs, sum(e.get("cost_usd") or 0 for e in steps + usage))
    L += ["", "## Stages and refinement rounds", "",
          "| Stage | Round | Agent | Chunk | Cost | Cumulative stage cost |", "|---|---|---|---|---|---|"]
    run = {}
    for s in steps:
        run[s["stage"]] = run.get(s["stage"], 0) + (s.get("cost_usd") or 0)
        L.append(f"| {s['stage']} | {s['round']} | {s['agent']} | {s.get('chunk') or ''} | "
                 f"${(s.get('cost_usd') or 0):.2f} | ${run[s['stage']]:.2f} |")
    L += ["", "## Files by agent", ""]
    for s in steps:
        if s.get("files"):
            L.append(f"**{s['agent']}** ({s['stage']} round {s['round']}, chunk {s.get('chunk') or '-'})")
            L += [f"- {f['status']}: `{f['path']}` +{f['added']} -{f['removed']}" for f in s["files"]]
            L.append("")
    L += ["## Gates and scenarios", ""]
    for g in (e for e in evs if e["type"] == "gate"):
        bad = [r for r in g["results"] if r["result"] != "pass"]
        L.append(f"- chunk {g['chunk']} / {g['gate']} by {g['agent']}: {len(g['results']) - len(bad)}/{len(g['results'])} pass")
        for r in sorted(bad, key=lambda r: r["result"] != "not_run"):
            L.append(f"  - **{r['result'].upper()}** {r['id']}: {r.get('reason') or r.get('evidence', '')}")
    L += ["", "## Decisions", "", "| By | Kind | Decision | Why | Ref |", "|---|---|---|---|---|"]
    for d in (e for e in evs if e["type"] == "decision"):
        who = "**owner**" if d["decided_by"] in DECIDERS else d["decided_by"]
        L.append(f"| {who} | {d.get('kind', '')} | {d['choice']} | {d.get('rationale', '')} | {d.get('ref', '')} |")
    return "\n".join(L) + "\n"
