---
name: configure
disable-model-invocation: true
description: Configure Code Review Assistant for all projects — set the knowledge-base folder where reports are written (e.g. a folder inside an Obsidian vault), and show the effective settings. Invoke with /code-review-assistant:configure.
argument-hint: "[folder]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), AskUserQuestion
---

# Configure

Plugin-wide settings live in `~/.config/code-review-assistant/config.yaml` and apply to every
project. A project's `docs/code-review/rules.yaml` can still override them, and the
`CODE_REVIEW_KB` environment variable overrides the file.

1. Show the current state:
   `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/configure.py --show`
2. Folder: use `$ARGUMENTS` if given; otherwise ask with AskUserQuestion, offering
   `~/code-review-kb/{project}` (default) and a folder inside an Obsidian vault
   (e.g. `~/Obsidian/<vault>/Code Review/{project}`), plus free text. Explain in one line that
   `{project}` becomes the repository folder name so projects stay separated.
3. Save: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/configure.py --report-dir "<folder>"`
4. Answer with the effective folder and where the setting is stored. If the folder is inside a
   synced location (iCloud, Dropbox, OneDrive, Obsidian Sync vault), mention once that reports
   contain code snippets from the reviewed repositories.
