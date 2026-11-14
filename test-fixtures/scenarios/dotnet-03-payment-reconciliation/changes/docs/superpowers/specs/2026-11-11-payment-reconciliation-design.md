# Bank Transfer Payment Reconciliation — Design

- **Date:** 2026-11-11
- **Status:** Approved for implementation (brainstorming session, billing team + finance)
- **Owner:** Billing team
- **Stakeholders:** Finance operations (accounts receivable), Ledger team, Notification team, Security
- **Related:** `docs/architecture/conventions.md`, gateway settlement reconciliation (`ReconcileSettlementCommand`)

---

## 1. Background and motivation

Today the billing service collects payments in exactly one way: the customer pays an invoice with a
card through the payment gateway, the gateway captures the charge, and the next day the settlement
report confirms the net amount, which `ReconcileSettlementCommand` uses to settle the payment.
That flow is automated end to end and has been stable since spring.

A growing share of our B2B customers, however, do not pay by card at all. They pay by bank
transfer, usually in a batch run from their own ERP at the end of the month, and they put the
invoice number into the remittance information field ("Verwendungszweck", "tytuł przelewu",
"reference"). Finance operations then downloads the bank statement every morning, opens each credit
line, looks up the invoice by number in the back office, and books the payment manually. In October
this was 1,340 transfers, roughly 31 hours of manual work, and 17 booking errors that had to be
corrected later (wrong invoice, wrong amount, a transfer booked twice).

Manual booking also delays the downstream effects of a payment. The ledger only learns about the
payment when finance books it, and the customer only receives a receipt at that point. Several
customers received payment reminders for invoices they had paid days before, because the overdue
sweep ran before finance got to their transfer. This generates support tickets and, in two cases
this quarter, escalations from key accounts.

The bank (our house bank for the EUR operating account) now offers two integration options that
make automation feasible:

1. A **webhook** that pushes credit notifications to a URL of our choice within seconds of booking,
   in batches of up to 50 transactions per call.
2. An **account information API** that returns booked transactions for a date range, which we can
   poll as a fallback when webhooks are delayed or lost.

This document describes how the billing service will ingest those transactions and reconcile them
against open invoices automatically, so that finance only handles the exceptions.

## 2. Goals

- Automatically match incoming bank transfers to open invoices using the invoice number in the
  remittance information, and book the corresponding payment without human involvement for the
  common case.
- Reduce manual booking effort by at least 80 % within one month of rollout.
- Make the result of reconciliation visible to finance (unmatched transactions) and to customers
  (payment status on their invoices).
- Keep the downstream behaviour identical to card payments: when an invoice becomes fully paid
  through a bank transfer, ledger-service and notification-service learn about it exactly as they
  do today.

## 3. Non-goals

- Outgoing payments, refunds and chargebacks. Refunds stay a manual finance process.
- Currencies other than the invoice currency. Cross-currency transfers are left unmatched.
- Replacing the card gateway settlement reconciliation. Both reconciliations co-exist and share
  nothing but the `Payment` aggregate.
- A user interface. Finance will use the existing back-office app, which consumes the API in §8.
- Fuzzy matching on customer name or IBAN. We considered it and decided to start with invoice
  numbers only; see §13.

## 4. Glossary

| Term | Meaning |
|------|---------|
| Bank transaction | One credit line on the operating account, identified by the bank's end-to-end id (`BankReference`). |
| Remittance information | Free text the payer enters; usually contains the invoice number. |
| Outstanding amount | `Invoice.Total − Invoice.AmountPaid`. |
| Tolerance | The small difference between transfer and outstanding amount that we accept as a full payment. |
| Matched | A bank transaction that has been booked as a payment against an invoice. |
| Unmatched | A bank transaction we could not book automatically; finance handles it. |

## 5. Current state

The relevant pieces of the existing system are:

- `Invoice` aggregate with the status machine `Draft → Issued → (PartiallyPaid ↔ Overdue) → Paid`.
  `ApplyPayment` already handles partial payments and rejects over-payments.
- `Payment` entity, currently always created from a card charge (`Payment.Capture`), with a
  `ProviderReference` holding the gateway charge id.
- `IUnitOfWork.ExecuteInTransactionAsync`, used by `PayInvoiceCommandHandler` to change payment and
  invoice atomically and to write integration events to the outbox in the same transaction.
- `InvoicePaid` (v1), published when an invoice becomes fully paid. Ledger-service books the
  receivable from it; notification-service sends the receipt. Both teams have confirmed they key on
  `InvoiceId` **and** read `PaymentReference` for their own reconciliation reports.
- `Money` value object with banker's rounding, which is also what the ledger uses.
- `OverdueInvoiceNotifier`, the hosted service that marks invoices overdue every 30 minutes.

## 6. Proposed solution

### 6.1 Overview

```
 bank ──webhook──► BankWebhookController ──► ReconcileBankTransactionCommand ──► Payment / Invoice / Outbox
   ▲                                              ▲
   └──poll── BankStatementImportWorker ───────────┘
```

Both ingestion paths — webhook (push) and statement polling (pull) — produce the same command,
`ReconcileBankTransactionCommand`, so matching rules exist in exactly one place. The command
handler imports the transaction, tries to match it, and if it matches, creates a `Payment` and
applies it to the invoice.

### 6.2 Functional requirements

**FR-1 Webhook ingestion.** The service exposes `POST /webhooks/bank/transactions`. The payload is
the bank's documented JSON format (event id plus an array of transactions with end-to-end id,
amount, currency, booking date, remittance information and debtor IBAN). The endpoint must answer
within the bank's 10-second timeout; the bank retries non-2xx responses with exponential backoff for
up to 24 hours. Because the webhook is called by the bank and not by a logged-in user, it cannot
use our JWT authentication, which is why it needs its own authenticity check described next, and
which the security team asked us to treat as the single most important part of this design given
that the endpoint can create payments: every request carries an `X-Bank-Signature` header with an
HMAC-SHA256 of the raw request body computed with a shared secret, plus an `X-Bank-Timestamp`
header; the service **must** recompute the HMAC over the raw body (before model binding), compare
it in constant time, reject requests whose timestamp is more than five minutes away from our clock,
and answer `401` without processing anything if either check fails (**FR-2**). The shared secret
lives in Key Vault under `bank-webhook-secret` and is rotated quarterly, so the verifier must accept
the current and the previous secret during a rotation window.

**FR-3 Idempotent deliveries.** The bank guarantees at-least-once delivery, and the polling
fallback will see the same transactions again for up to three days. Receiving a transaction whose
`BankReference` we already know — whether it is matched, unmatched or ignored — must be a no-op that
returns success (`200` for the webhook) so that the bank stops retrying. It must never create a
second payment, and it must never fail the whole batch.

**FR-4 Polling fallback.** A hosted service polls the account information API every 15 minutes for
the last three days of credit transactions and feeds each one into the same command. This covers
webhook outages on either side. The polling interval and look-back window are configuration.

**FR-5 Candidate selection.** The handler extracts invoice numbers matching `INV-YYYY-NNNNNN`
(case-insensitive) from the remittance information. The invoice must exist, be open for payment
(`Issued`, `PartiallyPaid` or `Overdue`), and have the same currency as the transfer. If the
remittance information contains no invoice number, the transaction is stored as unmatched.

**FR-6 Amount rules.** Let *difference = transfer amount − outstanding amount*.

- *difference* within tolerance (FR-7), including zero: book as a full payment of the outstanding
  amount. The invoice becomes `Paid`. The difference is recorded on the payment for the ledger.
- Under-payment beyond tolerance: book the transfer amount as a partial payment; the invoice becomes
  `PartiallyPaid`. A reminder for the remainder follows the normal overdue process.
- Over-payment beyond tolerance: do **not** book. Leave the transaction unmatched for finance, who
  will refund or allocate the excess manually. (`Invoice.ApplyPayment` rejects over-payments anyway.)

**FR-7 Tolerance.** Payers' banks sometimes deduct small charges, and some ERPs round differently,
so exact matching alone would leave too many transfers for finance. Finance agreed to accept
differences up to **0.5 % of the outstanding amount, capped at 5.00 in the invoice currency**,
i.e. *|difference| ≤ min(0.5 % × outstanding, 5.00)*. Both the percentage and the cap are
configuration (`Reconciliation:TolerancePercent`, `Reconciliation:MaxToleranceAmount`), but the
defaults above are the approved business rule. Worked examples are in Appendix A. Note that a fixed
absolute tolerance was explicitly rejected: on small invoices it would accept a large relative
under-payment, and on large invoices it would be too strict.

**FR-8 Atomicity.** For a matched transaction, the following must happen in **one database
transaction** via `IUnitOfWork.ExecuteInTransactionAsync` with a single `SaveChangesAsync`:
updating the bank transaction status, creating the `Payment`, applying it to the `Invoice`, and
writing the integration events to the outbox. A crash between steps must never leave a payment
without the corresponding invoice update or vice versa. This mirrors `PayInvoiceCommandHandler`.

**FR-9 Integration events.** When reconciliation makes an invoice fully paid, the service publishes
`InvoicePaid` **v1, unchanged**, with `PaymentReference` set to the bank reference. Ledger-service
and notification-service must not need any change to process bank-transfer payments. In addition,
for every matched transaction (full or partial) the service publishes a **new** event
`PaymentReconciled` v1 (`shop.payment.reconciled`) with: `PaymentId`, `InvoiceId`,
`BankTransactionId`, `BankReference`, `Amount`, `Currency`, `Difference`, `Outcome`,
`ReconciledAt`. Ledger has asked for `Difference` so that it can book tolerance write-offs.

**FR-10 Unmatched queue for finance.** Finance staff (`Finance` policy) can list unmatched bank
transactions, newest first, paged with the standard paging contract (`Paging.Normalize`, max 100),
returned as DTOs. Finance resolves them in the back-office app by booking manually or marking them
as ignored; manual resolution endpoints are a follow-up and not part of this iteration.

**FR-11 Customer visibility.** Customers see the reconciliation status of each payment on
`GET /api/invoices/{id}/payments`. The existing resource-based authorization (`InvoiceOwner`
policy) on this endpoint stays exactly as it is; only the response gains a field.

### 6.3 Data model

New entity `BankTransaction` (table `billing.BankTransactions`): `Id`, `BankReference` (unique,
max 64), `Amount`, `Currency`, `BookedAt`, `RemittanceInformation` (max 500), `CounterpartyIban`
(max 34), `Status` (`Unmatched`, `Matched`, `Ignored`), `MatchedInvoiceId`, `ReceivedAt`.

`Payment` gains `ReconciliationStatus` (`Unreconciled`, `Reconciled`, `Disputed`) and a nullable
`BankTransactionId`. Bank-transfer payments are created through a new factory
`Payment.FromBankTransfer` and are settled on receipt (no fee). `ProviderReference` holds the bank
reference for bank-transfer payments so that existing reports keep working.

`Invoice` gets a convenience property `IsOpenForPayment`; no persisted change.

All schema changes in this release are **additive**: one new table, two new nullable or defaulted
columns on `Payments`, new indexes. Following the expand/contract rule in the conventions, nothing
is renamed or dropped in this release. In particular the legacy `Invoices.PaymentNote` column — which
looks unused in code because it is only read by the finance audit export, not by this service — must
be kept; finance needs those notes for the 2026 audit and will tell us when they can be archived.
The schema change is one new EF Core migration; existing migrations are not touched.

### 6.4 Money and rounding

No change to `Money` is required or wanted. All tolerance calculations use `Money.Percentage`,
which rounds with banker's rounding like the ledger. Changing the rounding mode would silently shift
cents in gateway settlement reconciliation and in the ledger, and requires sign-off from finance
(conventions §9).

## 7. Interfaces

### 7.1 Webhook

`POST /webhooks/bank/transactions` — anonymous at the JWT level but protected by FR-2.
Response: `200 OK` with an empty body once all transactions in the batch are persisted (matched or
not). The response must not echo invoice ids or numbers back to the caller; the bank does not need
them and the endpoint is reachable from the internet.

### 7.2 Finance API

`GET /api/reconciliation/unmatched?page=&pageSize=` — `Finance` policy, returns
`PagedResult<UnmatchedBankTransactionDto>`.

### 7.3 Customer API

`GET /api/invoices/{id}/payments` — unchanged authorization; `PaymentDto` gains
`ReconciliationStatus`. No existing property is renamed or removed: the web shop and the
back-office app both deserialize `InvoiceDto` and `PaymentDto` strictly.

## 8. Non-functional requirements

**NFR-1 Bank API client.** Typed `HttpClient` registered through `IHttpClientFactory`, with a
10-second per-try timeout and three retries with exponential backoff and jitter, same as the
payment gateway client. The API key comes from Key Vault (`bank-api-key`). The statement endpoint
is paginated with a `nextCursor`; the client must follow it.

**NFR-2 Performance.** Webhook p95 below 2 seconds for a batch of 50 transactions. Invoice lookups
use the existing unique index on `Invoices.Number`.

**NFR-3 Observability.** Structured logs per transaction (no IBANs or names in logs), counters
`reconciliation_transactions_total{outcome}` and a gauge for the unmatched queue size.

**NFR-4 Security review.** The webhook endpoint and its signature verification are reviewed by the
security team before the endpoint is exposed in production.

## 9. Error handling

- Business rule violations use `DomainException` subclasses (`BankTransactionAlreadyMatchedException`
  is new) and are mapped by `ProblemDetailsMiddleware`.
- A failure while processing one transaction of a webhook batch must not lose the others: each
  transaction is processed and persisted independently, and the batch returns `200` once every
  transaction has been persisted in some state.
- Bank API failures in the polling worker are logged and retried on the next tick.

## 10. Testing strategy

- Unit tests for the handler covering every branch of FR-5 to FR-7: exact match, within tolerance
  (both below and above the outstanding amount), tolerance cap on a large invoice, partial payment,
  over-payment, currency mismatch, closed invoice, no invoice number, duplicate delivery (FR-3).
- Unit tests for the signature verifier: valid signature, tampered body, stale timestamp, previous
  secret during rotation.
- Integration test for the webhook endpoint against the SQL Server test container.
- Existing tests, in particular `ReconcileSettlementHandlerTests` and `MoneyTests`, must keep
  passing unchanged.

## 11. Rollout

1. Deploy with the webhook route disabled by configuration; enable polling only, in shadow mode
   (match but do not book) for one week, and compare with finance's manual bookings.
2. Enable booking for polling.
3. After the security review (NFR-4), register the webhook URL with the bank.

## 12. Risks

- **Wrong matches** because a payer references the wrong invoice. Mitigated by currency and amount
  rules; finance can reverse a booking manually.
- **Signature secret leakage** would allow anyone to create payments. Mitigated by Key Vault,
  rotation and the security review.
- **Downstream contract drift.** Ledger and notifications depend on `InvoicePaid` v1 staying as it
  is, hence FR-9.

## 13. Alternatives considered

- *Fuzzy matching on customer name / IBAN.* More matches, but much higher risk of wrong bookings.
  Deferred until we have data from the unmatched queue.
- *Third-party reconciliation SaaS.* Rejected for cost and because it would need access to customer
  data.
- *Extending `InvoicePaid` instead of a new event.* Rejected: it is a published v1 contract with two
  consumers, and the conventions require a new version for breaking changes. A separate
  `PaymentReconciled` event also covers partial payments, which `InvoicePaid` never did.

## 14. Open questions

1. **OQ-1 — One transfer, several invoices.** Some customers pay several invoices with one transfer
   and list all invoice numbers in the remittance information. Do we split the amount across the
   invoices (oldest first?) or leave such transfers unmatched in v1? Finance (Marta K.) to decide;
   until then, transfers with more than one invoice number should be left unmatched.
2. **OQ-2 — Ageing of unmatched transactions.** How long do unmatched transactions stay in the queue,
   and who is notified when one is older than three business days? Finance operations and the
   notification team have not agreed on an owner yet.

## Appendix A — Tolerance examples

| Outstanding | 0.5 % | Cap | Tolerance | Transfer | Result |
|-------------|-------|-----|-----------|----------|--------|
| 20.00 EUR | 0.10 | 5.00 | 0.10 | 19.60 | partial payment (difference −0.40) |
| 20.00 EUR | 0.10 | 5.00 | 0.10 | 19.92 | full payment, −0.08 written off |
| 600.00 EUR | 3.00 | 5.00 | 3.00 | 597.50 | full payment, −2.50 written off |
| 2,000.00 EUR | 10.00 | 5.00 | 5.00 | 1,993.00 | partial payment (difference −7.00) |
| 2,000.00 EUR | 10.00 | 5.00 | 5.00 | 2,004.00 | full payment, +4.00 recorded for refund decision |
| 150.00 EUR | 0.75 | 5.00 | 0.75 | 151.20 | over-payment → unmatched |
