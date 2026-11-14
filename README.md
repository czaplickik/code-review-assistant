# Code Review Assistant

Claude Code plugin that triages AI-generated (or manual) changes before review.
It tells you **how much** human attention a change needs and **where**, and runs focused AI
reviews (general, security, spec compliance). Reviews report only and leave a `review.md` fix
list to paste into a fixing session.

| Stage | Skill | What you get |
|---|---|---|
| Before implementation | `/code-review-assistant:change-plan-summary` | Spec + plan condensed to tables and diagrams |
| Review starts | `/code-review-assistant:change-impact-score` | Review mode verdict + ranked files (HTML) |
| Something is unclear | `/code-review-assistant:change-explanation <file\|symbol>` | Why it changed, traced to spec/plan |
| AI review | `/code-review-assistant:ai-review` | Practices, consistency, reinvention, dead code, overengineering, AI artifacts, tests |
| Security review | `/code-review-assistant:security-review` | AuthZ/IDOR, authN, validation, injection, secrets, exposure, config, deps |
| Spec compliance | `/code-review-assistant:spec-review` | Requirements matrix, plan decisions, worked examples, unrequested code |
| Once per project | `/code-review-assistant:review-init` | `docs/code-review/rules.yaml` |
| Once per machine | `/code-review-assistant:configure [folder]` | Knowledge-base folder for all projects |

Review modes: `build+tests+static` · `ai-review-only` · `ai+human-critical-paths` · `human-only`.

Specification: [docs/specification.md](docs/specification.md) · data contract:
[schemas/data-model.md](schemas/data-model.md).

## Install

From the marketplace in this repository (Claude Code):

```text
/plugin marketplace add czaplickik/code-review-assistant-plugin
/plugin install code-review-assistant@code-review-assistant
```

or in one step (Claude Code 2.1.275+):

```text
/plugin install code-review-assistant --marketplace czaplickik/code-review-assistant-plugin
```

For local development: `claude --plugin-dir /path/to/code-review-assistant-plugin`.

## Use

Default boundary: uncommitted changes (staged + unstaged) and untracked files vs `HEAD`.
`--base develop` reviews everything since the merge-base with `develop`.
Reports go to a knowledge base outside the repo, `~/code-review-kb/<project>/`, one folder per
feature: `{DATE}-{JIRA_ID}-{FEATURE}/` with `index.md` (overview), the HTML reports, review fix
lists and history. Open it in a browser or as an Obsidian vault.

Set the folder once for all projects with `/code-review-assistant:configure` (stored in
`~/.config/code-review-assistant/config.yaml`, e.g. `~/Obsidian/Work/Code Review/{project}`).
Precedence: project `docs/code-review/rules.yaml` > `CODE_REVIEW_KB` env var > user config >
default `~/code-review-kb/{project}`.

Requirements: git, Python 3.9+ (standard library only).

## How it works

Deterministic scripts do the repository work; the model only does the semantic part.

**Impact score** (`change-impact-score`)
1. `collect_changes.py` — change boundary (incl. untracked files, stacked-branch warning),
   diffs, spec/plan matched to the change, feature folder.
2. `triage.py` — rulesets per file, exclusions, mechanical changes (repeated patterns, renames,
   deleted modules with a dangling-reference check), deterministic rules, fan-in, linked tests,
   bug history from `git log` (files fixed often),
   tiers and batches (with the subagent model per tier).
3. Subagents per batch — role, interactions, semantic findings, what to verify.
4. `aggregate.py` — merge, blast-radius and missing-test signals, scores (0–5 points per
   finding, summed; model findings below the certainty threshold are listed but not counted),
   ranking (critical first, then severity, then score), review-mode policy,
   the human reading list with questions, `ai-review-focus.md`, plan drift.
5. `render_report.py` — self-contained HTML, published into the feature folder with
   `index.md` refreshed and the previous version moved to `history/`.

**Reviews** (`ai-review`, `security-review`, `spec-review`)
`review.py prepare` (scope, deterministic candidates, batches) → subagents per batch →
`review.py merge` (validation, `review.json`, `review.md` fix list; `review.py combine` folds
duplicates) → the `finding-verifier` agent re-checks every blocker/major (`review.py
verify-plan`) → final merge → `render_report.py review`. Only solid findings reach the main
list: minor/info need high certainty, `ai-review` shows at most 15, the rest is collapsed.

**Plan summary / explanation** — the model writes JSON (`schemas/data-model.md`),
`render_report.py` renders and publishes it.

## Rulesets

`rulesets/_base` (all files), `rulesets/java-spring`, `rulesets/dotnet`. Each has
`detect.yaml` (file types, tests, migrations, symbols, assertions), `signals.yaml`
(deterministic rules), `anchors.md` (rubric for the model), `conventions.md` (defaults when
a project documents none) and `review-*.md` checklists for the reviews. Add a language by
adding a directory.

Project overrides in `docs/code-review/rules.yaml`: thresholds of the review modes, rule
points (`rule_overrides`), own rules (`extra_rules`), `critical_modules`, exclusions, tiers and
`subagent_models` (default: session model for deep batches, `sonnet` for light ones).
Plugin-wide settings (all projects) go to `~/.config/code-review-assistant/config.yaml`.

## Testing

```bash
cd test-fixtures && ./setup.sh --all --force
cd sandbox/java-03-order-refunds && claude --plugin-dir ../../..
# in the session: /code-review-assistant:change-impact-score, then:
python3 ../../check_expected.py java-03-order-refunds
```

See [test-fixtures/README.md](test-fixtures/README.md).
