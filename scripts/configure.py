#!/usr/bin/env python3
"""Plugin-wide settings for all projects (stored in ~/.config/code-review-assistant/config.yaml).

Usage:
  configure.py --show
  configure.py --report-dir PATH      e.g. "~/Obsidian/Code Review/{project}" or "~/code-review-kb/{project}"

`{project}` is replaced by the repository folder name. Precedence: project rules.yaml >
CODE_REVIEW_KB environment variable > this file > plugin default (~/code-review-kb/{project}).
"""
from __future__ import annotations

import argparse
import os
import re

import _yaml
from _common import RULESETS_DIR, user_config_path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report-dir")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()
    path = user_config_path()
    if args.report_dir:
        value = args.report_dir.strip()
        if "{project}" not in value:
            print("note: no {project} placeholder — all projects will share one folder")
        text = path.read_text(encoding="utf-8") if path.is_file() else \
            "# Code Review Assistant — settings for all projects (project rules.yaml overrides them)\n"
        line = f"report_dir: '{value}'"
        if re.search(r"(?m)^report_dir:.*$", text):
            text = re.sub(r"(?m)^report_dir:.*$", line, text)
        else:
            text = text.rstrip("\n") + "\n" + line + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        os.makedirs(os.path.expanduser(value.split("{project}")[0]) or ".", exist_ok=True)
        print(f"wrote {path}")
    default = _yaml.load(RULESETS_DIR / "_base" / "defaults.yaml").get("report_dir")
    user = (_yaml.load(path) or {}).get("report_dir") if path.is_file() else None
    env = os.environ.get("CODE_REVIEW_KB")
    print(f"user config:  {path} {'(exists)' if path.is_file() else '(not created)'}")
    print(f"report_dir:   {env or user or default}"
          f"  [from {'CODE_REVIEW_KB' if env else 'user config' if user else 'plugin default'}]")
    print("a project's docs/code-review/rules.yaml can still override it")


if __name__ == "__main__":
    main()
