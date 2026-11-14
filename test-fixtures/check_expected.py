#!/usr/bin/env python3
"""Compare an impact analysis with a scenario's ground truth.

Usage:
  check_expected.py <scenario-id>                # sandbox/<id>, newest report
  check_expected.py <scenario-id> <report_dir>
  check_expected.py --all                        # every scenario that has a sandbox with a report

expected.json (in scenarios/<id>/):
  {"mode": "...", "mode_alternatives": ["..."],
   "top": {"n": 5, "files": ["path suffix", ...]},          each must rank within top n
   "must_detect": [{"path": "suffix", "dimension": "security" | ["conventions", "architecture"],
                    "min_points": 3, "note": "..."}],
   "traps": {"n": 10, "files": ["suffix", ...]},             none may rank within top n
   "plan_drift": {"unplanned": ["suffix"], "planned_not_changed": ["suffix"]}}
Exit code: 0 all pass, 1 failures, 2 usage / missing data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def match(path, suffix):
    return path == suffix or path.endswith("/" + suffix.lstrip("/"))


def newest_report(sandbox):
    base = sandbox / "docs" / "code-review" / "reports"
    if not base.is_dir():
        return None
    dirs = [p.parent for p in base.glob("*/runs/*/analysis.json")] + [p.parent for p in base.glob("*/analysis.json")]
    dirs = [d for d in dirs if "verdict" in json.loads((d / "analysis.json").read_text(encoding="utf-8"))
            and json.loads((d / "analysis.json").read_text(encoding="utf-8"))["verdict"]]
    return max(dirs, key=lambda d: d.name) if dirs else None


def check(sid, report_dir=None):
    exp_path = ROOT / "scenarios" / sid / "expected.json"
    if not exp_path.is_file():
        return None, [f"{sid}: no expected.json"]
    exp = json.loads(exp_path.read_text(encoding="utf-8"))
    rdir = Path(report_dir) if report_dir else newest_report(ROOT / "sandbox" / sid)
    if not rdir or not (rdir / "analysis.json").is_file():
        return None, [f"{sid}: no report found"]
    a = json.loads((rdir / "analysis.json").read_text(encoding="utf-8"))
    ranked = sorted((f for f in a["files"] if f.get("tier") != "excluded"),
                    key=lambda f: (-bool(f.get("critical")), -(f.get("severity") or 0), -(f.get("score") or 0),
                                   -(f["added_lines"] + f["deleted_lines"]), f["path"]))
    rank = {f["path"]: f.get("rank") or i + 1 for i, f in enumerate(ranked)}
    by_path = {f["path"]: f for f in a["files"]}
    results = []

    def res(ok, label):
        results.append((ok, label))

    mode = (a.get("verdict") or {}).get("mode")
    allowed = [exp.get("mode")] + exp.get("mode_alternatives", [])
    res(mode in allowed, f"mode: got {mode}, expected {' | '.join(allowed)}")

    def find(suffix):
        return next((p for p in by_path if match(p, suffix)), None)

    top = exp.get("top") or {}
    for s in top.get("files", []):
        p = find(s)
        r = rank.get(p)
        res(r is not None and r <= top.get("n", 5), f"top{top.get('n', 5)}: {s} (rank {r or '-'})")
    for m in exp.get("must_detect", []):
        p = find(m["path"])
        f = by_path.get(p) if p else None
        dims = m["dimension"] if isinstance(m["dimension"], list) else [m["dimension"]]
        hits = [x for x in (f or {}).get("findings", []) if x["dimension"] in dims
                and x["points"] >= m.get("min_points", 1)]
        best = max((x["points"] for x in (f or {}).get("findings", []) if x["dimension"] in dims), default=None)
        res(bool(hits), f"detect: {'/'.join(dims)} ≥{m.get('min_points', 1)} in {m['path']} (best {best})"
            + (f" — {m['note']}" if m.get("note") else ""))
    traps = exp.get("traps") or {}
    for s in traps.get("files", []):
        p = find(s)
        r = rank.get(p)
        res(r is None or r > traps.get("n", 10), f"trap outside top{traps.get('n', 10)}: {s} (rank {r or '-'})")
    drift = exp.get("plan_drift")
    if drift:
        got = a.get("plan_drift") or {}
        for s in drift.get("unplanned", []):
            res(any(match(p, s) for p in got.get("unplanned_files", [])), f"plan drift unplanned: {s}")
        for s in drift.get("planned_not_changed", []):
            res(any(match(p, s) or match(s, p) for p in got.get("planned_not_changed", [])),
                f"plan drift not implemented: {s}")
    return results, []


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)
    if args[0] == "--all":
        sids = sorted(d.name for d in (ROOT / "scenarios").iterdir() if d.is_dir())
        runs = [(s, None) for s in sids if newest_report(ROOT / "sandbox" / s)]
        if not runs:
            print("no sandbox has a report yet")
            sys.exit(2)
    else:
        runs = [(args[0], args[1] if len(args) > 1 else None)]
    total_fail = 0
    for sid, rdir in runs:
        results, errors = check(sid, rdir)
        if errors:
            for e in errors:
                print(f"SKIP {e}")
            continue
        fails = [l for ok, l in results if not ok]
        total_fail += len(fails)
        print(f"{'PASS' if not fails else 'FAIL'} {sid}: {len(results) - len(fails)}/{len(results)}")
        for ok, label in results:
            print(f"   {'ok  ' if ok else 'FAIL'} {label}")
    sys.exit(1 if total_fail else 0)


if __name__ == "__main__":
    main()
