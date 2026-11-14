#!/usr/bin/env python3
"""Stage 1, step 2: deterministic triage of a collected change.

Usage: triage.py <report_dir|latest>

Assigns rulesets, excludes noise, detects mechanical changes, evaluates deterministic rules,
computes fan-in / largest added block / linked tests, assigns tiers and model batches.
"""
from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

from _common import (changed_lines, git, glob_match, largest_added_block, load_config,
                     load_rulesets, parse_diff, read_json, repo_root, resolve_report_dir,
                     ruleset_for, write_json)

WS = re.compile(r"\s+")


def norm_line(body, self_name):
    s = WS.sub(" ", body.strip())
    if self_name:
        s = re.sub(rf"\b{re.escape(self_name)}\b", "<SELF>", s)
    return s


class Ctx:
    def __init__(self, root, cfg, analysis):
        self.root = root
        self.cfg = cfg
        self.a = analysis
        self.base_commit = analysis["change"]["base_commit"]
        self.base_rs, self.stacks = load_rulesets(cfg)
        self.sig = cfg.get("signals") or {}
        self.tiers = cfg.get("tiers") or {}
        self._all_files = None

    def all_files(self):
        if self._all_files is None:
            tracked = [p for p in git("ls-files", "-z", cwd=self.root).split("\0") if p]
            untracked = [f["path"] for f in self.a["files"] if f["untracked"]]
            self._all_files = sorted(set(tracked) | set(untracked))
        return self._all_files


def is_noise_line(body, rs_list):
    s = body.strip()
    if not s:
        return True
    for rs in rs_list:
        if any(rx.search(body) for rx in rs.import_res) or any(rx.search(body) for rx in rs.comment_res):
            return True
    return False


STR_LIT = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'')
TOKEN = re.compile(r"[A-Za-z_]\w*|\d+|\S")
IDENT = re.compile(r"^[A-Za-z_]\w*$")


def _edit_distance(a, b, cap=4):
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _is_typo_fix(old, new):
    """Small letter-only edit inside a message-like literal (has whitespace). Keys, roles,
    numbers and paths are never typos: "30" -> "50" or 'ADMIN' -> 'ADMINS' must stay visible."""
    if old == new:
        return True
    if not (re.search(r"\s", old) and re.search(r"\s", new)):
        return False
    if re.sub(r"[^0-9]", "", old) != re.sub(r"[^0-9]", "", new):
        return False
    return _edit_distance(old, new) <= 3


def trivial_lines(hunks, new_text):
    """Line ids ('-', old_no) / ('+', new_no) of pairs that only rename identifiers consistently
    (old name gone from the file) or fix typos inside string literals."""
    pairs = []
    for h in hunks:
        rem, add = [], []
        for tag, o, n, body in h["lines"] + [(" ", None, None, "")]:
            if tag == "-":
                if add:
                    pairs += list(zip(rem, add)) if len(rem) == len(add) else []
                    rem, add = [], []
                rem.append((o, body))
            elif tag == "+":
                add.append((n, body))
            else:
                if len(rem) == len(add):
                    pairs += list(zip(rem, add))
                rem, add = [], []
    new_tokens = set(TOKEN.findall(new_text or ""))
    renames, cand = {}, []
    for (o, ob), (n, nb) in pairs:
        if ob.strip() == nb.strip():
            continue
        ol, nl = STR_LIT.findall(ob), STR_LIT.findall(nb)
        if STR_LIT.sub('"S"', ob).strip() == STR_LIT.sub('"S"', nb).strip() and len(ol) == len(nl):
            if all(_is_typo_fix(x, y) for x, y in zip(ol, nl)):
                cand.append(((o, n), []))
            continue
        ot, nt = TOKEN.findall(ob), TOKEN.findall(nb)
        if len(ot) != len(nt):
            continue
        diffs = [(x, y) for x, y in zip(ot, nt) if x != y]
        if diffs and all(IDENT.match(x) and IDENT.match(y) and x not in new_tokens for x, y in diffs):
            cand.append(((o, n), diffs))
            for x, y in diffs:
                renames.setdefault(x, set()).add(y)
    out = set()
    for (o, n), diffs in cand:
        if all(len(renames[x]) == 1 for x, _ in diffs):
            out.add(("-", o))
            out.add(("+", n))
    return out


def ignored_new_lines(new_text, pattern):
    if not pattern or not new_text:
        return set()
    rx = re.compile(pattern)
    for i, line in enumerate(new_text.splitlines(), 1):
        if rx.search(line):
            return set(range(i, i + 100000))
    return set()


def apply_rules(f, hunks, rules, rs_list, is_test, trivial=frozenset(), new_text=""):
    findings = []
    lines = list(changed_lines(hunks))
    for r in rules:
        if r.get("kind", "deterministic") != "deterministic":
            continue
        tests = r.get("tests", "exclude")
        if (tests == "exclude" and is_test) or (tests == "only" and not is_test):
            continue
        paths = r.get("path")
        if paths and not glob_match(f["path"], [paths] if isinstance(paths, str) else paths):
            continue
        xpaths = r.get("exclude_path")
        if xpaths and glob_match(f["path"], [xpaths] if isinstance(xpaths, str) else xpaths):
            continue
        statuses = r.get("statuses")
        if statuses and f["status"] not in statuses:
            continue
        match = r.get("match", "changed")
        evidence = []
        if match == "file":
            evidence.append({"path": f["path"], "line_start": None, "line_end": None,
                             "side": "new", "snippet": f"{f['status']} file"})
        else:
            rx = re.compile(r["pattern"])
            not_rx = re.compile(r["not_pattern"]) if r.get("not_pattern") else None
            after = ignored_new_lines(new_text, r.get("ignore_after"))
            for tag, o, n, body in lines:
                if tag == "+" and n in after:
                    continue
                if match == "added" and tag != "+":
                    continue
                if match == "removed" and tag != "-":
                    continue
                if r.get("skip_noise", True) and (is_noise_line(body, rs_list)
                                                  or (tag, o if tag == "-" else n) in trivial):
                    continue
                if rx.search(body) and not (not_rx and not_rx.search(body)):
                    no = n if tag == "+" else o
                    evidence.append({"path": f["path"], "line_start": no, "line_end": no,
                                     "side": "new" if tag == "+" else "old",
                                     "snippet": (tag + body.strip())[:200]})
            if len(evidence) < int(r.get("min_hits", 1)):
                continue
        points = int(r.get("points", 1))
        if f["status"] == "added" and r.get("points_new_file") is not None:
            points = int(r["points_new_file"])
        findings.append(make_finding(r["id"], r["dimension"], points,
                                     bool(r.get("critical", False)), r.get("title", r["id"]),
                                     r.get("reason", r.get("title", "")), evidence[:4],
                                     tags=r.get("tags") or [], hits=len(evidence)))
    return findings


def make_finding(rule_id, dimension, points, critical, title, reason, evidence, tags=None, hits=None):
    f = {"rule_id": rule_id, "source": "deterministic", "dimension": dimension,
         "points": max(0, min(5, points)), "critical": critical, "title": title,
         "reason": reason, "evidence": evidence, "affected_symbols": [], "consequences": [],
         "confidence": "verified", "limitations": [], "tags": tags or []}
    if hits and hits > len(evidence):
        f["reason"] = f"{reason} ({hits} occurrences, first {len(evidence)} shown)"
    return f


def test_findings(f, hunks, rs, sig):
    out = []
    if f["status"] == "deleted":
        out.append(make_finding("base.tests.deleted", "tests", sig["weakened_test"]["points"], False,
                                "Test file deleted", "A test file was removed; verify the covered behaviour is still tested.",
                                [{"path": f["path"], "line_start": None, "line_end": None, "side": "old",
                                  "snippet": "deleted file"}], tags=["weakened_test"]))
        return out
    lines = list(changed_lines(hunks))
    skip_ev = [{"path": f["path"], "line_start": n, "line_end": n, "side": "new", "snippet": ("+" + b.strip())[:200]}
               for t, o, n, b in lines if t == "+" and any(rx.search(b) for rx in rs.skip_res)]
    if skip_ev:
        out.append(make_finding("base.tests.disabled", "tests", sig["weakened_test"]["points"], False,
                                "Test disabled / skipped",
                                "A test was disabled or skipped; behaviour it verified is no longer checked.",
                                skip_ev[:4], tags=["weakened_test"], hits=len(skip_ev)))
    removed = [(o, b) for t, o, n, b in lines if t == "-" and any(rx.search(b) for rx in rs.assert_res)]
    added = [b for t, o, n, b in lines if t == "+" and any(rx.search(b) for rx in rs.assert_res)]
    if len(removed) > len(added):
        ev = [{"path": f["path"], "line_start": o, "line_end": o, "side": "old", "snippet": ("-" + b.strip())[:200]}
              for o, b in removed[:4]]
        out.append(make_finding("base.tests.assertions-removed", "tests", sig["weakened_test"]["points"], False,
                                "Assertions removed from tests",
                                f"{len(removed)} assertion lines removed, {len(added)} added — test may have been weakened.",
                                ev, tags=["weakened_test"]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report_dir", nargs="?", default="latest")
    args = ap.parse_args()

    root = repo_root()
    rdir = resolve_report_dir(args.report_dir, root)
    a = read_json(rdir / "analysis.json")
    cfg = load_config(root)
    ctx = Ctx(root, cfg, a)
    sig, tiers = ctx.sig, ctx.tiers
    src = a["change"]["sources"]
    doc_sources = set(src["spec"]) | set(src["plan"])
    exclude = (cfg.get("exclude") or []) + (cfg.get("extra_exclude") or []) + ctx.base_rs.exclude
    crit_modules = cfg.get("critical_modules") or []
    a["limitations"] = []  # triage owns limitations; aggregate appends its own
    limitations = a["limitations"]

    hunks_by = {}
    trivial_by = {}
    used_rulesets = set()
    no_ruleset = []
    for f in a["files"]:
        rs = ruleset_for(f["path"], ctx.stacks)
        f["ruleset"] = rs.id if rs else "_base"
        if rs:
            used_rulesets.add(rs.id)
        rs_list = [x for x in (rs, ctx.base_rs) if x]
        f["is_test"] = any(x.is_test(f["path"]) for x in rs_list)
        f["module"] = next((m for m in (x.module_of(f["path"]) for x in rs_list) if m), None) \
            or (str(Path(f["path"]).parent) if "/" in f["path"] else "(root)")
        f.update({"tier": None, "tier_reasons": [], "excluded_reason": None, "mechanical_kind": None,
                  "symbols": [], "fan_in": 0, "fan_in_files": [], "largest_added_block": 0,
                  "linked_tests": [], "test_changed": None, "in_plan": None, "plan_refs": [],
                  "findings": [], "semantic_done": False})
        if f["path"] in doc_sources:
            f["tier"], f["excluded_reason"] = "excluded", "spec/plan document (used as context source)"
        elif glob_match(f["path"], exclude + (rs.exclude if rs else [])):
            f["tier"], f["excluded_reason"] = "excluded", "excluded path (generated, lockfile, build output or docs)"
        elif f.get("binary"):
            f["tier"], f["excluded_reason"] = "excluded", "binary file"
        if f["tier"] == "excluded":
            continue
        if not rs and f["language"] not in ("markdown", "other"):
            no_ruleset.append(f["path"])
        text = (rdir / f["diff_file"]).read_text(encoding="utf-8")
        hunks = parse_diff(text)
        hunks_by[f["path"]] = hunks
        try:
            new_text = "" if f["status"] == "deleted" else (root / f["path"]).read_text(encoding="utf-8", errors="replace")
        except OSError:
            new_text = ""
        trivial = trivial_lines(hunks, new_text)
        trivial_by[f["path"]] = trivial
        rules = ctx.base_rs.rules + (rs.rules if rs else [])
        f["findings"] = apply_rules(f, hunks, rules, rs_list, f["is_test"], trivial, new_text)
        if f["is_test"] and rs:
            f["findings"] += test_findings(f, hunks, rs, sig)
        mig = [p for x in rs_list for p in x.migration_patterns]
        mig_ignore = [p for x in rs_list for p in x.migration_ignore]
        if glob_match(f["path"], mig) and not glob_match(f["path"], mig_ignore) and f["status"] in ("modified", "deleted", "renamed") and not f["untracked"]:
            s = sig["migration_edited"]
            f["findings"].append(make_finding(
                "base.data.migration-edited", "data_integrity", s["points"], s.get("critical", True),
                "Existing migration modified",
                "A migration that already exists on the base was changed; environments where it ran will not re-run it "
                "and checksums may fail.",
                [{"path": f["path"], "line_start": None, "line_end": None, "side": "new", "snippet": f"{f['status']} migration"}],
                tags=["migration_edited"]))
        if crit_modules and glob_match(f["path"], crit_modules):
            s = sig["critical_module"]
            f["findings"].append(make_finding("base.config.critical-module", "core_logic", s["points"], False,
                                              "File in a configured critical module",
                                              "Listed in critical_modules of rules.yaml.", [], tags=["critical_module"]))
            f["tier_reasons"].append("critical module")
        f["largest_added_block"] = largest_added_block(hunks)

    if no_ruleset:
        limitations.append(f"No stack ruleset matched {len(no_ruleset)} file(s) — base rules only "
                           f"(e.g. {', '.join(no_ruleset[:3])}).")

    # ---- mechanical detection
    rs_by_id = {rs.id: rs for rs in ctx.stacks}
    candidates = [f for f in a["files"] if f["tier"] is None]
    norm_sets = {}
    for f in candidates:
        rs = rs_by_id.get(f["ruleset"])
        rs_list = [x for x in (rs, ctx.base_rs) if x]
        hunks = hunks_by[f["path"]]
        has_strong = any(x["points"] >= 3 or x["critical"] for x in f["findings"])
        trivial = trivial_by.get(f["path"], set())
        body_lines = [(t, b) for t, o, n, b in changed_lines(hunks)]
        nontrivial = [(t, b) for t, o, n, b in changed_lines(hunks) if (t, o if t == "-" else n) not in trivial]
        if any(glob_match(f["path"], x.generated_companions) for x in rs_list):
            f["tier"], f["mechanical_kind"] = "mechanical", "generated companion file"
            f["findings"] = []
            continue
        if not body_lines and f["status"] == "renamed":
            f["tier"], f["mechanical_kind"] = "mechanical", "pure rename"
            continue
        if has_strong or f["is_test"] and f["findings"]:
            continue
        code = [(t, b) for t, b in nontrivial if not is_noise_line(b, rs_list)]
        if body_lines and not code and len(nontrivial) < len(body_lines):
            f["tier"], f["mechanical_kind"] = "mechanical", "renames / typo fixes only"
            continue
        if body_lines and not code:
            kinds = {"import" if any(rx.search(b) for x in rs_list for rx in x.import_res) else "comment"
                     for t, b in body_lines if b.strip()}
            f["tier"], f["mechanical_kind"] = "mechanical", ("imports only" if kinds == {"import"} else
                                                             "comments only" if kinds == {"comment"} else
                                                             "imports/comments only")
            continue
        if f["status"] == "modified" and body_lines:
            ws = git("diff", ctx.base_commit, "-w", "--ignore-blank-lines", "--no-color", "--", f["path"], cwd=root)
            if not parse_diff(ws) or not list(changed_lines(parse_diff(ws))):
                f["tier"], f["mechanical_kind"] = "mechanical", "whitespace/formatting only"
                continue
        if f["status"] == "modified":
            stem = Path(f["path"]).stem
            norm_sets[f["path"]] = {(t, norm_line(b, stem)) for t, b in code}

    min_files = max(int((cfg.get("mechanical") or {}).get("min_files", 5)),
                    int(len(a["files"]) * float((cfg.get("mechanical") or {}).get("min_share", 0.03))))
    freq = Counter(l for s in norm_sets.values() for l in s)
    frequent = {l for l, c in freq.items() if c >= min_files}
    groups = defaultdict(list)
    for path, lines in norm_sets.items():
        if lines and lines <= frequent:
            groups[frozenset(lines)].append(path)
    by_path = {f["path"]: f for f in a["files"]}
    a["groups"] = []
    gid = 0
    for sig_lines, paths in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if len(paths) < min_files:
            continue
        gid += 1
        sample = sorted(sig_lines, key=lambda l: (-freq[l], l))[:3]
        for p in paths:
            by_path[p]["tier"] = "mechanical"
            by_path[p]["mechanical_kind"] = f"repeated pattern (group mech-{gid})"
        a["groups"].append({"id": f"mech-{gid}", "kind": "mechanical",
                            "description": f"Same change repeated in {len(paths)} files",
                            "files": sorted(paths),
                            "sample_line": "\n".join(f"{t}{l}" for t, l in sample)})
    for kind in ("generated companion file", "renames / typo fixes only", "imports only", "comments only", "imports/comments only",
                 "whitespace/formatting only", "pure rename"):
        paths = sorted(f["path"] for f in a["files"] if f["mechanical_kind"] == kind)
        if paths:
            gid += 1
            a["groups"].append({"id": f"mech-{gid}", "kind": "mechanical", "description": kind.capitalize(),
                                "files": paths, "sample_line": None})
    # partially mechanical files: remember residual size for the model
    for path, lines in norm_sets.items():
        f = by_path[path]
        if f["tier"] is None and lines & frequent:
            f["tier_reasons"].append(f"{len(lines - frequent)} line(s) beyond a repeated pattern seen in other files")

    # ---- symbols, fan-in, linked tests
    all_files = ctx.all_files()
    basenames = defaultdict(list)
    for p in all_files:
        basenames[Path(p).name].append(p)
    changed_paths = {f["path"] for f in a["files"]}
    fan_cfg = sig.get("fan_in") or {}
    for f in a["files"]:
        if f["tier"] in ("excluded",) or f["is_test"]:
            continue
        rs = rs_by_id.get(f["ruleset"])
        if not rs:
            continue
        try:
            if f["status"] == "deleted":
                content = git("show", f"{ctx.base_commit}:{f['path']}", cwd=root)
            else:
                content = (root / f["path"]).read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        syms = []
        for rx in rs.symbol_res:
            for m in rx.finditer(content):
                if m.group(1) not in syms:
                    syms.append(m.group(1))
        f["symbols"] = syms[:6]
        if f["tier"] != "mechanical" and syms:
            refs = set()
            specs = [f":(glob){g}" for g in rs.grep_globs]
            for s in syms[:3]:
                if len(s) < 4:
                    continue
                out = git("grep", "-l", "-w", "-F", "--untracked", "-e", s, "--", *specs, cwd=root, ok=(0, 1))
                refs.update(p for p in out.splitlines() if p and p != f["path"])
            f["fan_in"] = len(refs)
            f["fan_in_files"] = sorted(refs)[:30]
        cands = []
        for rx, targets in rs.test_name_map:
            m = rx.match(Path(f["path"]).name)
            if m:
                for t in targets:
                    cands.extend(basenames.get(m.expand(t), []))
        f["linked_tests"] = sorted(set(cands))
        f["test_changed"] = any(t in changed_paths for t in f["linked_tests"]) if f["linked_tests"] else False

    # ---- large added block signal
    lb = sig.get("large_block") or {}
    for f in a["files"]:
        if f["tier"] in ("excluded", "mechanical") or f["is_test"]:
            continue
        block = f["largest_added_block"]
        thr_hi = lb.get("new_file_threshold", 250) if f["status"] == "added" else lb.get("high_threshold", 150)
        thr = lb.get("new_file_threshold", 250) if f["status"] == "added" else lb.get("threshold", 80)
        pts = lb.get("high_points", 2) if block >= thr_hi else lb.get("points", 1) if block >= thr else 0
        if pts:
            f["findings"].append(make_finding(
                "base.drift.large-added-block", "core_logic", pts, False,
                f"Large contiguous block of new code ({block} lines)",
                "Long generated blocks are where drift from requirements and conventions hides.",
                [{"path": f["path"], "line_start": None, "line_end": None, "side": "new",
                  "snippet": f"{block} consecutive added lines"}], tags=["drift"]))

    # ---- tiers
    t_deep_pts = tiers.get("deep_min_points", 3)
    for f in a["files"]:
        if f["tier"]:
            continue
        reasons = f["tier_reasons"]
        strong = [x for x in f["findings"] if x["points"] >= t_deep_pts or x["critical"]]
        if strong:
            reasons.append(f"{len(strong)} deterministic finding(s) ≥ {t_deep_pts} points or critical")
        if f["fan_in"] >= tiers.get("deep_fan_in", 20):
            reasons.append(f"fan-in {f['fan_in']}")
        block_thr = (sig.get("large_block") or {}).get("new_file_threshold", 250) if f["status"] == "added" \
            else tiers.get("deep_added_block", 80)
        big_block = f["largest_added_block"] >= block_thr
        if big_block:
            reasons.append(f"{f['largest_added_block']}-line added block")
        deep = bool(strong) or f["fan_in"] >= tiers.get("deep_fan_in", 20) or big_block or "critical module" in reasons
        f["tier"] = "deep" if deep else "light"
        f["_prio"] = sum(x["points"] for x in f["findings"]) + f["fan_in"] / 10 + f["largest_added_block"] / 50

    deep = sorted((f for f in a["files"] if f["tier"] == "deep"), key=lambda f: -f["_prio"])
    cap = tiers.get("deep_max_files", 40)
    if len(deep) > cap:
        for f in deep[cap:]:
            f["tier"] = "light"
            f["tier_reasons"].append(f"deep-analysis cap ({cap}) reached")
        limitations.append(f"{len(deep) - cap} file(s) qualified for deep analysis but were analysed lightly "
                           f"(tiers.deep_max_files = {cap}).")
    for f in a["files"]:
        f.pop("_prio", None)

    batches, n = [], 0
    for tier, size in (("deep", tiers.get("deep_batch_size", 6)), ("light", tiers.get("light_batch_size", 15))):
        items = sorted((f for f in a["files"] if f["tier"] == tier), key=lambda f: (f["module"] or "", f["path"]))
        for i in range(0, len(items), size):
            n += 1
            batches.append({"id": n, "tier": tier, "files": [f["path"] for f in items[i:i + size]]})
    a["batches"] = batches

    st = a["change"]["stats"]
    st["excluded"] = sum(1 for f in a["files"] if f["tier"] == "excluded")
    st["mechanical"] = sum(1 for f in a["files"] if f["tier"] == "mechanical")
    st["modules"] = len({f["module"] for f in a["files"] if f["tier"] != "excluded"})
    a["change"]["rulesets"] = sorted(used_rulesets) or ["_base"]
    write_json(rdir / "analysis.json", a)

    tiers_count = Counter(f["tier"] for f in a["files"])
    print(f"report: {rdir}")
    print(f"tiers: deep {tiers_count['deep']}, light {tiers_count['light']}, mechanical {tiers_count['mechanical']}, "
          f"excluded {tiers_count['excluded']}; rulesets {', '.join(a['change']['rulesets'])}")
    print(f"batches: {len(batches)} ({sum(1 for b in batches if b['tier'] == 'deep')} deep, "
          f"{sum(1 for b in batches if b['tier'] == 'light')} light); mechanical groups: {len(a['groups'])}")
    top = sorted((x | {"_p": f["path"]} for f in a["files"] for x in f["findings"]),
                 key=lambda x: (-x["critical"], -x["points"]))[:10]
    if top:
        print("top deterministic findings:")
        for x in top:
            print(f"  [{x['points']}{'!' if x['critical'] else ''}] {x['dimension']}: {x['title']} — {x['_p']}")
    for lim in limitations:
        print(f"limitation: {lim}")


if __name__ == "__main__":
    main()
