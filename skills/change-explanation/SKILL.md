---
name: change-explanation
disable-model-invocation: true
description: Explain why a specific changed file, class, method, code section or diff hunk was modified and what it affects — traced to the spec, plan, related changes and existing code, with reason types (explicit / inferred / technical-necessity / unknown). Answers in the terminal or, on request, as HTML with diagrams. Use when the user is reviewing a change and asks "why was this changed", "what does this change do", "explain this hunk", or invokes /code-review-assistant:change-explanation.
argument-hint: "<file[:line[-line]] | Class.method | description>"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(git diff:*), Bash(git log:*), Bash(git show:*), Bash(git blame:*), Bash(git status:*), Read, Grep, Glob, Write, AskUserQuestion
---

# Change explanation

Goal: the developer understands why a piece of the change exists and what it touches, without
reading the whole spec. Never invent intentions — `unknown` is a valid answer.

Target: `$ARGUMENTS` (if empty, ask which file / symbol / lines).

## 1. Ask for the output form

Before analysing, ask with AskUserQuestion (one question):
- **Terminal** (recommended) — short answer here.
- **Terminal + HTML** — also an HTML page with before/after diff, dependency diagram,
  sequence before/after and spec excerpts.

## 2. Locate the change

- Resolve the target to file + line range + symbol. Use the latest impact report if one exists
  (`docs/code-review/reports/*/analysis.json`, newest directory): its entry for the file gives
  role, findings, interactions, flow and plan refs — start from those instead of re-analysing.
- Get the diff of the target: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/show_diff.py latest --file <path> --full`
  when a report exists, otherwise `git diff HEAD -- <path>` (untracked file: read it, everything is new).

## 3. Trace the reason — sources in this order

1. Spec (`docs/superpowers/specs/`, changed or newest) — search for the domain terms of the change.
2. Plan (`docs/superpowers/plans/`) — the task that names this file or symbol.
3. Related changes in the same change set (callers, callees, DTOs, migrations, tests).
4. Existing code and dependencies around the target.
5. Git history (`git log -L`, `git blame` on the old lines) — only when the old behaviour matters.

Classify each reason:
- `explicit` — stated in spec/plan; quote at most 2 sentences with `path#section`.
- `technical-necessity` — required by an interface, contract, framework or another change.
- `inferred` — your reading of the context; say what it is based on.
- `unknown` — no source explains it. Say so plainly; that itself is worth checking.

## 4. Answer

Terminal, in the user's language, compact:

```
<path>:<lines>  <symbol>
What changed   – 1–3 lines
Why            – [explicit] … (spec.md#refund-window)
                 [inferred] …
Context        – requirements, decisions, related components
Impact         – consequences, blast radius (callers, contracts, data)
Worth checking – 1–3 concrete questions for the reviewer
```

If HTML was requested, also write `explanation-<slug>.json` next to the latest report (or in a
new `docs/code-review/reports/<YYYYMMDD-HHMMSS>-explain/` directory) following the
`explanation-<slug>.json` section of `${CLAUDE_PLUGIN_ROOT}/schemas/data-model.md`, then:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py explanation <json path>
```

and give the HTML path. Include `sequence_before` only when the old flow differed.

Do not propose fixes unless the user asks.
