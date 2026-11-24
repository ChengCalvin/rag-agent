"""Runtime guardrail logic. Self-contained (PyYAML + git only) so render copies it to docs/team/tools/.

Used by check_scope.py (what an agent changed) and validate_return.py (what an agent returned).
"""
import re
import subprocess
from pathlib import Path

import yaml

POSITIVE = {"PASS", "DONE", "READY"}
RULE_ID = re.compile(r"\b([A-Z]{2,}(?:-[A-Z]+)*-\d+)\b")


# ---------- loading ----------

def load_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def load_all(repo):
    repo = Path(repo)
    cfg = load_yaml(repo / "docs/team/process.yaml")
    g = load_yaml(repo / "docs/team/guardrails.yaml")
    return cfg, g


# ---------- globs and tokens ----------

def glob_to_re(g):
    out, i = "", 0
    while i < len(g):
        c = g[i]
        if g.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif g.startswith("**", i):
            out += ".*"
            i += 2
        elif c == "*":
            out += "[^/]*"
            i += 1
        elif c == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(c)
            i += 1
    return re.compile("^" + out + "$")


def matches(path, patterns):
    p = path.replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    return any(glob_to_re(g).match(p) for g in patterns)


def token_map(cfg):
    paths = dict(cfg.get("paths") or {})
    fw = (cfg.get("framework") or {}).get("paths") or {}
    toks = {k: list(v or []) for k, v in paths.items()}
    toks["specs"] = [f"{fw['specs'].rstrip('/')}/**"] if fw.get("specs") else []
    toks["changes"] = [f"{fw['changes'].rstrip('/')}/**"] if fw.get("changes") else []
    toks["framework_rules"] = [fw["rules_home"]] if fw.get("rules_home") else []
    return toks


def expand(patterns, toks):
    out = []
    for pat in patterns or []:
        m = re.fullmatch(r"\{([\w]+)(?:\|([\w]+))?\}", pat)
        if m:
            vals = toks.get(m.group(1)) or (toks.get(m.group(2)) if m.group(2) else [])
            out += vals or []
        else:
            out.append(pat)
    return out


# ---------- scope ----------

def changed_files(repo, base="HEAD"):
    def run(*args):
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
        return [l.strip() for l in r.stdout.splitlines() if l.strip()]
    files = set(run("diff", "--name-only", base)) | set(run("ls-files", "--others", "--exclude-standard"))
    return sorted(f for f in files if "/__pycache__/" not in "/" + f and not f.endswith(".pyc"))


def scope_violations(agent, files, cfg, g, report_text=None):
    spec = (g.get("agents") or {}).get(agent)
    if spec is None:
        return [f"no guardrails entry for agent '{agent}' in docs/team/guardrails.yaml"]
    toks = token_map(cfg)
    allow = expand(spec.get("may_write"), toks)
    protected = expand(g.get("protected"), toks)
    prot_ok = expand(spec.get("may_write_protected"), toks)
    deps = toks.get("deps", [])
    errs = []
    for f in files:
        if matches(f, protected) and not matches(f, prot_ok):
            errs.append(f"{f}: protected file; {agent} may not change it")
        elif not matches(f, allow):
            errs.append(f"{f}: outside {agent}'s write scope")
    if agent in (g.get("dependency_gate_agents") or []) and deps:
        touched = [f for f in files if matches(f, deps)]
        if touched and not (report_text and re.search(r"^\W*dependency\W*:", report_text, re.I | re.M)):
            errs.append("dependency files changed (" + ", ".join(touched) + ") but the report has no 'Dependency:' justification line")
    return errs


# ---------- report validation ----------

KNOWN_SECTIONS = {"verdict", "tasks", "evidence", "findings", "open items", "standards self-check", "rollback",
                  "decisions", "open questions", "out of scope"}
_HEADERS = [(n, re.compile(r"^\s*(?P<h>#{1,6}\s*)?(?P<b>\*\*)?" + re.escape(n).replace(r"\ ", r"\s+") +
                           r"(?![A-Za-z])(?:\*\*)?\s*(?P<c>:)?(?:\*\*)?\s*(?P<rest>.*)$", re.I))
            for n in sorted(KNOWN_SECTIONS, key=len, reverse=True)]


def _sections(text):
    """Map lowercase section name -> body. Headers: '## Name', '**Name**', 'Name:' (known names only)."""
    out, cur = {}, None
    for line in text.splitlines():
        hit = None
        for name, rx in _HEADERS:
            m = rx.match(line)
            if m and (m.group("h") or m.group("b") or m.group("c")):
                hit = (name, m.group("rest"))
                break
        if hit:
            cur = hit[0]
            out.setdefault(cur, "")
            out[cur] += hit[1] + "\n"
        elif cur is not None:
            out[cur] += line + "\n"
    return out


def rule_ids_in(repo, cfg):
    ids = set()
    std = Path(repo) / (cfg.get("standards") or {}).get("file", "docs/engineering-standards.md")
    arch = Path(repo) / (cfg.get("architecture") or {}).get("file", "docs/architecture.md")
    for p in (std, arch):
        if p.exists():
            ids |= set(re.findall(r"`([A-Z]{2,}(?:-[A-Z]+)*-\d+)`", p.read_text(encoding="utf-8")))
    return ids


def validate_return(agent, text, cfg, g, repo=".", tasks=None):
    spec = (g.get("agents") or {}).get(agent)
    if spec is None:
        return [f"no guardrails entry for agent '{agent}'"]
    errs = []
    vm = re.search(r"^\W*verdict\W*[:\-]\s*\**\s*([A-Za-z][A-Za-z\-]*)", text, re.I | re.M)
    verdict = vm.group(1).upper() if vm else None
    allowed = [v.upper() for v in spec.get("verdicts", [])]
    if not verdict:
        errs.append("no 'Verdict:' line")
    elif verdict not in allowed:
        errs.append(f"verdict '{verdict}' is not allowed for {agent} (allowed: {', '.join(allowed)})")

    secs = _sections(text)
    for name in spec.get("sections", []):
        body = secs.get(name.lower())
        if body is None:
            errs.append(f"missing section '{name}'")
        elif name.lower() not in ("open items", "findings") and not re.sub(r"[\s\-*_`]|none|n/a", "", body, flags=re.I).strip():
            errs.append(f"section '{name}' is empty")

    ev = secs.get("evidence", "")
    if verdict in POSITIVE and "evidence" in [s.lower() for s in spec.get("sections", [])]:
        if "`" not in ev and not re.search(r"\w+\.\w+:\d+", ev):
            errs.append("positive verdict without evidence (needs commands run with results, or file:line references)")

    if verdict == "BLOCKED" and not re.sub(r"[\s\-*_`]|none|n/a", "", secs.get("open items", ""), flags=re.I).strip():
        errs.append("BLOCKED but 'Open items' does not say what is blocking")

    if "Tasks" in spec.get("sections", []) and tasks is not None:
        tm = re.search(r"^\W*tasks\W*[:\-]\s*(.+)$", text, re.I | re.M)
        reported = set(re.findall(r"\d+(?:\.\d+)*", tm.group(1))) if tm else set(re.findall(r"\d+(?:\.\d+)+", secs.get("tasks", "")))
        assigned = set(tasks)
        extra, missing = sorted(reported - assigned), sorted(assigned - reported)
        if extra:
            errs.append(f"reports tasks that were not assigned: {', '.join(extra)}")
        if missing and verdict != "BLOCKED":
            errs.append(f"assigned tasks not reported: {', '.join(missing)} (report them or return BLOCKED)")

    if "standards self-check" in [s.lower() for s in spec.get("sections", [])]:
        sc = secs.get("standards self-check", "")
        if re.search(r"\.{2,}\s*no\b|\bno\s*$", sc, re.I | re.M) and "standards-exception" not in text.lower():
            errs.append("self-check answers 'no' without a standards-exception line")

    if spec.get("findings"):
        f = secs.get("findings", "")
        ids = set(RULE_ID.findall(f))
        severe = re.search(r"\b(blocker|major)\b", f, re.I)
        if verdict == "PASS" and severe:
            errs.append("verdict PASS but findings contain Blocker/Major items")
        if verdict == "FAIL" and not (severe or ids):
            errs.append("verdict FAIL but no finding with a severity or rule ID")
        known = rule_ids_in(repo, cfg)
        if known:
            bad = sorted(i for i in ids if re.match(r"^(STRUCT|SIZE|TYPE|ERR|CONV|TEST|HYG|EVOL|ARCH)", i) and i not in known)
            if bad:
                errs.append(f"cites rule IDs that do not exist in the standards or architecture: {', '.join(bad)}")
    return errs
