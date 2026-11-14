"""Feature folders: one folder per feature in the knowledge base, named {DATE}-{JIRA_ID}-{FEATURE}.

Layout:
  <report base>/<YYYY-MM-DD>-<JIRA>-<feature-slug>/
    index.md                 overview note (frontmatter + summary + links), rebuilt on every publish
    feature.json             identity (jira, title, branch) + registry of the latest outputs
    impact-report.html, plan-summary.html, review-ai.html, review-ai.md, explanation-*.html …
    history/                 previous versions, prefixed with their date-time
    runs/<stamp>-<hash>/     working data of each collection (analysis.json, diffs, semantic, review-*)
"""
from __future__ import annotations

import datetime as dt
import re
import shutil
import unicodedata
from collections import Counter
from pathlib import Path

from _common import git, read_json, write_json

JIRA_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d{1,7})\b")
GENERIC_BRANCHES = {"main", "master", "develop", "development", "dev", "trunk", "head", "staging", "release"}
BRANCH_PREFIX = re.compile(r"^(feature|feat|bugfix|fix|hotfix|chore|refactor|task|story|ai|claude|wip)[/_-]", re.I)
CODE_STOP = {
    "service", "services", "controller", "controllers", "repository", "repositories", "dto", "dtos", "test", "tests",
    "impl", "config", "configuration", "mapper", "mappers", "request", "response", "entity", "model", "models",
    "handler", "handlers", "command", "query", "event", "events", "exception", "factory", "util", "utils",
    "helper", "helpers", "base", "abstract", "interface", "main", "src", "java", "kotlin", "resources", "com",
    "example", "org", "net", "app", "api", "domain", "application", "infrastructure", "common", "core", "shared",
    "create", "update", "get", "set", "new", "v1", "v2", "v3", "db", "migration", "migrations", "docs", "readme",
    "pom", "xml", "yml", "yaml", "json", "properties", "cs", "csproj", "sql", "md", "spec", "specs", "plan", "plans",
    "superpowers", "design", "the", "and", "for", "with", "shop", "status", "type", "line", "lines", "dbcontext",
    "designer", "snapshot", "program", "startup", "validator", "validators", "options", "client", "async",
}


def slugify(text, max_words=6):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    words = [w for w in re.split(r"[^A-Za-z0-9]+", text.lower()) if w]
    return "-".join(words[:max_words])[:60].strip("-")


def _camel_tokens(name):
    return [t.lower() for t in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", name)]


def title_from_code(paths, new_paths=()):
    """Most characteristic domain words of the changed file names (new files weigh double)."""
    count = Counter()
    for p in paths:
        stem = Path(p).stem
        weight = 2 if p in new_paths else 1
        for t in _camel_tokens(stem.replace("__", "_")):
            if len(t) > 2 and t not in CODE_STOP and not t.isdigit():
                count[t[:-1] if t.endswith("s") and len(t) > 4 else t] += weight
    top = [w for w, _ in count.most_common(3)]
    return " ".join(top) if top else None


def title_from_spec(root, spec_paths):
    for sp in spec_paths or []:
        try:
            for line in (Path(root) / sp).read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    t = line[2:].strip()
                    t = re.split(r"\s+[—–-]\s+|:\s", t)[0]
                    t = re.sub(r"(?i)\b(design|specification|spec|implementation plan|plan)\b", "", t).strip(" -—:")
                    if t:
                        return t
        except OSError:
            continue
    return None


def feature_info(root, branch, title=None, jira=None, spec_paths=None, changed=None, new=None):
    branch = branch or ""
    short = branch.split("/")[-1] if branch else ""
    generic = short.lower() in GENERIC_BRANCHES or not branch or branch == "HEAD"
    source = "argument" if title else None
    if not jira:
        m = JIRA_RE.search(branch)
        jira = m.group(1) if m else None
    if not jira:
        for sp in spec_paths or []:
            try:
                head = "\n".join((Path(root) / sp).read_text(encoding="utf-8").splitlines()[:15])
            except OSError:
                continue
            m = JIRA_RE.search(head)
            if m:
                jira = m.group(1)
                break
    if not title and not generic:
        t = BRANCH_PREFIX.sub("", branch.split("/", 1)[-1] if "/" in branch else branch)
        t = JIRA_RE.sub("", t).strip("-_/ ")
        if t:
            title, source = t.replace("-", " ").replace("_", " "), "branch"
    if not title:
        title = title_from_spec(root, spec_paths)
        source = "spec" if title else None
    if not title and changed:
        title = title_from_code(changed, new or ())
        source = "code" if title else None
    if not title:
        title, source = "change", "default"
    return {"jira": jira, "title": title.strip(), "slug": slugify(title) or "change", "branch": branch or None,
            "title_source": source}


def find_or_create(base, info, repo_root):
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    candidates = []
    for fj in base.glob("*/feature.json"):
        try:
            meta = read_json(fj)
        except ValueError:
            continue
        if meta.get("repo_root") and meta["repo_root"] != str(repo_root):
            continue
        if info["jira"] and meta.get("jira") == info["jira"]:
            candidates.append((3, fj.parent))
        elif not info["jira"] and info["branch"] and meta.get("branch") == info["branch"] \
                and info["branch"].split("/")[-1].lower() not in GENERIC_BRANCHES:
            candidates.append((2, fj.parent))
        elif not info["jira"] and meta.get("slug") == info["slug"]:
            candidates.append((1, fj.parent))
    if candidates:
        folder = sorted(candidates, key=lambda c: (-c[0], c[1].name))[-1][1]
        meta = read_json(folder / "feature.json")
        if info["jira"] and not meta.get("jira"):
            meta["jira"] = info["jira"]
            write_json(folder / "feature.json", meta)
        return folder
    date = dt.date.today().isoformat()
    name = "-".join(x for x in (date, info["jira"], info["slug"]) if x)
    folder = base / name
    n = 2
    while folder.exists():
        folder = base / f"{name}-{n}"
        n += 1
    folder.mkdir(parents=True)
    write_json(folder / "feature.json", {**info, "created": date, "repo_root": str(repo_root),
                                         "folder": folder.name, "outputs": {}})
    return folder


def feature_dir_of(path):
    p = Path(path).resolve()
    for parent in [p] + list(p.parents):
        if (parent / "feature.json").is_file():
            return parent
    return None


# ------------------------------------------------------------------ publish

PUBLISHED_NAMES = {
    "impact": "impact-report.html",
    "plan": "plan-summary.html",
    "review-ai": "review-ai.html",
    "review-security": "review-security.html",
    "review-spec": "review-spec.html",
}


def publish(kind, html_path, json_path=None, md_path=None, name=None):
    """Copy a rendered output to the feature folder root (previous version → history/), update
    the registry in feature.json and rebuild index.md. Returns the published path or None."""
    fdir = feature_dir_of(html_path)
    if not fdir:
        return None
    meta = read_json(fdir / "feature.json")
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    published = []
    for src, dest_name in ((html_path, name or PUBLISHED_NAMES.get(kind, Path(html_path).name)),
                           (md_path, (Path(name or PUBLISHED_NAMES.get(kind, "")).stem + ".md") if md_path else None)):
        if not src or not dest_name:
            continue
        dest = fdir / dest_name
        if dest.exists():
            (fdir / "history").mkdir(exist_ok=True)
            shutil.move(str(dest), str(fdir / "history" / f"{stamp}-{dest_name}"))
        shutil.copy2(src, dest)
        published.append(dest_name)
    key = kind if kind != "explanation" else f"explanation:{published[0] if published else name}"
    meta.setdefault("outputs", {})[key] = {
        "kind": kind, "files": published, "json": str(Path(json_path).resolve()) if json_path else None,
        "updated": dt.datetime.now().isoformat(timespec="minutes")}
    meta["updated"] = dt.datetime.now().isoformat(timespec="minutes")
    write_json(fdir / "feature.json", meta)
    write_index(fdir, meta)
    return fdir / published[0] if published else None


def _load(path):
    try:
        return read_json(path) if path and Path(path).is_file() else None
    except ValueError:
        return None


def write_index(fdir, meta):
    outs = meta.get("outputs") or {}
    title = (f"{meta['jira']} " if meta.get("jira") else "") + meta.get("title", "change").capitalize()
    plan = _load((outs.get("plan") or {}).get("json"))
    impact = _load((outs.get("impact") or {}).get("json"))
    reviews = {k.split("-", 1)[1]: _load(v.get("json")) for k, v in outs.items() if k.startswith("review-")}
    fm = {"jira": meta.get("jira") or "", "feature": meta.get("title"), "branch": meta.get("branch") or "",
          "created": meta.get("created"), "updated": meta.get("updated"),
          "review_mode": ((impact or {}).get("verdict") or {}).get("mode", "")}
    for k, r in reviews.items():
        if r:
            fm[f"{k}_blockers"] = r["summary"].get("blocker", 0)
            fm[f"{k}_majors"] = r["summary"].get("major", 0)
    lines = ["---"] + [f"{k}: {v if v is not None else ''}" for k, v in fm.items()] + \
            ["tags: [code-review]", "---", "", f"# {title}", ""]
    if meta.get("title_source") in ("code", "default"):
        lines += [f"> Title inferred from the changed code — rename the folder/title once the ticket is known.", ""]
    if plan:
        lines += ["## Goal", "", plan.get("goal") or "", ""]
        f = plan.get("findings") or {}
        n = {k: len(f.get(k) or []) for k in ("contradictions", "unaddressed_requirements",
                                               "unrequired_plan_items", "open_questions")}
        lines += [f"Plan: {n['contradictions']} contradiction(s), {n['unaddressed_requirements']} requirement(s) "
                  f"without a plan step, {n['open_questions']} open question(s) — [plan summary](plan-summary.html)", ""]
        for c in (f.get("contradictions") or [])[:5]:
            lines.append(f"- ⚠ {c.get('text')}")
        lines.append("")
    if impact:
        v = impact.get("verdict") or {}
        lines += ["## Review mode", "", f"**{v.get('mode', '?')}** — {v.get('explanation', '')}", ""]
        hf = v.get("human_files") or []
        if hf:
            lines += [f"Human reads {len(hf)} file(s):", ""] + [f"- `{p}`" for p in hf[:12]] + [""]
        ranked = sorted((x for x in impact.get("files") or [] if x.get("rank")), key=lambda x: x["rank"])[:5]
        if ranked:
            lines += ["Top files:", ""]
            for x in ranked:
                top = max(x.get("findings") or [{}], key=lambda y: (y.get("critical", False), y.get("points", 0)))
                lines.append(f"{x['rank']}. `{x['path']}` — {top.get('title', '')}{' ❗' if x.get('critical') else ''}")
            lines.append("")
        lines += ["[Impact report](impact-report.html)", ""]
    if any(reviews.values()):
        lines += ["## Reviews", "", "| Review | Blocker | Major | Minor | Info | Report | Fix list |",
                  "|---|---|---|---|---|---|---|"]
        for k in ("ai", "security", "spec"):
            r = reviews.get(k)
            if not r:
                continue
            s = r["summary"]
            lines.append(f"| {k} | {s.get('blocker', 0)} | {s.get('major', 0)} | {s.get('minor', 0)} | "
                         f"{s.get('info', 0)} | [html](review-{k}.html) | [md](review-{k}.md) |")
        lines.append("")
        blockers = [(k, x) for k, r in reviews.items() if r for x in r.get("findings") or [] if x["severity"] == "blocker"]
        if blockers:
            lines += ["Blockers:", ""] + [f"- [ ] ({k}) `{x['path']}` — {x['title']}" for k, x in blockers[:15]]
            if len(blockers) > 15:
                lines.append(f"- … {len(blockers) - 15} more in the fix lists")
            lines.append("")
    exps = [v for k, v in outs.items() if k.startswith("explanation:")]
    if exps:
        lines += ["## Explanations", ""] + [f"- [{Path(f).stem}]({f})" for v in exps for f in v["files"]] + [""]
    hist = sorted((fdir / "history").glob("*")) if (fdir / "history").is_dir() else []
    if hist:
        lines += ["## History", ""] + [f"- [{h.name}](history/{h.name})" for h in reversed(hist[-20:])] + [""]
    (fdir / "index.md").write_text("\n".join(lines), encoding="utf-8")
