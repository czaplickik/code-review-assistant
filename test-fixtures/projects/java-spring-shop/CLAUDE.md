# CLAUDE.md

Spring Boot 3 / Java 21 e-shop backend. Build: `mvn verify`. Unit tests: `mvn test`.

Before changing code, read and follow `docs/architecture/conventions.md`. In short:

- Constructor injection only. No `@Autowired` on fields.
- Business errors are `DomainException` subclasses (`common.error`), never raw `RuntimeException`.
- Services return DTOs; controllers never see JPA entities.
- Never edit an applied Flyway migration; add a new `V<n>__*.sql`.
- Never call external HTTP (payment gateway) inside a DB transaction.
- Kafka event schemas are versioned; breaking changes need a new version.
- Tests: `should_<behaviour>_when_<condition>`; do not delete or `@Disabled` tests to make a build green.

Money is always `com.example.shop.common.Money` — never `double`, never raw `BigDecimal` in domain logic.
