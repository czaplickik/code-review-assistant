# .NET anchors

Stack-specific calibration on top of `_base/anchors.md`.

| Situation | Dimension | Points |
|---|---|---|
| New controller + service + repository + EF configuration for one entity, copying an existing feature | core_logic | 1 |
| Same, with paging/filtering, validators, relations | core_logic | 2 |
| `[AllowAnonymous]` on an endpoint handling money, PII or state changes | security | 5, critical |
| Webhook endpoint without signature verification | security | 5, critical |
| Resource-owner policy (`[Authorize(Policy = "...Owner")]`) removed from one endpoint | security | 4–5, critical |
| `ValidateLifetime = false` / `ValidateIssuerSigningKey = false` | security | 5, critical |
| Two `SaveChangesAsync` calls across aggregates without a transaction | data_integrity | 3–4 |
| Already-applied migration edited | data_integrity | 4, critical (deterministic) |
| New migration that only adds a table / nullable column | data_integrity | 1–2 |
| Migration `DropColumn` on a column holding data | data_integrity | 4–5 |
| `ModelSnapshot` change matching a new migration | data_integrity | 0–1 (consequence of the migration) |
| Integration event property removed/renamed without version bump | contracts | 4 |
| DTO property renamed (JSON name changes) | contracts | 3 |
| `Money` value object rounding / equality changed | core_logic | 4 (blast radius via fan-in) |
| Singleton with static `Dictionary` mutated by requests and a `BackgroundService` | concurrency | 4 |
| `.Result` / `.Wait()` in request path | concurrency | 3 |
| `new HttpClient()` for an external API, no timeout/retry | integration | 3–4 |
| Primary-constructor injection convention broken by `IServiceProvider.GetService` | conventions | 2 |
| `throw new Exception(...)` where a `DomainException` hierarchy exists | conventions | 2 |
| Controller returns an EF entity | architecture | 2–3 |
| `[Fact(Skip = "flaky")]` on an existing business test | tests | 4 (deterministic) |

.NET specifics to keep in mind:
- A scoped service (DbContext) captured by a singleton or a hosted service without
  `IServiceScopeFactory` is a lifetime bug — concurrency 4.
- Middleware order in `Program.cs` matters: `UseAuthentication` before `UseAuthorization`,
  both before endpoint mapping; moving them is security 4–5.
- `AsNoTracking` removal or added `Include` chains are performance; a tracked entity updated
  outside the intended unit of work is data_integrity.
- Nullable reference type warnings suppressed with `!` on external input is input validation.
