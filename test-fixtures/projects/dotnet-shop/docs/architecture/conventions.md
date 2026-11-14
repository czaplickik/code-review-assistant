# Shop billing service — architecture & coding conventions

Status: accepted · Owner: billing team · Last reviewed: 2026-09-30

These conventions are enforced in code review. If you need to deviate, write it down in the PR
description and get a second approval from the billing team.

## 1. Layering and dependency direction

```
Shop.Api ──► Shop.Application ──► Shop.Domain
   │                ▲
   └──► Shop.Infrastructure (implements Application abstractions)
```

- `Shop.Domain` has no project or package references. Entities, value objects, domain exceptions.
- `Shop.Application` owns use cases (MediatR handlers or application services), DTOs, validators
  and the abstractions it needs (`Abstractions/`). It never references `Shop.Infrastructure`.
- `Shop.Infrastructure` contains EF Core, HTTP clients, messaging and hosted services.
- Controllers talk to the application layer only (`ISender` or an application service interface).
  **Controllers never inject `ShopDbContext` or repositories.**

## 2. Dependency injection

- Use **primary constructors** for constructor injection (`public sealed class Foo(IBar bar)`).
- **No service locator.** Do not inject `IServiceProvider` and call `GetService`/`GetRequiredService`
  in handlers, services, controllers or repositories. The only allowed places are the composition
  root (`DependencyInjection.cs`, `Program.cs`) and hosted services that create a scope through
  `IServiceScopeFactory` (see `OverdueInvoiceNotifier`).
- Lifetimes: repositories, `ShopDbContext` and handlers are scoped. A singleton must be stateless
  or hold state behind proper synchronization (`ConcurrentDictionary`, `IMemoryCache`). **No mutable
  `static` state.** Singletons must never capture scoped services.

## 3. Errors

- Business rule violations throw a subclass of `DomainException` (`Shop.Domain.Exceptions`).
- `ProblemDetailsMiddleware` maps them to RFC 7807 responses:

  | Exception                                   | Status |
  |---------------------------------------------|--------|
  | `NotFoundException`                         | 404    |
  | `InvalidInvoiceStateException`, `DuplicateCustomerException` | 409 |
  | `CurrencyMismatchException`, `InvalidCurrencyException`, `InvalidPaymentAmountException` | 422 |
  | `PaymentDeclinedException`                  | 402    |
  | FluentValidation `ValidationException`      | 400    |
  | any other `DomainException`                 | 400    |

- **Never throw `System.Exception`** (or `ApplicationException`). Infrastructure failures use the
  most specific BCL type (`HttpRequestException`, `InvalidOperationException`, ...).
- Do not catch-and-swallow. Hosted services catch at the loop level, log, and continue.

## 4. Async

- Async all the way. **No `.Result`, `.Wait()` or `.GetAwaiter().GetResult()`** anywhere in
  `src/`.
- Every async method accepts a `CancellationToken` and **passes it through** to every async call it
  makes (EF, HttpClient, MediatR, publisher).

## 5. Persistence

- EF Core 8 on SQL Server, schema `billing`. One `IEntityTypeConfiguration<T>` per entity under
  `Persistence/Configurations`.
- **Migrations are never edited once applied.** A migration is considered applied as soon as it is
  merged to `develop` (CI applies it to the shared dev/test databases). Fix forward with a new
  migration.
- Destructive schema changes (drop/rename column or table) use expand/contract over two releases
  and must preserve data (copy first, drop in a later release after sign-off from finance).
- A use case that changes more than one aggregate (e.g. `Payment` + `Invoice`) runs inside
  `IUnitOfWork.ExecuteInTransactionAsync` and calls `SaveChangesAsync` **once**. Integration events
  are written to the outbox inside the same transaction.
- Every list endpoint is paged (`Paging.Normalize`, max page size 100). No unbounded `ToListAsync()`
  over a table that grows with traffic.
- Read-only queries use `AsNoTracking()`.

## 6. Contracts

- API DTOs are `sealed record`s in `Shop.Application`. **DTOs never expose entities**, and
  controllers never return entities.
- Renaming or removing a public DTO property is a breaking change for the web shop and the
  back-office app. Add the new property, deprecate the old one, remove it in a later release.
- Integration events (`Shop.Application.Events`) are versioned contracts. **Never remove or rename
  a field of a published event.** Breaking changes require a new event version (e.g.
  `InvoicePaidV2`, `EventVersion = 2`) published side by side until all consumers have migrated.
  Additive, optional fields are allowed without a version bump.

## 7. Outbound HTTP

- Typed clients via `IHttpClientFactory` (`services.AddHttpClient<TInterface, TClient>()`).
  **Never `new HttpClient()`.**
- Every outbound client has a per-try timeout and a retry policy with exponential backoff and
  jitter (Polly). Non-idempotent calls send an `Idempotency-Key`.
- Base URLs and credentials come from options bound to configuration; secrets come from Key Vault,
  never from `appsettings.json`.

## 8. Security

- JWT bearer authentication; the fallback policy requires an authenticated user.
- **`[AllowAnonymous]` is only allowed on the health endpoint.** Webhooks from third parties must
  verify the sender's signature (HMAC) before any processing and are reviewed by security.
- Invoice and payment data is protected by resource-based authorization: controllers call
  `IAuthorizationService.AuthorizeAsync(User, invoice, Policies.InvoiceOwner)` before returning
  anything derived from an invoice.

## 9. Money

- All amounts go through the `Money` value object (`Shop.Domain.Common`). No raw `decimal`
  arithmetic on amounts outside `Money`.
- Rounding is banker's rounding (`MidpointRounding.ToEven`) to 2 decimals. This matches the ledger
  and the gateway settlement files. Changing it requires sign-off from finance.

## 10. Testing

- xUnit + FluentAssertions + Moq. Test project mirrors `src/` folders.
- Test names: `Method_Scenario_ExpectedResult` (e.g. `ApplyPayment_FullOutstanding_MarksPaid`).
- **Do not skip tests** (`Skip = ...`) without a linked issue, and do not loosen assertions to make
  a test pass. If behaviour changed intentionally, update the expected value and explain why in
  the PR.
- Every new handler gets tests for the happy path and each business rule branch.

## 11. Logging

- Structured logging with message templates (`logger.LogInformation("Invoice {InvoiceNumber} paid", ...)`),
  never string interpolation. No PII (emails, IBANs) in log messages.
