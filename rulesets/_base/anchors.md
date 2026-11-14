# Semantic rubric (all stacks)

You assess **criticality for review**, not correctness. A finding says "a reviewer must look
here, because…". Do not hunt for bugs line by line; when you notice a likely defect, report it as
a finding of the dimension it affects, with `confidence: inferred`.

## Points

| Points | Meaning | Typical example |
|---|---|---|
| 0 | Observed, no impact | Getter added to a DTO |
| 1 | Localised, low impact | Log message reworded; new field in an internal DTO; simple CRUD endpoint following an existing pattern |
| 2 | Meaningful change in one component | New validation rule; medium CRUD with paging/filtering; new query; side-logic change |
| 3 | Important behaviour or several components | Change of a business rule used by several flows; new integration call; public API field added/renamed; transaction scope changed |
| 4 | Core mechanism, broad blast radius | Pricing/discount/refund calculation changed; authorization rule changed; shared value object behaviour changed; event contract broken |
| 5 | Security boundary, data integrity, irreversible | Authorization bypass; authentication weakened; data loss or corruption possible; money moved incorrectly |

`critical: true` only when a wrong change here can cause a security incident, data loss/corruption,
money errors or an outage, **and** the diff shows it is plausible. Not every 4–5 is critical; a 3
is almost never critical.

## Simplicity has to be shown

- "Simple CRUD" (1 point) means: one entity, no business rules beyond field validation, no
  authorization change, no transaction/locking change, follows existing neighbouring code.
- Medium CRUD (2 points): paging/filtering/sorting, relations between entities, custom queries,
  mapping logic.
- Missing context is a limitation, not a reason for low points.

## Dimensions — what to look for

- **core_logic** — business rules, calculations, state transitions, workflows, shared domain
  services. Constants that encode business rules (limits, rates, windows) count.
- **error_handling** — swallowed exceptions, changed error mapping, generic exceptions instead
  of domain ones, missing cleanup, changed fallback.
- **concurrency** — shared mutable state (static/singleton collections), async misuse, locks,
  thread pools, scheduled/background jobs, lifecycle.
- **security** — authN/authZ, ownership checks, roles/policies, input validation on trust
  boundaries, crypto parameters, secrets, CORS/CSRF, anonymous endpoints, token handling.
- **data_integrity** — transaction boundaries, external calls inside transactions, multiple
  saves without a transaction, migrations (schema and data), idempotency, locking, cascade/
  orphan rules, rounding of stored amounts.
- **contracts** — REST request/response shapes, renamed/removed fields, status codes, event/
  message schemas and versions, public interfaces, serialization settings. Additive optional
  fields are 1–2; breaking changes 3–4.
- **integration** — external HTTP clients, messaging producers/consumers, retries, timeouts,
  circuit breakers, webhooks.
- **config_infra** — DI registrations, profiles/environment config, feature flags, startup,
  security config, deployment files.
- **architecture** — layer violations (controller → repository, domain → infrastructure),
  dependency direction, new cross-module coupling, responsibilities moved.
- **performance** — N+1, unbounded queries/collections, missing pagination, loops with I/O,
  blocking calls on hot paths, caching changes.
- **conventions** — deviation from the documented conventions (given in the batch header) and
  from 3–5 neighbouring files. Classify the deviation in `reason`: intentional/justified,
  valid new pattern, inconsistency, documented-standard violation, anti-pattern. A deviation is
  not automatically a defect: inconsistency 1–2, documented violation 2–3.
- **tests** — changed behaviour without tests, weakened tests (removed/loosened assertions,
  skipped tests, expected values bent to match new code), a "fix" that only changes the expected
  value — say whether the old or the new expectation matches the requirement.

## Certainty (every finding)

Give each finding `certainty` 0–100 — how sure you are the problem is real, after checking:

| certainty | when |
|---|---|
| 90–100 | you read the whole code path (incl. the called methods / config) and the problem is shown by it |
| 70–89 | strong evidence in the code you read; one assumption left unchecked — name it in `limitations` |
| 40–69 | plausible, but you did not read something decisive (callee, config, caller) |
| < 40 | a hunch — usually leave it out |

Findings below 70 are not counted and are shown to the reader as "to confirm". Prefer checking
over guessing: reading the callee usually turns a 50 into a 95 or into no finding at all.

## Output per file (semantic/batch-N.json)

```json
{
  "path": "…",
  "role": "What this file is for in the system — 1–2 sentences, more than its name says.",
  "interactions": {"called_by": ["…"], "calls": ["…"], "contracts": ["REST: POST /x", "Kafka: topic", "table: t"],
                   "changed_edges": ["names from the lists above whose interaction changed"]},
  "what_to_verify": ["2–3 concrete checks a reviewer can do, naming method/condition"],
  "findings": [{"dimension": "…", "points": 3, "critical": false, "title": "≤ 80 chars",
                "reason": "1–2 sentences: why it matters", "evidence": [{"path": "…", "line_start": 10, "line_end": 14,
                "side": "new", "snippet": "the relevant line(s)"}], "affected_symbols": ["Class.method"],
                "consequences": ["…"], "confidence": "verified|inferred", "certainty": 85,
                "limitations": []}],
  "adjust": [{"rule_id": "deterministic rule id", "points": 1, "critical": false,
              "reason": "why the deterministic score is wrong"}]
}
```

`critical` exists on findings and on `adjust`: set it explicitly. An adjust to 0–1 points always
clears it. A deterministic finding that is a false positive → `adjust` with `points: 0`.

- One finding per distinct concern. Do not repeat deterministic findings; use `adjust` to
  correct them (including down to 0 when a match is a false positive).
- `verified` only for what the diff/code shows directly; intent, consequences and likely bugs
  are `inferred`.
- Low-impact files still get `role` and may have zero findings.
- Never invent callers, tables or topics: list only what you saw in code you read.
- Before claiming a resource leak, missing close/cleanup, missing validation or missing error
  handling, **read the method the value is passed to** (and its library contract): many APIs
  close or validate for the caller. If you did not read it, the finding is `inferred` and must
  say what you did not check.
- Deleted files: say what was removed and whether something must replace it; do not re-review
  code that no longer exists.
