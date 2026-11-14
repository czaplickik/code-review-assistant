# Test fixtures

Scenario repos with planted changes and ground truth for validating the plugin
(spec section 13): `EXPECTED.md` for people, `expected.json` for `check_expected.py`.

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

Each sandbox commits a `docs/code-review/rules.yaml` with `report_dir: docs/code-review/reports`,
so reports stay inside the sandbox (`docs/code-review/reports/<feature>/`) instead of the
knowledge base in your home folder. After `/code-review-assistant:change-impact-score`:

```bash
python3 ../../check_expected.py java-03-order-refunds   # one scenario (newest report)
python3 ../../check_expected.py --all                   # every sandbox that has a report
```

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
  expected.json             the same, machine-readable (format in check_expected.py)
check_expected.py           compares the newest analysis.json with expected.json
```

## Pass criteria

- review mode equals the expected one (or an allowed alternative),
- the files in `top.files` rank within `top.n` (usually 5),
- every must-detect signal is reported with at least `min_points` in its dimension,
- no trap ranks within `traps.n` (10, or 3 for scenarios with few files),
- for scenarios with a plan: the expected plan drift is reported.

Add a scenario by creating a new `scenarios/<id>/` directory; no script changes needed.
