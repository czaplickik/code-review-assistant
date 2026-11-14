#!/usr/bin/env python3
"""Shared machinery for ai-review, security-review and spec-review.

Usage:
  review.py prepare <ai|security|spec> [--base BRANCH] [--spec PATH ...] [--plan PATH ...]
      Collects + triages the change (or reuses the newest report of the identical change),
      creates <report>/review-<kind>/ with scope.json, candidates.json and batches.
      Prints the review directory.
  review.py show <review_dir> --batch N [--full]
      Prints the model input for one batch: checklist paths, candidates, file metadata, diffs.
  review.py merge <review_dir>
      Validates the model output, writes review.json and review.md. Exit 1 lists problems.
  review.py verify-plan <review_dir>     batches of blocker/major findings for the finding-verifier agent
  review.py verify-show <review_dir> --batch N
  review.py combine <review_dir> <keep-id> <drop-id> [...]
      Folds duplicate findings (ids from the last merge) into one; then run merge again.

The whole change is always reviewed. Mechanical groups (the same edit repeated in many files)
are reviewed through 2 sample files per group plus their deterministic candidates.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from _common import (RULESETS_DIR, changed_lines, die, git, load_config, load_rulesets, parse_diff,
                     read_json, repo_root, ruleset_for, write_json)

SCRIPTS = Path(__file__).resolve().parent
KINDS = ("ai", "security", "spec")
SEVERITIES = ("blocker", "major", "minor", "info")
CATEGORIES = {
    "ai": ["conventions", "consistency", "reinvention", "dead_code", "overengineering", "ai_artifacts",
           "tests", "error_handling", "resources", "performance", "readability"],
    "security": ["authz", "authn", "input_validation", "injection", "secrets", "crypto", "data_exposure",
                 "ssrf", "deserialization", "config", "dependencies", "logging"],
    "spec": ["requirement", "business_rule", "decision", "contract", "unrequested", "test_gap"],
}
BATCH_SIZE = {"ai": 8, "security": 8, "spec": 12}

DEBUG_RE = re.compile(r"(System\.(out|err)\.print|printStackTrace\(\)|Console\.Write|Debug\.Write|"
                      r"console\.log\(|\bprint\(|Thread\.dumpStack)")
TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
PLACEHOLDER_RE = re.compile(r"(UnsupportedOperationException|NotImplementedException|NotImplementedError|"
                            r"return\s+null\s*;\s*//|return\s+default\s*;\s*//|//\s*(stub|placeholder|dummy|mock))", re.I)
COMMENTED_CODE_RE = re.compile(r"^\s*//\s*.*([;{}]\s*$|\w+\s*\(.*\)\s*;|^\s*//\s*(if|for|while|return|var|val|int|String)\b)")
SENSITIVE_LOG_RE = re.compile(r"(log\w*|logger\w*|_logger|Log)\s*\.\s*\w+\(.*(password|passwd|secret|token|apikey|api_key|"
                              r"card|cvv|iban|ssn|pesel|authorization)", re.I)
DEP_RE = re.compile(r"(<artifactId>[^<]+</artifactId>|PackageReference\s+Include=\"[^\"]+\"|"
                    r"implementation\s*\(?['\"][^'\"]+['\"]|\"[@\w/.-]+\"\s*:\s*\"[\^~]?\d)")
UTIL_NAME_RE = re.compile(r"(Util|Utils|Helper|Helpers|Support|Tools|Commons|Common|Manager)$")
METHOD_DECL = {
    "java-spring": re.compile(r"^\s*(?:@\w+(?:\([^)]*\))?\s*)*(?:public|protected|private|static|final|synchronized|\s)+"
                              r"\w[\w<>\[\],.? ]*\s+([a-z]\w*)\s*\([^;]*$"),
    "dotnet": re.compile(r"^\s*(?:\[[^\]]+\]\s*)*(?:public|protected|private|internal|static|async|virtual|override|sealed|\s)+"
                         r"\w[\w<>\[\],.?() ]*\s+([A-Z]\w*)\s*(?:<[^>]+>)?\s*\([^;]*$"),
}
ENTRY_RE = {
    "java-spring": re.compile(r"@(Get|Post|Put|Patch|Delete|Request)Mapping|@(KafkaListener|RabbitListener|JmsListener|Scheduled)"),
    "dotnet": re.compile(r"\[Http(Get|Post|Put|Patch|Delete)|\.Map(Get|Post|Put|Patch|Delete)\(|IConsumer<|BackgroundService|"
                         r"\[Route"),
}
SKIP_UNUSED = re.compile(r"@(Override|Bean|Test|ParameterizedTest|BeforeEach|AfterEach|EventListener|KafkaListener|"
                         r"Scheduled|PostConstruct|ExceptionHandler|\w*Mapping)|\[(Fact|Theory|Http\w+|Route)|override\s")


def run(script, *args, cwd):
    res = subprocess.run([sys.executable, str(SCRIPTS / script), *args], cwd=cwd, capture_output=True, text=True)
    if res.returncode not in (0,):
        sys.stderr.write(res.stdout + res.stderr)
        sys.exit(res.returncode)
    return res.stdout


# ------------------------------------------------------------------ prepare

def find_or_collect(root, args):
    extra = []
    if args.base:
        extra += ["--base", args.base]
    for s in args.spec:
        extra += ["--spec", s]
    for p in args.plan:
        extra += ["--plan", p]
    if args.title:
        extra += ["--title", args.title]
    if args.jira:
        extra += ["--jira", args.jira]
    out = run("collect_changes.py", *extra, cwd=root)
    new_dir = Path(out.splitlines()[0].strip())
    a = read_json(new_dir / "analysis.json")
    h = a["change"].get("change_hash")
    for d in sorted((p for p in new_dir.parent.iterdir() if p.is_dir() and p != new_dir), reverse=True):
        f = d / "analysis.json"
        if not f.is_file():
            continue
        try:
            old = read_json(f)
        except ValueError:
            continue
        if h and old["change"].get("change_hash") == h and "batches" in old:
            shutil.rmtree(new_dir)
            return d, True
    run("triage.py", str(new_dir), cwd=root)
    return new_dir, False


def added_blocks(rdir, f):
    text = (rdir / f["diff_file"]).read_text(encoding="utf-8")
    return parse_diff(text)


def candidates_for(kind, root, rdir, a, rs_by_id):
    cands = []

    def add(path, line, category, title, detail, snippet=""):
        cands.append({"id": f"C-{len(cands) + 1:03d}", "path": path, "line": line, "category": category,
                      "title": title, "detail": detail, "snippet": snippet[:200]})

    files = [f for f in a["files"] if f["tier"] != "excluded" and f["status"] != "deleted"]
    windows = defaultdict(list)
    for f in files:
        hunks = added_blocks(rdir, f)
        added = [(n, b) for t, o, n, b in changed_lines(hunks) if t == "+"]
        removed = [(o, b) for t, o, n, b in changed_lines(hunks) if t == "-"]
        rid = f.get("ruleset")
        if kind == "ai":
            for n, b in added:
                if DEBUG_RE.search(b):
                    add(f["path"], n, "ai_artifacts", "Debug output left in code", "stdout/debug print", b.strip())
                if TODO_RE.search(b):
                    add(f["path"], n, "ai_artifacts", "TODO/FIXME added", "unfinished work marker", b.strip())
                if PLACEHOLDER_RE.search(b) and not f["is_test"]:
                    add(f["path"], n, "ai_artifacts", "Placeholder / not-implemented code", "stub or dummy", b.strip())
                if COMMENTED_CODE_RE.search(b):
                    add(f["path"], n, "dead_code", "Commented-out code", "code kept in a comment", b.strip())
            if not f["is_test"]:
                code = [(n, b.strip()) for n, b in added if b.strip() and not b.strip().startswith(("//", "*", "/*", "import", "using"))]
                for i in range(len(code) - 5):
                    win = [c[1] for c in code[i:i + 6]]
                    if sum(len(x) for x in win) < 120:
                        continue
                    key = hashlib.sha1("\n".join(re.sub(r"\s+", " ", x) for x in win).encode()).hexdigest()
                    windows[key].append((f["path"], code[i][0], win[0]))
            decl = METHOD_DECL.get(rid)
            if decl and not f["is_test"] and f["language"] in ("java", "kotlin", "csharp"):
                lines_new = [b for _, b in added]
                for idx, (n, b) in enumerate(added):
                    m = decl.match(b)
                    if not m:
                        continue
                    name = m.group(1)
                    if len(name) < 4 or name in ("while", "switch", "catch", "return", "throw", "using", "lock", "foreach",
                                                 "else", "synchronized", "await", "yield", "new","main", "equals", "hashCode", "toString", "ToString", "Equals",
                                                 "GetHashCode", "Dispose", "DisposeAsync"):
                        continue
                    prev = " ".join(lines_new[max(0, idx - 3):idx])
                    if SKIP_UNUSED.search(prev + " " + b):
                        continue
                    out = git("grep", "-w", "-c", "--untracked", "-F", "-e", name, cwd=root, ok=(0, 1))
                    total = sum(int(l.rsplit(":", 1)[1]) for l in out.splitlines() if ":" in l)
                    if total <= 1:
                        add(f["path"], n, "dead_code", f"`{name}` is never referenced",
                            "declared in this change, no other occurrence in the repository", b.strip())
            for sym in f.get("symbols") or []:
                if f["status"] == "added" and UTIL_NAME_RE.search(sym):
                    existing = [p for p in git("ls-files", cwd=root).splitlines()
                                if UTIL_NAME_RE.search(Path(p).stem) and p != f["path"]][:8]
                    add(f["path"], None, "reinvention", f"New helper class `{sym}`",
                        "check for existing utilities: " + (", ".join(existing) or "none found"))
                if f["status"] == "added":
                    out = git("grep", "-l", "-E", rf"(class|interface|record|enum|struct)\s+{re.escape(sym)}\b",
                              "--", cwd=root, ok=(0, 1))
                    dup = [p for p in out.splitlines() if p != f["path"]]
                    if dup:
                        add(f["path"], None, "reinvention", f"Type name `{sym}` already declared elsewhere",
                            "existing: " + ", ".join(dup[:5]))
        if kind in ("ai", "security") and re.search(r"(pom\.xml|\.csproj|build\.gradle|package\.json|Directory\.Packages\.props)$", f["path"]):
            for n, b in added:
                if DEP_RE.search(b):
                    add(f["path"], n, "dependencies" if kind == "security" else "reinvention",
                        "New dependency", "check necessity, licence and known vulnerabilities", b.strip())
        if kind == "security":
            entry = ENTRY_RE.get(rid)
            if entry:
                for n, b in added:
                    if entry.search(b):
                        add(f["path"], n, "authz", "New or changed entry point",
                            "verify authentication, authorization (incl. ownership) and input validation", b.strip())
            for n, b in added:
                if SENSITIVE_LOG_RE.search(b):
                    add(f["path"], n, "logging", "Possibly sensitive data logged", "", b.strip())
            for o, b in removed:
                if re.search(r"(?i)(authorize|preauthorize|secured|rolesallowed|isowner|owner|forbid|accessdenied|"
                             r"validate|sanitize|escape|csrf|signature|hmac)", b):
                    add(f["path"], o, "authz", "Security-related line removed", "", b.strip())
            for x in f["findings"]:
                if x["dimension"] == "security" and x["source"] == "deterministic":
                    ln = (x.get("evidence") or [{}])[0].get("line_start")
                    add(f["path"], ln, "config", x["title"], x["reason"],
                        (x.get("evidence") or [{}])[0].get("snippet", ""))
    if kind == "ai":
        for key, occ in windows.items():
            paths = {p for p, _, _ in occ}
            if len(occ) >= 2:
                p, n, first = occ[0]
                add(p, n, "consistency", f"Duplicated block of new code ({len(occ)} places)",
                    "same 6+ lines added in: " + ", ".join(f"{q}:{m}" for q, m, _ in occ[:5]), first)
    if kind == "spec":
        pd = a.get("plan_drift") or {}
        for p in pd.get("unplanned_files") or []:
            add(p, None, "unrequested", "Changed file not mentioned in the plan", "check whether a requirement needs it")
        for p in pd.get("planned_not_changed") or []:
            add(p, None, "requirement", "Planned file not changed", "plan item possibly not implemented")
    return cands


def cmd_prepare(args):
    if args.kind not in KINDS:
        die(f"kind must be one of {KINDS}")
    root = repo_root()
    rdir, reused = find_or_collect(root, args)
    a = read_json(rdir / "analysis.json")
    cfg = load_config(root)
    _, stacks = load_rulesets(cfg)
    rs_by_id = {r.id: r for r in stacks}
    rv = rdir / f"review-{args.kind}"
    if rv.exists():
        shutil.rmtree(rv)
    rv.mkdir()

    cands = candidates_for(args.kind, root, rdir, a, rs_by_id)
    files = [f for f in a["files"] if f["tier"] != "excluded"]
    groups = a.get("groups") or []
    in_group = {p for g in groups for p in g["files"]}
    samples = []
    for g in groups:
        samples.append({"id": g["id"], "description": g["description"], "count": len(g["files"]),
                        "sample": g["files"][:2], "sample_line": g.get("sample_line")})
    review_files = [f for f in files if f["path"] not in in_group] + \
                   [f for f in files if f["path"] in {p for s in samples for p in s["sample"]}]
    review_files.sort(key=lambda f: (f.get("module") or "", f["path"]))
    size = BATCH_SIZE[args.kind]
    batches = []
    for i in range(0, len(review_files), size):
        paths = [f["path"] for f in review_files[i:i + size]]
        batches.append({"id": len(batches) + 1, "files": paths,
                        "candidates": [c["id"] for c in cands if c["path"] in paths]})
    orphan = [c["id"] for c in cands if not any(c["id"] in b["candidates"] for b in batches)]
    if orphan and batches:
        batches[-1]["candidates"] += orphan
    scope = {"kind": args.kind, "report_dir": str(rdir), "review_dir": str(rv), "reused_report": reused,
             "files": len(files), "reviewed": len(review_files),
             "excluded": sum(1 for f in a["files"] if f["tier"] == "excluded"),
             "mechanical_groups": samples, "batches": batches,
             "sources": a["change"]["sources"],
             "checklists": checklists(args.kind, {f.get("ruleset") for f in files})}
    write_json(rv / "scope.json", scope)
    write_json(rv / "candidates.json", {"candidates": cands})
    print(rv)
    print(f"{args.kind}-review: {len(review_files)} files to review in {len(batches)} batch(es)"
          f"{f', {len(samples)} mechanical group(s) sampled' if samples else ''}; {len(cands)} candidate(s)"
          f"{'; reused impact report of the identical change' if reused else ''}")
    src = scope["sources"]
    print(f"spec: {', '.join(src['spec']) or 'none'}; plan: {', '.join(src['plan']) or 'none'}; "
          f"conventions: {', '.join(src['conventions']) or 'none'}")


def checklists(kind, rulesets):
    out = [RULESETS_DIR / "_base" / f"review-{kind}.md"]
    for r in sorted(x for x in rulesets if x and x != "_base"):
        p = RULESETS_DIR / r / f"review-{kind}.md"
        if p.is_file():
            out.append(p)
    return [str(p) for p in out if p.is_file()]


# ------------------------------------------------------------------ show

def cmd_show(args):
    rv = Path(args.review_dir).resolve()
    scope = read_json(rv / "scope.json")
    cands = {c["id"]: c for c in read_json(rv / "candidates.json")["candidates"]}
    b = next((b for b in scope["batches"] if b["id"] == args.batch), None)
    if not b:
        die(f"batch {args.batch} not found")
    rdir = Path(scope["report_dir"])
    a = read_json(rdir / "analysis.json")
    by_path = {f["path"]: f for f in a["files"]}
    root = repo_root()
    print(f"# {scope['kind']}-review batch {b['id']} of {len(scope['batches'])}: {len(b['files'])} files")
    print(f"# write: {rv / ('batch-%d.json' % b['id'])}")
    print(f"# checklists: {', '.join(scope['checklists'])}")
    print(f"# output format: schemas/data-model.md › Reviews ({Path(__file__).resolve().parent.parent / 'schemas' / 'data-model.md'})")
    src = scope["sources"]
    print(f"# conventions: {', '.join(src['conventions']) or 'none documented'}")
    print(f"# spec: {', '.join(src['spec']) or 'none'}   plan: {', '.join(src['plan']) or 'none'}")
    print(f"# repo root: {root}")
    groups = [g for g in scope["mechanical_groups"] if set(g["sample"]) & set(b["files"])]
    for g in groups:
        print(f"# mechanical group {g['id']}: {g['description']} — {g['count']} files; this batch has samples "
              f"{', '.join(set(g['sample']) & set(b['files']))}. Review the pattern once; report a problem in it "
              f"as one finding mentioning the group.")
    if b["candidates"]:
        print("\n## Deterministic candidates (confirm as a finding with `candidate`, or dismiss with a reason)")
        for cid in b["candidates"]:
            c = cands[cid]
            loc = f"{c['path']}:{c['line']}" if c.get("line") else c["path"]
            print(f"- {cid} [{c['category']}] {c['title']} — {loc}" + (f" — {c['detail']}" if c.get("detail") else "")
                  + (f"\n    {c['snippet']}" if c.get("snippet") else ""))
    print()
    limit = None if args.full else 500
    for p in b["files"]:
        f = by_path.get(p)
        if not f:
            continue
        head = f"=== {p}  ({f['status']}{', untracked' if f.get('untracked') else ''}, +{f['added_lines']}/-{f['deleted_lines']})" \
               f"  ruleset={f.get('ruleset')}{'  TEST' if f.get('is_test') else ''}"
        print(head)
        if f.get("role"):
            print(f"  role: {f['role']}")
        if f.get("linked_tests"):
            print(f"  linked tests: {', '.join(f['linked_tests'])} (changed: {'yes' if f.get('test_changed') else 'NO'})")
        text = (rdir / f["diff_file"]).read_text(encoding="utf-8").splitlines()
        if limit and len(text) > limit:
            print(f"--- diff (first {limit} of {len(text)} lines; full: {rdir / f['diff_file']}) ---")
            text = text[:limit]
        else:
            print("--- diff ---")
        print("\n".join(text))
        print()


# ------------------------------------------------------------------ merge

def valid(x, where, kind, problems):
    if not isinstance(x, dict):
        problems.append(f"{where}: not an object")
        return False
    if x.get("severity") not in SEVERITIES:
        problems.append(f"{where}: severity must be one of {SEVERITIES}")
        return False
    if x.get("category") not in CATEGORIES[kind]:
        problems.append(f"{where}: category '{x.get('category')}' not in {CATEGORIES[kind]}")
        return False
    if not x.get("title") or not x.get("path"):
        problems.append(f"{where}: title and path are required")
        return False
    return True


def cmd_merge(args):
    rv = Path(args.review_dir).resolve()
    scope = read_json(rv / "scope.json")
    kind = scope["kind"]
    cands = {c["id"]: c for c in read_json(rv / "candidates.json")["candidates"]}
    rdir = Path(scope["report_dir"])
    a = read_json(rdir / "analysis.json")
    problems, findings, reviewed, handled = [], [], set(), set()
    for b in scope["batches"]:
        bf = rv / f"batch-{b['id']}.json"
        if not bf.is_file():
            if kind != "spec":
                problems.append(f"batch-{b['id']}.json missing")
            continue
        try:
            data = read_json(bf)
        except ValueError as exc:
            problems.append(f"{bf.name}: invalid JSON ({exc})")
            continue
        reviewed.update(data.get("files_reviewed") or [])
        missing = set(b["files"]) - set(data.get("files_reviewed") or [])
        if missing:
            problems.append(f"{bf.name}: files not reported as reviewed: {sorted(missing)[:4]}")
        for i, x in enumerate(data.get("findings") or []):
            if valid(x, f"{bf.name} findings[{i}]", kind, problems):
                if x.get("candidate"):
                    handled.add(x["candidate"])
                findings.append(x)
        for d in data.get("dismissed_candidates") or []:
            handled.add(d.get("candidate"))
        open_c = [c for c in b["candidates"] if c not in handled]
        if open_c:
            problems.append(f"{bf.name}: candidates neither confirmed nor dismissed: {open_c[:6]}")
    spec = None
    if kind == "spec":
        parts = sorted(rv.glob("spec-part-*.json"))
        if (rv / "spec-matrix.json").is_file():
            parts.insert(0, rv / "spec-matrix.json")
        if not parts:
            problems.append("spec-matrix.json missing")
        spec = {"sources": [], "requirements": [], "decisions": [], "examples": [], "unrequested": []}
        for p in parts:
            try:
                d = read_json(p)
            except ValueError as exc:
                problems.append(f"{p.name}: invalid JSON ({exc})")
                continue
            for k in spec:
                spec[k] += [x for x in d.get(k) or [] if x not in spec[k]]
        for r in spec["requirements"]:
            if r.get("status") not in ("implemented", "partial", "missing", "contradicted", "unclear"):
                problems.append(f"requirement {r.get('id')}: bad status '{r.get('status')}'")
        for fx in sorted(rv.glob("spec-findings*.json")):
            try:
                items = read_json(fx).get("findings") or []
            except ValueError as exc:
                problems.append(f"{fx.name}: invalid JSON ({exc})")
                continue
            findings += [x for i, x in enumerate(items) if valid(x, f"{fx.name} findings[{i}]", kind, problems)]
    if problems and not args.allow_incomplete:
        print("review output incomplete or invalid:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)

    rcfg = (load_config(repo_root()).get("review") or {})
    min_by_sev = rcfg.get("min_certainty") or {}
    if not isinstance(min_by_sev, dict):
        min_by_sev = {s_: int(min_by_sev) for s_ in SEVERITIES}
    verify_sevs = set(rcfg.get("verify_severities") or ["blocker", "major"])
    verdicts = load_verdicts(rv)
    to_confirm, rejected, kept = [], [], []
    for x in findings:
        x["key"] = finding_key(kind, x)
        try:
            cert = int(x.get("certainty", 90 if x.get("confidence") == "verified" else 70))
        except (TypeError, ValueError):
            cert = 70
        x["certainty"] = max(0, min(100, cert))
        v = verdicts.get(x["key"])
        if v:
            x["verification"] = {"verdict": v.get("verdict"), "certainty": v.get("certainty"),
                                 "reason": v.get("reason")}
            if v.get("verdict") == "rejected":
                rejected.append(x)
                continue
            if v.get("verdict") == "downgraded" and v.get("severity") in SEVERITIES:
                x["original_severity"] = x["severity"]
                x["severity"] = v["severity"]
            try:
                x["certainty"] = max(0, min(100, int(v.get("certainty", x["certainty"]))))
            except (TypeError, ValueError):
                pass
        threshold = int(min_by_sev.get(x["severity"], 70))
        (to_confirm if x["certainty"] < threshold else kept).append(x)
    findings = kept
    order = {s: i for i, s in enumerate(SEVERITIES)}
    findings.sort(key=lambda x: (order[x["severity"]], -x["certainty"], x["path"]))
    limit = int((rcfg.get("max_findings") or {}).get(kind, 0) or 0)
    more = []
    if limit and len(findings) > limit:
        # blockers are never cut; the weakest of the rest move to "More observations"
        must = [x for x in findings if x["severity"] == "blocker"]
        rest = [x for x in findings if x["severity"] != "blocker"]
        room = max(0, limit - len(must))
        findings, more = must + rest[:room], rest[room:]
    unverified = [x for x in findings if x["severity"] in verify_sevs and "verification" not in x]
    to_confirm.sort(key=lambda x: (order.get(x["severity"], 9), x["path"]))
    for i, x in enumerate(to_confirm, 1):
        x["id"] = f"U-{i:03d}"
    for i, x in enumerate(more, 1):
        x["id"] = f"M-{i:03d}"
    for i, x in enumerate(rejected, 1):
        x["id"] = f"X-{i:03d}"
    findings.sort(key=lambda x: (order[x["severity"]], x["path"], x.get("line_start") or 0))
    for i, x in enumerate(findings, 1):
        x["id"] = f"R-{i:03d}"
        x.setdefault("confidence", "inferred")
    by_file = defaultdict(list)
    for x in findings:
        by_file[x["path"]].append(x["id"])
    roles = {f["path"]: f.get("role") for f in a["files"]}
    summary = {s_: sum(1 for x in findings if x["severity"] == s_) for s_ in SEVERITIES}
    limitations = list(a.get("limitations") or [])
    if problems:
        limitations.append(f"Review incomplete: {len(problems)} problem(s) in model output.")
    if to_confirm:
        limitations.append(f"{len(to_confirm)} finding(s) below the certainty threshold are listed under "
                           f"'To confirm' and not counted.")
    if unverified:
        limitations.append(f"{len(unverified)} {'/'.join(sorted(verify_sevs))} finding(s) were not independently "
                           f"verified (run `review.py verify-plan` and the finding-verifier agent).")
    if rejected:
        limitations.append(f"{len(rejected)} finding(s) rejected by independent verification (kept in review.json).")
    if scope["mechanical_groups"]:
        limitations.append(f"{len(scope['mechanical_groups'])} mechanical group(s) reviewed through 2 sample files each.")
    if scope["sources"].get("discovered_from"):
        limitations.append(f"Spec/plan taken from the {scope['sources']['discovered_from']}.")
    review = {"schema_version": 1, "kind": kind, "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
              "report_dir": str(rdir), "change": a["change"],
              "scope": {"files": scope["files"], "reviewed": scope["reviewed"],
                        "mechanical_groups_sampled": len(scope["mechanical_groups"]), "excluded": scope["excluded"]},
              "summary": summary, "findings": findings,
              "files": [{"path": p, "role": roles.get(p), "findings": ids} for p, ids in sorted(by_file.items())],
              "spec": spec, "to_confirm": to_confirm, "more": more, "rejected": rejected,
              "verification": {"verified": sum(1 for x in findings if "verification" in x),
                               "unverified": len(unverified), "rejected": len(rejected),
                               "downgraded": sum(1 for x in findings + more + to_confirm
                                                 if x.get("original_severity"))},
              "limitations": limitations}
    write_json(rv / "review.json", review)
    (rv / "review.md").write_text(to_markdown(review), encoding="utf-8")
    print(f"{kind}-review: blocker {summary['blocker']}, major {summary['major']}, minor {summary['minor']}, "
          f"info {summary['info']}")
    print(f"json: {rv / 'review.json'}")
    print(f"md:   {rv / 'review.md'}")
    for x in findings[:8]:
        print(f"  [{x['severity']}] {x['path']}:{x.get('line_start') or '-'} — {x['title']}")
    dups = possible_duplicates(findings)
    if dups:
        print("possible duplicates across batches — for real duplicates run "
              "`review.py combine <review_dir> <keep> <drop...>`, then merge again:")
        for a_, b_ in dups[:15]:
            print(f"  {a_['id']} ~ {b_['id']}: {a_['title'][:60]} | {b_['title'][:60]}")


STOP = set("a an the of to in on for and or is are be by with without no not any from as at it its this that".split())


def _tokens(t):
    return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in STOP and len(w) > 2}


def possible_duplicates(findings):
    out = []
    for i, a_ in enumerate(findings):
        ta = _tokens(a_["title"] + " " + (a_.get("description") or "")[:200])
        for b_ in findings[i + 1:]:
            tb = _tokens(b_["title"] + " " + (b_.get("description") or "")[:200])
            sim = len(ta & tb) / len(ta | tb) if ta and tb else 0
            same_spot = a_["path"] == b_["path"] and a_.get("line_start") and a_.get("line_start") == b_.get("line_start")
            if sim >= 0.35 or (same_spot and sim >= 0.2) or (a_["category"] == b_["category"] and sim >= 0.25):
                out.append((a_, b_))
    return out


def to_markdown(r):
    kind_name = {"ai": "AI review", "security": "Security review", "spec": "Spec review"}[r["kind"]]
    ch = r["change"]
    lines = [f"# {kind_name} — fix list", "",
             f"Change: {ch.get('boundary')} vs {ch.get('base_ref')} on `{ch.get('branch')}` · generated {r['generated_at']}", "",
             "Fix the items below in order of severity. Change only what an item asks for; do not refactor",
             "unrelated code. Tick an item when it is fixed, or write `won't fix: <reason>` under it.",
             "Run the build and tests after the fixes.", ""]
    s = r["summary"]
    lines.append(f"**{s['blocker']} blocker · {s['major']} major · {s['minor']} minor · {s['info']} info**")
    lines.append("")
    spec = r.get("spec")
    if spec:
        bad = [q for q in spec.get("requirements") or [] if q.get("status") not in ("implemented",)]
        if bad:
            lines += ["## Requirements not fully met", ""]
            for q in bad:
                lines.append(f"- [ ] **{q.get('id')}** ({q.get('status')}, tested: {q.get('tested', '?')}) — "
                             f"{q.get('text')} — {q.get('note') or ''} `{q.get('ref') or ''}`".rstrip())
            lines.append("")
        exs = [e for e in spec.get("examples") or [] if e.get("match") is False]
        if exs:
            lines += ["## Worked examples that fail", ""]
            for e in exs:
                lines.append(f"- [ ] {e.get('rule')}: {e.get('input')} → expected **{e.get('expected')}**, "
                             f"code gives **{e.get('actual')}**")
            lines.append("")
    for sev in SEVERITIES:
        items = [x for x in r["findings"] if x["severity"] == sev]
        if not items:
            continue
        lines += [f"## {sev.capitalize()} ({len(items)})", ""]
        for x in items:
            loc = x["path"] + (f":{x['line_start']}" + (f"-{x['line_end']}" if x.get("line_end") and x["line_end"] != x["line_start"] else "")
                               if x.get("line_start") else "")
            ver = (x.get("verification") or {}).get("verdict")
            mark = " ✔ confirmed" if ver == "confirmed" else (f" ⬇ downgraded from {x['original_severity']}"
                                                              if x.get("original_severity") else "")
            lines.append(f"- [ ] **{x['id']}** `{loc}` — {x['title']} _({x['category']}{mark})_")
            if x.get("description"):
                lines.append(f"  - Problem: {x['description']}")
            if x.get("suggestion"):
                lines.append(f"  - Fix: {x['suggestion']}")
            for rel in x.get("related") or []:
                where = rel.get("path") + (f":{rel['line_start']}" if rel.get("line_start") else "")
                lines.append(f"  - See: `{where}` {rel.get('note') or ''}".rstrip())
            if x.get("refs"):
                lines.append(f"  - Refs: {', '.join('`' + ref + '`' for ref in x['refs'])}")
        lines.append("")
    if r.get("more"):
        lines += [f"## More observations ({len(r['more'])}) — lower priority, not in the counts above", ""]
        for x in r["more"]:
            loc = x["path"] + (f":{x['line_start']}" if x.get("line_start") else "")
            lines.append(f"- [ ] **{x['id']}** `{loc}` — {x['title']} _({x['severity']})_")
        lines.append("")
    if r.get("to_confirm"):
        lines += [f"## To confirm ({len(r['to_confirm'])}) — low certainty, check before fixing", ""]
        for x in r["to_confirm"]:
            loc = x["path"] + (f":{x['line_start']}" if x.get("line_start") else "")
            lines.append(f"- [ ] **{x['id']}** `{loc}` — {x['title']} _({x['severity']}, certainty "
                         f"{x.get('certainty')})_")
            if x.get("description"):
                lines.append(f"  - Suspicion: {x['description']}")
        lines.append("")
    if r.get("limitations"):
        lines += ["## Limitations of this review", ""] + [f"- {l}" for l in r["limitations"]] + [""]
    return "\n".join(lines)


def finding_key(kind, x):
    raw = f"{kind}|{x.get('path')}|{x.get('line_start')}|{x.get('title')}"
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


def load_verdicts(rv):
    out = {}
    for vf in sorted(rv.glob("verify-*.json")):
        if vf.name == "verify-plan.json":
            continue
        try:
            for v in read_json(vf).get("verdicts") or []:
                if v.get("key"):
                    out[v["key"]] = v
        except ValueError:
            continue
    return out


def cmd_verify_plan(args):
    """Batches of blocker/major findings for the finding-verifier agent."""
    rv = Path(args.review_dir).resolve()
    r = read_json(rv / "review.json")
    rcfg = (load_config(repo_root()).get("review") or {})
    sevs = set(rcfg.get("verify_severities") or ["blocker", "major"])
    size = int(rcfg.get("verify_batch_size", 8))
    done = load_verdicts(rv)
    todo = [x for x in r["findings"] if x["severity"] in sevs and x.get("key") not in done]
    todo.sort(key=lambda x: (x["path"], x.get("line_start") or 0))
    used = [int(m.group(1)) for m in (re.match(r"verify-(\d+)\.json$", f.name) for f in rv.glob("verify-*.json")) if m]
    start = max(used, default=0) + 1  # never overwrite verdicts of an earlier round
    batches = [{"id": start + i // size, "keys": [x["key"] for x in todo[i:i + size]]} for i in range(0, len(todo), size)]
    write_json(rv / "verify-plan.json", {"kind": r["kind"], "batches": batches})
    print(f"{len(todo)} finding(s) to verify in {len(batches)} batch(es); {len(done)} already verified")
    for b in batches:
        print(f"batch {b['id']}: {len(b['keys'])} finding(s) -> write {rv / ('verify-%d.json' % b['id'])}")


def cmd_verify_show(args):
    rv = Path(args.review_dir).resolve()
    r = read_json(rv / "review.json")
    plan = read_json(rv / "verify-plan.json")
    b = next((b for b in plan["batches"] if b["id"] == args.batch), None)
    if not b:
        die(f"verify batch {args.batch} not found")
    by_key = {x.get("key"): x for x in r["findings"]}
    print(f"# Verify {len(b['keys'])} {r['kind']}-review finding(s); write {rv / ('verify-%d.json' % b['id'])}")
    print(f"# repo root: {repo_root()}")
    src = (r.get("change") or {}).get("sources") or {}
    print(f"# spec: {', '.join(src.get('spec') or []) or 'none'}   plan: {', '.join(src.get('plan') or []) or 'none'}")
    for k in b["keys"]:
        x = by_key.get(k)
        if not x:
            continue
        loc = x["path"] + (f":{x['line_start']}-{x.get('line_end') or x['line_start']}" if x.get("line_start") else "")
        print(f"\n## key {k}  [{x['severity']}] {x['category']}  {loc}")
        print(f"title: {x['title']}")
        if x.get("description"):
            print(f"description: {x['description']}")
        for rel in x.get("related") or []:
            print(f"related: {rel.get('path')}:{rel.get('line_start') or ''} {rel.get('note') or ''}")
        if x.get("refs"):
            print(f"refs: {', '.join(x['refs'])}")
        if x.get("snippet"):
            print("snippet:\n" + x["snippet"])


def cmd_combine(args):
    """Merge duplicate findings: keep the first id, fold the others into its `related`."""
    rv = Path(args.review_dir).resolve()
    r = read_json(rv / "review.json")
    by_id = {x["id"]: x for x in r["findings"]}
    ids = [args.keep] + args.drop
    missing = [i for i in ids if i not in by_id]
    if missing:
        die(f"unknown finding id(s): {missing} (ids come from the last merge)")
    files = sorted(rv.glob("batch-*.json")) + sorted(rv.glob("spec-findings*.json"))
    docs = {f: read_json(f) for f in files}

    def locate(x):
        for f, d in docs.items():
            for i, y in enumerate(d.get("findings") or []):
                if y.get("path") == x["path"] and y.get("title") == x["title"] \
                        and y.get("line_start") == x.get("line_start"):
                    return f, i
        die(f"cannot find {x['id']} in batch files")

    kf, ki = locate(by_id[args.keep])
    keeper = docs[kf]["findings"][ki]
    drops = []
    for d_id in args.drop:
        f, i = locate(by_id[d_id])
        y = docs[f]["findings"][i]
        keeper.setdefault("related", []).append(
            {"path": y["path"], "line_start": y.get("line_start"), "line_end": y.get("line_end"),
             "note": y["title"]})
        for rel in y.get("related") or []:
            keeper["related"].append(rel)
        if y.get("candidate"):
            docs[f].setdefault("dismissed_candidates", []).append(
                {"candidate": y["candidate"], "reason": f"merged into {args.keep}"})
        drops.append((f, i))
    for f, i in sorted(drops, key=lambda t: -t[1]):
        docs[f]["findings"].pop(i)
    for f, d in docs.items():
        write_json(f, d)
    print(f"merged {', '.join(args.drop)} into {args.keep}; run merge again (ids are renumbered)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("kind")
    p.add_argument("--base")
    p.add_argument("--spec", action="append", default=[])
    p.add_argument("--plan", action="append", default=[])
    p.add_argument("--title")
    p.add_argument("--jira")
    s = sub.add_parser("show")
    s.add_argument("review_dir")
    s.add_argument("--batch", type=int, required=True)
    s.add_argument("--full", action="store_true")
    m = sub.add_parser("merge")
    m.add_argument("review_dir")
    m.add_argument("--allow-incomplete", action="store_true")
    vp = sub.add_parser("verify-plan")
    vp.add_argument("review_dir")
    vs = sub.add_parser("verify-show")
    vs.add_argument("review_dir")
    vs.add_argument("--batch", type=int, required=True)
    c = sub.add_parser("combine")
    c.add_argument("review_dir")
    c.add_argument("keep")
    c.add_argument("drop", nargs="+")
    args = ap.parse_args()
    {"prepare": cmd_prepare, "show": cmd_show, "merge": cmd_merge, "combine": cmd_combine,
     "verify-plan": cmd_verify_plan, "verify-show": cmd_verify_show}[args.cmd](args)


if __name__ == "__main__":
    main()
