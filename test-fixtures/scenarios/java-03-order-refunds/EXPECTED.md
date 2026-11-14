# Expected: java-03-order-refunds
Stack: Java 21 / Spring Boot 3
Change source: uncommitted vs HEAD (+ untracked)

- 27 files: 15 modified + 12 untracked (10 code/test files + spec + plan copied from java-00).
- Implements (badly) the java-00 plan. Base refund-free code is on `develop`.

## Expected review mode
`ai+human-critical-paths` — money-moving feature touching core logic (refund calculation, shared `Money` rounding), security (who may refund), data integrity (gateway call inside the DB transaction, edited applied migration) and contracts (REST JSON rename, Kafka schema change without bump). AI triage is useful for the ~20 low/medium files; the CRITICAL files need a human. `human-only` is defensible (refund endpoint is a security boundary moving money), `ai-review-only` / `build+tests+static` are wrong.

## Expected top files (ordered, approximate)
1. `src/main/java/com/example/shop/order/service/RefundService.java` — new 242-line file, `refund()` is one 167-line `@Transactional` method (L69–236) mixing validation, calculation, gateway call, persistence, stock and events (drift risk); `paymentClient.refund(...)` at L194 inside the transaction, before `refundRepository.save` (L203); pro-rata by **quantity** `discount.proportion(quantity, totalUnits)` (L168) instead of by value; over-cap amount silently **clamped** (L183–186) instead of rejected; idempotency key derived from `previousRefunds.size() + 1` (L193); no row lock (`findWithItemsById`, no `FOR UPDATE`) so concurrent refunds both pass the cap; 6 `@Autowired` fields (L51–67); 12× `throw new RuntimeException(...)` (→ 500 via generic handler) [CRITICAL]
2. `src/main/java/com/example/shop/order/controller/RefundController.java` — `@PreAuthorize("hasRole('USER')")` (L31) with no `@orderSecurity.isOwner` check: any customer can refund any order; SUPPORT (single-role users) is locked out — neither spec (SUPPORT only) nor plan (SUPPORT or owner); list endpoint same (L40) → any customer reads any order's refunds; returns the `Refund` JPA entity (L32, L41) [CRITICAL]
3. `src/main/java/com/example/shop/common/Money.java` — `ROUNDING` HALF_EVEN → HALF_UP (L18) on the highest fan-in type (Order, OrderItem, OrderService discount calc, Product, ProductService, PaymentClient capture amounts, OrderPlacedEvent amounts via Order, 3 test classes); Javadoc rewritten to justify it; plan Task 3 says "do not change the existing rounding mode"; conventions §4 require payments-owner sign-off; adds `proportion(long,long)` and `proportion(Money,Money)` [CRITICAL]
4. `src/main/resources/db/migration/V2__order_discounts_and_payment.sql` — already-applied migration edited to add `refunded_amount` and `last_refunded_at` (L6–7); Flyway checksum failure in every shared environment, columns never created there; spec/plan put them in V3 [CRITICAL]
5. `src/main/java/com/example/shop/order/event/OrderStatusChangedEvent.java` — field `toStatus` renamed to `status`, `refundedAmount` inserted, `SCHEMA_VERSION` still `1` (L21) on `shop.order.status-changed.v1`; breaks every consumer reading `toStatus` (conventions §6) [CRITICAL]
6. `src/main/java/com/example/shop/order/dto/OrderDto.java` — public JSON field `total` renamed to `totalAmount` (breaking for mobile app/back-office), `refundedAmount` added (fine); plan Task 7 says "do not rename existing fields"
7. `src/test/java/com/example/shop/order/service/OrderServiceTest.java` — weakened: cap test lost `discountPercent`/`discount`/`total` assertions, replaced by `totalAmount()).isNotNull()` (L104); `should_restore_stock_when_order_cancelled` `@Disabled("flaky on CI …")` (L139); rounding test renamed to `…half_up…` and expected values changed 15.02/45.08 → 15.03/45.07 to follow the Money change
8. `src/main/java/com/example/shop/order/domain/Order.java` — `registerRefund` (L136) has no cap invariant (`>= 0` → REFUNDED hides an over-refund); new columns mapped that only exist via the edited V2; plus trivial getters (`getRefundedAmount`, `getLastRefundedAt`, `getUpdatedAt`, `getVersion`)
9. `src/main/java/com/example/shop/payment/PaymentClient.java` — new `refund()` (L104): no 4xx handling, no recovery callback (raw `HttpServerErrorException` after retries), no status check of the gateway response; `PaymentClientTest` not extended (plan Task 4)
10. `src/main/java/com/example/shop/security/SecurityConfig.java` — not in the plan; adds URL rule `POST /api/orders/*/refunds` `hasAnyRole("USER", "SUPPORT")` (L42), which signals intent to let SUPPORT in but is overridden by the method-level `hasRole('USER')`
11. `src/main/java/com/example/shop/order/domain/OrderStatus.java` — new `PARTIALLY_REFUNDED`/`REFUNDED`; `DELIVERED` no longer terminal (changes `isTerminal()` semantics)
12. `src/main/resources/db/migration/V3__create_refunds.sql` — refunds tables without `idempotency_key` (UNIQUE) and `reason_category` required by spec/plan
13. `src/test/java/com/example/shop/order/service/RefundServiceTest.java` — 2 tests, single-line order only (pro-rata bug invisible), `isInstanceOf(RuntimeException.class)`; plan required a two-line discounted order case
14. `src/test/java/com/example/shop/order/controller/OrderControllerTest.java` — `$.total` → `$.totalAmount` assertion edited to follow the breaking rename
15. `src/main/java/com/example/shop/order/event/OrderEventPublisher.java`, `src/main/java/com/example/shop/order/event/OrderRefundedEvent.java`, `src/main/java/com/example/shop/config/ShopKafkaProperties.java`, `src/main/resources/application.yml` — new `OrderRefunded` v1 on `shop.order.refunded.v1`; no `NewTopic` bean in `KafkaConfig` (plan Task 8)

## Must-detect signals
- [ ] core_logic: pro-rata implemented by quantity, not value. Example: lines 100.00×1 + 10.00×3, subtotal 130.00, 20% discount 26.00, total 104.00; refunding the 100.00 line should return 80.00 (100 × 104/130), implementation returns 93.50 (100 − 26 × 1/4) — `src/main/java/com/example/shop/order/service/RefundService.java`
- [ ] core_logic: large contiguous new block, 167-line method — drift risk — `RefundService.java`
- [ ] data_integrity: gateway refund call inside `@Transactional` before the DB write (money refunded at gateway even if the commit fails; row held during HTTP call); plan Task 5 / spec §12 / conventions §5 require two-phase — `RefundService.java`
- [ ] data_integrity: cap not concurrency-safe (no lock, PENDING not counted) and over-cap amounts clamped instead of rejected (spec FR-3) — `RefundService.java`
- [ ] data_integrity: no client idempotency key; derived key `order-<id>-refund-<n>` collides for concurrent requests and changes on retry — `RefundService.java`
- [ ] conventions: `@Autowired` field injection; `throw new RuntimeException` instead of `DomainException` subclasses — `RefundService.java`
- [ ] security: refund endpoint `hasRole('USER')` without ownership check — `src/main/java/com/example/shop/order/controller/RefundController.java`
- [ ] conventions / architecture: controller returns JPA entity `Refund` (and `List<Refund>`) — `RefundController.java`
- [ ] core_logic: `Money` rounding HALF_EVEN → HALF_UP, blast radius via fan-in — `src/main/java/com/example/shop/common/Money.java`
- [ ] data_integrity: applied migration V2 edited — `src/main/resources/db/migration/V2__order_discounts_and_payment.sql`
- [ ] contracts: Kafka event field renamed (`toStatus` → `status`) without version bump — `src/main/java/com/example/shop/order/event/OrderStatusChangedEvent.java`
- [ ] contracts: REST DTO field renamed `total` → `totalAmount` — `src/main/java/com/example/shop/order/dto/OrderDto.java`
- [ ] tests: weakened existing test (assertions removed, `@Disabled`, expectations changed to match new rounding) — `src/test/java/com/example/shop/order/service/OrderServiceTest.java`
- [ ] tests: new 167-line method covered by 2 single-line tests — `src/test/java/com/example/shop/order/service/RefundServiceTest.java`
- [ ] error_handling / integration: refund call without 4xx mapping / recovery / response-status check — `src/main/java/com/example/shop/payment/PaymentClient.java`
- [ ] security (low): unplanned `SecurityConfig` URL rule for refunds — `src/main/java/com/example/shop/security/SecurityConfig.java`

## Traps (must NOT rank high)
- `src/main/java/com/example/shop/product/controller/ProductController.java` — line-wrapping only (3 signatures/returns re-wrapped), no semantic change, not in the plan
- `src/main/java/com/example/shop/order/domain/RefundLine.java` — `@Embeddable` with three fields and getters
- `src/main/java/com/example/shop/order/dto/RefundRequest.java` — new record, validation annotations only
- `src/main/java/com/example/shop/order/domain/RefundStatus.java` — 3-constant enum
- `src/main/java/com/example/shop/order/repository/RefundRepository.java` — one derived query
- `src/main/java/com/example/shop/order/service/OrderMapper.java` — one added mapping line
- `docs/superpowers/specs/2026-11-10-order-refunds-design.md`, `docs/superpowers/plans/2026-11-10-order-refunds.md` — context for plan-vs-implementation, not risk

## Plan vs implementation (only for scenarios with docs)
- Unplanned files changed: `src/main/java/com/example/shop/security/SecurityConfig.java` (primary), `src/main/java/com/example/shop/product/controller/ProductController.java` (formatting), `OrderServiceTest.java` and `OrderControllerTest.java` (plan says existing tests keep passing unmodified), `V2__order_discounts_and_payment.sql` (plan: V1/V2 not touched).
- Planned but not implemented: Task 6 idempotency key (no `Idempotency-Key` header, no `idempotency_key` column, no `findByIdempotencyKey`) — primary; Task 7 `RefundDto` and `RefundControllerTest` not created, `@ConditionalOnProperty` feature flag missing; Task 4 `PaymentClientTest` not extended; Task 5 step 4 metrics missing; Task 8 `KafkaConfig` topic bean missing; Task 9 product price caching (`ProductPriceCache`, `CacheConfig`, `ProductService`, `pom.xml`) not implemented (fine — it had no requirement).
- Implemented differently from the plan: Task 1 `refunded_amount` added by editing V2 instead of V3; Task 3 rounding changed despite "do not change"; Task 5 single transaction with gateway call inside instead of the two-phase pattern, quantity-based allocation instead of `Money#proportion(Money, Money)`; Task 7 authorization `hasRole('USER')` instead of `hasRole('SUPPORT') or @orderSecurity.isOwner(...)`; Task 7 `OrderDto` rename instead of additive field; Task 8 `OrderStatusChanged` v1 changed incompatibly (plan: unchanged).
- Spec requirements: NFR-3 audit log neither planned nor implemented; FR-3 "reject, do not clamp" violated; FR-5 (SUPPORT only) violated; spec §10 (OrderStatusChanged v2) not followed — implementation follows the plan's `OrderRefunded` v1 and additionally breaks v1.
