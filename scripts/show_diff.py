#!/usr/bin/env python3
"""Print model input for a batch or for single files: metadata, deterministic findings, diff.

Usage:
  show_diff.py <report_dir|latest> --batch N
  show_diff.py <report_dir|latest> --file PATH [--file PATH ...] [--full]
  show_diff.py <report_dir|latest> --list-batches
  show_diff.py <report_dir|latest> --roles      (compact roles/interactions from semantic output, for flows)
"""
from __future__ import annotations

import argparse

from _common import RULESETS_DIR, die, read_json, repo_root, resolve_report_dir

LIMITS = {"deep": 600, "light": 200, "mechanical": 60, "excluded": 0}


def file_block(rdir, f, full):
    head = (f"=== [{f['tier']}] {f['path']}  ({f['status']}{', untracked' if f.get('untracked') else ''}, "
            f"+{f['added_lines']}/-{f['deleted_lines']})  ruleset={f['ruleset']}  module={f['module']}"
            f"{'  TEST' if f.get('is_test') else ''}")
    out = [head]
    if f.get("old_path"):
        out.append(f"renamed from: {f['old_path']}")
    meta = []
    if f.get("symbols"):
        meta.append("symbols: " + ", ".join(f["symbols"]))
    if f.get("fan_in"):
        meta.append(f"fan-in: {f['fan_in']} files (e.g. {', '.join(f['fan_in_files'][:5])})")
    if f.get("linked_tests"):
        meta.append(f"linked tests: {', '.join(f['linked_tests'])} (changed: {'yes' if f.get('test_changed') else 'NO'})")
    elif not f.get("is_test") and f["tier"] in ("deep", "light"):
        meta.append("linked tests: none found")
    if f.get("largest_added_block"):
        meta.append(f"largest added block: {f['largest_added_block']} lines")
    if f.get("tier_reasons"):
        meta.append("tier reasons: " + "; ".join(f["tier_reasons"]))
    out += ["  " + m for m in meta]
    if f.get("findings"):
        out.append("  deterministic findings (do NOT repeat; adjust via 'adjust' if wrong):")
        for x in f["findings"]:
            ev = x["evidence"][0]["snippet"] if x.get("evidence") else ""
            out.append(f"    - {x['rule_id']} [{x['points']}{' CRITICAL' if x['critical'] else ''}] "
                       f"{x['dimension']}: {x['title']}  {ev}")
    if f["tier"] == "excluded":
        out.append(f"  excluded: {f.get('excluded_reason')}")
        return "\n".join(out)
    text = (rdir / f["diff_file"]).read_text(encoding="utf-8")
    lines = text.splitlines()
    limit = None if full else LIMITS.get(f["tier"], 200)
    if limit is not None and len(lines) > limit:
        out.append(f"--- diff (first {limit} of {len(lines)} lines; full: {rdir / f['diff_file']}) ---")
        lines = lines[:limit]
    else:
        out.append("--- diff ---")
    out += lines
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report_dir", nargs="?", default="latest")
    ap.add_argument("--batch", type=int)
    ap.add_argument("--file", action="append", default=[])
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--list-batches", action="store_true")
    ap.add_argument("--roles", action="store_true")
    args = ap.parse_args()

    root = repo_root()
    rdir = resolve_report_dir(args.report_dir, root)
    a = read_json(rdir / "analysis.json")
    by_path = {f["path"]: f for f in a["files"]}

    if args.roles:
        import json
        sem = {}
        for bf in sorted((rdir / "semantic").glob("batch-*.json")):
            try:
                for item in json.loads(bf.read_text(encoding="utf-8")).get("files") or []:
                    sem[item.get("path")] = item
            except ValueError:
                print(f"# {bf.name}: invalid JSON")
        for f in sorted(a["files"], key=lambda f: (f.get("module") or "", f["path"])):
            if f["tier"] in ("excluded", "mechanical"):
                continue
            item = sem.get(f["path"], {})
            inter = item.get("interactions") or {}
            pts = max([x.get("points", 0) for x in item.get("findings") or []] + [x["points"] for x in f["findings"]] + [0])
            print(f"{f['path']}  [{f['tier']}, max {pts}{', TEST' if f.get('is_test') else ''}]")
            print(f"    role: {item.get('role') or '(missing)'}")
            for k in ("called_by", "calls", "contracts"):
                if inter.get(k):
                    print(f"    {k}: {', '.join(inter[k][:8])}")
        return

    if args.list_batches:
        for b in a.get("batches", []):
            done = (rdir / "semantic" / f"batch-{b['id']}.json").is_file()
            print(f"batch {b['id']:>3} [{b['tier']}] model={b.get('model', 'inherit')} {len(b['files'])} files "
                  f"{'DONE' if done else ''}")
        return

    if args.batch is not None:
        b = next((b for b in a.get("batches", []) if b["id"] == args.batch), None)
        if not b:
            die(f"batch {args.batch} not found")
        rulesets = sorted({by_path[p]["ruleset"] for p in b["files"]})
        anchors = [str(RULESETS_DIR / "_base" / "anchors.md")] + \
                  [str(RULESETS_DIR / r / "anchors.md") for r in rulesets if r != "_base"]
        src = a["change"]["sources"]
        print(f"# Batch {b['id']} ({b['tier']}), {len(b['files'])} files")
        print(f"# write: {rdir / 'semantic' / ('batch-%d.json' % b['id'])}")
        print(f"# rubric: {', '.join(anchors)}")
        print(f"# conventions: {', '.join(src['conventions']) or 'none documented'}")
        print(f"# spec: {', '.join(src['spec']) or 'none'}   plan: {', '.join(src['plan']) or 'none'}")
        print(f"# repo root: {root}")
        print()
        paths = b["files"]
    else:
        paths = args.file
        if not paths:
            die("use --batch N, --file PATH or --list-batches")
    for p in paths:
        f = by_path.get(p)
        if not f:
            print(f"=== {p}: not in this change")
            continue
        print(file_block(rdir, f, args.full))
        print()


if __name__ == "__main__":
    main()
