# AI review — .NET specifics

- Look for existing building blocks first: shared value objects (`Money`), `DomainException`
  hierarchy and ProblemDetails mapping, base entity / repository types, `IClock` /
  `TimeProvider`, result types, paging helpers, extension methods, test builders.
- Typical AI deviations: service locator (`GetService`), `.Result`/`.Wait()`, missing
  `CancellationToken` propagation, `new HttpClient()`, `DateTime.Now` instead of the injected
  clock, controllers returning EF entities or using `DbContext` directly, `throw new Exception`,
  `async void`, synchronous EF calls (`ToList()` instead of `ToListAsync`).
- Dead code: unused `private`/`internal` members, DTO properties never set, DI registrations
  of types nobody resolves, options classes never bound.
- Tests: `[Fact(Skip=...)]`, assertions loosened (`BeCloseTo` with wide tolerance, `NotBeNull`
  only), tests asserting the mock setup, missing tests for the new branch.
