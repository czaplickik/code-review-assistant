# Default .NET conventions

Used for convention-deviation analysis only when the project documents none.
When the project has its own conventions, they win; neighbouring code wins over these defaults.

- Constructor (or primary-constructor) injection; no service locator outside the composition root.
- Async all the way; no `.Result`, `.Wait()`, `async void` (except event handlers).
- `CancellationToken` accepted and passed through on async APIs.
- Controllers/endpoints expose DTOs, never EF entities; no DbContext in the API layer.
- Domain errors as dedicated exception types mapped to ProblemDetails centrally.
- `IHttpClientFactory` / typed clients with configured timeouts and resilience.
- EF migrations are immutable once applied; schema changes via new migrations.
- Structured logging with message templates (`LogInformation("Paid {InvoiceId}", id)`).
- Tests: xUnit, `Method_Scenario_ExpectedResult`, no `Skip` without an issue reference.
