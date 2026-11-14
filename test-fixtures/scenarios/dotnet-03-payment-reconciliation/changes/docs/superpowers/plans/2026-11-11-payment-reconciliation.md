# Bank Transfer Payment Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended)
> or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`)
> syntax for tracking.

**Goal:** Automatically match incoming bank transfers to open invoices and book them as payments, so
that finance only handles exceptions.

**Architecture:** Webhook and polling worker both send `ReconcileBankTransactionCommand` (MediatR).
The handler imports a `BankTransaction`, finds the invoice by the number in the remittance
information, applies the amount rules and books a `Payment`. Finance gets a read API for unmatched
transactions; customers see the reconciliation status on their payments.

**Tech Stack:** .NET 8, ASP.NET Core, EF Core 8 (SQL Server), MediatR 12, FluentValidation, Polly,
xUnit + FluentAssertions + Moq.

**Spec:** `docs/superpowers/specs/2026-11-11-payment-reconciliation-design.md`

---

## Background for the implementer

You are adding a second way for invoices to get paid. Today every payment is a card charge created
by `PayInvoiceCommandHandler`, which is the best reference for how a use case that touches both a
`Payment` and an `Invoice` should look in this codebase: it loads the invoice through the
repository, validates the status, talks to the outside world first, and only then changes both
aggregates inside `IUnitOfWork.ExecuteInTransactionAsync`, writing the `InvoicePaid` event to the
outbox before the single `SaveChangesAsync`. Read it before starting Task 5.

The second reference is `ReconcileSettlementCommandHandler`, which reconciles the card gateway's
settlement report. It is unrelated to bank transfers but shows how we report discrepancies instead
of guessing, and it is covered by tests that must keep passing.

The conventions document (`docs/architecture/conventions.md`) applies in full. The parts that
matter most here are: primary constructors and no service locator (§2), `DomainException`
subclasses instead of generic exceptions (§3), async all the way with cancellation tokens (§4), the
migration rules (§5), DTOs instead of entities in API responses (§6), typed HTTP clients with
retry and timeout (§7), and the webhook rule in §8.

Bank transfers differ from card payments in three ways that drive the design: they arrive without
our involvement (we cannot attach an idempotency key), the amount may differ slightly from what we
asked for, and the payer tells us which invoice they meant only through free text.

---

## File map

| Area | Files |
|------|-------|
| Domain | `src/Shop.Domain/Payments/BankTransaction.cs`, `ReconciliationStatus.cs`, `Payment.cs`, `src/Shop.Domain/Invoices/Invoice.cs`, `src/Shop.Domain/Exceptions/DomainExceptions.cs` |
| Application | `src/Shop.Application/Reconciliation/*`, `src/Shop.Application/Abstractions/IBankTransactionRepository.cs`, `src/Shop.Application/Events/InvoicePaid.cs`, `src/Shop.Application/Invoices/*` |
| Infrastructure | `src/Shop.Infrastructure/Banking/BankApiClient.cs`, `src/Shop.Infrastructure/BackgroundJobs/BankStatementImportWorker.cs`, persistence files, `DependencyInjection.cs` |
| API | `src/Shop.Api/Controllers/BankWebhookController.cs`, `ReconciliationController.cs`, `InvoicesController.cs`, `src/Shop.Api/Security/BankWebhookSignatureVerifier.cs` |
| Tests | `tests/Shop.Tests/Domain/BankTransactionTests.cs`, `tests/Shop.Tests/Application/ReconcileBankTransactionHandlerTests.cs`, `tests/Shop.Tests/Api/BankWebhookSignatureVerifierTests.cs` |

Each task ends with a commit. Keep tasks small; run the full test suite before every commit.

---

### Task 1: Domain model

**Files:**
- Create: `src/Shop.Domain/Payments/BankTransaction.cs`
- Create: `src/Shop.Domain/Payments/ReconciliationStatus.cs`
- Modify: `src/Shop.Domain/Payments/Payment.cs`
- Modify: `src/Shop.Domain/Invoices/Invoice.cs`
- Modify: `src/Shop.Domain/Exceptions/DomainExceptions.cs`
- Test: `tests/Shop.Tests/Domain/BankTransactionTests.cs`

- [x] **Step 1: Write failing tests for `BankTransaction`**

  Cover `Import` (status `Unmatched`, remittance trimmed), `MarkMatched` (sets invoice id) and
  `MarkMatched` on an already matched transaction (throws `BankTransactionAlreadyMatchedException`).

- [x] **Step 2: Run tests to verify they fail**

  Run: `dotnet test --filter FullyQualifiedName~BankTransactionTests`
  Expected: FAIL (type does not exist)

- [x] **Step 3: Implement `BankTransaction`, `BankTransactionStatus`, `ReconciliationStatus`**

  Private EF constructor, private setters, `Value` as `Money`, factory `Import(...)`.

- [x] **Step 4: Extend `Payment`**

  Add `ReconciliationStatus` and `BankTransactionId`, plus the factory:

  ```csharp
  public static Payment FromBankTransfer(
      Guid invoiceId, Money amount, string bankReference, Guid bankTransactionId, DateTimeOffset receivedAt)
  ```

  Bank transfers are settled on receipt, fee 0, `ProviderReference = bankReference`.

- [x] **Step 5: Add `Invoice.IsOpenForPayment`**

  `Status is Issued or PartiallyPaid or Overdue`. No persisted change.

- [x] **Step 6: Run tests, commit**

  Run: `dotnet test` — Expected: PASS
  `git commit -m "feat(reconciliation): domain model for bank transactions"`

---

### Task 2: Reconciliation options

**Files:**
- Create: `src/Shop.Application/Reconciliation/ReconciliationOptions.cs`

- [ ] **Step 1: Create the options class**

  Bound from the `Reconciliation` section. The tolerance is a flat amount: a fixed absolute
  tolerance is simpler to explain to finance than a percentage and avoids rounding edge cases on
  tiny invoices, so we use one setting for all invoices.

  ```csharp
  public sealed class ReconciliationOptions
  {
      public const string SectionName = "Reconciliation";

      /// <summary>Accepted absolute difference per transaction, in invoice currency.</summary>
      public decimal ToleranceAmount { get; init; } = 0.50m;

      public TimeSpan ImportInterval { get; init; } = TimeSpan.FromMinutes(15);

      public int ImportLookbackDays { get; init; } = 3;
  }
  ```

- [ ] **Step 2: Commit**

  `git commit -m "feat(reconciliation): options"`

---

### Task 3: Persistence

**Files:**
- Create: `src/Shop.Application/Abstractions/IBankTransactionRepository.cs`
- Create: `src/Shop.Infrastructure/Persistence/Repositories/BankTransactionRepository.cs`
- Create: `src/Shop.Infrastructure/Persistence/Configurations/BankTransactionConfiguration.cs`
- Create: `src/Shop.Infrastructure/Persistence/Migrations/<timestamp>_AddBankReconciliation.cs` (+ `.Designer.cs`)
- Modify: `src/Shop.Infrastructure/Persistence/Migrations/ShopDbContextModelSnapshot.cs`

- [ ] **Step 1: Repository interface and implementation**

  `GetByBankReferenceAsync`, `ListUnmatchedAsync(skip, take)` (paged, `AsNoTracking`), `Add`.

- [ ] **Step 2: EF configuration**

  Table `BankTransactions`, unique index on `BankReference`, index on `Status`, `Status` stored as
  string (max 20), `Amount` precision (18, 2), `Currency` `nchar(3)`.

- [ ] **Step 3: Scaffold the migration**

  Run: `dotnet ef migrations add AddBankReconciliation --project src/Shop.Infrastructure --startup-project src/Shop.Api`

  Expected content: create `BankTransactions` with its indexes, add `Payments.ReconciliationStatus`
  (`int`, default 0) and `Payments.BankTransactionId` (nullable). Review the generated file — **do
  not modify existing migrations**; if the scaffold contains anything else, fix the model instead.

- [ ] **Step 4: Apply locally and commit**

  Run: `pwsh scripts/reset-db.ps1` — Expected: database recreated without errors.
  `git commit -m "feat(reconciliation): persistence and migration"`

---

### Task 4: Bank API client

**Files:**
- Create: `src/Shop.Infrastructure/Banking/BankApiClient.cs`

- [ ] **Step 1: Define `IBankApiClient` and `BankStatementEntry`**

  ```csharp
  public interface IBankApiClient
  {
      Task<IReadOnlyList<BankStatementEntry>> GetCreditTransactionsAsync(DateOnly from, DateOnly to, CancellationToken cancellationToken);
  }
  ```

- [ ] **Step 2: Implement the client as a typed client**

  Register with `services.AddHttpClient<IBankApiClient, BankApiClient>()`, reuse the retry policy and
  the 10-second per-try timeout from the payment gateway registration in `DependencyInjection.cs`.
  Options class `BankApiOptions` bound from `Bank` (`BaseUrl`, `AccountId`); the API key header is
  added from Key Vault configuration.

- [ ] **Step 3: Commit**

  `git commit -m "feat(reconciliation): bank API client"`

---

### Task 5: Reconcile command and handler

**Files:**
- Create: `src/Shop.Application/Reconciliation/ReconcileBankTransactionCommand.cs` (command + handler)
- Create: `src/Shop.Application/Reconciliation/ReconciliationResultDto.cs`
- Modify: `src/Shop.Application/Events/InvoicePaid.cs`
- Modify: `src/Shop.Application/Invoices/PayInvoiceCommand.cs`
- Modify: `tests/Shop.Tests/Application/PayInvoiceCommandHandlerTests.cs`
- Test: `tests/Shop.Tests/Application/ReconcileBankTransactionHandlerTests.cs`

- [ ] **Step 1: Write the failing handler tests**

  Cases:
  - exact amount with invoice number in remittance information → `Matched`, invoice `Paid`
  - difference within tolerance → `MatchedWithinTolerance`, invoice `Paid`
  - under-payment beyond tolerance → `PartiallyPaid`
  - over-payment beyond tolerance → `Unmatched`, nothing booked
  - currency mismatch → `Unmatched`
  - invoice not open for payment → `Unmatched`
  - no invoice number → `Unmatched`

  Example for the first case (mirror the setup style of `PayInvoiceCommandHandlerTests`):

  ```csharp
  [Fact]
  public async Task Handle_ExactAmountWithInvoiceNumber_MarksInvoicePaid()
  {
      var invoice = Invoice.Draft("INV-2026-000123", Guid.NewGuid(), "EUR", new DateOnly(2026, 11, 30));
      invoice.AddLine("Office chair", 1, Money.Of(120m, "EUR"));
      invoice.Issue(DateTimeOffset.UtcNow);
      _invoices.Setup(r => r.GetByNumberAsync("INV-2026-000123", It.IsAny<CancellationToken>())).ReturnsAsync(invoice);

      var result = await _handler.Handle(
          new ReconcileBankTransactionCommand("E2E-0001", 120m, "EUR", DateTimeOffset.UtcNow, "Payment for INV-2026-000123", null),
          CancellationToken.None);

      result.Outcome.Should().Be("Matched");
      invoice.Status.Should().Be(InvoiceStatus.Paid);
  }
  ```

  Use the same arrange helpers for the other cases; tolerance cases should use amounts on both sides
  of the boundary.

- [ ] **Step 2: Run tests to verify they fail**

  Run: `dotnet test --filter FullyQualifiedName~ReconcileBankTransactionHandlerTests`
  Expected: FAIL

- [ ] **Step 3: Implement the handler**

  Flow:
  1. Import the `BankTransaction`; ignore zero and negative amounts.
  2. Extract invoice numbers with `INV-\d{4}-\d{6}` from the remittance information.
  3. Load the invoice (`IInvoiceRepository.GetByNumberAsync`), check `IsOpenForPayment` and currency.
  4. `difference = amount − outstanding`; if `|difference| <= ToleranceAmount` book the outstanding
     amount, if negative beyond tolerance book a partial payment, if positive beyond tolerance leave
     unmatched.
  5. Inside `unitOfWork.ExecuteInTransactionAsync`: create the payment with
     `Payment.FromBankTransfer`, mark the transaction matched, `invoice.ApplyPayment`, publish
     events, then a single `SaveChangesAsync`.

  Inject everything through the primary constructor (repositories, `IUnitOfWork`,
  `IEventPublisher`, `IOptions<ReconciliationOptions>`, `TimeProvider`, logger).

- [ ] **Step 4: Extend `InvoicePaid`**

  Add `Guid? ReconciliationId` so ledger can link the payment to the bank transaction. Drop
  `PaymentReference`: for bank transfers it would only duplicate the bank reference, and
  ledger-service can join on `InvoiceId`. This keeps a single "invoice paid" event for both card and
  bank payments; no new event type is needed. Update `PayInvoiceCommand.cs` and
  `PayInvoiceCommandHandlerTests.cs` accordingly.

- [ ] **Step 5: Run tests, commit**

  Run: `dotnet test` — Expected: PASS
  `git commit -m "feat(reconciliation): reconcile bank transaction handler"`

---

### Task 6: Webhook endpoint

**Files:**
- Create: `src/Shop.Api/Controllers/BankWebhookController.cs`

- [ ] **Step 1: Controller**

  `POST /webhooks/bank/transactions`, `[AllowAnonymous]` (the bank cannot send a JWT; authenticity
  is handled in Task 7). Payload records `BankWebhookPayload` / `BankWebhookTransaction` in the same
  file. Send one `ReconcileBankTransactionCommand` per transaction and return `200`.

- [ ] **Step 2: Commit**

  `git commit -m "feat(reconciliation): bank webhook endpoint"`

---

### Task 7: Webhook signature verification

**Files:**
- Create: `src/Shop.Api/Security/BankWebhookSignatureVerifier.cs`
- Modify: `src/Shop.Api/Controllers/BankWebhookController.cs`
- Modify: `src/Shop.Api/Program.cs`
- Test: `tests/Shop.Tests/Api/BankWebhookSignatureVerifierTests.cs`

- [ ] **Step 1: Write failing tests**

  Valid signature, tampered body, timestamp older than 5 minutes, previous secret during rotation.

- [ ] **Step 2: Implement the verifier**

  ```csharp
  public sealed class BankWebhookSignatureVerifier(IOptionsMonitor<BankWebhookOptions> options, TimeProvider clock)
  {
      public bool IsValid(ReadOnlySpan<byte> body, string? signatureHeader, string? timestampHeader) { ... }
  }
  ```

  HMAC-SHA256 over the raw body, `CryptographicOperations.FixedTimeEquals`, current and previous
  secret.

- [ ] **Step 3: Wire it into the controller**

  Enable request buffering, read the raw body, return `401` before model binding when the check
  fails. Register the verifier and `BankWebhookOptions` in `Program.cs`.

- [ ] **Step 4: Run tests, commit**

  Run: `dotnet test --filter FullyQualifiedName~BankWebhookSignatureVerifierTests` — Expected: PASS
  `git commit -m "feat(reconciliation): verify bank webhook signatures"`

---

### Task 8: Finance API for unmatched transactions

**Files:**
- Create: `src/Shop.Api/Controllers/ReconciliationController.cs`
- Create: `src/Shop.Application/Reconciliation/ListUnmatchedBankTransactionsQuery.cs` (query, handler, `UnmatchedBankTransactionDto`)

- [ ] **Step 1: Query and handler**

  Use `IBankTransactionRepository.ListUnmatchedAsync` with `Paging.Normalize`; map to
  `UnmatchedBankTransactionDto`.

- [ ] **Step 2: Controller**

  `GET /api/reconciliation/unmatched?page=&pageSize=`, `Finance` policy, `ISender` only.

- [ ] **Step 3: Commit**

  `git commit -m "feat(reconciliation): finance API for unmatched transactions"`

---

### Task 9: Reconciliation status on customer payments

**Files:**
- Modify: `src/Shop.Application/Invoices/InvoiceDtos.cs`
- Modify: `src/Shop.Api/Controllers/InvoicesController.cs`

- [ ] **Step 1: Extend `PaymentDto`**

  Add `string ReconciliationStatus` and map it in `PaymentDto.From`.

- [ ] **Step 2: Update the XML documentation of `GetPayments`**

  Mention the new field. No authorization changes in this controller.

- [ ] **Step 3: Commit**

  `git commit -m "feat(reconciliation): expose reconciliation status on payments"`

---

### Task 10: In-memory reconciliation cache

**Files:**
- Create: `src/Shop.Application/Reconciliation/ReconciliationCache.cs`

- [ ] **Step 1: Cache open invoice numbers**

  Webhook batches contain up to 50 transactions; looking each invoice up by number costs a round trip
  per transaction. Keep a dictionary `invoice number → invoice id` of open invoices in a singleton,
  refreshed by the import worker (Task 11) and updated when an invoice gets paid. The handler asks
  the cache first and falls back to the database.

- [ ] **Step 2: Use the cache in the handler**

- [ ] **Step 3: Commit**

  `git commit -m "perf(reconciliation): cache open invoice numbers"`

---

### Task 11: Statement polling worker

**Files:**
- Create: `src/Shop.Infrastructure/BackgroundJobs/BankStatementImportWorker.cs`

- [ ] **Step 1: Hosted service**

  Same structure as `OverdueInvoiceNotifier`: `PeriodicTimer` with `ImportInterval`, a new scope per
  run via `IServiceScopeFactory`, catch-log-continue at loop level. Each run refreshes the cache and
  sends `ReconcileBankTransactionCommand` for every credit transaction of the last
  `ImportLookbackDays` days.

- [ ] **Step 2: Commit**

  `git commit -m "feat(reconciliation): statement polling fallback"`

---

### Task 12: Wiring and configuration

**Files:**
- Modify: `src/Shop.Infrastructure/DependencyInjection.cs`
- Modify: `src/Shop.Api/appsettings.json`

- [ ] **Step 1: Register services**

  `IBankTransactionRepository` (scoped), `ReconciliationOptions`, `ReconciliationCache` (singleton),
  bank API typed client (Task 4), `BankStatementImportWorker` (hosted service).

- [ ] **Step 2: Configuration**

  Add `Bank` (`BaseUrl`, `AccountId`) and `Reconciliation` sections with defaults. Secrets stay in
  Key Vault.

- [ ] **Step 3: Commit**

  `git commit -m "chore(reconciliation): wiring and configuration"`

---

### Task 13: Regression check and polish

**Files:**
- Modify: `src/Shop.Application/Abstractions/IInvoiceRepository.cs` (XML docs only)
- Verify: `tests/Shop.Tests/Application/ReconcileSettlementHandlerTests.cs` (must stay green, no changes expected)

- [ ] **Step 1: Add XML documentation to `IInvoiceRepository`**

  The new handler relies on `GetByNumberAsync` and `ListAsync`; document what they load.

- [ ] **Step 2: Full test run**

  Run: `dotnet test` — Expected: all tests pass, including the existing gateway settlement tests.

- [ ] **Step 3: Format and commit**

  Run: `dotnet format` on the files you touched.
  `git commit -m "chore(reconciliation): docs and cleanup"`

---

## Execution notes

- Tasks 1–3 are prerequisites for everything else. Tasks 4, 6–9 and 11 can be done in any order once
  Task 5 exists; Task 10 must come after Task 5 because it changes the handler.
- Do not expose the webhook route in any shared environment before Task 7 is merged. Locally you can
  call it with `curl` without a signature while Task 7 is in progress.
- When the scaffolded migration in Task 3 looks wrong, the cause is almost always the model, not the
  migration. Regenerate rather than hand-edit.
- Keep log messages free of IBANs and payer names; log the bank reference instead.
- If a step turns out to need a change outside the files listed for its task, stop and note it in
  the PR description so the reviewer can check it against the spec.

## Self-review

- Spec coverage: webhook (Tasks 6–7), polling (Task 11), matching and amount rules (Task 5), finance
  API (Task 8), customer visibility (Task 9), events (Task 5), schema (Task 3).
- No placeholders left; every task names its files.
- Type consistency: `ReconcileBankTransactionCommand`, `ReconciliationResultDto`,
  `ReconciliationOptions.ToleranceAmount`, `BankTransactionStatus` are used consistently across tasks.
