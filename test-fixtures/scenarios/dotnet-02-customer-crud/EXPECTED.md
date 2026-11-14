# Expected: dotnet-02-customer-crud
Stack: .NET 8 / ASP.NET Core / EF Core
Change source: uncommitted vs HEAD (+ untracked)

16 files: 12 untracked (new), 4 modified. New "customer notes" CRUD under `/api/customers/{customerId}/notes`, modelled on the existing `CustomerService` / `CustomersController`.

## Expected review mode
`ai-review-only` — self-contained new CRUD feature (staff-only notes) that follows the project conventions: service + repository + DTOs + validators + paging + tests, one additive migration (new table), no change to existing behaviour, contracts, auth model or core billing logic.

## Expected top files (ordered, approximate)
1. `src/Shop.Application/Customers/CustomerNoteService.cs` — new business logic (create/update/delete/list), customer existence check, note scoped by customer; `DeleteAsync` passes `CancellationToken.None` to `SaveChangesAsync`
2. `src/Shop.Infrastructure/Persistence/Migrations/20261105120000_AddCustomerNotes.cs` — new migration: additive `CustomerNotes` table, FK to `Customers` with cascade delete, index `(CustomerId, CreatedAt)`; no existing table touched
3. `src/Shop.Application/Customers/CustomerNoteValidators.cs` — `Body` max length 4000 while the column is `nvarchar(2000)`
4. `src/Shop.Api/Controllers/CustomerNotesController.cs` — 5 new endpoints, `[Authorize(Policy = Policies.Staff)]`, author taken from `sub` claim
5. `src/Shop.Infrastructure/Persistence/Repositories/CustomerNoteRepository.cs` — paged list, `AsNoTracking`, lookups filter by both `noteId` and `customerId`
6. `src/Shop.Infrastructure/Persistence/Configurations/CustomerNoteConfiguration.cs` — `HasMaxLength(CustomerNote.MaxBodyLength)` (2000), cascade delete
7. `tests/Shop.Tests/Application/CustomerNoteValidatorTests.cs` — boundary test uses 4001 chars, i.e. it encodes the 4000 limit and misses the 2000-char DB limit
8. `src/Shop.Domain/Customers/CustomerNote.cs` — new entity, `MaxBodyLength = 2000`
9. `tests/Shop.Tests/Application/CustomerNoteServiceTests.cs` — 7 tests: happy paths, not-found branches, paging clamp
10. `src/Shop.Application/Abstractions/ICustomerNoteRepository.cs` — new port
11. `src/Shop.Infrastructure/Persistence/ShopDbContext.cs`, `src/Shop.Infrastructure/DependencyInjection.cs`, `src/Shop.Application/DependencyInjection.cs` — one-line wiring each (scoped lifetimes, consistent with neighbours)

## Must-detect signals
- [ ] data integrity / validation: validator allows up to 4000 chars but the column is `nvarchar(2000)` → bodies of 2001–4000 chars pass validation and fail in `SaveChanges` (500 instead of 400) — `CustomerNoteValidators.cs` vs `CustomerNoteConfiguration.cs` / `CustomerNote.cs`
- [ ] tests: the validator test pins the wrong limit (4001) and no test covers the DB limit — `tests/Shop.Tests/Application/CustomerNoteValidatorTests.cs`
- [ ] convention deviation: `CancellationToken.None` instead of passing the token through (conventions §4) — `CustomerNoteService.cs` (`DeleteAsync`)
- [ ] data integrity: migration is additive (new table only) and matches the snapshot/Designer; cascade delete of notes with a customer is intentional — `20261105120000_AddCustomerNotes.cs`
- [ ] security (positive check): all endpoints require `Staff` policy; repository scopes every note lookup by `customerId` (no IDOR); `[AllowAnonymous]` not used — `CustomerNotesController.cs`, `CustomerNoteRepository.cs`
- [ ] performance (positive check): list is paged via `Paging.Normalize` (max 100) and backed by index `(CustomerId, CreatedAt)` — `CustomerNoteRepository.cs`
- [ ] contracts: only new DTO records; no existing DTO/event changed — `CustomerNoteDtos.cs`
- [ ] architecture: layering respected (controller → service interface → repository port; no DbContext in controller/service)

## Traps (must NOT rank high)
- `src/Shop.Infrastructure/Persistence/Migrations/20261105120000_AddCustomerNotes.Designer.cs` — EF-generated target model
- `src/Shop.Infrastructure/Persistence/Migrations/ShopDbContextModelSnapshot.cs` — EF-generated, +44 lines for the new entity only
- `src/Shop.Application/Customers/CustomerNoteDtos.cs` — DTO records + trivial mapping, no logic
- `src/Shop.Infrastructure/Persistence/ShopDbContext.cs`, both `DependencyInjection.cs` files — single added line each
