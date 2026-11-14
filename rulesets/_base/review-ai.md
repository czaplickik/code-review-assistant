# AI review checklist (all stacks)

Goal: find what a careful senior reviewer of this codebase would flag in AI-generated code.
Review only the change (diff), but judge it against the existing code around it.

## How to work

1. Read the project conventions files listed in the batch header (once per batch).
2. For each file: read the diff, then the full file if the change is larger than a few lines,
   then **2–4 neighbouring files** of the same kind (same package/namespace, same layer:
   another controller, service, repository, test) — they define "how we do it here".
3. Before reporting reinvention, **search the repository** (Grep) for existing helpers,
   value objects, base classes, mappers, error types, validators that do the same thing.
4. Before reporting dead code, **search for usages** of the symbol (Grep, including tests,
   config, reflection/DI by name).
5. Before reporting a resource leak or missing validation/error handling, **read the callee**
   the value is handed to — many library methods close or check for the caller.
6. Confirm or dismiss every deterministic candidate in the batch.

## What to check

| Category | Look for |
|---|---|
| `conventions` | Violations of documented rules (CLAUDE.md, docs/architecture, rules.yaml): injection style, layering, DTO vs entity, exception types, logging format, naming, test naming |
| `consistency` | Code that works differently from its neighbours without reason: different error handling, mapping style, validation approach, package placement, duplicated logic between new files |
| `reinvention` | New helper/util/mapper/validator/value object that duplicates an existing one; manual code where the project has a utility (Money, clock, id generator, pagination, error mapping); new dependency when an equivalent is already used |
| `dead_code` | Unused new methods, parameters, fields, classes, DTO fields, config keys; commented-out code; unreachable branches; flags nobody reads; old code left next to its replacement |
| `overengineering` | Abstractions, interfaces with one implementation, generic frameworks, factories, config options, extension points, caching or async **not required by the task**; scope creep beyond the request ("it was easier this way") |
| `ai_artifacts` | Calls to methods/APIs that do not exist; stubs, `TODO`, hard-coded values that only make a test pass; defensive checks for impossible states; comments that narrate the code; leftover debug output; inconsistent naming between files of the same change |
| `tests` | Tests that verify mocks instead of behaviour, have no meaningful assertion, duplicate the implementation's formula, were changed to match new (possibly wrong) behaviour, are disabled/skipped; changed behaviour with no test; edge cases of the change not covered |
| `error_handling` | Swallowed or overly broad catches, lost cause, generic exceptions, wrong status mapping, errors that hide bugs |
| `resources` | Unclosed streams/connections, missing timeouts, blocking calls in async code, lifetime/scoping mistakes |
| `performance` | N+1 queries, unbounded queries or collections, I/O in loops, repeated expensive work |
| `readability` | Misleading names, long methods mixing responsibilities, magic numbers, deep nesting — only when it hurts maintenance |

Security and spec compliance have their own reviews — mention them only when blatant, as
`info`, so the developer runs the right review.

## Severity

- `blocker` — wrong behaviour, data loss, crash, or a test that hides a defect.
- `major` — real maintenance or correctness cost: convention violation the team enforces,
  reinvention, dead code that misleads, missing test for changed behaviour, overengineering
  that adds moving parts.
- `minor` — small inconsistency or readability issue.
- `info` — question or observation.

One finding per distinct problem; if the same problem repeats in many places, report it once
with all locations in `related`. Point to the existing code in `related` for consistency and
reinvention findings. Suggestions in words, never a patch. `verified` only for what the code
shows; intent and likely consequences are `inferred`.
