# AI review — Java / Spring specifics

- Look for existing building blocks before accepting new ones: `common` packages (value
  objects like `Money`, error hierarchy, pagination, mappers), `@ConfigurationProperties`
  records, `Clock` beans, test fixtures/builders.
- Typical AI deviations: `@Autowired` fields, `RuntimeException` instead of the project's
  exceptions, controllers returning entities, `Optional.get()` without check, manual mapping
  where MapStruct/mappers exist, `@Transactional` on private methods or self-invocation,
  `findAll()` then filtering in memory, `new ObjectMapper()` instead of the injected one,
  `LocalDateTime.now()` instead of the injected `Clock`.
- Dead code: unused `private` methods, DTO fields never mapped, repository methods never
  called, `@Bean`s nobody injects, new properties never bound.
- Tests: `@MockBean` everywhere instead of slice tests the project uses; assertions only on
  `verify(...)`; `@Disabled`; expected values copied from the implementation's output.
