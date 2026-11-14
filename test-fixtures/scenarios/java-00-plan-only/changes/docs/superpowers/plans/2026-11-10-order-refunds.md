# Order Refunds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement full and partial order refunds as described in the design specification `docs/superpowers/specs/2026-11-10-order-refunds-design.md`.

**Architecture:** A new `RefundService` in the order feature orchestrates validation, amount calculation, the payment-gateway refund call and persistence. A new `RefundController` exposes the REST endpoints. Refunds are stored in new tables created by a new Flyway migration. A new Kafka event informs downstream systems. The implementation follows the existing layering (controller → service → repository/domain) and the project conventions.

**Tech Stack:** Java 21, Spring Boot 3.3, Spring Data JPA, PostgreSQL, Flyway, Spring Kafka, Spring Retry, JUnit 5, Mockito, MockMvc.

---

## Context

This plan breaks the refund feature down into small, independently verifiable tasks. Each task follows the test-driven development cycle: write a failing test, run it to see it fail, implement the minimal code to make it pass, run the tests again, and commit. Following this cycle consistently ensures that the implementation is correct, well-tested and easy to review. Tasks are ordered so that each one builds on the previous one, starting with the database and the domain model and ending with the API and the events.

Before starting, make sure that the project builds and all existing tests pass:

```bash
mvn -q verify
```

If any test is failing before you start, stop and report it instead of continuing, so that pre-existing failures are not confused with failures introduced by this work.

## Conventions Reminder

The project has explicit conventions in `docs/architecture/conventions.md`. They apply to every task in this plan. The most relevant ones are repeated here for convenience, so that the implementer does not have to switch between documents:

- **Constructor injection only.** All new Spring beans (`RefundService`, `RefundController`, `ProductPriceCache`) receive their dependencies through a single public constructor. Fields are `private final`. No `@Autowired` on fields.
- **Business errors are `DomainException` subclasses.** Use `BusinessRuleException` with the error codes listed in the specification. Never throw a raw `RuntimeException`.
- **Services return DTOs.** `RefundService` returns `RefundDto`; the controller never returns the `Refund` entity.
- **Money is always `Money`.** No `double`, no ad-hoc `BigDecimal` arithmetic in the service.
- **One migration per change.** The refunds schema goes into a new `V3__create_refunds.sql`. `V1` and `V2` are not touched.
- **No external HTTP inside a transaction.** The gateway refund call happens between two short transactions, like `OrderService#payOrder`.
- **Versioned events.** New event types start at schema version 1; existing events are not changed incompatibly.
- **Logging.** SLF4J with a short message followed by `key=value` pairs.
- **Tests.** `should_<behaviour>_when_<condition>`; existing tests are not weakened or disabled.

Keeping these conventions in mind from the start avoids rework during code review.

## File Structure

The following files will be created or modified. Paths are relative to the repository root.

**Create:**
- `src/main/resources/db/migration/V3__create_refunds.sql`
- `src/main/java/com/example/shop/order/domain/Refund.java`
- `src/main/java/com/example/shop/order/domain/RefundLine.java`
- `src/main/java/com/example/shop/order/domain/RefundStatus.java`
- `src/main/java/com/example/shop/order/repository/RefundRepository.java`
- `src/main/java/com/example/shop/order/service/RefundService.java`
- `src/main/java/com/example/shop/order/controller/RefundController.java`
- `src/main/java/com/example/shop/order/dto/RefundRequest.java`
- `src/main/java/com/example/shop/order/dto/RefundDto.java`
- `src/main/java/com/example/shop/order/event/OrderRefundedEvent.java`
- `src/main/java/com/example/shop/product/service/ProductPriceCache.java`
- `src/main/java/com/example/shop/config/CacheConfig.java`
- `src/test/java/com/example/shop/order/service/RefundServiceTest.java`
- `src/test/java/com/example/shop/order/controller/RefundControllerTest.java`

**Modify:**
- `src/main/java/com/example/shop/order/domain/Order.java`
- `src/main/java/com/example/shop/order/domain/OrderStatus.java`
- `src/main/java/com/example/shop/common/Money.java`
- `src/main/java/com/example/shop/payment/PaymentClient.java`
- `src/main/java/com/example/shop/order/dto/OrderDto.java`
- `src/main/java/com/example/shop/order/service/OrderMapper.java`
- `src/main/java/com/example/shop/order/event/OrderEventPublisher.java`
- `src/main/java/com/example/shop/config/ShopKafkaProperties.java`
- `src/main/java/com/example/shop/config/KafkaConfig.java`
- `src/main/java/com/example/shop/product/service/ProductService.java`
- `src/main/resources/application.yml`
- `pom.xml`
- `src/test/java/com/example/shop/payment/PaymentClientTest.java`

---

### Task 1: Database migration

**Files:**
- Create: `src/main/resources/db/migration/V3__create_refunds.sql`

- [ ] **Step 1: Write the migration**

```sql
CREATE TABLE refunds (
    id                BIGSERIAL     PRIMARY KEY,
    order_id          BIGINT        NOT NULL REFERENCES orders (id),
    requested_by      BIGINT        NOT NULL REFERENCES users (id),
    amount            NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    currency          CHAR(3)       NOT NULL,
    status            VARCHAR(20)   NOT NULL,
    reason_category   VARCHAR(20)   NOT NULL,
    reason            VARCHAR(500)  NOT NULL,
    idempotency_key   UUID          NOT NULL UNIQUE,
    gateway_reference VARCHAR(64),
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
    completed_at      TIMESTAMPTZ
);

CREATE TABLE refund_lines (
    refund_id  BIGINT        NOT NULL REFERENCES refunds (id) ON DELETE CASCADE,
    product_id BIGINT        NOT NULL,
    quantity   INTEGER       NOT NULL CHECK (quantity > 0),
    amount     NUMERIC(12,2) NOT NULL
);

ALTER TABLE orders ADD COLUMN refunded_amount NUMERIC(12,2) NOT NULL DEFAULT 0;

CREATE INDEX idx_refunds_order ON refunds (order_id);
```

- [ ] **Step 2: Verify the migration applies on a clean database**

Run: `mvn -q verify -Dgroups=integration -Dtest=FlywayMigrationIT`
Expected: PASS, schema validated by Hibernate.

- [ ] **Step 3: Commit**

```bash
git add src/main/resources/db/migration/V3__create_refunds.sql
git commit -m "feat(refunds): add refunds schema"
```

### Task 2: Domain model

**Files:**
- Create: `order/domain/Refund.java`, `order/domain/RefundLine.java`, `order/domain/RefundStatus.java`
- Modify: `order/domain/Order.java`, `order/domain/OrderStatus.java`

- [ ] **Step 1: Write failing tests for the new state transitions**

Add tests that verify that `PAID`, `SHIPPED`, `DELIVERED` and `PARTIALLY_REFUNDED` can transition to `PARTIALLY_REFUNDED` and `REFUNDED`, and that `REFUNDED` is terminal.

- [ ] **Step 2: Extend `OrderStatus`**

Add `PARTIALLY_REFUNDED` and `REFUNDED` and the transitions listed above to the `ALLOWED` map. Keep the existing transitions unchanged.

```java
ALLOWED.put(PAID, EnumSet.of(SHIPPED, PARTIALLY_REFUNDED, REFUNDED));
ALLOWED.put(SHIPPED, EnumSet.of(DELIVERED, PARTIALLY_REFUNDED, REFUNDED));
ALLOWED.put(DELIVERED, EnumSet.of(PARTIALLY_REFUNDED, REFUNDED));
ALLOWED.put(PARTIALLY_REFUNDED, EnumSet.of(PARTIALLY_REFUNDED, REFUNDED));
ALLOWED.put(REFUNDED, EnumSet.noneOf(OrderStatus.class));
```

Note that `DELIVERED` is no longer terminal after this change. Check all callers of `isTerminal()` and confirm that this is acceptable for them.

- [ ] **Step 3: Add `refundedAmount` to `Order`**

Add the `refunded_amount` column mapping, a `getRefundedAmount()` getter returning `Money`, and a `registerRefund(Money amount, Instant at)` method that adds the amount, verifies the cap (refunded ≤ total) as an invariant, and transitions to `REFUNDED` or `PARTIALLY_REFUNDED`.

- [ ] **Step 4: Create `Refund`, `RefundLine` (embeddable) and `RefundStatus` (`PENDING`, `COMPLETED`, `FAILED`)**

`Refund` exposes `complete(String gatewayReference, Instant at)` and `fail(Instant at)`.

- [ ] **Step 5: Run tests and commit**

Run: `mvn -q test -Dtest=OrderStatusTest`
Expected: PASS.

### Task 3: Money helper for pro-rata allocation

**Files:**
- Modify: `src/main/java/com/example/shop/common/Money.java`

- [ ] **Step 1: Write a failing test**

`Money.of("100.00","EUR").proportion(Money.of("88.00","EUR"), Money.of("110.00","EUR"))` must return `80.00`.

- [ ] **Step 2: Implement `proportion(Money numerator, Money denominator)`**

Multiply first, divide last, use the existing `ROUNDING`. **Do not change the existing rounding mode or any existing method** — `Money` is used across orders, products, payments and events.

- [ ] **Step 3: Run tests and commit**

### Task 4: Payment gateway refund call

**Files:**
- Modify: `src/main/java/com/example/shop/payment/PaymentClient.java`
- Modify: `src/test/java/com/example/shop/payment/PaymentClientTest.java`

- [ ] **Step 1: Write failing tests with `MockRestServiceServer`**

Cover: successful refund, retry on 503 with the same idempotency key, no retry on 4xx, gateway unavailable after retries.

- [ ] **Step 2: Implement `refund(RefundCommand)`**

```java
public record RefundCommand(String paymentReference, Money amount, String idempotencyKey) {}
public record RefundResult(String refundReference, String status) {}
```

`POST /v1/captures/{paymentReference}/refunds` with the `Idempotency-Key` header, reusing the existing `RetryTemplate` and timeouts.

- [ ] **Step 3: Run tests and commit**

### Task 5: RefundService

**Files:**
- Create: `src/main/java/com/example/shop/order/service/RefundService.java`
- Create: `src/main/java/com/example/shop/order/repository/RefundRepository.java`
- Create: `src/test/java/com/example/shop/order/service/RefundServiceTest.java`

- [ ] **Step 1: Write failing tests for the calculation**

Include a discounted order with two lines of different prices (100.00 and 10.00, 20% discount); refunding the 100.00 line must return 80.00. Include the 30-day boundary, the cap and invalid quantities.

- [ ] **Step 2: Implement the service using the two-phase pattern of `OrderService#payOrder`**

1. `TransactionTemplate` #1: lock and load the order, validate status, window, quantities and cap (including `PENDING` refunds), compute the amount with `Money#proportion`, save the refund as `PENDING`.
2. Outside any transaction: `paymentClient.refund(...)`.
3. `TransactionTemplate` #2: `refund.complete(...)`, `order.registerRefund(...)`, release stock for `PAID` orders, publish events.

Use constructor injection and `BusinessRuleException` with the error codes from the spec.

Suggested skeleton:

```java
@Service
public class RefundService {

    private final OrderRepository orderRepository;
    private final RefundRepository refundRepository;
    private final PaymentClient paymentClient;
    private final ProductRepository productRepository;
    private final ApplicationEventPublisher events;
    private final TransactionTemplate transactionTemplate;
    private final Clock clock;

    // constructor omitted

    public RefundDto refund(Long orderId, UUID idempotencyKey, RefundRequest request, AuthenticatedUser requester) {
        Refund pending = transactionTemplate.execute(status -> validateAndReserve(orderId, idempotencyKey, request, requester));
        PaymentClient.RefundResult result = paymentClient.refund(new PaymentClient.RefundCommand(
                pending.getPaymentReference(), pending.getAmount(), idempotencyKey.toString()));
        return transactionTemplate.execute(status -> completeRefund(pending.getId(), result));
    }
}
```

Keep `validateAndReserve` and `completeRefund` small; extract the amount calculation into a package-private method `calculateRefundAmount(Order, List<RefundRequest.Line>)` so that it can be unit-tested in isolation. A single long method mixing validation, calculation, gateway call and persistence is hard to review and should be avoided.

- [ ] **Step 3: Handle gateway failure**

If `paymentClient.refund` throws `PaymentFailedException`, mark the refund `FAILED` in its own transaction and rethrow a `BusinessRuleException` with code `PAYMENT_REFUND_FAILED`. The order is not changed.

- [ ] **Step 4: Add metrics**

Inject `MeterRegistry` and record `shop.refunds.created` and `shop.refunds.failed` counters and a `shop.refunds.amount` distribution summary, all tagged with `reasonCategory`.

- [ ] **Step 5: Run tests and commit**

Run: `mvn -q test -Dtest=RefundServiceTest`
Expected: PASS.

### Task 6: Idempotency key

**Files:**
- Modify: `order/service/RefundService.java`, `order/repository/RefundRepository.java`, `order/controller/RefundController.java`

- [ ] **Step 1: Write failing tests**

Same key + same payload returns the existing refund; same key + different payload fails with `IDEMPOTENCY_KEY_REUSED`.

- [ ] **Step 2: Implement**

Read the `Idempotency-Key` header in the controller (`@RequestHeader(name = "Idempotency-Key") UUID key`), pass it to the service, look it up via `RefundRepository#findByIdempotencyKey` before validation, and forward the same key to the gateway. The unique constraint from Task 1 is the last line of defence against races.

- [ ] **Step 3: Run tests and commit**

### Task 7: REST API

**Files:**
- Create: `order/controller/RefundController.java`, `order/dto/RefundRequest.java`, `order/dto/RefundDto.java`
- Create: `src/test/java/com/example/shop/order/controller/RefundControllerTest.java`
- Modify: `order/dto/OrderDto.java`, `order/service/OrderMapper.java`

- [ ] **Step 1: Write failing controller tests**

Cover: 201 for an allowed caller, 403 for a customer who does not own the order, 400 for an invalid body, 401 without a token.

- [ ] **Step 2: Implement the controller**

```java
@PostMapping
@PreAuthorize("hasRole('SUPPORT') or @orderSecurity.isOwner(#orderId, authentication)")
public ResponseEntity<RefundDto> create(@PathVariable Long orderId, ...)
```

Order owners are allowed to refund their own orders so that customers can self-serve simple cases from the mobile app, and support agents can refund any order. `GET /api/orders/{orderId}/refunds` uses the same expression.

Annotate the controller with `@ConditionalOnProperty(name = "shop.refunds.enabled", havingValue = "true")` and add `shop.refunds.enabled: false` to `application.yml`, so that the endpoint can be rolled out gradually.

- [ ] **Step 3: Extend `OrderDto`**

Add `refundedAmount` as a new field at the end of the record and map it in `OrderMapper`. Do not rename existing fields.

- [ ] **Step 4: Run tests and commit**

### Task 8: Kafka event

**Files:**
- Create: `order/event/OrderRefundedEvent.java`
- Modify: `order/event/OrderEventPublisher.java`, `config/ShopKafkaProperties.java`, `config/KafkaConfig.java`, `src/main/resources/application.yml`

- [ ] **Step 1: Create `OrderRefundedEvent` (schema version 1)**

```java
public record OrderRefundedEvent(UUID eventId, int schemaVersion, Long orderId, Long refundId,
        String currency, BigDecimal amount, BigDecimal totalRefundedAmount, String reasonCategory,
        Instant occurredAt) {
    public static final int SCHEMA_VERSION = 1;
}
```

- [ ] **Step 2: Publish it after commit**

Add `on(OrderRefundedEvent)` to `OrderEventPublisher` with topic `shop.order.refunded.v1` (new `orderRefunded` property), and a `NewTopic` bean in `KafkaConfig`. The existing `OrderStatusChanged` v1 event continues to be published for the status transition unchanged.

- [ ] **Step 3: Run tests and commit**

### Task 9: Product price caching

**Files:**
- Create: `product/service/ProductPriceCache.java`, `config/CacheConfig.java`
- Modify: `product/service/ProductService.java`, `pom.xml`

- [ ] **Step 1: Add Caffeine**

Add `com.github.ben-manes.caffeine:caffeine` and `spring-boot-starter-cache` to `pom.xml`, enable caching in `CacheConfig` with a `productPrices` cache (max 10,000 entries, 10-minute TTL).

- [ ] **Step 2: Cache product prices**

`ProductPriceCache#currentPrice(Long productId)` returns the current price; `ProductService#update` evicts the entry. This reduces database load when many refunds and orders are processed.

- [ ] **Step 3: Run tests and commit**

### Task 10: Full verification

- [ ] **Step 1: Run the whole test suite**

Run: `mvn -q verify`
Expected: all tests pass, including the existing `OrderServiceTest`, `OrderControllerTest`, `ProductServiceTest` and `PaymentClientTest`.

- [ ] **Step 2: Manual smoke test**

Start the application locally, place and pay an order, refund one line, refund the rest, and verify the order status, the `refunds` rows and the published events in the local Kafka.

- [ ] **Step 3: Commit any remaining changes**

---

## Definition of Done

The feature is considered done when all of the following are true:

- [ ] All tasks above are checked.
- [ ] `mvn verify` passes locally and in CI.
- [ ] No existing test was removed, weakened or disabled.
- [ ] No existing migration was modified.
- [ ] The new endpoints are covered by controller tests, including authorization.
- [ ] The refund calculation is covered by unit tests, including a multi-line discounted order.
- [ ] The new event is documented for downstream consumers.
- [ ] The pull request description links to the specification and this plan.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Double refund on client retry | Idempotency key (Task 6) and unique constraint (Task 1) |
| Over-refund on discounted orders | Value-based pro-rata via `Money#proportion` (Tasks 3, 5) and dedicated tests |
| Gateway and database out of sync | Two-phase pattern (Task 5); `PENDING` refunds remain visible for reconciliation |
| Breaking API consumers | Additive `OrderDto` change only (Task 7) |
| Breaking event consumers | New event type instead of changing `OrderStatusChanged` (Task 8) |
| Increased database load | Product price cache (Task 9) |

## Self-Review

- **Spec coverage:** partial and full refunds (Tasks 2, 5), 30-day window (Task 5), cap (Tasks 2, 5), pro-rata (Tasks 3, 5), authorization (Task 7), idempotency (Task 6), statuses (Task 2), stock (Task 5), API (Task 7), events (Task 8), migration (Task 1), transaction ordering (Task 5), metrics (Task 5), feature flag (Task 7).
- **Placeholder scan:** no TODOs left in the plan.
- **Type consistency:** `RefundCommand`, `RefundResult`, `Refund`, `RefundLine` and `RefundStatus` names are used consistently across tasks.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-11-10-order-refunds.md`. Two execution options:

1. **Subagent-driven (recommended)** — a fresh subagent per task, review between tasks.
2. **Inline execution** — execute tasks in this session with checkpoints.
