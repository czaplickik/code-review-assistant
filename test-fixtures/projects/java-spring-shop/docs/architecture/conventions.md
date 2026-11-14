# Engineering conventions

These rules are enforced in code review. If a rule does not fit your change, raise it in
`#shop-backend` before merging, do not quietly deviate.

## 1. Package layout and layering

```
com.example.shop.<feature>.controller   REST endpoints, request validation, HTTP mapping only
com.example.shop.<feature>.service      transactions, business rules, DTO mapping (service or a mapper it calls)
com.example.shop.<feature>.repository   Spring Data repositories
com.example.shop.<feature>.domain       JPA entities, enums, invariants
com.example.shop.<feature>.dto          request/response records
com.example.shop.<feature>.event        Kafka event records and publishers
```

- Dependencies point inwards: `controller -> service -> repository/domain`. A repository or
  entity never depends on a service; a service never depends on a controller.
- **Services never return JPA entities to controllers.** Map to a DTO inside the service
  layer (directly or via a `*Mapper` component in the same `service` package). Controllers
  never expose entities in a response body.
- Cross-feature calls go service-to-service, never controller-to-foreign-repository.

## 2. Dependency injection

- **Constructor injection only.** No `@Autowired` on fields or setters. Fields are `private final`.
- One public constructor per Spring bean; no Lombok `@RequiredArgsConstructor` (we do not use Lombok).

## 3. Errors

- **Business errors are subclasses of `com.example.shop.common.error.DomainException`**:
  `ResourceNotFoundException` (404), `BusinessRuleException` (422), `ForbiddenOperationException` (403).
  Never throw a raw `RuntimeException`, `IllegalStateException` or `ResponseStatusException`
  for a business condition. `IllegalArgumentException` is acceptable only for programming
  errors inside value objects (e.g. currency mismatch in `Money`).
- Every `BusinessRuleException` carries a stable, UPPER_SNAKE error `code`; clients depend on it.
- `GlobalExceptionHandler` is the only place that maps exceptions to HTTP responses (RFC 7807 `ProblemDetail`).

## 4. Money

- All monetary values in domain and service code are `com.example.shop.common.Money`.
  Entities persist `BigDecimal` + currency and expose `Money` getters.
- Rounding is HALF_EVEN at scale 2, defined once in `Money`. Do not round anywhere else.
  `Money` is used by orders, products, payments and events: any behavioural change to it
  needs sign-off from the payments owner.

## 5. Transactions and integration

- `@Transactional` lives on service methods only. Any method that performs more than one
  write must be transactional.
- **Never call an external HTTP service (payment gateway, carriers) inside a database
  transaction.** Pattern (see `OrderService#payOrder`): validate + load in a short
  transaction, call the gateway outside it, persist the result in a second transaction.
- Every outbound HTTP client has explicit connect/read timeouts and a bounded retry policy.
  Only idempotent calls (or calls with an `Idempotency-Key`) may be retried.

## 6. Kafka events

- Events are immutable records in `<feature>.event` with an explicit `schemaVersion` and a
  `SCHEMA_VERSION` constant. Topic names end with the major version (`shop.order.placed.v1`).
- Within a version only **additive, optional** fields are allowed. Renaming/removing a field
  or changing its type/semantics requires a new version (new record + new topic) and a
  migration window where both are published.
- Events are published after commit (`@TransactionalEventListener(phase = AFTER_COMMIT)`).

## 7. REST API contracts

- Response DTOs are part of the public contract (mobile app, back-office). Renaming or removing
  a JSON field is a breaking change and needs an API version bump; adding fields is fine.
- Authorization is declared on controller methods with `@PreAuthorize`. Resource ownership is
  checked with `@orderSecurity.isOwner(#orderId, authentication)` (or the equivalent bean for
  the resource). Role-only checks (`hasRole('USER')`) are **not** sufficient for per-customer data.

## 8. Database migrations (Flyway)

- One migration per change: `V<next>__<snake_case_description>.sql`.
- **Never edit a migration that has been merged to `develop`** — it is already applied in
  shared environments and Flyway will fail on checksum mismatch. Add a new migration instead.
- Data-rewriting migrations (`UPDATE`/`DELETE` on existing rows) need a backup plan described
  in the PR and an explicit review by the data owner.

## 9. Logging

- SLF4J only: `private static final Logger log = LoggerFactory.getLogger(Foo.class);`
- Structured messages: a short human-readable message followed by `key=value` pairs, e.g.
  `log.info("Order placed orderId={} userId={} total={}", ...)`. No string concatenation.
- Never log secrets, tokens, passwords, full card data or raw request bodies.

## 10. Security

- Passwords: `BCryptPasswordEncoder` with cost 12 (`PasswordConfig`). Tests that need speed
  override the bean in test configuration, never in main code.
- JWT access tokens are short-lived (15 min) and always validated for signature, issuer and
  expiry. Refresh tokens are opaque, stored hashed in `refresh_tokens`, rotated on use.
- `SecurityConfig` changes (especially `permitAll`) require review by a second backend dev.

## 11. Tests

- JUnit 5 + Mockito for services, `@WebMvcTest` + MockMvc for controllers, Testcontainers for
  repository/integration tests (tagged `integration`).
- Test method names: `should_<behaviour>_when_<condition>`, e.g.
  `should_cap_discount_when_coupon_and_volume_discount_exceed_limit`.
- Assert on behaviour and values, not just "no exception". Do not delete, weaken or `@Disabled`
  an existing test to get a green build; fix the code or open a ticket and fix the test in the same PR.
