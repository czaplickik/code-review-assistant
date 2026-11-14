---
name: security-review
disable-model-invocation: true
description: Security review of the current change (uncommitted + untracked, or vs a base branch), stack-aware for Java/Spring and .NET — entry-point inventory, authorization and ownership (IDOR), authentication and tokens, input validation, injection, secrets, crypto, data exposure, SSRF, deserialization, security config, dependencies, sensitive logging, and the security requirements of the spec. Produces an HTML report and a review.md fix list. Reports only. Use when the user asks for a security review of a change, or invokes /code-review-assistant:security-review.
argument-hint: "[--base <branch>]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Read, Grep, Glob, Write, Agent
---

# Security review

Find exploitable weaknesses introduced or exposed by the **whole change**. Report only — do not
edit code. Arguments: `$ARGUMENTS`

## 1. Prepare

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review.py prepare security $ARGUMENTS
```

Prints the review directory (`REVIEW`), batches and candidates: new/changed entry points,
removed security-related lines, deterministic security findings from the rulesets, possibly
sensitive logging, new dependencies. Exit code 3 = nothing to review.

## 2. Context you read yourself (once)

- The security configuration of the application (filter chain / auth setup, policies,
  CORS/CSRF) — find it with Grep, read it, and summarise the effective defaults in 3–5 lines.
- The security requirements of the spec (roles, ownership, audit, data classification) if
  the prepare output lists a spec.

Put both summaries into each subagent brief below.

## 3. Review the batches

- **1 batch:** do it yourself.
- **More:** one subagent per batch, up to 6 in parallel. Brief:

  > You do a security review of one batch of a code change (report only — never edit files).
  > Repository root: `<repo root>`. Effective security configuration: <summary>. Security
  > requirements from the spec: <summary or "none">. Run
  > `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review.py show <REVIEW> --batch <N>`, read the
  > checklists named in its header and follow them: for every entry point trace input to its
  > use (DB, external calls, files, responses, logs), check authorization including ownership,
  > validation and data exposure; read callers/callees as needed. Confirm or dismiss every
  > candidate. Describe each finding as an attack in one sentence. Write
  > `<REVIEW>/batch-<N>.json` as described in `${CLAUDE_PLUGIN_ROOT}/schemas/data-model.md`
  > (section "Reviews"). Reply with one line: batch number and counts per severity.

## 4. Merge and render

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review.py merge <REVIEW>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py review <REVIEW>
```

Fix problems reported by `merge` and merge again. `merge` prints possible duplicates across
batches: the same weakness reported twice (e.g. once at the controller, once at the security
config) becomes one finding with the other location in `related` — edit the batch files (a
dropped finding's candidate goes to `dismissed_candidates` with "merged"), merge again.

## 5. Answer in the terminal

Short, in the user's language: counts per severity, every `blocker` and up to 5 `major`
findings as `[severity] path:line — attack in one sentence`, paths of `review.html` and
`review.md` (fix list for a fixing session), limitations (e.g. dependency versions not checked
online). Do not offer to fix.
