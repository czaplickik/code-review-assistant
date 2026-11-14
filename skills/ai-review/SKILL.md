---
name: ai-review
disable-model-invocation: true
description: General AI code review of the current change (uncommitted + untracked, or vs a base branch) — checks project practices and rules, consistency with the existing codebase, reinvented helpers, dead code, unrequested or over-engineered code, typical AI artifacts (non-existent APIs, stubs, tests bent to the code), tests, error handling, resources and performance. Produces an HTML report and a review.md fix list to hand to a fixing session. Reports only, never edits code. Use when the user asks for an AI review / code review of a change, or invokes /code-review-assistant:ai-review.
argument-hint: "[--base <branch>]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Read, Grep, Glob, Write, Agent
---

# AI review

Review the **whole change** like a senior reviewer of this codebase. Report only — do not edit
code. Arguments: `$ARGUMENTS`

## 1. Prepare

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

## 4. Answer in the terminal

In the user's language, short:
1. Counts: blocker / major / minor / info.
2. Up to 7 most important findings: `[severity] path:line — title`.
3. Paths of `review.html` and `review.md` — say that `review.md` is the checklist to paste
   into a fixing session.
4. Limitations (sampled mechanical groups, missing conventions docs).

Never offer to apply fixes in this skill; the user decides.
