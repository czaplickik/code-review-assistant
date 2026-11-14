"""Shared helpers: paths, git, config, rulesets, globbing, diff parsing."""
from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import _yaml

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
RULESETS_DIR = PLUGIN_ROOT / "rulesets"
PROJECT_CONFIG = "docs/code-review/rules.yaml"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

DIMENSIONS = [
    "core_logic", "error_handling", "concurrency",
    "security", "data_integrity",
    "contracts", "integration", "config_infra",
    "architecture", "performance", "conventions", "tests",
]
MODES = ["build+tests+static", "ai-review-only", "ai+human-critical-paths", "human-only"]


def die(msg, code=2):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------- git

def git(*args, cwd=None, ok=(0,), raw=False):
    """Runs git; exit codes outside `ok` abort (diff --no-index / grep use ok=(0, 1))."""
    cmd = ["git", "-c", "core.quotepath=false", *args]
    res = subprocess.run(cmd, cwd=cwd, capture_output=True)
    if res.returncode not in ok:
        die(f"{' '.join(cmd)} failed: {res.stderr.decode(errors='replace').strip()}")
    return res.stdout if raw else res.stdout.decode("utf-8", errors="replace")


def git_ok(*args, cwd=None):
    res = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    return res.returncode == 0


def repo_root(start="."):
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start,
                         capture_output=True, text=True)
    if out.returncode != 0:
        die("not inside a git repository")
    return Path(out.stdout.strip())


# ---------------------------------------------------------------- json io

def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def report_base(root, cfg=None):
    """Knowledge-base folder for this repository: report_dir with `~` and `{project}` expanded;
    relative paths are relative to the repository root."""
    cfg = cfg or load_config(root)
    raw = str(cfg.get("report_dir") or "~/code-review-kb/{project}").replace("{project}", Path(root).name)
    p = Path(os.path.expanduser(raw))
    return p if p.is_absolute() else Path(root) / p


def resolve_report_dir(arg, root):
    """Accepts a run directory path or 'latest' (newest run of this repository)."""
    if arg and arg != "latest":
        p = Path(arg)
        return p if p.is_absolute() else (Path.cwd() / p).resolve()
    base = report_base(root)
    if not base.is_dir():
        die(f"no reports in {base}")
    runs = [p.parent for p in base.glob("*/runs/*/analysis.json")] + \
           [p.parent for p in base.glob("*/analysis.json")]
    mine = []
    for d in runs:
        try:
            if read_json(d / "analysis.json").get("repo_root") == str(root):
                mine.append(d)
        except ValueError:
            continue
    if not mine:
        die(f"no reports for {root} in {base}")
    return max(mine, key=lambda d: d.name)


# ---------------------------------------------------------------- glob

_glob_cache = {}


def glob_re(pattern):
    rx = _glob_cache.get(pattern)
    if rx is None:
        i, out = 0, []
        while i < len(pattern):
            c = pattern[i]
            if pattern.startswith("**/", i):
                out.append("(?:.*/)?")
                i += 3
            elif pattern.startswith("**", i):
                out.append(".*")
                i += 2
            elif c == "*":
                out.append("[^/]*")
                i += 1
            elif c == "?":
                out.append("[^/]")
                i += 1
            else:
                out.append(re.escape(c))
                i += 1
        rx = re.compile("^" + "".join(out) + "$")
        _glob_cache[pattern] = rx
    return rx


def glob_match(path, patterns):
    return any(glob_re(p).match(path) for p in patterns or [])


# ---------------------------------------------------------------- config

def deep_merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def user_config_path():
    """Plugin-wide user settings (all projects): $XDG_CONFIG_HOME or ~/.config."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "code-review-assistant" / "config.yaml"


def load_config(root, overrides=None):
    """Plugin defaults → user config (~/.config/code-review-assistant/config.yaml)
    → CODE_REVIEW_KB environment variable (report_dir) → project docs/code-review/rules.yaml."""
    cfg = _yaml.load(RULESETS_DIR / "_base" / "defaults.yaml")
    user = user_config_path()
    cfg["_user_config"] = None
    if user.is_file():
        cfg = deep_merge(cfg, _yaml.load(user) or {})
        cfg["_user_config"] = str(user)
    if os.environ.get("CODE_REVIEW_KB"):
        cfg["report_dir"] = os.environ["CODE_REVIEW_KB"]
    proj = Path(root) / PROJECT_CONFIG
    if proj.is_file():
        cfg = deep_merge(cfg, _yaml.load(proj))
        cfg["_project_config"] = PROJECT_CONFIG
    else:
        cfg["_project_config"] = None
    if overrides:
        cfg = deep_merge(cfg, overrides)
    return cfg


# ---------------------------------------------------------------- rulesets

class Ruleset:
    def __init__(self, rid, detect, rules, anchors_path):
        self.id = rid
        self.detect = detect
        self.rules = rules
        self.anchors_path = anchors_path
        d = detect
        self.file_patterns = d.get("file_patterns", [])
        self.project_markers = d.get("project_markers", [])
        self.test_patterns = d.get("test_patterns", [])
        self.migration_patterns = d.get("migration_patterns", [])
        self.migration_ignore = d.get("migration_ignore", [])
        self.generated_companions = d.get("generated_companions", [])
        self.exclude = d.get("exclude", [])
        self.source_patterns = d.get("source_patterns", self.file_patterns)
        self.symbol_res = [re.compile(p, re.M) for p in d.get("symbol_patterns", [])]
        self.import_res = [re.compile(p) for p in d.get("import_patterns", [])]
        self.comment_res = [re.compile(p) for p in d.get("comment_patterns", [])]
        self.assert_res = [re.compile(p) for p in d.get("assertion_patterns", [])]
        self.skip_res = [re.compile(p) for p in d.get("skip_patterns", [])]
        self.module_res = [re.compile(p) for p in d.get("module_patterns", [])]
        self.test_name_map = [(re.compile(m["from"]), m["to"]) for m in d.get("test_name_map", [])]
        self.grep_globs = d.get("reference_globs", self.source_patterns)

    def is_test(self, path):
        return glob_match(path, self.test_patterns)

    def module_of(self, path):
        for rx in self.module_res:
            m = rx.search(path)
            if m:
                return "/".join(g for g in m.groups() if g)
        return None


def load_rulesets(cfg):
    """Returns (base, [stack rulesets]) with project overrides applied."""
    overrides = cfg.get("rule_overrides") or {}
    extra = cfg.get("extra_rules") or []
    loaded = {}
    for d in sorted(RULESETS_DIR.iterdir()):
        if not d.is_dir() or not (d / "detect.yaml").is_file():
            continue
        detect = _yaml.load(d / "detect.yaml")
        sig = _yaml.load(d / "signals.yaml") if (d / "signals.yaml").is_file() else {}
        rules = []
        for r in sig.get("rules", []) or []:
            ov = overrides.get(r["id"])
            if ov:
                if ov.get("disabled"):
                    continue
                r = {**r, **ov}
            rules.append(r)
        anchors = d / "anchors.md"
        loaded[d.name] = Ruleset(d.name, detect, rules, anchors if anchors.is_file() else None)
    base = loaded.pop("_base", None)
    if base is None:
        die("rulesets/_base missing")
    for r in extra:
        target = loaded.get(r.get("ruleset", "_base"), base)
        target.rules.append(r)
    enabled = cfg.get("rulesets")
    stacks = [rs for rid, rs in loaded.items() if not enabled or rid in enabled]
    return base, stacks


def ruleset_for(path, stacks):
    best, best_len = None, -1
    for rs in stacks:
        for p in rs.file_patterns:
            if glob_re(p).match(path) and len(p) > best_len:
                best, best_len = rs, len(p)
    return best


# ---------------------------------------------------------------- diff parsing

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_diff(text):
    """Returns list of hunks: {old_start, new_start, lines:[(tag, old_no, new_no, text)]}."""
    hunks, cur = [], None
    old_no = new_no = 0
    for line in text.splitlines():
        m = _HUNK.match(line)
        if m:
            old_no, new_no = int(m.group(1)), int(m.group(3))
            cur = {"old_start": old_no, "new_start": new_no, "lines": []}
            hunks.append(cur)
            continue
        if cur is None or line.startswith("\\ No newline"):
            continue
        tag = line[:1]
        body = line[1:]
        if tag == "+":
            cur["lines"].append(("+", None, new_no, body))
            new_no += 1
        elif tag == "-":
            cur["lines"].append(("-", old_no, None, body))
            old_no += 1
        elif tag == " ":
            cur["lines"].append((" ", old_no, new_no, body))
            old_no += 1
            new_no += 1
    return hunks


def changed_lines(hunks):
    for h in hunks:
        for tag, o, n, body in h["lines"]:
            if tag in "+-":
                yield tag, o, n, body


def largest_added_block(hunks):
    best = run = 0
    for h in hunks:
        run = 0
        for tag, _, _, body in h["lines"]:
            if tag == "+":
                run += 1
                best = max(best, run)
            elif tag == " ":
                run = 0
    return best
