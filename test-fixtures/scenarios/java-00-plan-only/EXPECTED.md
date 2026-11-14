# Expected: java-00-plan-only
Stack: Java 21 / Spring Boot 3
Change source: uncommitted vs HEAD (+ untracked)

- 2 untracked files, no code change: spec `docs/superpowers/specs/2026-11-10-order-refunds-design.md` (~2,850 words) and plan `docs/superpowers/plans/2026-11-10-order-refunds.md` (~2,240 words).
- Both are deliberately verbose (restated background, glossary, boilerplate goals/testing/rollout/summary sections). The plugin is mainly tested here on **summarising** and **spec-vs-plan comparison**.

## Expected review mode
`ai-review-only` — documentation only, nothing executable changes, so build/tests/static add nothing; an AI read is needed to surface the two spec/plan contradictions and the open questions, which a human must then decide (as questions, not as a code review). Must NOT be `human-only` or `ai+human-critical-paths` (no code path is touched).

## Expected top files (ordered, approximate)
1. `docs/superpowers/specs/2026-11-10-order-refunds-design.md` — source of the requirements; security (FR-5) and data-integrity (FR-3, §12) decisions live here
2. `docs/superpowers/plans/2026-11-10-order-refunds.md` — contradicts the spec in two places, misses NFR-3, adds unrequired Task 9

## Must-detect signals
Summary of the spec must surface the buried essentials (not the boilerplate):
- [ ] core_logic: full + partial refunds per line (productId + quantity, empty lines = refund the rest), reason required (≤ 500 chars) + reason category — spec FR-1
- [ ] core_logic: 30-day window counted from `paidAt`; never-paid orders not refundable — spec FR-2
- [ ] data_integrity: cumulative refunds never exceed the captured amount, also under concurrency; over-cap requests are **rejected, not clamped** (`REFUND_EXCEEDS_CAPTURED_AMOUNT`) — spec FR-3
- [ ] core_logic: discounted orders refunded pro-rata **by value**: `lineRefund = lineGross × total / subtotal`; allocation by quantity explicitly wrong; last refund absorbs rounding — spec FR-4
- [ ] security: only `SUPPORT` may create refunds; owner may only read the list — spec FR-5
- [ ] data_integrity: mandatory `Idempotency-Key` header (UUID), unique constraint, same key + different payload → `IDEMPOTENCY_KEY_REUSED`, key forwarded to gateway — spec FR-6
- [ ] contracts: new statuses `PARTIALLY_REFUNDED` / `REFUNDED` (terminal), refund allowed from PAID/SHIPPED/DELIVERED/PARTIALLY_REFUNDED — spec FR-7
- [ ] contracts: `POST /api/orders/{orderId}/refunds` returning `RefundDto`, `GET` list; `OrderDto.refundedAmount` additive only — spec §9
- [ ] contracts: event = `OrderStatusChanged` **v2** on `shop.order.status-changed.v2`, v1 kept in parallel, **no** separate `OrderRefunded` event — spec §10
- [ ] data_integrity: new migration `V3__create_refunds.sql` (refunds, refund_lines, `orders.refunded_amount`), V1/V2 untouched — spec §11
- [ ] integration: two-phase ordering: tx1 lock + validate + insert PENDING, gateway call outside any transaction, tx2 COMPLETED/FAILED + order update + events; PENDING counts towards the cap — spec §12
- [ ] config_infra / non-functional: audit log NFR-3 (append-only `audit_log`, every attempt incl. rejected ones, 7-year retention, mandatory for go-live); metrics NFR-2; feature flag `shop.refunds.enabled` — spec §13, §16

Spec vs plan comparison:
- [ ] contradiction 1 (security): spec FR-5 "only SUPPORT may create refunds; customers, including the owner, cannot" vs plan Task 7 `@PreAuthorize("hasRole('SUPPORT') or @orderSecurity.isOwner(#orderId, authentication)")` "so that customers can self-serve"
- [ ] contradiction 2 (contracts): spec §10 `OrderStatusChanged` v2 on a new topic, explicitly no `OrderRefunded` event vs plan Task 8 new `OrderRefundedEvent` v1 on `shop.order.refunded.v1` with `OrderStatusChanged` v1 unchanged (spec §18 even lists the separate event as a rejected alternative)
- [ ] requirement not addressed by the plan: NFR-3 audit log (the word "audit" does not appear in the plan; no table, task or file)
- [ ] plan step without a requirement: Task 9 "Product price caching" (Caffeine, `ProductPriceCache`, `CacheConfig`, `pom.xml`, `ProductService`) — no spec requirement mentions caching or price lookup performance
- [ ] open question OQ-1: claw back the 5% volume discount when a partial refund drops the remaining subtotal below 500.00?
- [ ] open question OQ-2: four-eyes approval for refunds above ~1,000.00 EUR (would need an approval sub-state of PENDING)?

Plan file list (Superpowers "File Structure", must be extracted): create `V3__create_refunds.sql`, `order/domain/{Refund,RefundLine,RefundStatus}.java`, `order/repository/RefundRepository.java`, `order/service/RefundService.java`, `order/controller/RefundController.java`, `order/dto/{RefundRequest,RefundDto}.java`, `order/event/OrderRefundedEvent.java`, `product/service/ProductPriceCache.java`, `config/CacheConfig.java`, `RefundServiceTest`, `RefundControllerTest`; modify `Order`, `OrderStatus`, `Money`, `PaymentClient`, `OrderDto`, `OrderMapper`, `OrderEventPublisher`, `ShopKafkaProperties`, `KafkaConfig`, `ProductService`, `application.yml`, `pom.xml`, `PaymentClientTest`. Not in the list: `SecurityConfig` (relevant for java-03).

## Traps (must NOT rank high)
- Boilerplate spec sections (§1 Overview, §2 Background, §3 Goals, §5 Glossary, §6 Stakeholders, §15 Testing, §17 Risks, §20 Summary) and plan sections (Context, Conventions Reminder, Definition of Done, Self-Review, Execution Handoff) — restatements; a summary that spends its space on them has failed.
- Plan "Self-Review" claims full spec coverage — it is wrong (NFR-3 missing, FR-5/§10 contradicted); the plugin must not take it at face value.

## Plan vs implementation (only for scenarios with docs)
- No implementation in this scenario. Expected output is the spec-vs-plan comparison above; "implementation" side is empty (all plan tasks "not started").
- Incidental, not planted (do not penalise either way): spec §9.4 maps `PAYMENT_REFUND_FAILED` to 502 while also saying all errors are `BusinessRuleException` (which the handler maps to 422).
