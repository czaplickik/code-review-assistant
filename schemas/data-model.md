# Data model

Contract between scripts, the model and the HTML renderers. All files are UTF-8 JSON.

Run directory: `<report_dir>/<DATE>-<JIRA>-<feature>/runs/<YYYYMMDD-HHMMSS>-<short-id>/`
(`report_dir` default `~/code-review-kb/{project}`). The feature folder holds `feature.json`
(identity + registry of published outputs), `index.md`, the published pages and `history/`.

| File | Written by | Read by |
|---|---|---|
| `analysis.json` | `collect_changes.py`, `triage.py`, `aggregate.py` | everything |
| `diffs/<n>.diff` | `collect_changes.py` | `show_diff.py`, model |
| `semantic/batch-<n>.json` | model (subagents) | `aggregate.py` |
| `flows.json` | model | `aggregate.py` |
| `impact-report.html` | `render_report.py` | developer |
| `plan-summary.json` / `.html` | model / `render_report.py` | developer, `aggregate.py` |
| `explanation-<slug>.json` / `.html` | model / `render_report.py` | developer |

## Enumerations

**Dimensions** (`dimension`):

| id | label | family |
|---|---|---|
| `core_logic` | Core Logic | logic |
| `error_handling` | Error Handling | logic |
| `concurrency` | Concurrency & State | logic |
| `security` | Security | security_data |
| `data_integrity` | Data Integrity | security_data |
| `contracts` | Contracts | contracts_integration |
| `integration` | Integration | contracts_integration |
| `config_infra` | Configuration & Infrastructure | contracts_integration |
| `architecture` | Architecture | quality |
| `performance` | Performance & Resources | quality |
| `conventions` | Convention Deviation | quality |
| `tests` | Tests & Verification | quality |

Families: `logic` (Logic), `security_data` (Security & Data), `contracts_integration`
(Contracts & Integration), `quality` (Quality & Structure).

**Review modes** (`verdict.mode`): `build+tests+static`, `ai-review-only`,
`ai+human-critical-paths`, `human-only`.

**File status**: `added`, `modified`, `deleted`, `renamed`. Untracked files are `added` with
`untracked: true`.

**Tier** (how deeply the file is analysed): `excluded`, `mechanical`, `light`, `deep`.

**Confidence**: `verified` (directly visible in the diff/code), `inferred` (model reasoning).

## Finding

```json
{
  "id": "f-0042",
  "rule_id": "java.security.method-security-changed",
  "source": "deterministic",
  "dimension": "security",
  "points": 4,
  "critical": true,
  "title": "Ownership check removed from refund endpoint",
  "reason": "@PreAuthorize changed from isOwner(#id) to hasRole('USER'); any user can refund any order.",
  "evidence": [
    {"path": "src/main/java/.../OrderController.java", "line_start": 54, "line_end": 56,
     "side": "new", "snippet": "@PreAuthorize(\"hasRole('USER')\")"}
  ],
  "affected_symbols": ["OrderController.refund"],
  "consequences": ["Horizontal privilege escalation"],
  "confidence": "verified",
  "limitations": []
}
```

`points` 0–5. `source`: `deterministic` | `semantic`. `side`: `new` | `old`.
`tags` (optional list): `weakened_test`, `migration_edited`, `drift`, `blast_radius`, `missing_test`,
`critical_module` — used by the review-mode policy and filters.
`id` is assigned by `aggregate.py`; the model omits it.

## analysis.json

```json
{
  "schema_version": 1,
  "generated_at": "2026-11-13T21:04:00",
  "report_dir": "docs/code-review/reports/20261113-210400-a1b2c3",
  "change": {
    "boundary": "uncommitted",
    "base_ref": "HEAD",
    "base_commit": "a1b2c3d",
    "branch": "develop",
    "stats": {"files": 23, "added_lines": 1210, "deleted_lines": 140, "untracked": 9,
              "modules": 5, "excluded": 1, "mechanical": 3},
    "rulesets": ["java-spring"],
    "sources": {
      "spec": ["docs/superpowers/specs/2026-11-10-order-refunds-design.md"],
      "plan": ["docs/superpowers/plans/2026-11-10-order-refunds.md"],
      "conventions": ["docs/architecture/conventions.md", "CLAUDE.md"],
      "missing": []
    }
  },
  "files": [
    {
      "path": "src/main/java/com/example/shop/order/OrderService.java",
      "old_path": null,
      "status": "modified",
      "untracked": false,
      "language": "java",
      "ruleset": "java-spring",
      "module": "order",
      "is_test": false,
      "added_lines": 180,
      "deleted_lines": 12,
      "diff_file": "diffs/0007.diff",
      "tier": "deep",
      "tier_reasons": ["critical deterministic finding", "fan-in 34"],
      "excluded_reason": null,
      "mechanical_kind": null,
      "symbols": ["OrderService"],
      "fan_in": 34,
      "fan_in_files": ["src/main/java/.../OrderController.java"],
      "largest_added_block": 152,
      "linked_tests": ["src/test/java/.../OrderServiceTest.java"],
      "test_changed": true,
      "in_plan": true,
      "plan_refs": ["docs/superpowers/plans/2026-11-10-order-refunds.md#task-3"],

      "role": "Application service orchestrating the order lifecycle: placement, payment, refunds.",
      "interactions": {
        "called_by": ["OrderController", "RefundController"],
        "calls": ["OrderRepository", "PaymentClient", "OrderEventPublisher"],
        "contracts": ["Kafka: order-events (OrderRefunded)", "table: refunds"],
        "changed_edges": ["PaymentClient", "table: refunds"]
      },
      "what_to_verify": [
        "Gateway call happens inside @Transactional — check rollback when the DB write fails."
      ],
      "flow": "refund-request",
      "semantic_done": true,

      "findings": [],
      "score": 17,
      "severity": 5,
      "severity_reach_bonus": false,
      "rank": 1,
      "critical": true,
      "dimensions": {"core_logic": 4, "data_integrity": 5, "integration": 3}
    }
  ],
  "groups": [
    {"id": "mech-1", "kind": "mechanical", "description": "Logger field replaced by @Slf4j",
     "files": ["..."], "sample_line": "-    private static final Logger log = ..."},
    {"id": "mech-2", "kind": "deleted_module", "root": "legacy-gateway", "description": "Module legacy-gateway deleted (120 files)",
     "files": ["..."], "dangling_refs": [{"path": "...", "line": 12, "snippet": "...", "symbol": "GatewayClient"}]}
  ],
  "flows": [
    {"id": "refund-request", "name": "Refund request", "description": "REST → service → gateway → DB → event",
     "files": ["...Controller.java", "...Service.java"], "max_score": 17}
  ],
  "plan_drift": {
    "unplanned_files": ["src/main/java/.../SecurityConfig.java"],
    "planned_not_changed": ["src/main/java/.../AuditLogService.java"],
    "planned_refs": {"src/main/java/.../AuditLogService.java": "docs/superpowers/plans/x.md#task-7"}
  },
  "verdict": {
    "mode": "ai+human-critical-paths",
    "policy_rule": "ai_human.key_dimension_points",
    "explanation": "Findings ≥ 3 points in security, data_integrity and core_logic.",
    "deciding_findings": ["f-0042", "f-0013"],
    "human_files": ["paths the human should read (ai+human-critical-paths only)"]
  },
  "ai_review_focus": ["Verify refund amount never exceeds captured amount (RefundService.calculate)."],
  "human_review": [{"path": "...", "status": "modified", "rank": 1, "reasons": ["finding title (4 pt, critical)"],
                    "questions": ["what_to_verify items"], "replaces": ["deleted paths whose logic moved here"]}],
  "limitations": ["No ruleset matched 2 files (scripts/*.ps1): base rules only."],
  "config": {"policy": {}, "tiers": {}}
}
```

Fields above the blank line in a file entry are filled by scripts; `role` … `semantic_done` by
the model (merged from `semantic/*.json` and `flows.json`); `findings` … `dimensions` by
`aggregate.py`.

Ranking (computed by `aggregate.py`, stored as `rank`; excluded files have `rank: null`):
`critical` desc, then `severity` desc (the file's most serious finding, +1 when the file has
fan-in ≥ `ranking.reach_fan_in` or the finding is in a reach dimension such as contracts; max 5),
then `score` desc, then `added_lines + deleted_lines` desc, then path. `score` stays the plain sum.

## semantic/batch-<n>.json (written by the model)

```json
{
  "batch": 3,
  "files": [
    {
      "path": "src/main/java/com/example/shop/order/OrderService.java",
      "role": "1–2 sentences: what this file is for in the system.",
      "interactions": {"called_by": [], "calls": [], "contracts": [], "changed_edges": []},
      "what_to_verify": ["2–3 concrete checks"],
      "findings": [ { "...finding without id, source = semantic..." } ],
      "mechanical_confirmed": null
    }
  ]
}
```

`adjust` (optional): `[{"rule_id": "...", "points": 0-5, "critical": bool?, "reason": "..."}]` corrects a
deterministic finding on the same file (e.g. down to 0 for a false positive).

`mechanical_confirmed`: for files with tier `mechanical`, `true` if the sample confirms the
change is purely mechanical, `false` (plus findings) otherwise; `null` for other tiers.

## flows.json (written by the model)

```json
{"flows": [{"id": "refund-request", "name": "Refund request",
            "description": "short", "files": ["ordered by execution"]}]}
```

Every non-excluded file belongs to at most one flow. Files without a flow are shown under
"Other changes".

## plan-summary.json (written by the model)

```json
{
  "schema_version": 1,
  "title": "Order refunds",
  "sources": [{"path": "docs/superpowers/specs/x.md", "kind": "spec", "words": 3120}],
  "goal": "One paragraph.",
  "requirements": [{"id": "R1", "text": "short", "kind": "functional|non_functional|security",
                    "ref": "x.md#refund-window"}],
  "business_rules": [{"id": "B1", "text": "...", "ref": "..."}],
  "contracts": [{"kind": "rest|event|db|external", "name": "POST /api/orders/{id}/refunds",
                 "change": "new|modified|removed", "details": "...", "ref": "..."}],
  "decisions": [{"text": "...", "rationale": "...", "ref": "..."}],
  "constraints": [{"text": "...", "ref": "..."}],
  "acceptance_criteria": [{"text": "...", "ref": "..."}],
  "edge_cases": [{"text": "...", "ref": "..."}],
  "stages": [{"name": "Task 1: ...", "files": ["path"], "ref": "..."}],
  "testing_strategy": [{"text": "...", "ref": "..."}],
  "risks": [{"text": "...", "ref": "..."}],
  "expected_files": [{"path": "...", "action": "create|modify|delete", "ref": "..."}],
  "components": {
    "nodes": [{"id": "refund-svc", "label": "RefundService", "layer": "api|application|domain|data|external|messaging",
               "status": "new|modified|existing"}],
    "edges": [{"from": "refund-ctl", "to": "refund-svc", "label": "calls", "status": "new|modified|existing"}]
  },
  "sequence": {
    "title": "Main scenario",
    "participants": [{"id": "client", "label": "Client"}],
    "steps": [{"from": "client", "to": "api", "label": "POST /refunds", "note": null}]
  },
  "findings": {
    "contradictions": [{"text": "...", "refs": ["spec#a", "plan#b"]}],
    "unaddressed_requirements": [{"text": "...", "refs": []}],
    "unrequired_plan_items": [{"text": "...", "refs": []}],
    "open_questions": [{"text": "...", "refs": []}]
  },
  "cut": {"words_in": 6100, "words_out": 900}
}
```

`ref` format: `<relative path>#<heading slug>`; renderers show it as path + section.

## explanation-<slug>.json (written by the model, only when HTML output was requested)

```json
{
  "schema_version": 1,
  "target": {"path": "...", "symbol": "RefundService.calculate", "line_start": 40, "line_end": 120},
  "diff": "unified diff of the selected hunk(s)",
  "what_changed": "...",
  "why": [{"type": "explicit|inferred|technical-necessity|unknown", "text": "...", "refs": ["spec#x"],
           "quote": "≤ 2 sentences quoted from the source, or null"}],
  "context": ["..."],
  "impact": ["..."],
  "worth_checking": ["..."],
  "dependencies": {"nodes": [{"id": "", "label": "", "status": "new|modified|existing"}],
                   "edges": [{"from": "", "to": "", "label": "", "status": "new|modified|existing"}]},
  "sequence_before": null,
  "sequence_after": {"title": "", "participants": [], "steps": []}
}
```

## Reviews (ai-review, security-review, spec-review)

Each review writes into its own sub-directory of the report directory:
`<report_dir>/review-<kind>/` with `kind` = `ai` | `security` | `spec`.

| File | Written by | Read by |
|---|---|---|
| `scope.json` | `review_scope.py` | model, `merge_review.py` |
| `candidates.json` | `review_scope.py` (deterministic hints) | model |
| `batch-<n>.json` | model (subagents) | `merge_review.py` |
| `spec-matrix.json` | model (spec only) | `merge_review.py` |
| `review.json` | `merge_review.py` | `render_report.py review` |
| `review.html` | `render_report.py review` | developer |
| `review.md` | `merge_review.py` | a fixing session (hand-off checklist) |

**Severity**: `blocker` (must fix before merge: wrong behaviour, security hole, data loss,
requirement violated), `major` (should fix: convention/design problem with real cost, missing
test for changed behaviour), `minor` (worth fixing: readability, small inconsistency),
`info` (observation, question).

**Categories**
- ai: `conventions`, `consistency`, `reinvention`, `dead_code`, `overengineering`,
  `ai_artifacts`, `tests`, `error_handling`, `resources`, `performance`, `readability`
- security: `authz`, `authn`, `input_validation`, `injection`, `secrets`, `crypto`,
  `data_exposure`, `ssrf`, `deserialization`, `config`, `dependencies`, `logging`
- spec: `requirement`, `business_rule`, `decision`, `contract`, `unrequested`, `test_gap`

### Review finding (batch files and review.json)

```json
{
  "id": "R-012",
  "category": "reinvention",
  "severity": "major",
  "title": "New MoneyFormatter duplicates Money.format",
  "description": "1–3 sentences: what is wrong and why it matters here.",
  "path": "src/.../RefundService.java",
  "line_start": 120, "line_end": 134,
  "snippet": "relevant new code (≤ 15 lines)",
  "related": [{"path": "src/.../Money.java", "line_start": 40, "line_end": 52, "note": "existing implementation"}],
  "suggestion": "what to do instead, in words (no patch)",
  "refs": ["docs/architecture/conventions.md#exceptions", "spec.md#fr-3-refund-amount-cap"],
  "confidence": "verified|inferred",
  "candidate": "C-007 or null (deterministic hint that led to it)"
}
```

`id` is assigned by `merge_review.py`; the model omits it.

### batch-<n>.json

```json
{"batch": 1, "files_reviewed": ["paths"], "findings": [ ... ],
 "dismissed_candidates": [{"candidate": "C-003", "reason": "used via reflection in X"}]}
```

Every path of the batch must be in `files_reviewed`. Every candidate assigned to the batch must
end up either in a finding (`candidate` field) or in `dismissed_candidates`.

### spec-matrix.json (spec-review only)

```json
{
  "sources": ["docs/superpowers/specs/x.md", "docs/superpowers/plans/x.md"],
  "requirements": [
    {"id": "FR-3", "text": "short", "ref": "spec#fr-3",
     "status": "implemented|partial|missing|contradicted|unclear",
     "tested": "yes|partial|no",
     "evidence": [{"path": "", "line_start": 0, "line_end": 0, "note": ""}],
     "note": "why this status (1–2 sentences)"}
  ],
  "decisions": [
    {"text": "Gateway call outside DB transaction", "ref": "plan#task-5",
     "status": "followed|deviated|not_applicable|unclear", "evidence": [], "note": ""}
  ],
  "examples": [
    {"rule": "FR-4 pro-rata", "input": "lines 100 + 10, 20% discount, refund the 100 line",
     "expected": "80.00", "actual": "89.00", "evidence": [], "match": false}
  ],
  "unrequested": [{"text": "Product price cache", "evidence": [], "note": ""}]
}
```

### review.json (merged)

```json
{
  "schema_version": 1, "kind": "ai|security|spec", "generated_at": "", "report_dir": "",
  "change": { "...": "copied from analysis.json change" },
  "scope": {"files": 25, "reviewed": 25, "mechanical_groups_sampled": 1, "excluded": 2},
  "summary": {"blocker": 1, "major": 6, "minor": 4, "info": 2},
  "findings": [ ... ],
  "files": [{"path": "", "role": "", "findings": ["R-001"]}],
  "spec": { "...": "spec-matrix.json content, spec-review only" },
  "limitations": [""]
}
```
