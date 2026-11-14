# Default Java / Spring conventions

Used for convention-deviation analysis only when the project documents none.
When the project has its own conventions, they win; neighbouring code wins over these defaults.

- Constructor injection (final fields, no `@Autowired` on fields).
- Layering: controller → service → repository; controllers never use repositories.
- Controllers expose DTOs, never JPA entities.
- Business errors use the project's exception types; global mapping in `@RestControllerAdvice`.
- `@Transactional` on service methods, not on controllers or repositories.
- External calls outside of database transactions.
- Schema changes only through new migrations; applied migrations are immutable.
- SLF4J logging with parameters (`log.info("x {}", y)`), no string concatenation, no secrets in logs.
- Tests: JUnit 5, one behaviour per test, no `@Disabled` without an issue reference.
