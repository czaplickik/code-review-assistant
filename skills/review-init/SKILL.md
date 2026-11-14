---
name: review-init
disable-model-invocation: true
description: Set up Code Review Assistant for the current repository — detect the stack (Java/Spring, .NET), create docs/code-review/rules.yaml with review-mode thresholds, rule points, exclusions, critical modules and spec/plan directories, and keep reports out of git. Use when the user wants to configure or tune the review assistant, or invokes /code-review-assistant:review-init.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Read, Edit, Glob, Grep, AskUserQuestion
---

# Review init

1. Preview: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/init_rules.py --dry-run` (shows the detected
   stacks; do not paste the whole file).
2. If `docs/code-review/rules.yaml` already exists, read it and ask whether to keep it
   (then only tune it, step 4) or regenerate it (`--force`).
3. Ask with AskUserQuestion whether to add the report directory to `.gitignore`
   (recommended). Then run `init_rules.py` with `--gitignore` if they agreed.
4. Offer to tune, based on what you can see in the repo (look, do not guess):
   - `critical_modules` — e.g. payment, billing, security, auth packages/namespaces you find;
   - `sources.spec_dirs` / `plan_dirs` if specs and plans live elsewhere;
   - `base_branch` if they review whole feature branches instead of uncommitted changes;
   - `extra_exclude` for generated code directories you find.
   Apply only what the user confirms, with Edit.
5. Summarise in 3–5 lines: detected rulesets, what was written, what was tuned.
