# Test fixtures

Scenario repos with planted changes and ground truth (`EXPECTED.md`) for validating the plugin
(spec section 13).

## Usage

```bash
./setup.sh --list                      # available scenarios
./setup.sh java-03-order-refunds       # builds sandbox/java-03-order-refunds
./setup.sh --all --force               # rebuild every scenario
```

Each sandbox is a fresh git repo: the base project is committed on `develop`, the change under
review is left **uncommitted** (new files untracked). Run Claude Code with the plugin inside it:

```bash
cd sandbox/java-03-order-refunds
claude --plugin-dir ../../..
```

Then compare the report with `scenarios/<id>/EXPECTED.md`.

## Layout

```text
projects/<base>/            base project, committed as the starting state
scenarios/<id>/
  base                      name of the base project
  prepare.py                optional: inflates the base before the first commit
  committed/                optional: committed on feature/<id> (branch-boundary tests)
  delete.txt                optional: paths deleted (uncommitted)
  changes/                  files copied over the base (uncommitted / untracked)
  generate.py               optional: bulk edits after the base commit
  staged.txt                optional: paths to `git add` (partial staging)
  EXPECTED.md               ground truth: mode, top files, must-detect signals, traps
```

## Pass criteria

- review mode equals the expected one,
- files marked CRITICAL are in the top 5,
- every must-detect signal is reported,
- no trap is in the top 10.

Add a scenario by creating a new `scenarios/<id>/` directory; no script changes needed.
