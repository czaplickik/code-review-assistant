#!/usr/bin/env python3
"""Stage 1, step 4: merge model output, score files, decide the review mode.

Usage: aggregate.py <report_dir|latest> [--allow-incomplete]

Reads semantic/batch-*.json, flows.json and (optionally) plan-summary.json from the report
directory. Exits 1 with a list of problems when model output is invalid or missing
(unless --allow-incomplete).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _common import (DIMENSIONS, glob_match, load_config, read_json, repo_root,
                     resolve_report_dir, write_json)

CONFIDENCE = ("verified", "inferred")
PATH_RE = re.compile(r"`([^`\s]+/[^`\s]+\.[A-Za-z0-9]{1,8})`|(?<![\w/.-])((?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]{1,8})(?![\w/])"
                     r"|`([\w.-]+\.(?:xml|ya?ml|json|gradle|kts|toml|csproj|sln|props|targets|sql|properties|java|kt|cs))`")
CODE_LANGS = {"java", "kotlin", "groovy", "csharp", "fsharp", "python", "typescript", "javascript",
              "go", "ruby", "php"}


def clamp_points(v):
    try:
        return max(0, min(5, int(v)))
    except (TypeError, ValueError):
        return None


def normalize_finding(x, path, problems, where):
    if not isinstance(x, dict):
        problems.append(f"{where}: finding is not an object")
        return None
    dim = x.get("dimension")
    pts = clamp_points(x.get("points"))
    if dim not in DIMENSIONS:
        problems.append(f"{where}: unknown dimension '{dim}' (use one of {', '.join(DIMENSIONS)})")
        return None
    if pts is None:
        problems.append(f"{where}: points must be an integer 0-5")
        return None
    if not x.get("title"):
        problems.append(f"{where}: finding without title")
        return None
    conf = x.get("confidence") if x.get("confidence") in CONFIDENCE else "inferred"
    ev = []
    for e in x.get("evidence") or []:
        if isinstance(e, dict):
            ev.append({"path": e.get("path") or path, "line_start": e.get("line_start"),
                       "line_end": e.get("line_end", e.get("line_start")), "side": e.get("side", "new"),
                       "snippet": (e.get("snippet") or "")[:400]})
    return {"rule_id": x.get("rule_id") or f"semantic.{dim}", "source": "semantic", "dimension": dim,
            "points": pts, "critical": bool(x.get("critical", False)) and pts >= 3, "title": str(x["title"])[:160],
            "reason": x.get("reason") or "", "evidence": ev[:4],
            "affected_symbols": list(x.get("affected_symbols") or []),
            "consequences": list(x.get("consequences") or []), "confidence": conf,
            "limitations": list(x.get("limitations") or []), "tags": list(x.get("tags") or [])}


def load_semantic(rdir, a, problems):
    by_path = {f["path"]: f for f in a["files"]}
    seen = set()
    for bf in sorted((rdir / "semantic").glob("batch-*.json")):
        try:
            data = read_json(bf)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{bf.name}: invalid JSON ({exc})")
            continue
        for i, item in enumerate(data.get("files") or []):
            where = f"{bf.name} files[{i}]"
            path = item.get("path")
            f = by_path.get(path)
            if not f:
                problems.append(f"{where}: path '{path}' is not in this change")
                continue
            seen.add(path)
            f["role"] = item.get("role") or f.get("role")
            inter = item.get("interactions") or {}
            f["interactions"] = {k: list(inter.get(k) or []) for k in ("called_by", "calls", "contracts", "changed_edges")}
            f["what_to_verify"] = list(item.get("what_to_verify") or [])[:5]
            for j, x in enumerate(item.get("findings") or []):
                nf = normalize_finding(x, path, problems, f"{where} findings[{j}]")
                if nf:
                    f["findings"].append(nf)
            for adj in item.get("adjust") or []:
                tgt = next((x for x in f["findings"] if x["rule_id"] == adj.get("rule_id") and x["source"] == "deterministic"), None)
                pts = clamp_points(adj.get("points"))
                if tgt is None or pts is None:
                    problems.append(f"{where}: adjust refers to unknown rule '{adj.get('rule_id')}' or bad points")
                    continue
                tgt["reason"] += f" — adjusted {tgt['points']}→{pts} by semantic review: {adj.get('reason', '')}"
                tgt["points"] = pts
                if "critical" in adj:
                    tgt["critical"] = bool(adj["critical"])
                if pts <= 1:  # lowered to (almost) nothing: never critical
                    tgt["critical"] = False
            if item.get("mechanical_confirmed") is False and f["tier"] == "mechanical":
                f["tier"] = "light"
                f["tier_reasons"].append("model found non-mechanical content")
            f["semantic_done"] = True
    missing = [f["path"] for f in a["files"] if f["tier"] in ("deep", "light") and f["path"] not in seen]
    return missing


def load_flows(rdir, a, problems):
    p = rdir / "flows.json"
    if not p.is_file():
        return False
    by_path = {f["path"]: f for f in a["files"]}
    flows = []
    for i, fl in enumerate(read_json(p).get("flows") or []):
        files = [x for x in fl.get("files") or [] if x in by_path]
        bad = [x for x in fl.get("files") or [] if x not in by_path]
        if bad:
            problems.append(f"flows.json flows[{i}]: unknown paths {bad[:3]}")
        if not files:
            continue
        fid = fl.get("id") or f"flow-{i + 1}"
        for x in files:
            by_path[x]["flow"] = by_path[x].get("flow") or fid
        flows.append({"id": fid, "name": fl.get("name") or fid, "description": fl.get("description") or "",
                      "files": files})
    a["flows"] = flows
    return True


def plan_paths(root, rdir, a):
    ps = rdir / "plan-summary.json"
    if not ps.is_file():  # newest plan summary (any report dir) built from the same plan documents
        plans = set(a["change"]["sources"]["plan"])
        cands = []
        for cand in rdir.parent.glob("*/plan-summary.json"):
            try:
                srcs = {x.get("path") for x in read_json(cand).get("sources") or []}
            except Exception:  # noqa: BLE001
                continue
            if plans & srcs:
                cands.append(cand)
        ps = max(cands, key=lambda c: c.parent.name) if cands else ps
    out = {}
    if ps.is_file():
        try:
            for e in read_json(ps).get("expected_files") or []:
                if e.get("path"):
                    out[e["path"].strip("./")] = e.get("ref") or "plan-summary"
        except Exception:  # noqa: BLE001
            pass
    for plan in a["change"]["sources"]["plan"]:
        try:
            text = (root / plan).read_text(encoding="utf-8")
        except OSError:
            continue
        section = ""
        for line in text.splitlines():
            if line.startswith("#"):
                section = re.sub(r"[^a-z0-9]+", "-", line.lstrip("#").strip().lower()).strip("-")
            for m in PATH_RE.finditer(line):
                p = (m.group(1) or m.group(2) or m.group(3)).strip("./")
                if p.startswith(("http", "www.")) or p.endswith(".md") or (root / p).is_dir():
                    continue
                out.setdefault(p, f"{plan}#{section}")
    return out


def path_matches(changed, planned):
    if "<" in planned or "*" in planned:  # placeholders like <timestamp>_AddX.cs
        rx = re.escape(planned)
        rx = re.sub(r"(\\<[^>]*\\>|<[^>]*>|\\\*)", "[^/]*", rx)
        return bool(re.search(r"(^|/)" + rx + "$", changed))
    return changed == planned or changed.endswith("/" + planned) or \
        ("/" not in planned and Path(changed).name == planned)


def replace_deleted(paths, a, by_path):
    """A deleted file is not something to read: point to the files that took over its logic
    (same flow, interactions naming it, or files still referencing its module)."""
    out = []
    for p in paths:
        f = by_path.get(p)
        if not f or f["status"] != "deleted":
            out.append(p)
            continue
        succ = []
        fl = next((fl for fl in a.get("flows") or [] if p in fl["files"]), None)
        if fl:
            succ += [q for q in fl["files"] if by_path.get(q, {}).get("status") != "deleted"]
        stem = Path(p).stem
        for g in by_path.values():
            inter = g.get("interactions") or {}
            names = " ".join((inter.get("calls") or []) + (inter.get("called_by") or []) + (inter.get("contracts") or []))
            if g["status"] != "deleted" and stem and stem in names:
                succ.append(g["path"])
        for g in a.get("groups") or []:
            if g.get("kind") == "deleted_module" and p in g["files"]:
                succ += [r["path"] for r in g.get("dangling_refs") or []]
        succ = [q for q in dict.fromkeys(succ) if q in by_path and by_path[q]["tier"] in ("deep", "light")]
        succ.sort(key=lambda q: by_path[q].get("rank") or 9999)
        if succ:
            for q in succ[:3]:
                by_path[q].setdefault("_replaces", []).append(p)
            out += succ[:3]
        else:
            out.append(p)
    return list(dict.fromkeys(out))


def human_review(paths, by_path, a):
    items = []
    for p in paths:
        f = by_path.get(p)
        if not f:
            continue
        top = sorted((x for x in f["findings"] if x["points"] > 0),
                     key=lambda x: (-x["critical"], -x["points"]))[:3]
        reasons = [f"{x['title']} ({x['points']} pt{', critical' if x['critical'] else ''})" for x in top]
        replaces = f.pop("_replaces", [])
        if replaces and not reasons:
            reasons = [f"took over logic of deleted {', '.join(Path(r).name for r in replaces[:3])}"]
        items.append({"path": p, "status": f["status"], "rank": f.get("rank"), "reasons": reasons,
                      "questions": list(f.get("what_to_verify") or [])[:4], "replaces": replaces})
    return items


def write_focus_md(rdir, a, focus):
    v = a.get("verdict") or {}
    lines = ["# AI review focus", "",
             f"Change: {a['change'].get('boundary')} vs {a['change'].get('base_ref')} on `{a['change'].get('branch')}`. "
             f"Review mode: {v.get('mode')}.", "",
             "Check each point below in the code and report what is wrong, with file and line. "
             "Files read by the human reviewer are not listed.", ""]
    if not focus:
        lines.append("_No points: the human reviewer covers the change._")
    for item in focus:
        path, _, q = item.partition(": ")
        lines.append(f"- [ ] `{path}` — {q}")
    (rdir / "ai-review-focus.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report_dir", nargs="?", default="latest")
    ap.add_argument("--allow-incomplete", action="store_true")
    args = ap.parse_args()

    root = repo_root()
    rdir = resolve_report_dir(args.report_dir, root)
    a = read_json(rdir / "analysis.json")
    cfg = load_config(root)
    sig = cfg.get("signals") or {}
    pol = cfg.get("policy") or {}
    problems = []

    for f in a["files"]:  # idempotent re-runs: drop previously merged semantic data
        f["findings"] = [x for x in f["findings"] if x["source"] == "deterministic"
                         and not x["rule_id"].startswith(("base.blast.", "base.tests.missing"))]
        f["flow"] = None
    missing = load_semantic(rdir, a, problems)
    has_flows = load_flows(rdir, a, problems)
    if missing:
        problems.append(f"{len(missing)} analysed file(s) have no semantic output, e.g. {missing[:5]}")
    if not has_flows:
        problems.append("flows.json missing")
    if problems and not args.allow_incomplete:
        print("model output incomplete or invalid:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)
    incomplete = bool(missing)
    lim = [l for l in a.get("limitations", []) if not l.startswith("Semantic analysis missing")]
    if missing:
        lim.append(f"Semantic analysis missing for {len(missing)} file(s); review mode cannot go below ai-review-only.")
    a["limitations"] = lim

    # ---- plan drift
    if a["change"]["sources"]["plan"]:
        planned = plan_paths(root, rdir, a)
        matched = set()
        unplanned = []
        for f in a["files"]:
            if f["tier"] == "excluded":
                continue
            refs = [ref for p, ref in planned.items() if path_matches(f["path"], p)]
            matched.update(p for p in planned if path_matches(f["path"], p))
            f["in_plan"] = bool(refs)
            f["plan_refs"] = sorted(set(refs))[:3]
            if not refs and not glob_match(f["path"], ["**/*.md"]):
                unplanned.append(f["path"])
        missing = [p for p in planned if p not in matched]
        # the same file is often named both by full path and by a shorter path in a plan
        not_changed = sorted(p for p in missing
                             if not any(q != p and (q.endswith("/" + p) or path_matches(q, p)) for q in missing))
        a["plan_drift"] = {"unplanned_files": unplanned, "planned_not_changed": not_changed,
                           "planned_refs": {p: planned[p] for p in not_changed}}

    # ---- amplifiers
    fan = sig.get("fan_in") or {}
    mt = sig.get("missing_test") or {}
    for f in a["files"]:
        if f["tier"] in ("excluded", "mechanical"):
            continue
        behavioural = [x for x in f["findings"] if x["points"] >= 2 and "drift" not in x.get("tags", [])]
        if behavioural and f.get("fan_in", 0) >= fan.get("threshold", 20):
            pts = fan.get("high_points", 3) if f["fan_in"] >= fan.get("high_threshold", 60) else fan.get("points", 2)
            f["findings"].append({
                "rule_id": "base.blast.fan-in", "source": "deterministic", "dimension": "architecture",
                "points": pts, "critical": False, "title": f"Wide blast radius: referenced from {f['fan_in']} files",
                "reason": f"Behavioural change in a symbol used by {f['fan_in']} files ({', '.join(f['symbols'][:3])}).",
                "evidence": [{"path": p, "line_start": None, "line_end": None, "side": "new", "snippet": "references"}
                             for p in f["fan_in_files"][:3]],
                "affected_symbols": f["symbols"][:3], "consequences": [], "confidence": "verified",
                "limitations": [], "tags": ["blast_radius"]})
        logic = [x for x in f["findings"] if x["dimension"] in ("core_logic", "data_integrity", "security")
                 and x["points"] >= 2 and "drift" not in x.get("tags", [])]
        if logic and not f["is_test"] and f["language"] in CODE_LANGS and not f.get("test_changed"):
            has = bool(f.get("linked_tests"))
            f["findings"].append({
                "rule_id": "base.tests.missing-update", "source": "deterministic", "dimension": "tests",
                "points": mt.get("points", 2), "critical": False,
                "title": "Behaviour changed, linked tests not updated" if has else "Behaviour changed, no tests found",
                "reason": ("Linked tests exist but were not changed: " + ", ".join(f["linked_tests"][:2])) if has
                else "No test file matching this class was found.",
                "evidence": [], "affected_symbols": [], "consequences": [], "confidence": "verified",
                "limitations": ["Test discovery is name-based; tests elsewhere may cover this."],
                "tags": ["missing_test"]})

    # ---- scoring
    weights = (cfg.get("scoring") or {}).get("confidence_weight") or {}
    n = 0
    for f in a["files"]:
        for x in f["findings"]:
            n += 1
            x["id"] = f"f-{n:04d}"
        f["score"] = round(sum(x["points"] * float(weights.get(x["confidence"], 1.0)) for x in f["findings"]))
        f["critical"] = any(x["critical"] for x in f["findings"])
        dims = {}
        for x in f["findings"]:
            dims[x["dimension"]] = max(dims.get(x["dimension"], 0), x["points"])
        f["dimensions"] = dims
    # ---- ranking: critical first, then the most severe finding (with reach bonus), then the sum
    rk = cfg.get("ranking") or {}
    reach_fan_in = rk.get("reach_fan_in", 10)
    reach_dims = set(rk.get("reach_dimensions") or ["contracts"])
    bonus = rk.get("reach_bonus", 1)
    for f in a["files"]:
        sev, raw = 0, 0
        for x in f["findings"]:
            p = x["points"]
            raw = max(raw, p)
            if p >= 2 and not set(x.get("tags", [])) & {"drift", "blast_radius", "missing_test"} and \
                    (f.get("fan_in", 0) >= reach_fan_in or x["dimension"] in reach_dims):
                p = min(5, p + bonus)
            sev = max(sev, p)
        f["severity"] = sev
        f["severity_reach_bonus"] = sev > raw
    order = sorted((f for f in a["files"] if f["tier"] != "excluded"),
                   key=lambda f: (-f["critical"], -f["severity"], -f["score"],
                                  -(f["added_lines"] + f["deleted_lines"]), f["path"]))
    for i, f in enumerate(order, 1):
        f["rank"] = i
    for f in a["files"]:
        if f["tier"] == "excluded":
            f["rank"] = None

    for fl in a["flows"]:
        fl["max_score"] = max((next(f for f in a["files"] if f["path"] == p)["score"] for p in fl["files"]), default=0)
    a["flows"].sort(key=lambda fl: -fl["max_score"])

    # ---- verdict
    analysed = [f for f in a["files"] if f["tier"] in ("deep", "light")]
    allf = [(f, x) for f in a["files"] for x in f["findings"]]
    sd = {"security", "data_integrity"}
    ho = pol.get("human_only") or {}
    ah = pol.get("ai_human") or {}
    aio = pol.get("ai_review_only") or {}
    bts = pol.get("build_tests_static") or {}
    key_dims = set(ah.get("key_dimensions") or ["core_logic", "security", "data_integrity", "contracts"])
    key_pts = ah.get("key_dimension_points", 3)
    crit_sd_files = {f["path"] for f, x in allf if x["critical"] and x["dimension"] in sd}
    top_sd = [(f, x) for f, x in allf if x["dimension"] in sd and x["points"] >= ho.get("security_data_max_points", 5)]
    crits = [(f, x) for f, x in allf if x["critical"]]
    keys = [(f, x) for f, x in allf if x["dimension"] in key_dims and x["points"] >= key_pts]
    weakened = [(f, x) for f, x in allf if "weakened_test" in x.get("tags", [])]
    maxp = max((x["points"] for _, x in allf), default=0)
    lines = sum(f["added_lines"] + f["deleted_lines"] for f in analysed if not f["is_test"])

    def pick(pairs, k=5):
        return [x["id"] for f, x in sorted(pairs, key=lambda p: (-p[1]["critical"], -p[1]["points"]))[:k]]

    reviewable = [f for f in a["files"] if f["tier"] != "excluded"]
    crit_files = {f["path"] for f, x in crits}
    crit_share = len(crit_files) / max(1, len(reviewable))
    min_share = ho.get("min_critical_share", 0.25)
    if (len(crit_sd_files) >= ho.get("security_data_critical_files", 3) or top_sd) and crit_share >= min_share:
        mode, rule = "human-only", "human_only.security_data"
        why = (f"Critical security/data findings in {len(crit_sd_files)} files" if crit_sd_files else "") + \
              ("; " if crit_sd_files and top_sd else "") + \
              (f"{len(top_sd)} finding(s) at 5 points in security/data integrity" if top_sd else "") + \
              f"; critical files are {crit_share:.0%} of the change"
        deciding = pick(top_sd + [(f, x) for f, x in crits if x["dimension"] in sd])
    elif crits:
        mode, rule, why, deciding = "ai+human-critical-paths", "ai_human.critical", \
            f"{len(crits)} critical finding(s) in {len(crit_files)} file(s)" + \
            (f" — concentrated ({crit_share:.0%} of the change), so human review of those files instead of everything"
             if top_sd or crit_sd_files else ""), pick(crits)
    elif keys:
        mode, rule = "ai+human-critical-paths", "ai_human.key_dimension_points"
        why = f"Findings ≥ {key_pts} points in {', '.join(sorted({x['dimension'] for _, x in keys}))}"
        deciding = pick(keys)
    elif maxp <= bts.get("max_points", 1) and len(analysed) <= bts.get("max_files", 30) and not weakened and not incomplete:
        mode, rule, why, deciding = "build+tests+static", "build_tests_static", \
            f"Only mechanical or low-impact changes (max {maxp} point(s))", pick(allf, 3)
    elif maxp <= aio.get("max_points", 2) and len(analysed) <= aio.get("max_files", 20) \
            and lines <= aio.get("max_changed_lines", 1000):
        mode, rule = "ai-review-only", "ai_review_only"
        why = f"Max {maxp} point(s), {len(analysed)} analysed files, {lines} changed lines" + \
              ("; weakened tests lift the mode above build+tests+static" if weakened else "") + \
              ("; incomplete semantic analysis" if incomplete else "")
        deciding = pick(weakened or allf, 3)
    else:
        mode, rule = "ai+human-critical-paths", "ai_human.exceeds_ai_review_only_limits"
        why = f"Exceeds ai-review-only limits (max {maxp} points, {len(analysed)} files, {lines} lines)"
        deciding = pick(allf)

    human_pts = ah.get("human_file_points", 4)
    human = sorted({f["path"] for f, x in crits} |
                   {f["path"] for f, x in keys if x["points"] >= human_pts}) \
        if mode == "ai+human-critical-paths" else []
    by_path = {f["path"]: f for f in a["files"]}
    if mode in ("ai+human-critical-paths", "human-only") and not human:
        dec = {x["id"] for f, x in allf if x["id"] in deciding}
        human = sorted({f["path"] for f, x in allf if x["id"] in dec})
    human = replace_deleted(human, a, by_path)
    if mode in ("ai+human-critical-paths", "human-only") and \
            not any(by_path[p]["status"] != "deleted" for p in human if p in by_path):
        # nothing readable left (e.g. the deciding file was deleted): add the top ranked live files
        human += [f["path"] for f in order if f["status"] != "deleted" and f["tier"] in ("deep", "light")
                  and f["path"] not in human][:5]
    if mode == "human-only":
        extra = [f["path"] for f in order if f["tier"] in ("deep", "light") and f["path"] not in human]
        human = human + extra[:max(0, 15 - len(human))]
    human.sort(key=lambda p: by_path[p].get("rank") or 9999 if p in by_path else 9999)
    a["verdict"] = {"mode": mode, "policy_rule": rule, "explanation": why, "deciding_findings": deciding,
                    "human_files": human}
    a["human_review"] = human_review(human, by_path, a)

    # ---- AI review focus
    focus = []
    ranked = sorted(analysed, key=lambda f: f["rank"])
    for f in ranked:
        if mode == "human-only" or f["path"] in human:
            continue
        for item in f.get("what_to_verify") or []:
            focus.append(f"{f['path']}: {item}")
    a["ai_review_focus"] = focus[:30]
    write_focus_md(rdir, a, focus)

    write_json(rdir / "analysis.json", a)
    print(f"verdict: {mode}  ({rule}: {why})")
    if human:
        print(f"human review: {len(human)} file(s)")
    for i, f in enumerate(order[:10], 1):
        top = max(f["findings"], key=lambda x: (x["critical"], x["points"]), default=None)
        print(f"{i:>3}. sev {f['severity']} score {f['score']:>3}{' !' if f['critical'] else '  '} {f['path']}"
              + (f"  — {top['title']}" if top else ""))
    if problems:
        print(f"warnings ({len(problems)}):")
        for p in problems[:10]:
            print(f"  - {p}")


if __name__ == "__main__":
    main()
