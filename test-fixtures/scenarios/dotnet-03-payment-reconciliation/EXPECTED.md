# Expected: dotnet-03-payment-reconciliation
Stack: .NET 8 / ASP.NET Core / EF Core
Change source: feature branch vs develop + uncommitted

- Branch `feature/dotnet-03-payment-reconciliation`, 1 commit on top of `develop` ("WIP ... already committed part", from `committed/`): 10 files — plan Task 1 (domain model) plus parts of Tasks 2/3 (`ReconciliationOptions`, `IBankTransactionRepository`, `BankTransactionRepository`, `BankTransactionConfiguration`), and `BankTransactionTests`.
- Uncommitted on top of that (from `changes/`): 13 modified + 12 untracked = 25 files (23 code/config/test + spec + plan).
- Spec: `docs/superpowers/specs/2026-11-11-payment-reconciliation-design.md` (~2,700 words). Plan: `docs/superpowers/plans/2026-11-11-payment-reconciliation.md` (~2,200 words).

## Expected review mode
`ai+human-critical-paths` — feature touches L3/L4 paths at once (anonymous endpoint that creates payments, money rounding, destructive + edited migrations, published event contract, transaction boundaries, shared mutable state); AI triage is useful for the bulk, but the critical files below require human review. Must NOT come out as `ai-review-only` or `build+tests+static`.

## Expected top files (ordered, approximate)
1. `src/Shop.Application/Reconciliation/ReconcileBankTransactionCommand.cs` — new 246-line file, `Handle` is ~205 contiguous lines; tolerance compares absolute difference to `TolerancePercent` (L155); two `SaveChangesAsync` (L202 payment+transaction, L233 invoice+outbox) with no `ExecuteInTransactionAsync`; `IServiceProvider.GetService<IEventPublisher>()` (L209); `throw new Exception` on duplicate (L58); sync-over-async via cache; first-fitting candidate wins (multi-invoice transfers) [CRITICAL]
2. `src/Shop.Api/Controllers/BankWebhookController.cs` — `[AllowAnonymous]` POST that creates payments, no `X-Bank-Signature` HMAC/timestamp check; returns invoice ids/numbers to an anonymous caller; one failing transaction fails the whole batch [CRITICAL]
3. `src/Shop.Domain/Common/Money.cs` — rounding `ToEven` → `AwayFromZero` and constructor now rounds; 3-line diff on the highest fan-in type (14 other files: Invoice, Payment, BankTransaction, settlement reconciliation, CreateInvoice, gateway contract, 6 test files); XML `<remarks>` still says banker's rounding; breaks `MoneyTests.Of_MidpointValue_UsesBankersRounding` and the midpoint settlement test; not in the plan, spec §6.4 forbids it [CRITICAL]
4. `src/Shop.Infrastructure/Persistence/Migrations/20261112143000_AddBankReconciliation.cs` — `DropColumn Invoices.PaymentNote` (legacy audit data, spec §6.3 says keep it; Down cannot restore data); otherwise additive [CRITICAL]
5. `src/Shop.Infrastructure/Persistence/Migrations/20260415093000_AddPaymentReference.cs` — already-applied (April) migration edited to add `Payments.ReconciliationStatus`; existing databases never get the column, the new migration does not add it [CRITICAL]
6. `src/Shop.Api/Controllers/InvoicesController.cs` — `IsOwnerAsync`/`InvoiceOwner` check removed from `GetPayments` ("optimisation"); any authenticated user can read any invoice's payments (IDOR); plan Task 9 says no authorization changes [CRITICAL]
7. `src/Shop.Application/Events/InvoicePaid.cs` — `PaymentReference` removed, `ReconciliationId` added, `Version` still `1`; consumers (ledger, notifications) read `PaymentReference`; doc comment edited to claim ledger matches on `InvoiceId` [CRITICAL]
8. `src/Shop.Application/Reconciliation/ReconciliationCache.cs` — singleton with `private static readonly Dictionary<,>` mutated by `BankStatementImportWorker` (`Replace`/`Clear`) and by request threads (`TryGetInvoiceId`, `Remove`) without synchronization; `loadFromDatabase(...).Result` [CRITICAL]
9. `src/Shop.Infrastructure/Banking/BankApiClient.cs` — `new HttpClient()` per instance, registered transient, never disposed (socket exhaustion); no timeout/retry/jitter; key read from `IConfiguration`; ignores `NextCursor` pagination; classic constructor instead of primary constructor
10. `src/Shop.Application/Invoices/InvoiceDtos.cs` — public `InvoiceDto.AmountDue` renamed to `OutstandingAmount` (breaking for web shop/back-office; compiles because the record is positional); `PaymentDto.ReconciliationStatus` added (fine)
11. `tests/Shop.Tests/Application/ReconcileSettlementHandlerTests.cs` — `[Fact(Skip = "flaky")]` on `Handle_FeeAtRoundingMidpoint_SettlesUsingBankersRounding` (actually broken by the Money change); exact `Difference == -0.05` assertion loosened to `Discrepancies.Should().NotBeEmpty()`
12. `src/Shop.Infrastructure/BackgroundJobs/BankStatementImportWorker.cs` — mutates the static cache from a background thread; `ListAsync(status, 0, int.MaxValue)` loads every open invoice with lines every 15 min (unbounded); re-importing the 3-day window hits the duplicate `System.Exception` and aborts the run at the first already-matched transaction
13. `src/Shop.Api/Controllers/ReconciliationController.cs` — controller injects `ShopDbContext` (layering), returns `List<BankTransaction>` entities, unpaged `ToListAsync`, tracked query; plan/spec require paged DTOs via `ISender`
14. `src/Shop.Infrastructure/DependencyInjection.cs` — lifetimes: `AddTransient<IBankApiClient, BankApiClient>` (not `AddHttpClient`), `AddSingleton<ReconciliationCache>`, transient client captured by singleton hosted service
15. `src/Shop.Domain/Invoices/Invoice.cs` (committed) — removes `PaymentNote` ("kept for audit" doc removed) → enables the column drop; adds `IsOpenForPayment` (planned)
16. `tests/Shop.Tests/Application/PayInvoiceCommandHandlerTests.cs` — `evt.PaymentReference == "ch_123"` assertion deleted to follow the contract break
17. `tests/Shop.Tests/Application/ReconcileBankTransactionHandlerTests.cs` — one happy-path test for a 205-line handler; no tolerance/partial/over-payment/currency/duplicate tests (plan lists 7 cases)
18. `src/Shop.Application/Invoices/PayInvoiceCommand.cs` — follows the event change (drops `PaymentReference` argument); card payments now publish `InvoicePaid` without a reference
19. `src/Shop.Api/appsettings.json` — new `Bank` and `Reconciliation` sections; `Bank:ApiKey` placeholder in appsettings (conventions §7: secrets from Key Vault)

## Must-detect signals
- [ ] core logic: tolerance implemented as `|difference| <= TolerancePercent` (absolute 0.50) instead of `min(0.5 % × outstanding, MaxToleranceAmount)`; `MaxToleranceAmount` unused; e.g. 20.00 invoice paid with 19.60 is booked as fully paid (spec: partial), 2,000.00 paid with 1,996.00 is booked as partial (spec: full) — `src/Shop.Application/Reconciliation/ReconcileBankTransactionCommand.cs`
- [ ] core logic: within tolerance the `Payment` records the transfer amount while the invoice is credited the outstanding amount (payment and invoice disagree) — `ReconcileBankTransactionCommand.cs`
- [ ] core logic: large contiguous new block (~205-line method) — drift risk — `ReconcileBankTransactionCommand.cs`
- [ ] security: `[AllowAnonymous]` webhook without HMAC signature/timestamp verification (spec FR-2, conventions §8) — `src/Shop.Api/Controllers/BankWebhookController.cs`
- [ ] security: anonymous webhook response leaks invoice ids/numbers (spec §7.1) — `BankWebhookController.cs`
- [ ] security: InvoiceOwner resource authorization removed from `GET /api/invoices/{id}/payments` — `src/Shop.Api/Controllers/InvoicesController.cs`
- [ ] data integrity: payment/transaction saved, then invoice + outbox saved in a second `SaveChangesAsync`, no transaction (spec FR-8, conventions §5, neighbour `PayInvoiceCommandHandler` does it right) — `ReconcileBankTransactionCommand.cs`
- [ ] data integrity: applied migration edited — `src/Shop.Infrastructure/Persistence/Migrations/20260415093000_AddPaymentReference.cs`
- [ ] data integrity: new migration drops `Invoices.PaymentNote` with data — `src/Shop.Infrastructure/Persistence/Migrations/20261112143000_AddBankReconciliation.cs`
- [ ] concurrency & state: static `Dictionary<string, Guid>` in a singleton, written from the hosted service and from requests — `src/Shop.Application/Reconciliation/ReconciliationCache.cs`
- [ ] concurrency & state: `.Result` on an async EF lookup in the request path — `ReconciliationCache.cs` (called from `ReconcileBankTransactionCommand.cs`)
- [ ] integration: `new HttpClient()` in a transient service, no timeout/retry, pagination ignored — `src/Shop.Infrastructure/Banking/BankApiClient.cs` (+ registration in `src/Shop.Infrastructure/DependencyInjection.cs`)
- [ ] contracts: `InvoicePaid` field removed without version bump (`Version = 1`) — `src/Shop.Application/Events/InvoicePaid.cs`
- [ ] contracts: public DTO property `AmountDue` renamed to `OutstandingAmount` — `src/Shop.Application/Invoices/InvoiceDtos.cs`
- [ ] core logic / fan-in: `Money` rounding mode and constructor rounding changed; blast radius across all amount calculations and the gateway settlement reconciliation — `src/Shop.Domain/Common/Money.cs`
- [ ] convention deviation: service locator `serviceProvider.GetService<IEventPublisher>()` in a handler — `ReconcileBankTransactionCommand.cs`
- [ ] convention deviation: raw `System.Exception` thrown although `BankTransactionAlreadyMatchedException` exists (→ unmapped 500; webhook batch retried by the bank forever; worker run aborted) — `ReconcileBankTransactionCommand.cs`
- [ ] convention deviation / architecture: controller returns EF entity and injects `ShopDbContext` — `src/Shop.Api/Controllers/ReconciliationController.cs`
- [ ] performance: unbounded queries — `ReconciliationController.GetUnmatched` (`ToListAsync` without paging) and `BankStatementImportWorker.RefreshCacheAsync` (`int.MaxValue`, includes lines)
- [ ] tests: `[Fact(Skip = "flaky")]` on an existing reconciliation test — `tests/Shop.Tests/Application/ReconcileSettlementHandlerTests.cs`
- [ ] tests: assertion loosened (`ContainSingle().Which.Difference.Should().Be(-0.05)` → `NotBeEmpty()`) — `ReconcileSettlementHandlerTests.cs`
- [ ] tests: assertion on `PaymentReference` removed — `tests/Shop.Tests/Application/PayInvoiceCommandHandlerTests.cs`
- [ ] tests: missing tests for tolerance, partial/over-payment, currency mismatch, duplicates; no tests for webhook/signature — `tests/Shop.Tests/Application/ReconcileBankTransactionHandlerTests.cs`
- [ ] tests: existing `MoneyTests.Of_MidpointValue_UsesBankersRounding` will fail with the new rounding but was not touched (build+tests must go red) — `tests/Shop.Tests/Domain/MoneyTests.cs` (unchanged)
- [ ] config & infra: transient HTTP client + singleton cache + new hosted service registered; `Bank:ApiKey` key in appsettings — `src/Shop.Infrastructure/DependencyInjection.cs`, `src/Shop.Api/appsettings.json`
- [ ] error handling: one bad transaction fails the whole webhook batch (spec §9 requires independent processing) — `BankWebhookController.cs`

## Traps (must NOT rank high)
- `src/Shop.Application/Reconciliation/ReconciliationResultDto.cs` — new positional record with XML param docs, no logic
- `src/Shop.Api/Controllers/CustomersController.cs` — whitespace/line-wrapping only (unplanned, but cosmetic)
- `src/Shop.Application/Abstractions/IInvoiceRepository.cs` — XML doc comments added, signatures unchanged (planned in Task 13)
- `src/Shop.Infrastructure/Persistence/Migrations/20261112143000_AddBankReconciliation.Designer.cs` — EF-generated
- `src/Shop.Infrastructure/Persistence/Migrations/ShopDbContextModelSnapshot.cs` — EF-generated; at most supporting evidence for the `PaymentNote` drop / `ReconciliationStatus` column
- `docs/superpowers/specs/...`, `docs/superpowers/plans/...` — documentation; input for summary/plan comparison, not ranked as code risk
- committed `src/Shop.Domain/Payments/BankTransaction.cs`, `ReconciliationStatus.cs`, `BankTransactionConfiguration.cs`, `BankTransactionRepository.cs`, `tests/Shop.Tests/Domain/BankTransactionTests.cs` — clean, convention-following new code (medium-low at most)

## Plan vs implementation (only for scenarios with docs)
- Spec ↔ plan contradiction 1 — tolerance: spec FR-7 = 0.5 % of outstanding capped at 5.00 (and explicitly rejects a flat tolerance); plan Task 2/5 = flat `ToleranceAmount = 0.50`. Committed `ReconciliationOptions` follows the spec (`TolerancePercent`, `MaxToleranceAmount`), the handler applies the plan's flat semantics to the spec's percent field → wrong under both documents.
- Spec ↔ plan contradiction 2 — events: spec FR-9 = `InvoicePaid` v1 unchanged (with `PaymentReference` = bank reference) plus a new `PaymentReconciled` v1 event (§13 rejects extending `InvoicePaid`); plan Task 5 Step 4 = extend `InvoicePaid`, drop `PaymentReference`, "no new event type". Implementation follows the plan; `PaymentReconciled` does not exist.
- Requirement not addressed by the plan: FR-3 idempotent deliveries (duplicate `BankReference` → 200, no-op, never fail the batch). No plan task or test case mentions duplicates; implementation improvises: duplicate of a matched transaction throws `System.Exception`.
- Plan step without a requirement: Task 10 "In-memory reconciliation cache" — no spec requirement (NFR-2 relies on the existing `Invoices.Number` index); it is where the static-state/`.Result` problems live.
- Open questions in spec §14: OQ-1 one transfer for several invoices (interim rule: leave unmatched) — implementation silently answers it by booking the first fitting candidate; OQ-2 ageing/escalation owner for unmatched transactions — unresolved, nothing implemented (correct).
- Plan task not implemented: Task 7 webhook signature verification — `src/Shop.Api/Security/BankWebhookSignatureVerifier.cs`, `tests/Shop.Tests/Api/BankWebhookSignatureVerifierTests.cs` missing, `src/Shop.Api/Program.cs` and controller wiring untouched.
- File changed that the plan did not mention: `src/Shop.Domain/Common/Money.cs` (substantive; spec §6.4 forbids it). Also unplanned: `CustomersController.cs` (cosmetic) and `20260415093000_AddPaymentReference.cs` (plan Task 3 explicitly says do not modify existing migrations). `ReconcileSettlementHandlerTests.cs` is listed only as "verify, no changes expected" but was changed.
- Implemented differently than planned: Task 3 `ReconciliationStatus` column put into the old migration, new migration drops `PaymentNote` (not in plan; committed `Invoice.cs` also removes the property); Task 4 typed client → `new HttpClient()`/transient; Task 5 Step 3 `ExecuteInTransactionAsync` + single save → two saves, publisher via service locator; Task 5 tests 1 of 7 cases; Task 8 planned `ListUnmatchedBankTransactionsQuery.cs` + DTO + paging → controller on `DbContext` returning entities (file missing); Task 9 "no authorization changes" → owner check removed, plus unplanned `AmountDue` rename.
- Checkbox state is not evidence: only Task 1 is ticked; Tasks 2–6 and 8–13 are unticked although (mostly) implemented, Task 7 is unticked and absent.
- Committed vs uncommitted split: the feature commit contains Task 1 and the persistence/option pieces of Tasks 2–3; everything else, including the migration, is uncommitted.
