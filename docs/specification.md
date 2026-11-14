# Code Review Assistant – Product Specification

**Version:** 1.1
**Target platform:** Claude Code
**Integration:** Superpowers (optional)
**Artifact type:** Claude Code Plugin
**Status:** iterative — expected to change after each round of real-world use

### Changes since 1.0

- Specification reorganised around the developer's review workflow (Stages 0–3).
- Added the **review mode verdict** (4 modes) as the first output of the impact report.
- Replaced L0–L4 levels with **additive rule points (0–5)** and a **critical flag**.
- Added **language rulesets** (Java/Spring, .NET) and layered project configuration (`rules.yaml`).
- Defined the change boundary: uncommitted changes + untracked files, with an optional base branch.
- `change-plan-summary` only condenses, it does not evaluate. Visuals replace text wherever possible.
- `change-explanation` answers in the terminal by default; the user picks the output form.
- Added plan-vs-implementation drift, weakened-test detection, the JSON analysis model and the test fixture set.
- Removed clickable IDE references, time budgeting and running builds/tests from scope.

---

# 1. Objective

Help a developer review a change produced by AI (or by hand) by answering, in order:

1. **Before implementation:** what does this spec and plan actually say? (Stage 0)
2. **At review start:** how much human attention does this change need? (Stage 1)
3. **During manual review:** which files first, and why each of them matters? (Stage 2)
4. **When something is unclear:** why was this changed, and what does it affect? (Stage 3)

The plugin does **not** review code for bugs and does **not** replace human or AI code review.
It assesses criticality and directs attention. Bug hunting is delegated to existing tools
(e.g. Claude Code `/code-review`), build/test/static analysis is run by the developer.

# 2. Workflow and Skills

| Stage | When | Skill | Output |
|---|---|---|---|
| 0 | Spec and plan written, before implementation | `change-plan-summary` | HTML summary with diagrams |
| 1 | Implementation done, review starts | `change-impact-score` | Review mode verdict (top of the HTML report) |
| 2 | Manual review | `change-impact-score` | Ranked file list with per-file rationale (same report) |
| 3 | A change is unclear | `change-explanation` | Terminal answer, optional HTML with diagrams |
| 4 | AI review of the change | `ai-review`, `security-review`, `spec-review` | HTML report + `review.md` fix list |
| — | Once per project | `review-init` | `docs/code-review/rules.yaml` |
| — | Once per machine | `configure` | knowledge-base folder for all projects |

Stages 1 and 2 are one skill producing one report: the verdict is the first thing on the page,
the ranking follows.

# 3. Shared Foundation

## 3.1. Change Boundary

Default: **uncommitted changes against `HEAD`**:

- staged + unstaged modifications and deletions (`git diff HEAD`),
- **untracked files** that are not ignored (`git ls-files --others --exclude-standard`) — AI-created
  files are usually untracked and must never be missed,
- renames detected (`-M`).

Optional: a base branch (`develop` or a branch given by the user). The boundary then becomes
`merge-base(<base>, HEAD)` → working tree, i.e. committed branch work + uncommitted changes + untracked.

## 3.2. Data Sources

| Source | Use | Required |
|---|---|---|
| Change boundary (3.1) | What changed | yes |
| Repository | Neighbouring code, references, conventions | yes |
| Spec / plan documents | Requirements, decisions, expected files | no |
| Project docs (`CLAUDE.md`, `docs/architecture/**`) | Documented conventions | no |
| Git history | Historical context for explanations | no |

Missing optional sources reduce capability, never block. Every report lists what was missing.

## 3.3. Spec and Plan Discovery

Spec and plan documents are discovered **from the change itself**: files in the change boundary
located under the configured spec/plan directories
(default `docs/superpowers/specs/` and `docs/superpowers/plans/`).

- Several matches → all are used; the report lists which.
- No match → the analysis runs without them and states so.
- The user can pass paths explicitly, which overrides discovery.
- Stage 0 runs before implementation, so its inputs are typically untracked working-tree files.

No dependency on undocumented Superpowers internals: only the documents on disk are read.

## 3.4. Analysis Principles

- Never classify based on file names or paths alone. Paths and annotations are signals that
  direct analysis, semantics decide.
- Distinguish functional, mechanical and refactoring changes.
- Simple CRUD is not automatically low-risk: "simple" must be established (no business rules,
  no auth, no transaction or contract changes).
- Never assume generated code is correct.
- Absence of evidence is not evidence of absence.
- Every finding has concrete evidence. Verified facts and inferences are labelled differently.
- Never invent dependencies, references or implementation intentions.

## 3.5. Pipeline

Cost is controlled by doing deterministic work first and spending model attention where it matters.

1. **Collect** (script): change boundary, per-file stats, hunks, renames, untracked files.
2. **Triage** (script + ruleset): mechanical-change detection (rename only, whitespace, imports,
   generated files, lockfiles), deterministic signals (annotations, attributes, migration files,
   test↔production mapping, fan-in, largest added block), excluded paths.
3. **Light semantic pass** (model): every non-excluded file, batched; mechanical groups assessed
   as groups.
4. **Deep pass** (model): top-N files and every file with a critical finding — evidence,
   dependencies, consequences, "what to verify".
5. **Aggregate** (script): score, verdict, rankings, flows, plan drift.
6. **Render** (script): HTML from the analysis JSON. The model never writes report HTML.

Every file appears in the report: excluded and mechanically-assessed files are listed with the
reason they were not analysed deeply.

## 3.6. Analysis Model (JSON)

All skills read and write one model, stored per run in
`<feature folder>/runs/<timestamp>-<short-id>/analysis.json` (see 10.1). A JSON Schema ships with the
plugin (`schemas/analysis.schema.json`). Core entities:

- **change** — boundary, base, stats, rulesets used, sources found/missing.
- **file** — path, change type, language, ruleset, role summary ("what this file is for"),
  symbols changed, fan-in, largest added block, linked tests, findings, score, critical flag,
  "what to verify" (2–3 items), interactions (callers/callees for the diagram).
- **finding** — `rule_id`, `dimension`, `points` (0–5), `critical` (bool), `reason`, `evidence`
  (path + line range + snippet), `affected_symbols`, `consequences`, `confidence`
  (`verified` | `inferred`), `limitations`.
- **flow** — named group of files forming one execution path (e.g. endpoint → service →
  repository → event), ordered by execution.
- **plan** — requirements, decisions, expected files, extracted from spec/plan with source refs.
- **plan_drift** — files changed but not in the plan, planned items not implemented.

File-level results are cached by content hash, so re-running after fixes only re-analyses
files that changed again.

# 4. Rules, Scoring and Dimensions

## 4.1. Dimensions

Findings belong to one of twelve dimensions (areas to analyse unchanged from 1.0):

| Family (overview) | Dimensions |
|---|---|
| Logic | Core Logic, Error Handling, Concurrency & State |
| Security & Data | Security, Data Integrity |
| Contracts & Integration | Contracts, Integration, Configuration & Infrastructure |
| Quality & Structure | Architecture, Performance & Resources, Convention Deviation, Tests & Verification |

The overview shows four families; drill-down shows all twelve.

## 4.2. Rules and Points

A **rule** describes one risk signal. When it fires on a file it produces a finding worth
**0–5 points**:

| Points | Meaning |
|---|---|
| 0 | Observed, no meaningful impact (kept for traceability) |
| 1 | Localised, low impact |
| 2 | Meaningful change within one component |
| 3 | Important application behaviour or several components affected |
| 4 | High: core mechanisms, broad blast radius |
| 5 | Critical: security boundary, data integrity, irreversible effects |

Rules may set a fixed number of points or a range the model chooses from using the rule's anchor
examples. A rule may be marked **`critical: true`**: a finding from it flags the file as critical.

Rule kinds:
- **deterministic** — evaluated by scripts (e.g. "applied migration edited", "`@Disabled` added",
  "fan-in > 50", "added block > 150 LOC");
- **semantic** — evaluated by the model with a rubric and anchor examples.

## 4.3. File Score

- **Score** = sum of points of all findings on the file.
- **Ranking**: critical files first, then by **severity** — the file's most serious finding —
  and only then by score. One severe finding outranks many small ones. Severity gets +1
  (max 5) when the change has reach: the file is referenced from ≥ 10 files, or the finding
  breaks a contract that crosses component boundaries (configurable under `ranking`).
- **Dimension value** for the heatmap = highest points among the file's findings in that dimension.
- Inferred findings count fully but are visibly marked. Weighting by confidence is a
  `rules.yaml` option.

## 4.4. Mandatory Built-in Signals

| Signal | Kind | Notes |
|---|---|---|
| Fan-in of changed symbols | deterministic | number of referencing files, shown on the file |
| Largest contiguous added block | deterministic | drift risk of long generated code |
| Test ↔ production mapping | deterministic | changed behaviour without changed test |
| **Weakened tests** | deterministic + semantic | removed/loosened assertions, `@Disabled`, `[Fact(Skip)]`, `@Ignore`, deleted tests, expected values bent to fit the code — never counts as a "test fix" |
| Edited already-applied migration | deterministic | critical |
| Convention deviation | semantic | compared with documented conventions **and** 3–5 neighbouring files in the same package/namespace; intentional new patterns are distinguished from inconsistencies |
| Plan drift | deterministic + semantic | file outside the plan, plan item without implementation |

# 5. Language Rulesets

Knowledge about a stack lives in data files, not in scripts.

```text
rulesets/
├── _base/                 # stack-independent rules, rubric, anchors
├── java-spring/
│   ├── detect.yaml        # pom.xml, build.gradle(.kts), *.java
│   ├── signals.yaml       # @Transactional, @PreAuthorize, SecurityFilterChain, Flyway/Liquibase,
│   │                      # @KafkaListener, @Async, JPA entities, @Disabled …
│   ├── references.yaml    # how to find fan-in: imports, FQCN usage, Spring bean injection
│   ├── anchors.md         # point examples per rule
│   └── conventions.md     # default conventions when the project documents none
└── dotnet/
    ├── detect.yaml        # *.csproj, *.sln, *.cs
    ├── signals.yaml       # [Authorize]/[AllowAnonymous], policies, DbContext, EF Migrations,
    │                      # BackgroundService, HttpClient, .Result/.Wait(), [Fact(Skip)] …
    ├── references.yaml    # usings, type usage, DI registrations
    ├── anchors.md
    └── conventions.md
```

- A ruleset is selected **per file**, so a repository mixing Java and .NET works.
- Each ruleset extends `_base`.
- A file with no matching ruleset is analysed with `_base` only, with reduced confidence
  reported.
- Adding a language = adding a ruleset directory; no script changes.

## 5.1. Project Configuration

Configuration is layered; later layers override earlier ones:

1. Plugin rulesets (auto-detected).
2. **`docs/code-review/rules.yaml`** in the project (committed, shared with the team):
   mode thresholds, point overrides, extra rules, critical modules, excluded paths,
   spec/plan directories, default base branch, report directory.
3. Arguments of the skill invocation (e.g. base branch, explicit spec/plan paths).

`review-init` detects the stack and generates a commented `rules.yaml` with defaults.
Without it, the plugin runs on the defaults.

# 6. Stage 0 – `change-plan-summary`

## 6.1. Purpose

Condense a long spec and plan so the developer can read only what matters and correct the plan
before implementation. **The skill does not evaluate the plan** — no verdict, no quality score.

## 6.2. Input

Discovered spec/plan files (3.3) or explicit paths. Feature specs, requirement docs,
implementation plans, design and decision documents.

## 6.3. What Is Kept

Budget: at most 10% of the input words (hard cap 600 words).

Kept: goal (2–3 sentences), up to 8 design-shaping requirements, up to 5 business rules,
every new or changed contract (API, event, table, external call), up to 5 technical decisions,
stages at component level, the two diagrams.

Cut: edge cases, testing strategy, risks, acceptance criteria, constraints, file lists,
restatements, boilerplate, background, glossary, stakeholders, rollout prose, non-goals,
alternatives, non-functional details that do not change the design, filler. A requirement the
plan ignores is surfaced as a gap instead.

Surfaced as facts (not judgements): contradictions between spec and plan, requirements without a
plan step, plan steps without a requirement, questions left open.

## 6.4. Output

HTML report, visual first:
- one-paragraph goal,
- component diagram of the planned change (existing vs new vs modified components),
- flow/sequence diagram of the main scenario,
- short tables for requirements, business rules, contracts, decisions — each row with a
  reference to the source file and section,
- stages at component level,
- contradictions / gaps / open questions as a short list.

The summary never reproduces whole sections and never fills gaps with invented content.

# 7. Stage 1 – Review Mode Verdict (`change-impact-score`)

## 7.1. Modes

| Mode | Typical changes |
|---|---|
| `build+tests+static` | Renames, typos, simple CRUD, test fixes, simple script fixes |
| `ai-review-only` | Simple to medium CRUD, standard changes in a small number of files with moderate LOC, side (non-core) application logic |
| `ai+human-critical-paths` | Anything beyond the above that is not `human-only`; the human reads the critical files and flows, AI reviews the rest |
| `human-only` | Critical security, data-integrity or core mechanisms affected broadly |

## 7.2. Policy

The verdict is produced by a **deterministic policy** over findings, defined in `rules.yaml`
(defaults shipped by the plugin), never by free model judgement. Default policy, evaluated top
down:

1. Any critical finding in Security or Data Integrity spread across ≥ 3 files, or any finding
   with 5 points in Security / Data Integrity — **and** critical files make up ≥ 25% of the
   change → `human-only`. When critical issues are concentrated in a few files of a large
   change (e.g. 3 real changes hidden in 200 mechanical ones), reading everything is wasted
   effort: the human reads the critical files instead (rule 2).
2. Any critical finding, or any finding ≥ 3 points in Core Logic, Security, Data Integrity or
   Contracts → `ai+human-critical-paths`.
3. Only findings ≤ 2 points, change within the configured file/LOC limits, no contract change →
   `ai-review-only`.
4. Only mechanical changes, findings ≤ 1 point, and no weakened tests → `build+tests+static`.

A weakened test always lifts the mode to at least `ai-review-only`.
Reaching mode 3 or 4 requires positive evidence of simplicity — absence of findings because of
missing context is not enough.

## 7.3. Output (top of report)

- the mode, with the 3–5 findings that decided it (the policy rule that fired is named),
- size: files, added/deleted LOC, components, modules, contracts touched,
- dimension profile (radar or bar per family),
- module treemap (size = LOC changed, colour = highest points),
- for `ai-review-only` and `ai+human-critical-paths`: a ready-to-use list of focus points to
  hand to an AI reviewer,
- limitations: missing sources, unmatched rulesets, low-confidence areas.

# 8. Stage 2 – File Ranking (`change-impact-score`)

## 8.1. Ranked List

- Default view: **flows**, ordered by their highest file score; files inside a flow in execution
  order — to understand the change end to end.
- Toggle: pure ranking (critical first, then score).
- Views filtered by dimension (e.g. security-only, core-logic-only).
- Heatmap: files × dimensions.
- The developer decides how much to read; the plugin does not budget time.

## 8.2. Per-File Row

Collapsed: path, score, critical flag, change type, top 1–2 reasons, dimension chips.

Expanded:
- **What this file is for** — 1–2 sentences on the file's role in the system, beyond what the
  source tree tells.
- **Interaction diagram** — who calls it, what it calls, which contracts/events/tables it
  touches; changed edges highlighted.
- **Why review it** — findings with points, evidence snippet (before/after), confidence.
- **What to verify** — 2–3 concrete checks.
- Fan-in, largest added block, linked tests, plan reference (or "not in plan").

## 8.3. Plan vs Implementation

When a plan was found: changed files not in the plan, planned items with no corresponding
change, both linked to the plan section.

# 9. Stage 3 – `change-explanation`

## 9.1. Invocation

On demand for a file, class, method, code section or hunk.

Before answering, the skill asks the user (AskUserQuestion) for the output form:
- terminal only (default, recommended for a quick answer),
- terminal + HTML with diagrams (before/after sequence or dependency diagram, spec excerpts).

## 9.2. Sources, in order

Spec → plan → related changes in the same change set → existing code and dependencies →
git history (when relevant). Reuses `analysis.json` when available, so it starts from the
already-known findings for the file.

## 9.3. Structure

- **What changed** — the actual modification.
- **Why** — with reason type: `explicit` (quoted from spec/plan, with reference),
  `inferred`, `technical-necessity`, or `unknown`.
- **Context** — requirements, decisions, related components.
- **Impact** — consequences and blast radius.
- **Worth checking** — open questions for the reviewer.

The skill never invents intentions; `unknown` is a valid answer.

# 9a. Stage 4 – AI Reviews

Three independent skills for the AI part of the review. Each always reviews the **whole
change** (they are general-purpose; the impact verdict does not narrow them), reports only and
never edits code, and writes `review-<kind>/review.html` plus `review-<kind>/review.md` — a
checklist to paste into a fixing session.

| Skill | Checks |
|---|---|
| `ai-review` | project rules and conventions, consistency with neighbouring code, reinvented helpers and duplicated logic, dead code, unrequested/over-engineered code, AI artifacts (non-existent APIs, stubs, tests bent to the code), tests, error handling, resources, performance, readability |
| `security-review` | entry-point inventory, authorization incl. ownership (IDOR), authentication/tokens, input validation, injection, secrets, crypto, data exposure, SSRF, deserialization, security config, dependencies, sensitive logging, security requirements of the spec |
| `spec-review` | requirements matrix (implemented / partial / missing / contradicted / unclear, tested?), plan decisions followed/deviated, business rules verified with worked examples, unrequested behaviour, contract mismatches |

Mechanics: `scripts/review.py prepare <kind>` collects and triages the change (reusing an
impact report of the identical change), computes deterministic candidates (possible dead code,
debug output, TODO/stubs, duplicated blocks, new helper classes, new dependencies, entry points,
removed security lines, sensitive logging, plan drift) and batches. Subagents review batches
against the checklists in `rulesets/*/review-<kind>.md` and must confirm or dismiss every
candidate. `review.py merge` validates and writes `review.json` and `review.md`.
Mechanical groups are reviewed through 2 sample files each. Severity: blocker / major / minor /
info. Spec and plan are found in the change or — when committed before implementation — as the
newest documents in the spec/plan directories.

# 10. Reports

## 10.1. Location — knowledge base

Reports form a knowledge base outside the repository: `report_dir`, default
`~/code-review-kb/{project}/` (`~` and `{project}` expanded; a relative path is relative to the
repository root). The folder is a plugin-wide setting chosen once with the `configure` skill
(`~/.config/code-review-assistant/config.yaml`). Precedence: project `rules.yaml` >
`CODE_REVIEW_KB` environment variable > user config > plugin default. One folder per feature, named `{DATE}-{JIRA_ID}-{FEATURE}`:

- `JIRA_ID` from the branch name (or the first lines of the spec); omitted when unknown.
- `FEATURE` from the branch name; on generic branches (`develop`, `main`) from the spec title;
  otherwise a short title the skill derives from the changed code (`--title`), with a
  deterministic fallback from the changed file names.
- `DATE` is the day the folder was created; later runs for the same ticket (or the same
  non-generic branch / title) reuse the folder.

Contents: `index.md` (overview note with frontmatter — ticket, feature, branch, review mode,
blocker counts — goal, plan contradictions, review mode, top files, review table, blockers,
links; rebuilt on every publish), the latest pages (`plan-summary.html`, `impact-report.html`,
`review-<kind>.html` + `review-<kind>.md`, `explanation-*.html`), `history/` with previous
versions and `runs/` with working data. The folder can be opened in a browser, Finder or as an
Obsidian vault (markdown notes, frontmatter for Dataview/Bases; HTML via a viewer plugin or the
browser). `docs/code-review/rules.yaml` stays in the repository and is meant to be committed.

## 10.2. Technical Requirements

- One self-contained HTML file per report, works offline, no backend.
- Inline CSS and JS. Third-party JS libraries (diagrams, graphs) are allowed only **vendored
  and inlined** in the file — no CDN.
- Data embedded as JSON and rendered client-side; must stay responsive with 200+ files.
- Shared design system across reports.

## 10.3. Principles

- **Visual over text** wherever a picture explains faster: diagrams, heatmaps, treemaps,
  graphs, tables. Prose only for what cannot be drawn.
- Key information first; details collapsed until requested.
- Search, filter, sort, expand; copyable snippets.
- Verified vs inferred always visually distinct.
- No repetition across sections.

# 11. Architecture

```text
code-review-assistant/
├── .claude-plugin/plugin.json
├── skills/
│   ├── change-impact-score/SKILL.md
│   ├── change-explanation/SKILL.md
│   ├── change-plan-summary/SKILL.md
│   └── review-init/SKILL.md
├── rulesets/              # see section 5
├── schemas/
│   └── analysis.schema.json
├── scripts/
│   ├── collect_changes.py     # boundary, stats, hunks, untracked
│   ├── triage.py              # mechanical detection, deterministic rules
│   ├── references.py          # fan-in per ruleset
│   ├── aggregate.py           # score, verdict policy, flows, plan drift
│   └── render_report.py       # analysis.json → HTML
├── templates/
│   ├── impact-report.html
│   ├── plan-summary.html
│   ├── explanation.html
│   └── shared/            # CSS, JS, vendored libraries
├── test-fixtures/         # see section 13
└── README.md
```

Scripts: Python 3 standard library only, no install step. Logical structure, not a prescription —
prefer the simplest reliable approach Claude Code supports.

# 12. Non-Functional Requirements

- **Performance:** only the change boundary plus selectively loaded neighbours; never the whole
  repository in context; cache per file hash.
- **Reliability:** no fabricated references; every finding traceable to evidence; missing
  context reported.
- **Consistency:** two runs on the same change produce the same verdict and the same top-10
  (order within ties may differ).
- **Maintainability:** stack knowledge in rulesets; scripts generic; rules extensible.
- **Compatibility:** standard Claude Code plugin conventions; works with or without Superpowers.

# 13. Validation

`test-fixtures/` contains scenario repos with planted changes and ground truth.
`./setup.sh <scenario>` builds a throwaway git repo in `test-fixtures/sandbox/<scenario>` with the
change left uncommitted.

| Scenario | Expected mode | Exercises |
|---|---|---|
| `java-00-plan-only` | — | Stage 0 summary, contradictions, gaps |
| `java-01-trivial` | `build+tests+static` | mechanical detection, test fix ≠ weakening |
| `java-02-category-crud` | `ai-review-only` | CRUD that is not trivial |
| `java-03-order-refunds` | `ai+human-critical-paths` | all dimensions, plan drift, conventions, weakened tests |
| `java-04-auth-rewrite` | `human-only` | security boundaries, data rewrite |
| `java-05-large-refactor` | `ai+human-critical-paths` | 200+ files, 3 real changes hidden in mechanical noise |
| `dotnet-01-trivial` | `build+tests+static` | .NET ruleset, mechanical detection |
| `dotnet-02-customer-crud` | `ai-review-only` | .NET CRUD |
| `dotnet-03-payment-reconciliation` | `ai+human-critical-paths` | branch + uncommitted boundary, concurrency, integration, contracts |

Each scenario's `EXPECTED.md` lists the expected mode, top files, must-detect signals and traps.
A run passes when the mode matches, the critical files are in the top 5, every must-detect signal
is present and no trap is in the top 10. Fixtures are extended with real historical PRs over time.

# 14. Acceptance Criteria

1. All four skills are available in Claude Code.
2. The change boundary includes untracked files; an optional base branch works.
3. The impact report opens with a review mode verdict and the findings that decided it.
4. Every file in the boundary appears in the report, with findings or with the reason it was
   excluded/assessed mechanically.
5. Every finding has points, dimension, evidence and confidence.
6. Files are ranked critical-first, then by additive score; flow view and dimension filters work.
7. Expanded file rows show role, interaction diagram, reasons and what to verify.
8. Weakened tests and edited applied migrations are always detected.
9. Java/Spring and .NET rulesets work, including in one mixed repository.
10. `rules.yaml` overrides thresholds, points and exclusions.
11. The plan summary keeps what matters with source references, includes diagrams and does not
    evaluate the plan.
12. The explanation skill asks for the output form and labels reason types.
13. All fixture scenarios pass (section 13), including the 200+ file scenario.
14. Reports are self-contained, offline, and responsive with 200+ files.

# 15. Out of Scope

- Fixing code (all review skills report only; `review.md` is handed to a fixing session).
- Running build, tests or static analysis.
- Time budgeting of the review.
- Clickable IDE links.
- Modifying or replacing Superpowers skills.

# 16. Implementation Order

1. **Foundation:** analysis schema, `collect_changes.py`, `_base` ruleset, `rules.yaml` loading,
   fixtures.
2. **Stage 1–2 core:** triage, references, scoring, verdict policy, `change-impact-score` with a
   minimal report. Validate against fixtures from here on.
3. **Rulesets:** `java-spring`, `dotnet`, `review-init`.
4. **Report:** heatmap, treemap, flows, interaction diagrams, filters.
5. **Stage 0:** `change-plan-summary`, plan extraction reused for plan drift.
6. **Stage 3:** `change-explanation`.
7. **Calibration:** real PRs, consistency check, false positive / negative review, cost tuning.

# 17. Design Principles

1. Prioritise developer attention, not code volume.
2. Decide the review mode first, then rank.
3. Explain why a file matters, with evidence.
4. Draw instead of writing wherever possible.
5. Deterministic tooling for repository facts, model reasoning for semantics, deterministic
   policy for decisions.
6. Never fabricate rationale, references or dependencies.
7. Do not duplicate what Claude Code, Superpowers or AI review tools already do.
