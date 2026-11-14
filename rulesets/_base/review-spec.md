# Spec review guide (all stacks)

Goal: a critical check that the implementation does what the spec requires and follows the
decisions and assumptions of the plan — not more, not less, not differently.

## Sources

- Spec and plan named in the scope (also when they were committed before the change).
- A `plan-summary.json` from `change-plan-summary`, if one exists for the same documents,
  is a good starting list of requirements — but always verify against the documents.

## 1. Requirements matrix

For every requirement that affects code (functional, security, data, contract, and
non-functional ones with code impact such as audit logging, metrics, flags):
- find the implementing code (Grep for domain terms, endpoints, error codes, field names),
- set `status`: `implemented` (all parts present and correct), `partial`, `missing`,
  `contradicted` (code does something the requirement forbids or the opposite of it),
  `unclear` (cannot be determined from the code — say what is missing),
- set `tested`: is there a test that would fail if the requirement were broken?
- give evidence (file + lines) and a 1–2 sentence note.

## 2. Decisions and assumptions

For every technical decision or assumption in the spec/plan (transaction boundaries, ordering
of calls, idempotency, versioning, layering, "existing X stays unchanged", "no rename"):
`followed` / `deviated` / `not_applicable` / `unclear`, with evidence. Treat deviations
critically: does the code silently rely on an assumption the spec does not make?

## 3. Worked examples

For each business rule with a formula or limit, compute **2–3 concrete examples by hand from
the spec** (including the examples the spec/plan give) and trace what the code would return
for the same input. Record expected vs actual; a mismatch is a `blocker` finding in
`business_rule`.

## 4. Unrequested behaviour

Code that implements something no requirement asks for (extra endpoints, caches, config,
statuses, events, side effects) → `unrequested` entries, and a finding when it adds risk.

## Findings

Write findings for everything that is not `implemented`/`followed` and matters:
- `requirement` — missing / partial / contradicted requirement,
- `business_rule` — wrong calculation or limit,
- `decision` — deviation from a plan/spec decision,
- `contract` — API, event or schema differs from the spec,
- `unrequested` — added behaviour without a requirement,
- `test_gap` — requirement without a test that would catch its violation.

Severity: `blocker` = contradicted or wrong business rule / security requirement / data rule;
`major` = missing or partial requirement, deviated decision, contract mismatch;
`minor` = unrequested low-risk behaviour, test gap on a simple rule; `info` = ambiguity in
the spec itself (quote it). Quote the spec (≤ 2 sentences) in `description` when it decides
the finding, and put the `path#section` in `refs`.
