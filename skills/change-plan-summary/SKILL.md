---
name: change-plan-summary
disable-model-invocation: true
description: Condense a long feature spec and implementation plan (e.g. Superpowers docs/superpowers/specs and plans) into a short visual summary (≤ 10% of the original) — goal, key requirements and business rules, contracts, decisions, component and sequence diagrams, contradictions, gaps and open questions — so the developer can correct the plan before implementation without reading 10 pages. No edge cases, test strategy or boilerplate. Does not grade the plan. Use when the user asks to summarise a spec/plan, "what does this plan say", or invokes /code-review-assistant:change-plan-summary.
argument-hint: "[spec-or-plan paths…]"
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*), Bash(git status:*), Bash(git ls-files:*), Bash(wc:*), Read, Grep, Glob, Write
---

# Change plan summary

Goal: the developer reads only what matters in the spec and plan, sees it as diagrams and
tables, and corrects the plan before implementation. **Condense, never evaluate**: no grade,
no "the plan is good/bad", no recommendations. Facts like contradictions or gaps are listed
neutrally.

Arguments: `$ARGUMENTS`

## 1. Find the documents

- Paths given in the arguments win.
- Otherwise: changed or untracked Markdown files under the spec/plan directories
  (`docs/superpowers/specs/`, `docs/superpowers/plans/`, or `sources.spec_dirs` /
  `sources.plan_dirs` in `docs/code-review/rules.yaml`):
  `git status --porcelain --untracked-files=all -- docs/superpowers` (adjust to config).
- Nothing changed there: take the most recent file in each directory and say which you used.
- Nothing at all: ask the user for the paths and stop.

Count words (`wc -w`) for the `sources[].words` and `cut.words_in` fields.

## 2. Read and extract

Read the documents fully. Then read only the code needed to place planned changes in the
existing architecture (e.g. whether a component already exists) — do not explore broadly.

The developer reads this summary to **correct the plan before implementation**. Keep only what
they must know to judge it; everything else stays in the source documents (the refs lead there).

**Budget: ≤ 10% of the input words, hard cap 600 words** (count all text fields). If you are
over, drop the least important rows — never shorten numbers or names.

Keep (fill these fields only):
- `goal` — 2–3 sentences: what is built and for whom.
- `requirements` — **max 8**, the ones that shape the design: who may do what, core behaviour,
  hard limits. One line each, numbers exact (windows, caps, roles, error codes only if decisive).
- `business_rules` — **max 5**: formulas and rules the code must get exactly right.
- `contracts` — every new or changed API / event / table / external call, one line each.
- `decisions` — **max 5** technical decisions that constrain the implementation, with a
  short rationale.
- `stages` — task names with their **component**-level scope (not file lists).
- `components` + `sequence` — the diagrams (step 3).
- `findings` — contradictions, unaddressed requirements, unrequired plan items, open questions.

Leave out entirely (do not write these fields): `edge_cases`, `testing_strategy`, `risks`,
`acceptance_criteria`, `constraints`, `expected_files`. Also cut: restatements, boilerplate,
background, motivation, glossary, stakeholders, rollout prose, non-goals, alternatives,
non-functional details that do not change the design (latency targets, metric names, log formats),
and anything duplicated between spec and plan.

Exception: a non-functional or testing item that the plan **ignores** goes into
`findings.unaddressed_requirements`, not into the summary body.

Cross-check spec vs plan and record as facts:
- `contradictions` — spec and plan say different things (quote both sides briefly, both refs),
- `unaddressed_requirements` — requirement with no plan step,
- `unrequired_plan_items` — plan step with no requirement,
- `open_questions` — explicitly open or left undecided.

Rules: every row has a `ref` (`<path>#<heading-slug>`); never invent content to fill a gap —
a missing section is simply absent; short sentences, numbers kept exact.

## 3. Diagrams

- `components`: nodes for components touched or relied on (layer: api, application, domain,
  data, messaging, external; status: new / modified / existing), edges for calls, events,
  reads/writes. Aim for 5–10 nodes.
- `sequence`: the main scenario only, as participants + ordered steps (≤ 10 steps), notes
  only for conditions that matter (e.g. "outside transaction").

## 4. Write and render

Get the run directory in the feature folder (title and ticket id come from the branch,
otherwise from the spec title; pass `--title` / `--jira` if you know better):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/feature_dir.py --spec <spec path> --kind plan
```

Write `plan-summary.json` into the printed directory, following the `plan-summary.json`
section of `${CLAUDE_PLUGIN_ROOT}/schemas/data-model.md` exactly. Then:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py plan <dir>/plan-summary.json
```

It publishes `plan-summary.html` into the feature folder and refreshes its `index.md`.

## 5. Answer in the terminal

In the user's language, at most ~12 lines: the goal in one sentence, 3–5 key points the
developer must know (rules, contracts, decisions), the contradictions / gaps / open questions
as a short list, `words_in → words_out`, and the paths of `plan-summary.html` and `index.md` in the feature folder. No judgement of the plan.

`change-impact-score` later reuses the newest `plan-summary.json` built from the same plan
documents (its `expected_files`) for plan-vs-implementation drift; nothing else is needed.
