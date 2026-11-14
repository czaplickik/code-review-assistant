---
name: spec-review
disable-model-invocation: true
description: Critical review of an implementation against its spec and plan (e.g. Superpowers docs/superpowers/specs and plans, also when they were committed earlier) — requirements matrix with status and tests per requirement, plan decisions and assumptions followed or deviated, business rules verified with worked examples, unrequested behaviour and contract mismatches. Produces an HTML report and a review.md fix list. Reports only. Use when the user asks whether the implementation matches the spec/plan/requirements, or invokes /code-review-assistant:spec-review.
argument-hint: "[--base <branch>] [--spec <path>] [--plan <path>] [--title <feature>] [--jira <ID>]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Read, Grep, Glob, Write, Agent
---

# Spec review

Check critically that the **whole change** does what the spec requires and follows the plan's
decisions — not more, not less, not differently. Report only. Arguments: `$ARGUMENTS`

## 1. Prepare

**Feature folder.** Results go to the knowledge base (`report_dir`, default
`~/code-review-kb/<project>/`), one folder per feature named `{DATE}-{JIRA_ID}-{FEATURE}`.
The ticket id and title come from the branch name; on a generic branch (`develop`, `main`)
from the spec title. If the branch has no ticket/feature name **and** no spec is part of the
change, run `git status --short` first, pick a 2–4 word title of what the change does and
pass `--title "<title>"` (and `--jira <ID>` if the user mentioned one).

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review.py prepare spec $ARGUMENTS
```

Prints the review directory (`REVIEW`) and the spec/plan used. Spec and plan are taken from the
change, or — when they were committed before the implementation — the newest documents in the
spec/plan directories. If the output says `spec: none; plan: none`, ask the user for the paths
and re-run with `--spec` / `--plan`.

## 2. Build the requirement list (you)

Read the spec and the plan fully (or start from the `plan-summary.json` of the same feature —
the feature folder's `feature.json` lists it under `outputs.plan.json` — then verify against
the documents). List every requirement
with code impact (`id`, short text, `ref` as `path#heading-slug`), every technical decision or
assumption, and every business rule with a formula or limit. Read
`${CLAUDE_PLUGIN_ROOT}/rulesets/_base/review-spec.md`.

Also read `REVIEW/candidates.json`: files changed outside the plan and planned files not changed.

## 3. Verify (subagents)

Split the requirements into groups of about 6 (keep related ones together; decisions and
business rules go with the requirements they belong to). One subagent per group, up to 6 in
parallel. Brief:

> You verify part of an implementation against its spec (report only — never edit files).
> Repository root: `<repo root>`. Spec: `<path>`, plan: `<path>`. Read
> `${CLAUDE_PLUGIN_ROOT}/rulesets/_base/review-spec.md`. Your items: <list with ids, text, refs>.
> The changed files are listed in `<REVIEW>/scope.json` (report dir → analysis.json); use
> `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/show_diff.py <report_dir> --file <path> --full` to see
> a diff. For each item find the implementing code (Grep), decide the status, check whether a
> test would catch a violation, and compute 2–3 worked examples for every formula or limit
> (expected from the spec vs actual from the code). Write `<REVIEW>/spec-part-<N>.json`
> (`requirements`, `decisions`, `examples`, `unrequested` as in the "spec-matrix.json"
> section of `${CLAUDE_PLUGIN_ROOT}/schemas/data-model.md`) and
> `<REVIEW>/spec-findings-<N>.json` (`{"findings": [...]}` with review findings, categories
> requirement / business_rule / decision / contract / unrequested / test_gap). Reply with one
> line: counts of statuses and findings.

Yourself, in parallel: go through the candidates and the changed files for **unrequested
behaviour** (code no requirement asks for) and write `REVIEW/spec-matrix.json` with
`sources` and `unrequested`, plus `REVIEW/spec-findings-0.json` for findings about it.

## 4. Merge and render

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review.py merge <REVIEW>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py review <REVIEW>
```

Fix reported problems and merge again. Groups overlap (e.g. idempotency appears in a
requirement and in a decision): merge findings that `merge` lists as possible duplicates into
one with `related` locations, then merge again.

## 5. Answer in the terminal

Short, in the user's language: requirement coverage (implemented / partial / missing /
contradicted / unclear), failed worked examples (`rule: expected X, code gives Y`), deviated
decisions, top findings, and the the published `review-<kind>.html` and `review-<kind>.md` in the feature folder and its `index.md` (printed by `render_report.py`) (fix list for a fixing
session). Never invent a requirement or an intention; ambiguity in the spec is an `info`
finding quoting the spec.
