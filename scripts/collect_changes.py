#!/usr/bin/env python3
"""Stage 1, step 1: collect the change boundary into a new report directory.

Usage: collect_changes.py [--base BRANCH] [--spec PATH ...] [--plan PATH ...]

Default boundary: uncommitted changes vs HEAD (staged + unstaged) plus untracked files.
With --base (or base_branch in rules.yaml): merge-base(BRANCH, HEAD) -> working tree.
Prints the report directory.
"""
from __future__ import annotations

import argparse
import sys
import datetime as dt
import difflib
import hashlib
from pathlib import Path

from _common import (EMPTY_TREE, die, git, git_ok, glob_match, load_config, parse_diff,
                     report_base, repo_root, write_json)
from _feature import feature_info, find_or_create, select_doc

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


def stacked_parent(root, base_ref, branch, limit=300):
    """Nearest other branch whose tip is in HEAD's history but not in base_ref (branch cut from a
    feature branch). Returns {"ref", "commits"} or None."""
    refs = [r for r in git("for-each-ref", "--format=%(refname:short)", "refs/remotes", "refs/heads",
                           cwd=root).split() if not r.endswith("/HEAD")][:limit]
    own = {branch, f"origin/{branch}"} if branch else set()
    best = None
    for r in refs:
        if r in own or r == base_ref or r.endswith("/" + str(base_ref)):
            continue
        if not git_ok("merge-base", "--is-ancestor", r, "HEAD", cwd=root):
            continue
        if git_ok("merge-base", "--is-ancestor", r, base_ref, cwd=root):
            continue
        ahead = int(git("rev-list", "--count", f"{base_ref}..{r}", cwd=root).strip() or 0)
        between = int(git("rev-list", "--count", f"{r}..HEAD", cwd=root).strip() or 0)
        if ahead == 0:
            continue
        if best is None or between < best["between"] or (between == best["between"] and r.startswith("origin/")):
            best = {"ref": r, "commits": ahead, "between": between}
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", help="base branch (merge-base with HEAD)")
    ap.add_argument("--spec", action="append", default=[], help="explicit spec document")
    ap.add_argument("--plan", action="append", default=[], help="explicit plan document")
    ap.add_argument("--title", help="feature title (default: branch, spec title or changed code)")
    ap.add_argument("--jira", help="ticket id (default: from the branch name)")
    args = ap.parse_args()

    root = repo_root()
    cfg = load_config(root)
    base_dir = report_base(root, cfg)
    try:
        report_root = str(base_dir.resolve().relative_to(root.resolve()))
    except ValueError:
        report_root = None  # knowledge base outside the repository

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
    stacked_on = stacked_parent(root, base_ref, branch) if boundary == "base" else None
    if stacked_on:
        print(f"WARNING: stacked branch — HEAD contains {stacked_on['commits']} commit(s) of {stacked_on['ref']} "
              f"that are not in {base_ref}; they are part of this boundary. To review only this branch run "
              f"again with --base {stacked_on['ref']}", file=sys.stderr)

    def ignored(path):
        return bool(report_root) and path.startswith(report_root.rstrip("/") + "/")

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

    files, texts, tot_add, tot_del = [], [], 0, 0
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
        texts.append((diff_rel, text))
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

    change_hash = hashlib.sha1("".join(f["path"] + t for f, (_, t) in zip(files, texts)).encode()).hexdigest()
    changed = {f["path"] for f in files if f["status"] != "deleted"}
    src = cfg.get("sources") or {}

    def discover(explicit, dirs):
        if explicit:
            return [Path(p).as_posix() for p in explicit]
        return sorted(p for p in changed if p.endswith(".md")
                      and any(p.startswith(d.strip("/") + "/") for d in dirs or []))

    spec = discover(args.spec, src.get("spec_dirs"))
    plan = discover(args.plan, src.get("plan_dirs"))
    discovered_from = None
    if not spec and not plan and not args.spec and not args.plan:
        # specs and plans are usually committed before the implementation starts:
        # fall back to the newest document in each configured directory
        repo_files = split_z(git("ls-files", "-z", cwd=root))
        reasons = []
        for key in ("spec", "plan"):
            doc, why = select_doc(root, src.get(f"{key}_dirs"), branch, changed, repo_files)
            if doc:
                (spec if key == "spec" else plan).append(doc)
                reasons.append(f"{key}: {why}")
        if spec or plan:
            discovered_from = "committed document matched to this change (" + "; ".join(reasons) + ")"
    all_files = split_z(git("ls-files", "-z", cwd=root)) + [f["path"] for f in files if f["untracked"]]
    conventions = sorted({p for p in all_files if glob_match(p, src.get("convention_files"))}
                         - set(spec) - set(plan))
    missing = [k for k, v in (("spec", spec), ("plan", plan), ("conventions", conventions)) if not v]

    info = feature_info(root, branch, title=args.title, jira=args.jira, spec_paths=spec,
                        changed=[f["path"] for f in files if f["status"] != "deleted" and not f["path"].endswith(".md")],
                        new={f["path"] for f in files if f["status"] == "added"})
    fdir = find_or_create(base_dir, info, root)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    short = hashlib.sha1((base_commit + stamp).encode()).hexdigest()[:6]
    report_dir = fdir / "runs" / f"{stamp}-{short}"
    (report_dir / "diffs").mkdir(parents=True, exist_ok=False)
    (report_dir / "semantic").mkdir()
    for rel, text in texts:
        (report_dir / rel).write_text(text, encoding="utf-8")

    analysis = {
        "schema_version": 1,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "repo_root": str(root),
        "report_dir": str(report_dir),
        "feature": {**info, "folder": str(fdir)},
        "change": {
            "boundary": boundary, "base_ref": base_ref, "base_commit": base_commit[:12],
            "branch": branch, "change_hash": change_hash,
            "stacked_on": stacked_on["ref"] if stacked_on else None,
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
    print(f"feature: {fdir.name} (title from {info['title_source']}"
          f"{', no ticket id' if not info['jira'] else ''})")
    print(f"{len(files)} files (+{tot_add} / -{tot_del}), untracked {analysis['change']['stats']['untracked']}, "
          f"boundary {boundary} vs {base_ref}; spec {len(spec)}, plan {len(plan)}, conventions {len(conventions)}")


if __name__ == "__main__":
    main()
