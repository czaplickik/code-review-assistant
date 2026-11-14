#!/usr/bin/env python3
"""Resolve (or create) the feature folder for the current repository and print a new run directory.

Usage: feature_dir.py [--title TITLE] [--jira ID] [--spec PATH ...] [--kind plan|explain]

Used by skills that do not collect a change (change-plan-summary) or write extra outputs
(change-explanation without an impact report). Prints the run directory to write JSON into.
"""
from __future__ import annotations

import argparse
import datetime as dt

from _common import git, git_ok, load_config, report_base, repo_root
from _feature import feature_info, find_or_create


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--title")
    ap.add_argument("--jira")
    ap.add_argument("--spec", action="append", default=[])
    ap.add_argument("--kind", default="plan")
    args = ap.parse_args()
    root = repo_root()
    cfg = load_config(root)
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=root).strip() \
        if git_ok("rev-parse", "--verify", "-q", "HEAD", cwd=root) else None
    changed = [p for p in git("status", "--porcelain", "--untracked-files=all", cwd=root).splitlines()]
    changed = [l[3:] for l in changed if not l[3:].endswith(".md")]
    info = feature_info(root, branch, title=args.title, jira=args.jira, spec_paths=args.spec, changed=changed)
    fdir = find_or_create(report_base(root, cfg), info, root)
    run = fdir / "runs" / f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{args.kind}"
    run.mkdir(parents=True, exist_ok=True)
    print(run)
    print(f"feature: {fdir.name} (title from {info['title_source']}{', no ticket id' if not info['jira'] else ''})")


if __name__ == "__main__":
    main()
