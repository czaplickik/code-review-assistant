# Order Refunds — Design Specification

**Date:** 2026-11-10
**Status:** Draft — ready for review
**Feature area:** Orders / Payments
**Related documents:** `docs/architecture/conventions.md`, implementation plan `docs/superpowers/plans/2026-11-10-order-refunds.md`

---

## 1. Overview

This document describes the design for introducing order refunds into the shop backend. Refunds are an important capability for any e-commerce platform, and our platform currently does not support them. The purpose of this specification is to capture the requirements, the proposed design, the constraints and the open questions related to refunds, so that the implementation can proceed in a structured and well-understood way.

In short, this specification proposes adding the ability to refund an order, either fully or partially, through a new REST endpoint, with the refund being executed against the external payment gateway and reflected in the order state, in the database and in the events that other systems consume.

The specification is intentionally comprehensive. It covers the background, the goals, the non-goals, the functional requirements, the API, the data model, the event model, transactional behaviour, non-functional requirements, the testing approach, the rollout, the risks and the alternatives that were considered. Readers who are only interested in a particular aspect can jump directly to the relevant section.

## 2. Background and Motivation

Today, once an order has been paid, there is no way to give money back to the customer from within the shop backend. When a customer contacts customer support because an item arrived damaged, because they changed their mind, or because an item was missing from the parcel, the support team has to log in to the payment provider's dashboard and issue the refund manually. After that, they have to remember to update the order in the back-office, which in practice often does not happen.

This manual process has several well-known problems:

- It is slow, because support agents have to switch between two systems.
- It is error-prone, because the amount is typed by hand and it is easy to make a mistake.
- It is invisible to the rest of the platform, because no event is published and no data is stored in our database.
- It makes financial reconciliation difficult, because the finance team cannot match refunds in the gateway with orders in the shop.
- It does not scale, because the number of orders is growing and the number of support requests grows with it.

It is therefore clear that the shop needs a first-class refund capability. Having refunds inside the platform will make the process faster, more reliable, more transparent and easier to reconcile. It will also make it possible to build further features on top of refunds in the future, such as returns management or store credit.

## 3. Goals

The goals of this feature are as follows:

1. Allow an order to be refunded fully.
2. Allow an order to be refunded partially.
3. Ensure that the refund is executed against the payment gateway.
4. Ensure that the refund is persisted in our database.
5. Ensure that the order state reflects the refund.
6. Ensure that other systems are informed about the refund through Kafka.
7. Ensure that the refund process is safe, reliable and consistent.
8. Ensure that the implementation follows the existing conventions of the project.

## 4. Non-Goals

To keep the scope manageable, the following items are explicitly out of scope for this iteration:

- A returns-management workflow (RMA numbers, return shipping labels, warehouse inspection).
- Store credit or gift cards as a refund method. Refunds always go back to the original payment method.
- Refunds of shipping costs. The current order model has no shipping cost, so there is nothing to refund.
- Multi-currency refunds. Refunds are always in the currency of the order.
- A user interface. The back-office UI will be built by the front-end team against the API defined here.
- Automatic refunds triggered by other systems (for example by the warehouse).

## 5. Glossary

- **Order** — a customer's purchase, represented by the `Order` entity.
- **Order item / line** — a product and quantity within an order (`OrderItem`).
- **Subtotal** — the sum of all line totals before discount.
- **Discount** — the amount subtracted from the subtotal, from a coupon and/or the volume discount, capped at 30%.
- **Total** — subtotal minus discount; this is the amount that is captured.
- **Capture** — the act of actually charging the customer through the payment gateway.
- **Captured amount** — the amount that was successfully captured for an order (equal to the order total).
- **Refund** — returning all or part of the captured amount to the customer.
- **Partial refund** — a refund of less than the full remaining refundable amount.
- **Payment gateway** — the external payment provider that we call over HTTP.
- **Idempotency key** — a client-generated unique value that allows a request to be safely retried.

## 6. Stakeholders

- **Customer support** — primary users of the refund functionality.
- **Finance** — consumers of refund data for reconciliation and reporting.
- **Customers** — receive the money back.
- **Backend team** — implements and operates the feature.
- **Front-end / back-office team** — builds the UI on top of the API.
- **Data / analytics team** — consumes Kafka events.

## 7. Current State

The current order lifecycle is implemented as an explicit state machine in `OrderStatus`. An order is created in status `CREATED`. When the payment is captured it moves to `PAID`. After that it can move to `SHIPPED` and then to `DELIVERED`. An order in status `CREATED` can be cancelled, which moves it to `CANCELLED`. There is no transition that represents a refund.

Payments are captured through `PaymentClient`, which calls the gateway's `/v1/captures` endpoint with an `Idempotency-Key` header, explicit timeouts and a bounded retry policy. `OrderService#payOrder` deliberately does not hold a database transaction while calling the gateway: it loads and validates the order in one short transaction, calls the gateway outside of any transaction, and then records the result in a second transaction.

Orders publish `OrderPlaced` (v1) and `OrderStatusChanged` (v1) events to Kafka after commit. Money is represented everywhere by the `Money` value object, with HALF_EVEN rounding at scale 2.

## 8. Functional Requirements

### FR-1: Full and partial refunds

A refund can cover the whole order or a subset of its lines. A partial refund is expressed per line, as a product id and a quantity, where the quantity is between 1 and the quantity of that line that has not been refunded yet. Several partial refunds can be issued for the same order over time. When no lines are given, the request means "refund everything that has not been refunded yet". A refund always has a free-text reason (required, max 500 characters) and a reason category (`DAMAGED`, `MISSING_ITEM`, `CHANGED_MIND`, `OTHER`).

### FR-2: Refund window

It is important that refunds are only possible for a limited time after purchase, both for business reasons and because payment providers limit how long a capture can be refunded. A refund may only be created within **30 calendar days counted from the moment the payment was captured** (`paidAt`). Requests outside the window are rejected with error code `REFUND_WINDOW_EXPIRED`. Orders that were never paid cannot be refunded at all (`ORDER_NOT_REFUNDABLE`).

### FR-3: Refund amount cap

The sum of all completed refunds of an order must **never exceed the captured amount** of that order. This must hold even under concurrent requests. A request that would exceed the remaining refundable amount is rejected with `REFUND_EXCEEDS_CAPTURED_AMOUNT`; it must not be silently reduced to the remaining amount, because the support agent needs to know that their calculation was wrong.

### FR-4: Refunds of discounted orders (pro-rata)

Orders may have a discount of up to 30%. When lines of a discounted order are refunded, the customer must receive what they actually paid for those lines, not their list price. The discount is therefore allocated to lines **pro-rata by value**:

```
lineRefund = lineGross × (orderTotal / orderSubtotal)
```

where `lineGross = unitPrice × refundedQuantity`. Allocating the discount by quantity (or splitting it evenly between lines) is explicitly wrong, because it over-refunds cheap items and under-refunds expensive ones. Rounding uses the standard `Money` rounding; the final refund that brings the order to fully refunded refunds exactly the remaining captured amount, so that rounding remainders never accumulate.

### FR-5: Who may refund

Refunds move real money and are a known fraud vector, so access must be tightly controlled. **Only users with the `SUPPORT` role may create refunds.** Customers, including the owner of the order, cannot trigger a refund themselves; they request one through a support ticket, and the support agent decides. Reading the list of refunds of an order is allowed for `SUPPORT` and for the order owner.

### FR-6: Idempotency

Support tools and network intermediaries retry requests. To prevent double refunds, every create-refund request must carry an `Idempotency-Key` header (UUID). The key is stored with the refund under a unique constraint. A repeated request with the same key and the same payload returns the original refund with `200 OK` instead of creating a new one; the same key with a different payload is rejected with `IDEMPOTENCY_KEY_REUSED`. The same key is forwarded to the payment gateway.

### FR-7: Order status

Two new statuses are added to the state machine: `PARTIALLY_REFUNDED` and `REFUNDED`. A refund is allowed from `PAID`, `SHIPPED`, `DELIVERED` and `PARTIALLY_REFUNDED`. After a refund, the order is `REFUNDED` if the refunded amount equals the captured amount and `PARTIALLY_REFUNDED` otherwise. `REFUNDED` is terminal.

### FR-8: Stock

If the order has not been shipped yet (status `PAID`), refunded quantities are released back to stock. For shipped orders the stock is not changed, because the goods are not back in the warehouse.

## 9. API Design

### 9.1 Create refund

```
POST /api/orders/{orderId}/refunds
Idempotency-Key: 4f7c2d0e-...
Authorization: Bearer <SUPPORT token>

{
  "reasonCategory": "DAMAGED",
  "reason": "Keyboard arrived with broken keycaps",
  "lines": [ { "productId": 12, "quantity": 1 } ]
}
```

Response `201 Created`:

```
{
  "refundId": 91,
  "orderId": 1234,
  "status": "COMPLETED",
  "amount": 71.92,
  "currency": "EUR",
  "lines": [ { "productId": 12, "quantity": 1, "amount": 71.92 } ],
  "createdAt": "2026-11-12T10:15:00Z"
}
```

The response is a dedicated `RefundDto`; as with all endpoints, entities are never returned from controllers.

### 9.2 List refunds

`GET /api/orders/{orderId}/refunds` returns the refunds of an order, newest first.

### 9.3 Changes to existing contracts

`OrderDto` gains one **additive** field, `refundedAmount`. No existing field is renamed or removed, because the mobile app and the back-office depend on the current field names.

### 9.4 Errors

| Code | HTTP | Meaning |
|------|------|---------|
| `ORDER_NOT_REFUNDABLE` | 422 | Order status does not allow refunds |
| `REFUND_WINDOW_EXPIRED` | 422 | More than 30 days since capture |
| `REFUND_EXCEEDS_CAPTURED_AMOUNT` | 422 | Cap from FR-3 would be violated |
| `REFUND_QUANTITY_INVALID` | 422 | Quantity is zero, negative or above the refundable quantity |
| `IDEMPOTENCY_KEY_REUSED` | 422 | Same key, different payload |
| `PAYMENT_REFUND_FAILED` | 502 | Gateway rejected or did not confirm the refund |

All errors are `BusinessRuleException` subclasses, mapped by `GlobalExceptionHandler`.

## 10. Events

Downstream systems (finance, analytics, e-mail) need to learn about refunds. The finance consumer already processes `OrderStatusChanged` and keeps its own projection of order states. Rather than introducing a new event type that every consumer would have to subscribe to, the design is to **publish `OrderStatusChanged` version 2** to a new topic `shop.order.status-changed.v2`. Version 2 adds `refundId`, `refundedAmount` and `totalRefundedAmount`. During a migration window of at least two releases, the service publishes both v1 (unchanged) and v2. No separate `OrderRefunded` event is introduced.

## 11. Data Model

A new migration, `V3__create_refunds.sql`, adds:

- table `refunds` (`id`, `order_id`, `requested_by`, `amount`, `currency`, `status` (`PENDING`, `COMPLETED`, `FAILED`), `reason_category`, `reason`, `idempotency_key` UNIQUE, `gateway_reference`, `created_at`, `completed_at`);
- table `refund_lines` (`refund_id`, `product_id`, `quantity`, `amount`);
- column `orders.refunded_amount NUMERIC(12,2) NOT NULL DEFAULT 0`.

Existing migrations `V1` and `V2` are already applied in all environments and are not modified.

## 12. Transaction and Payment-Gateway Ordering

Calling the gateway inside a database transaction would hold the order row lock for the duration of an HTTP call (up to the 5 s read timeout times the retry count) and, worse, could leave money refunded at the gateway while our transaction rolls back. The refund therefore follows the same pattern as `payOrder`:

1. **Transaction 1:** lock the order (`SELECT ... FOR UPDATE`), validate FR-1 to FR-5, compute the amount, insert the refund with status `PENDING`, commit. Because the amount of pending refunds counts towards the cap, concurrent requests cannot both pass validation.
2. **No transaction:** call the gateway's refund endpoint with the idempotency key.
3. **Transaction 2:** mark the refund `COMPLETED` (or `FAILED`), update `orders.refunded_amount` and the status, release stock if applicable, publish events after commit.

Refunds left in `PENDING` (for example after a crash between steps 2 and 3) are reconciled by a scheduled job that queries the gateway. The job itself is out of scope for this iteration, but the data model must support it.

## 13. Non-Functional Requirements

- **NFR-1 Performance:** p95 latency of the create endpoint below 800 ms excluding gateway time.
- **NFR-2 Observability:** metrics `shop.refunds.created`, `shop.refunds.failed` and `shop.refunds.amount` (tagged by reason category); structured logs following the logging conventions.
- **NFR-3 Audit log:** every refund attempt — successful, failed or rejected by validation — must be written to an append-only `audit_log` table with the actor id, actor role, order id, requested amount, reason, idempotency key, outcome and timestamp. Audit entries are retained for 7 years and are never updated or deleted. This is a compliance requirement from finance and is mandatory for go-live.
- **NFR-4 Security:** authorization as defined in FR-5; no payment data other than the gateway reference is stored.
- **NFR-5 Reliability:** the gateway call uses the existing timeout and retry configuration; only calls with an idempotency key are retried.

## 14. Error Handling

Errors are handled consistently with the rest of the application. Business errors are raised as `DomainException` subclasses and translated by the global exception handler into RFC 7807 problem details with a stable error code. Unexpected errors are logged and returned as a generic 500 response. Gateway failures after retries are exhausted mark the refund as `FAILED` and return `PAYMENT_REFUND_FAILED`.

## 15. Testing Strategy

The feature will be tested thoroughly at several levels:

- **Unit tests** for the refund calculation, including pro-rata allocation with lines of different prices, rounding, the cap, and the window boundary (day 30 vs. day 31).
- **Service tests** for the transaction ordering, using mocks for the gateway.
- **Controller tests** for authorization (SUPPORT allowed, owner rejected, other customer rejected) and validation.
- **Payment client tests** using `MockRestServiceServer` for the refund call, including retry behaviour.
- **Integration tests** with Testcontainers for the migration and for concurrent refund requests.

Existing tests must keep passing and must not be weakened.

## 16. Rollout

The feature is released behind the configuration flag `shop.refunds.enabled` (default `false`). It is enabled first in staging, then for a limited group of support agents, and finally for everyone. Because the v2 event is published in parallel with v1, consumers can migrate at their own pace.

## 17. Risks

- **Double refunds** because of retries — mitigated by idempotency keys (FR-6).
- **Over-refunds** because of rounding or wrong allocation — mitigated by FR-3 and FR-4 and by tests.
- **Inconsistency between gateway and database** — mitigated by the transaction ordering in section 12 and by the reconciliation job.
- **Fraud by customers** — mitigated by restricting refunds to SUPPORT (FR-5).
- **Breaking consumers** — mitigated by additive DTO changes and versioned events.

## 18. Alternatives Considered

- **Refund inside a single transaction.** Simpler, but rejected for the reasons given in section 12.
- **Allowing customers to self-refund.** Convenient, but rejected for fraud reasons; may be revisited with limits in the future.
- **A separate `OrderRefunded` event.** Considered, but rejected because finance already consumes status changes and would have to join two streams.
- **Refunding by amount instead of by line.** Rejected, because it makes stock handling and reporting per product impossible.

## 19. Open Questions

1. **OQ-1:** If a partial refund brings the remaining subtotal of an order below the volume-discount threshold (500.00), should the 5% volume discount be clawed back from the refund amount? Finance and product have not agreed yet.
2. **OQ-2:** Should refunds above a certain amount (proposal: 1,000.00 EUR) require approval by a second support agent (four-eyes principle)? If yes, the `PENDING` status needs an approval sub-state.

## 20. Summary

This specification introduces full and partial refunds for orders. Refunds are issued by support agents through a new REST endpoint, executed against the payment gateway outside of a database transaction, persisted in a new `refunds` table created by a new migration, reflected in the order state machine with two new statuses, and announced to other systems through a new version of the order status event. The design respects the existing conventions of the project regarding money handling, errors, transactions, API contracts, events and migrations. With this feature in place, the shop will have a faster, safer and more transparent refund process, which will benefit customers, support agents and the finance team alike.
