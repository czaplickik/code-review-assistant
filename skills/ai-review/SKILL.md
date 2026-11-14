---
name: ai-review
disable-model-invocation: true
description: General AI code review of the current change (uncommitted + untracked, or vs a base branch) — checks project practices and rules, consistency with the existing codebase, reinvented helpers, dead code, unrequested or over-engineered code, typical AI artifacts (non-existent APIs, stubs, tests bent to the code), tests, error handling, resources and performance. Produces an HTML report and a review.md fix list to hand to a fixing session. Reports only, never edits code. Use when the user asks for an AI review / code review of a change, or invokes /code-review-assistant:ai-review.
argument-hint: "[--base <branch>] [--title <feature>] [--jira <ID>]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Read, Grep, Glob, Write, Agent
---

# AI review

Review the **whole change** like a senior reviewer of this codebase. Report only — do not edit
code. Arguments: `$ARGUMENTS`

## 1. Prepare

**Feature folder.** Results go to the knowledge base (`report_dir`, default
`~/code-review-kb/<project>/`), one folder per feature named `{DATE}-{JIRA_ID}-{FEATURE}`.
The ticket id and title come from the branch name; on a generic branch (`develop`, `main`)
from the spec title. If the branch has no ticket/feature name **and** no spec is part of the
change, run `git status --short` first, pick a 2–4 word title of what the change does and
pass `--title "<title>"` (and `--jira <ID>` if the user mentioned one).

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review.py prepare ai $ARGUMENTS
```

Prints the review directory (`REVIEW`), the number of batches and deterministic candidates
(possible dead code, debug output, TODOs, stubs, duplicated blocks, new helper classes,
new dependencies). Exit code 3 = nothing to review: say so and stop.

## 2. Review the batches

- **1 batch:** do it yourself (step below).
- **More:** one subagent per batch (Agent tool, general-purpose), up to 6 in parallel. Brief:

  > You review one batch of a code change (AI code review, report only — never edit files).
  > Repository root: `<repo root>`. Run
  > `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review.py show <REVIEW> --batch <N>`.
  > Read the checklists named in its header and the project conventions files, then follow the
  > checklist: for each file read the diff, the full file when needed and 2–4 neighbouring files
  > of the same kind; Grep the repository before claiming reinvention or dead code. Confirm or
  > dismiss every candidate listed. Write `<REVIEW>/batch-<N>.json` exactly as described in
  > `${CLAUDE_PLUGIN_ROOT}/schemas/data-model.md` (section "Reviews"): `files_reviewed` with
  > every file of the batch, `findings`, `dismissed_candidates`. Reply with one line: batch
  > number and finding counts per severity.

Do not read the batch diffs yourself when you delegated them.

## 3. Merge and render

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review.py merge <REVIEW>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py review <REVIEW>
```

`merge` exits 1 with a list of problems (missing batch, file not reviewed, candidate not
handled, bad category/severity): fix the batch file or re-run its subagent, then merge again.

`merge` also prints **possible duplicates across batches**. Check them (and the list once
yourself): the same problem reported by several batches becomes one finding with the other
locations in `related` — edit the batch files (a dropped finding's candidate goes to
`dismissed_candidates` with "merged"), then merge again.

## Verify (independent second opinion)

After the first merge, have every blocker/major re-checked by the **finding-verifier** agent
of this plugin (it reads the code from scratch and tries to refute each finding):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review.py verify-plan <REVIEW>
```

For each printed batch dispatch one `finding-verifier` agent (Agent tool; if that agent type
is not available, a general-purpose agent with the same brief), up to 6 in parallel:

> Verify review findings (you did not write them). Repository root: `<repo root>`. Run
> `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review.py verify-show <REVIEW> --batch <N>` to get
> them, follow `${CLAUDE_PLUGIN_ROOT}/agents/finding-verifier.md`, and write
> `<REVIEW>/verify-<N>.json`. Reply with one line: counts per verdict.

Then merge again. If `merge` still reports unverified blocker/major findings (findings that
moved up after others were rejected or downgraded), run `verify-plan` and the verifier once
more for those only. Rejected findings leave the report (kept in review.json), downgraded ones
change severity, minor/info need certainty ≥ 85, and only the strongest findings stay in the
main list (`review.max_findings` in the config):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review.py merge <REVIEW>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py review <REVIEW>
```

## 4. Answer in the terminal

In the user's language, short:
1. Counts: blocker / major / minor / info, and how many were verified / rejected by the
   verifier.
2. Up to 7 most important findings: `[severity] path:line — title`.
3. The published `review-<kind>.html` and `review-<kind>.md` in the feature folder and its `index.md` (printed by `render_report.py`) — say that `review.md` is the checklist to paste
   into a fixing session.
4. Limitations (sampled mechanical groups, missing conventions docs).

Never offer to apply fixes in this skill; the user decides.
