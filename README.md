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

## Use

```bash
claude --plugin-dir /path/to/code-review-assistant-plugin
```

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

1. `scripts/collect_changes.py` — change boundary, diffs, spec/plan discovery.
2. `scripts/triage.py` — rulesets per file, exclusions, mechanical-change detection (repeated
   patterns across files), deterministic rules, fan-in, linked tests, tiers and batches.
3. Model (subagents per batch) — role, interactions, semantic findings, what to verify.
4. `scripts/aggregate.py` — merge, blast-radius and missing-test signals, additive scores
   (0–5 points per finding, critical flag pins a file to the top), review-mode policy, plan drift.
5. `scripts/render_report.py` — self-contained HTML.

## Rulesets

`rulesets/_base` (all files), `rulesets/java-spring`, `rulesets/dotnet`. Each has
`detect.yaml` (file types, tests, migrations, symbols, assertions), `signals.yaml`
(deterministic rules), `anchors.md` (rubric for the model) and `conventions.md` (defaults when
a project documents none). Add a language by adding a directory.

Project overrides in `docs/code-review/rules.yaml`: thresholds of the review modes, rule
points (`rule_overrides`), own rules (`extra_rules`), `critical_modules`, exclusions.

## Testing

```bash
cd test-fixtures && ./setup.sh --all --force
cd sandbox/java-03-order-refunds && claude --plugin-dir ../../..
python3 ../../check_expected.py java-03-order-refunds
```

See [test-fixtures/README.md](test-fixtures/README.md).
