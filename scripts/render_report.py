#!/usr/bin/env python3
"""Render code-review-assistant JSON models into self-contained HTML reports.

Usage:
  render_report.py impact <report_dir|latest>                   -> <report_dir>/impact-report.html
  render_report.py plan <json_path> [--out <html_path>]         -> plan summary (default: same name .html)
  render_report.py explanation <json_path> [--out <html_path>]  -> change explanation
  render_report.py review <review.json|review_dir> [--out <html_path>] -> review page (review.json -> review.html)

The JSON contract is documented in schemas/data-model.md. Output HTML inlines the
shared CSS/JS from templates/shared/ and embeds the data as
<script type="application/json">, so the file works offline from file://.
Python 3 standard library only.
"""

import argparse
import html
import json
import os
import re
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(PLUGIN_ROOT, "templates")

DIFF_MAX_LINES = 400          # per embedded diff
DIFF_BUDGET_BYTES = 3_000_000  # total embedded diff text

PLACEHOLDER = re.compile(r"@@([A-Z_]+)@@")


class RenderError(Exception):
    pass


# --------------------------------------------------------------------------- io

def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise RenderError("file not found: %s" % path)
    except json.JSONDecodeError as exc:
        raise RenderError("invalid JSON in %s: %s" % (path, exc))


def write_text(path, text):
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def embed_json(value):
    """JSON safe to place inside <script type="application/json">.

    Escaping every '<' covers '</script', '<!--' and '<script'; U+2028/2029 are
    escaped for good measure. JSON.parse turns them back into the original text.
    """
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (text.replace("<", "\\u003c")
                .replace(" ", "\\u2028")
                .replace(" ", "\\u2029"))


def load_asset(rel, closing_tag):
    path = os.path.join(TEMPLATES, rel)
    try:
        text = read_text(path)
    except FileNotFoundError:
        raise RenderError("template asset missing: %s" % path)
    if closing_tag in text.lower():
        raise RenderError("%s contains '%s' and cannot be inlined" % (rel, closing_tag))
    return text


def fill_template(name, values):
    path = os.path.join(TEMPLATES, name)
    try:
        template = read_text(path)
    except FileNotFoundError:
        raise RenderError("template missing: %s" % path)

    def sub(match):
        key = match.group(1)
        if key not in values:
            raise RenderError("template %s uses unknown placeholder @@%s@@" % (name, key))
        return values[key]

    # single pass: substituted content is never re-scanned for placeholders
    return PLACEHOLDER.sub(sub, template)


def render(template_name, title, data, extra=None):
    values = {
        "TITLE": html.escape(title or "Code review report"),
        "BASE_CSS": load_asset(os.path.join("shared", "base.css"), "</style"),
        "COMPONENTS_JS": load_asset(os.path.join("shared", "components.js"), "</script"),
        "DATA_JSON": embed_json(data),
    }
    if extra:
        values.update(extra)
    return fill_template(template_name, values)


# --------------------------------------------------------------------------- impact

def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _rank_key(f):
    findings = f.get("findings") if isinstance(f.get("findings"), list) else []
    critical = bool(f.get("critical")) or any(isinstance(x, dict) and x.get("critical") for x in findings)
    score = f.get("score")
    if score is None:
        score = sum(_num(x.get("points")) for x in findings if isinstance(x, dict))
    size = _num(f.get("added_lines")) + _num(f.get("deleted_lines"))
    return (0 if critical else 1, -_num(score), -size, str(f.get("path") or ""))


def collect_diffs(report_dir, files):
    """Embed diffs for files with findings or tier 'deep', most important first."""
    embedded, skipped_budget, missing = {}, [], []
    used = 0
    root = os.path.realpath(report_dir)
    candidates = []
    for f in files:
        if not isinstance(f, dict) or not f.get("path") or not f.get("diff_file"):
            continue
        findings = f.get("findings")
        if f.get("tier") == "deep" or (isinstance(findings, list) and findings):
            candidates.append(f)
    candidates.sort(key=_rank_key)

    for f in candidates:
        diff_path = os.path.realpath(os.path.join(report_dir, str(f["diff_file"])))
        if not (diff_path == root or diff_path.startswith(root + os.sep)):
            missing.append(f["path"])  # refuses paths outside the report directory
            continue
        try:
            with open(diff_path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            missing.append(f["path"])
            continue
        lines = text.splitlines()
        shown = lines[:DIFF_MAX_LINES]
        chunk = "\n".join(shown) + ("\n" if shown else "")
        size = len(chunk.encode("utf-8"))
        if used + size > DIFF_BUDGET_BYTES:
            skipped_budget.append(f["path"])
            continue
        used += size
        embedded[f["path"]] = {
            "text": chunk,
            "lines_total": len(lines),
            "lines_shown": len(shown),
            "truncated": len(lines) > len(shown),
        }
    meta = {
        "embedded": len(embedded),
        "bytes": used,
        "budget_bytes": DIFF_BUDGET_BYTES,
        "cap_lines": DIFF_MAX_LINES,
        "budget_exhausted": bool(skipped_budget),
        "skipped_budget": skipped_budget,
        "missing": missing,
    }
    return {"files": embedded, "meta": meta}


def resolve_latest(arg):
    """'latest' = newest report dir of the git repo in the cwd (via _common.resolve_report_dir)."""
    if arg != "latest":
        return arg
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from _common import repo_root, resolve_report_dir
    except ImportError as exc:
        raise RenderError("cannot resolve 'latest' (scripts/_common.py unavailable: %s)" % exc)
    return str(resolve_report_dir("latest", repo_root()))


def render_impact(report_dir, out_path=None):
    report_dir = resolve_latest(report_dir)
    if not os.path.isdir(report_dir):
        raise RenderError("report directory not found: %s" % report_dir)
    analysis = load_json(os.path.join(report_dir, "analysis.json"))
    if not isinstance(analysis, dict):
        raise RenderError("analysis.json must contain a JSON object")
    files = analysis.get("files") if isinstance(analysis.get("files"), list) else []
    diffs = collect_diffs(report_dir, files)
    change = analysis.get("change") if isinstance(analysis.get("change"), dict) else {}
    verdict = analysis.get("verdict") if isinstance(analysis.get("verdict"), dict) else {}
    bits = ["Impact report"]
    if verdict.get("mode"):
        bits.append(str(verdict["mode"]))
    if change.get("branch"):
        bits.append(str(change["branch"]))
    title = " · ".join(bits)
    page = render("impact-report.html", title, analysis, {"DIFFS_JSON": embed_json(diffs)})
    out = out_path or os.path.join(report_dir, "impact-report.html")
    write_text(out, page)
    return out


# --------------------------------------------------------------------------- plan / explanation

def default_out(json_path, out_path):
    if out_path:
        return out_path
    base, _ = os.path.splitext(json_path)
    return base + ".html"


def render_plan(json_path, out_path=None):
    data = load_json(json_path)
    if not isinstance(data, dict):
        raise RenderError("plan summary must be a JSON object")
    title = "Plan summary · %s" % data["title"] if data.get("title") else "Plan summary"
    out = default_out(json_path, out_path)
    write_text(out, render("plan-summary.html", title, data))
    return out


def render_explanation(json_path, out_path=None):
    data = load_json(json_path)
    if not isinstance(data, dict):
        raise RenderError("explanation must be a JSON object")
    target = data.get("target") if isinstance(data.get("target"), dict) else {}
    label = target.get("symbol") or (os.path.basename(str(target.get("path"))) if target.get("path") else None)
    title = "Explanation · %s" % label if label else "Change explanation"
    out = default_out(json_path, out_path)
    write_text(out, render("explanation.html", title, data))
    return out


REVIEW_TITLES = {"ai": "AI review", "security": "Security review", "spec": "Spec review"}


def render_review(path, out_path=None):
    json_path = os.path.join(path, "review.json") if os.path.isdir(path) else path
    data = load_json(json_path)
    if not isinstance(data, dict):
        raise RenderError("review must be a JSON object")
    title = REVIEW_TITLES.get(data.get("kind"), "Review")
    change = data.get("change") if isinstance(data.get("change"), dict) else {}
    if change.get("branch"):
        title += " \u00b7 %s" % change["branch"]
    out = default_out(json_path, out_path)
    write_text(out, render("review.html", title, data))
    return out


# --------------------------------------------------------------------------- cli

def main(argv=None):
    parser = argparse.ArgumentParser(description="Render code-review-assistant reports to self-contained HTML.")
    sub = parser.add_subparsers(dest="kind", required=True)
    p_imp = sub.add_parser("impact", help="impact report from <report_dir>/analysis.json (or 'latest')")
    p_imp.add_argument("report_dir")
    p_imp.add_argument("--out", help="output HTML path (default: <report_dir>/impact-report.html)")
    p_plan = sub.add_parser("plan", help="plan summary from plan-summary.json")
    p_plan.add_argument("json_path")
    p_plan.add_argument("--out")
    p_exp = sub.add_parser("explanation", help="change explanation from explanation-<slug>.json")
    p_exp.add_argument("json_path")
    p_exp.add_argument("--out")
    p_rev = sub.add_parser("review", help="review page from review.json (or its directory)")
    p_rev.add_argument("json_path")
    p_rev.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        if args.kind == "impact":
            out = render_impact(args.report_dir, args.out)
        elif args.kind == "plan":
            out = render_plan(args.json_path, args.out)
        elif args.kind == "review":
            out = render_review(args.json_path, args.out)
        else:
            out = render_explanation(args.json_path, args.out)
    except RenderError as exc:
        print("render_report: error: %s" % exc, file=sys.stderr)
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
