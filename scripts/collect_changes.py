#!/usr/bin/env python3
"""Stage 1, step 1: collect the change boundary into a new report directory.

Usage: collect_changes.py [--base BRANCH] [--spec PATH ...] [--plan PATH ...]

Default boundary: uncommitted changes vs HEAD (staged + unstaged) plus untracked files.
With --base (or base_branch in rules.yaml): merge-base(BRANCH, HEAD) -> working tree.
Prints the report directory.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
from pathlib import Path

from _common import (EMPTY_TREE, die, git, git_ok, glob_match, load_config, parse_diff,
                     repo_root, write_json)

LANG_BY_EXT = {
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".groovy": "groovy",
    ".cs": "csharp", ".csproj": "msbuild", ".sln": "msbuild", ".props": "msbuild",
    ".fs": "fsharp", ".py": "python", ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".go": "go", ".rb": "ruby", ".php": "php",
    ".sql": "sql", ".xml": "xml", ".yml": "yaml", ".yaml": "yaml", ".json": "json",
    ".properties": "properties", ".md": "markdown", ".sh": "shell", ".ps1": "powershell",
    ".gradle": "groovy", ".tf": "terraform", ".html": "html", ".css": "css",
}


def language(path):
    name = Path(path).name
    if name == "Dockerfile" or name.startswith("Dockerfile."):
        return "docker"
    return LANG_BY_EXT.get(Path(path).suffix.lower(), "other")


def split_z(out):
    return [p for p in out.split("\0") if p]


def pair_moves(entries, root, base_commit, min_ratio=0.7):
    """git cannot detect renames into untracked files; pair deleted + untracked files with the
    same name and similar content so moved classes show as renames with a small diff."""
    deleted = {}
    for e in entries:
        if e["status"] == "deleted":
            deleted.setdefault(Path(e["path"]).name, []).append(e)
    if not deleted:
        return
    drop = []
    for e in entries:
        if not e["untracked"] or Path(e["path"]).name not in deleted:
            continue
        try:
            new = (root / e["path"]).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        best, best_ratio, best_old = None, 0.0, None
        for d in deleted[Path(e["path"]).name]:
            if d in drop:
                continue
            old = git("show", f"{base_commit}:{d['path']}", cwd=root, ok=(0, 128))
            ratio = difflib.SequenceMatcher(None, old, new, autojunk=False).ratio()
            if ratio > best_ratio:
                best, best_ratio, best_old = d, ratio, old
        if best is None or best_ratio < min_ratio:
            continue
        drop.append(best)
        e.update(status="renamed", old_path=best["path"], similarity=int(best_ratio * 100))
        body = "".join(difflib.unified_diff(best_old.splitlines(True), new.splitlines(True),
                                            f"a/{best['path']}", f"b/{e['path']}", n=3))
        e["move_diff"] = f"diff --git a/{best['path']} b/{e['path']}\nsimilarity index {e['similarity']}%\n" \
                         f"rename from {best['path']}\nrename to {e['path']}\n{body}"
    for d in drop:
        entries.remove(d)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", help="base branch (merge-base with HEAD)")
    ap.add_argument("--spec", action="append", default=[], help="explicit spec document")
    ap.add_argument("--plan", action="append", default=[], help="explicit plan document")
    args = ap.parse_args()

    root = repo_root()
    cfg = load_config(root)
    report_root = cfg["report_dir"].strip("/")

    has_head = git_ok("rev-parse", "--verify", "-q", "HEAD", cwd=root)
    base_ref = args.base or cfg.get("base_branch")
    if base_ref:
        if not git_ok("rev-parse", "--verify", "-q", base_ref, cwd=root):
            die(f"base branch '{base_ref}' not found")
        base_commit = git("merge-base", base_ref, "HEAD", cwd=root).strip()
        boundary = "base"
    else:
        base_ref = "HEAD" if has_head else "(empty)"
        base_commit = git("rev-parse", "HEAD", cwd=root).strip() if has_head else EMPTY_TREE
        boundary = "uncommitted"
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=root).strip() if has_head else None

    def ignored(path):
        return path.startswith(report_root + "/")

    entries = []
    toks = split_z(git("diff", base_commit, "-M", "--name-status", "-z", cwd=root))
    i = 0
    while i < len(toks):
        st = toks[i]
        if st[0] in "RC":
            old, new = toks[i + 1], toks[i + 2]
            i += 3
            entries.append({"status": "renamed" if st[0] == "R" else "added", "path": new,
                            "old_path": old if st[0] == "R" else None,
                            "similarity": int(st[1:] or 0), "untracked": False})
        else:
            path = toks[i + 1]
            i += 2
            status = {"A": "added", "M": "modified", "D": "deleted", "T": "modified"}.get(st[0], "modified")
            entries.append({"status": status, "path": path, "old_path": None,
                            "similarity": None, "untracked": False})
    for path in split_z(git("ls-files", "--others", "--exclude-standard", "-z", cwd=root)):
        entries.append({"status": "added", "path": path, "old_path": None,
                        "similarity": None, "untracked": True})
    entries = [e for e in entries if not ignored(e["path"])]
    pair_moves(entries, root, base_commit)
    entries.sort(key=lambda e: e["path"])
    if not entries:
        die("no changes found in the boundary", code=3)

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    short = hashlib.sha1((base_commit + stamp).encode()).hexdigest()[:6]
    report_dir = root / report_root / f"{stamp}-{short}"
    (report_dir / "diffs").mkdir(parents=True, exist_ok=False)
    (report_dir / "semantic").mkdir()

    files, tot_add, tot_del = [], 0, 0
    for n, e in enumerate(entries, 1):
        if e.get("move_diff") is not None:
            text = e.pop("move_diff")
        elif e["untracked"]:
            text = git("diff", "--no-index", "--no-color", "-U3", "--", "/dev/null", e["path"],
                       cwd=root, ok=(0, 1))
        else:
            paths = [p for p in (e["old_path"], e["path"]) if p]
            text = git("diff", base_commit, "-M", "--no-color", "-U3", "--", *paths, cwd=root)
        binary = "\nBinary files " in text or text.startswith("Binary files ")
        diff_rel = f"diffs/{n:04d}.diff"
        (report_dir / diff_rel).write_text(text, encoding="utf-8")
        hunks = parse_diff(text)
        add = sum(1 for h in hunks for l in h["lines"] if l[0] == "+")
        dele = sum(1 for h in hunks for l in h["lines"] if l[0] == "-")
        tot_add += add
        tot_del += dele
        files.append({
            "path": e["path"], "old_path": e["old_path"], "status": e["status"],
            "untracked": e["untracked"], "similarity": e["similarity"], "binary": binary,
            "language": language(e["path"]), "added_lines": add, "deleted_lines": dele,
            "diff_file": diff_rel,
        })

    change_hash = hashlib.sha1("".join(
        f["path"] + (report_dir / f["diff_file"]).read_text(encoding="utf-8") for f in files).encode()).hexdigest()
    changed = {f["path"] for f in files if f["status"] != "deleted"}
    src = cfg.get("sources") or {}

    def discover(explicit, dirs):
        if explicit:
            return [str(Path(p)) for p in explicit]
        return sorted(p for p in changed if p.endswith(".md")
                      and any(p.startswith(d.strip("/") + "/") for d in dirs or []))

    spec = discover(args.spec, src.get("spec_dirs"))
    plan = discover(args.plan, src.get("plan_dirs"))
    discovered_from = None
    if not spec and not plan and not args.spec and not args.plan:
        # specs and plans are usually committed before the implementation starts:
        # fall back to the newest document in each configured directory
        def newest(dirs):
            best, best_t = None, -1
            for d in dirs or []:
                for p in sorted((root / d).glob("*.md")) if (root / d).is_dir() else []:
                    rel = str(p.relative_to(root))
                    t = git("log", "-1", "--format=%ct", "--", rel, cwd=root).strip()
                    t = int(t) if t.isdigit() else int(p.stat().st_mtime)
                    if t > best_t:
                        best, best_t = rel, t
            return [best] if best else []
        spec, plan = newest(src.get("spec_dirs")), newest(src.get("plan_dirs"))
        if spec or plan:
            discovered_from = "newest document in the spec/plan directories (not part of the change)"
    all_files = split_z(git("ls-files", "-z", cwd=root)) + [f["path"] for f in files if f["untracked"]]
    conventions = sorted({p for p in all_files if glob_match(p, src.get("convention_files"))}
                         - set(spec) - set(plan))
    missing = [k for k, v in (("spec", spec), ("plan", plan), ("conventions", conventions)) if not v]

    analysis = {
        "schema_version": 1,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "repo_root": str(root),
        "report_dir": str(report_dir.relative_to(root)),
        "change": {
            "boundary": boundary, "base_ref": base_ref, "base_commit": base_commit[:12],
            "branch": branch, "change_hash": change_hash,
            "stats": {"files": len(files), "added_lines": tot_add, "deleted_lines": tot_del,
                      "untracked": sum(1 for f in files if f["untracked"])},
            "rulesets": [],
            "sources": {"spec": spec, "plan": plan, "conventions": conventions, "missing": missing,
                        "discovered_from": discovered_from},
        },
        "files": files,
        "groups": [], "flows": [], "plan_drift": None, "verdict": None,
        "ai_review_focus": [], "limitations": [],
        "config": {"project_config": cfg.get("_project_config")},
    }
    write_json(report_dir / "analysis.json", analysis)
    print(report_dir)
    print(f"{len(files)} files (+{tot_add} / -{tot_del}), untracked {analysis['change']['stats']['untracked']}, "
          f"boundary {boundary} vs {base_ref}; spec {len(spec)}, plan {len(plan)}, conventions {len(conventions)}")


if __name__ == "__main__":
    main()
