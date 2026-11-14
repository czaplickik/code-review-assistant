# Shop billing service

.NET 8 / ASP.NET Core service that issues invoices for shop orders, collects payments through the
payment gateway and reconciles gateway settlements.

- Architecture and coding conventions: `docs/architecture/conventions.md` (read before changing code).
- Build: `dotnet build Shop.sln` · Tests: `dotnet test` · Local DB: `pwsh scripts/reset-db.ps1`
- Layers: `Shop.Api` -> `Shop.Application` -> `Shop.Domain`; `Shop.Infrastructure` implements
  Application abstractions. Never reference Infrastructure from Application or Domain.
- Migrations live in `src/Shop.Infrastructure/Persistence/Migrations`. Never edit a migration that
  is already on `develop`; add a new one.
- `InvoicePaid` is a published integration contract consumed by ledger-service and
  notification-service. Do not change it without a version bump.
