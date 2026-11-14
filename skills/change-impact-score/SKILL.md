---
name: change-impact-score
disable-model-invocation: true
description: Assess how much human review an AI-generated (or manual) code change needs and rank the changed files by criticality. Produces a review-mode verdict (build+tests+static / ai-review-only / ai+human-critical-paths / human-only) and an interactive HTML report with per-file scores, evidence, roles and interaction diagrams. Use when the user starts reviewing a change, asks "how risky is this change", "what should I review first", "can I leave this to AI review", or invokes /code-review-assistant:change-impact-score.
argument-hint: "[--base <branch>] [--spec <path>] [--plan <path>] [--title <feature>] [--jira <ID>]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Read, Grep, Glob, Write, Agent
---

# Change impact score

Goal: tell the developer **at the start of review** how much human attention the change needs,
and give them a **ranked list of files** with the reason each one matters. This is triage, not
code review: do not hunt for bugs, do not fix code.

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/` and must be run from the repository root.
Arguments passed by the user: `$ARGUMENTS`

## 1. Collect and triage (deterministic)

**Feature folder.** Results go to the knowledge base (`report_dir`, default
`~/code-review-kb/<project>/`), one folder per feature named `{DATE}-{JIRA_ID}-{FEATURE}`.
The ticket id and title come from the branch name; on a generic branch (`develop`, `main`)
from the spec title. If the branch has no ticket/feature name **and** no spec is part of the
change, run `git status --short` first, pick a 2–4 word title of what the change does and
pass `--title "<title>"` (and `--jira <ID>` if the user mentioned one).

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/collect_changes.py $ARGUMENTS
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/triage.py latest
```

`collect_changes.py` prints the run directory (`<feature folder>/runs/<id>`). Use that path
as `REPORT` below. Exit code 3 means there is nothing to review — tell the user and stop.

The triage output lists tiers, batches, top deterministic findings and limitations. If
`docs/code-review/rules.yaml` does not exist, mention once at the end that
`/code-review-assistant:review-init` creates a tunable config.

## 2. Semantic pass (model)

List the batches:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/show_diff.py REPORT --list-batches
```

Every batch must produce `REPORT/semantic/batch-<N>.json` in the format described in
`${CLAUDE_PLUGIN_ROOT}/rulesets/_base/anchors.md` (section "Output per file").

- **1–2 batches:** do them yourself.
- **More batches:** dispatch one subagent per batch with the Agent tool (general-purpose),
  up to 6 in parallel, then the next wave. Use the batch's `model` from `--list-batches` as the
  Agent `model` parameter (`inherit` = leave it out); light batches default to a cheaper model. Give each subagent this brief, filled in:

  > You assess review criticality of changed files (triage, not bug hunting). Repository root:
  > `<repo root>`. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/show_diff.py <REPORT> --batch <N>` to get
  > the files, metadata, deterministic findings and diffs. Read the rubric files named in the
  > output header, and the project's conventions files if listed. For `deep` files read the
  > surrounding code you need (the full file, 2–4 neighbouring files in the same package or
  > namespace, callers listed under fan-in) — never the whole repository. For `light` files the
  > diff is usually enough. Write `<REPORT>/semantic/batch-<N>.json` exactly in the documented
  > format: every file of the batch must appear, with `role`, `interactions`, `what_to_verify`,
  > `findings`, optional `adjust`. Do not repeat deterministic findings; use `adjust` to correct
  > them. Mark facts seen in code as `verified`, reasoning as `inferred`. Never invent callers,
  > tables or topics. Reply with one line: the batch number and the number of findings.

Deep batches first. Do not read diffs of batches you delegated — keep your context free.

## 3. Flows (model)

After all batches are written, build execution flows from a compact view of roles and
interactions:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/show_diff.py REPORT --roles
```

Then write `REPORT/flows.json`:

```json
{"flows": [{"id": "kebab-id", "name": "Refund request", "description": "REST → service → gateway → DB → event",
            "files": ["paths in execution order"]}]}
```

A flow is one path a reviewer should read end to end (entry point → logic → persistence /
integration). 2–8 flows for typical changes; files may stay outside flows (they appear under
"Other changes"). Tests go into the flow of the code they test, at the end. Mechanical and
excluded files stay out.

## 4. Aggregate and render

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/aggregate.py REPORT
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py impact REPORT
```

`aggregate.py` exits 1 and lists problems when a batch is missing or invalid — fix the batch
(re-run its subagent or edit the JSON) and run it again. Do not use `--allow-incomplete` for
the final run unless a batch cannot be produced; then say so in the summary.

## 5. Answer in the terminal

Short, in the user's language:

1. **Review mode** and the one-line reason (from `aggregate.py` output).
2. For `ai+human-critical-paths`: the files the human should read (`verdict.human_files`),
   at most 10, with the top reason each. For `human-only`: the top 10 ranked files.
   For `ai-review-only`: say the AI-review focus list is in the report.
3. Limitations that matter (missing spec/plan, unmatched rulesets, incomplete analysis).
4. The feature folder: `impact-report.html` and `index.md` (overview note, also usable as an
   Obsidian note) — `render_report.py` prints both paths after `published:` / `index:`.

Do not paste the whole ranking or the JSON. Do not offer to fix code.
