# Expected: dotnet-01-trivial
Stack: .NET 8 / ASP.NET Core / EF Core
Change source: uncommitted vs HEAD (+ untracked)

7 modified files, 0 untracked, +24/−24 lines. Produced by `generate.py` (exact string/regex replacements on the base).

## Expected review mode
`build+tests+static` — typo fixes in comments/XML docs/log text, a private method + local rename, a corrected test expectation and a path fix in a dev script; no public symbol, contract, schema, auth or behaviour change in `src/`.

## Expected top files (ordered, approximate)
1. `tests/Shop.Tests/Domain/InvoiceTests.cs` — expected value changed `45.99m` → `44.99m` in `Total_WithMultipleLines_SumsLineTotals`; must be classified as a **correction** (2 × 19.99 + 5.01 = 44.99, the base test was failing; assertion still exact `Should().Be`, nothing skipped or loosened), not a weakening
2. `scripts/reset-db.ps1` — project path typo `Shop.Infrastucture` → `Shop.Infrastructure` (2×) and `database drop` now passes `--connection $Connection`; small behaviour change in a local dev script only
3. `src/Shop.Infrastructure/BackgroundJobs/OverdueInvoiceNotifier.cs` — largest diff (30 lines) but pure rename: private `CreateEvt` → `CreateOverdueEvent`, locals `inv` → `invoice`, `due` → `overdueInvoices`, two comment typos; no logic change
4. `src/Shop.Application/Customers/CustomerService.cs` — private static helper `Normalise` → `NormalizeEmail` (2 call sites, both in the same file)
5. `src/Shop.Infrastructure/Payments/PaymentGatewayClient.cs` — log message typo `Paymnet` → `Payment`
6. `src/Shop.Domain/Common/Money.cs` — XML doc typos only (`monetery`, `distribued`)
7. `src/Shop.Api/Controllers/InvoicesController.cs` — XML doc typo only (`Retrives`)

## Must-detect signals
- [ ] tests: expected value corrected, not weakened (same assertion strictness, arithmetic matches arrange) — `tests/Shop.Tests/Domain/InvoiceTests.cs`
- [ ] fan-in: renamed symbols are `private` (`CreateEvt`, `Normalise`) — fan-in 1 file each; no public API touched — `OverdueInvoiceNotifier.cs`, `CustomerService.cs`
- [ ] config & infra: dev-only script fix, not deployed infrastructure — `scripts/reset-db.ps1`
- [ ] convention deviation: none introduced (renames move code *towards* naming conventions)
- [ ] whole change: no new code blocks, no logic/contract/schema/auth changes → lowest review mode

## Traps (must NOT rank high)
- `src/Shop.Domain/Common/Money.cs` — highest fan-in type in the solution (10 other files reference `Money`), but the diff touches XML doc comments only; fan-in must not be applied to comment-only changes
- `src/Shop.Api/Controllers/InvoicesController.cs` — security-sensitive file (InvoiceOwner checks) but only a `<summary>` typo changed
- `src/Shop.Infrastructure/BackgroundJobs/OverdueInvoiceNotifier.cs` — BackgroundService / concurrency-relevant file with the biggest diff, but semantically identical (rename only)
- `src/Shop.Infrastructure/Payments/PaymentGatewayClient.cs` — external integration file; only a log string changed
