using Shop.Application.Abstractions;

namespace Shop.Application.Events;

/// <summary>
/// Published when an invoice becomes fully paid.
/// </summary>
/// <remarks>
/// Contract <c>shop.invoice.paid</c>, version 1. Consumers: ledger-service (books the receivable),
/// notification-service (sends the receipt). Ledger matches on <see cref="InvoiceId"/>.
/// Do not remove or rename fields — publish <c>InvoicePaidV2</c> side by side instead
/// (see docs/architecture/conventions.md §6).
/// </remarks>
public sealed record InvoicePaid(
    Guid InvoiceId,
    string InvoiceNumber,
    Guid CustomerId,
    decimal Amount,
    string Currency,
    DateTimeOffset PaidAt,
    Guid? ReconciliationId = null) : IIntegrationEvent
{
    public const string Type = "shop.invoice.paid";
    public const int Version = 1;

    public string EventType => Type;

    public int EventVersion => Version;
}
