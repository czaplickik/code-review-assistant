using Shop.Application.Abstractions;

namespace Shop.Application.Events;

/// <summary>
/// Published when an invoice passes its due date unpaid. Contract <c>shop.invoice.overdue</c>, v1.
/// Consumed by notification-service (payment reminder e-mail).
/// </summary>
public sealed record InvoiceOverdue(
    Guid InvoiceId,
    string InvoiceNumber,
    Guid CustomerId,
    decimal OutstandingAmount,
    string Currency,
    DateOnly DueDate) : IIntegrationEvent
{
    public const string Type = "shop.invoice.overdue";
    public const int Version = 1;

    public string EventType => Type;

    public int EventVersion => Version;
}
