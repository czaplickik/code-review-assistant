using Shop.Domain.Invoices;
using Shop.Domain.Payments;

namespace Shop.Application.Invoices;

public sealed record InvoiceDto(
    Guid Id,
    string Number,
    Guid CustomerId,
    string? OrderNumber,
    string Status,
    string Currency,
    decimal Total,
    decimal AmountPaid,
    decimal AmountDue,
    DateOnly DueDate,
    DateTimeOffset? IssuedAt,
    DateTimeOffset? PaidAt,
    IReadOnlyList<InvoiceLineDto> Lines)
{
    public static InvoiceDto From(Invoice invoice) => new(
        invoice.Id,
        invoice.Number,
        invoice.CustomerId,
        invoice.OrderNumber,
        invoice.Status.ToString(),
        invoice.Currency,
        invoice.Total.Amount,
        invoice.AmountPaid.Amount,
        invoice.Outstanding.Amount,
        invoice.DueDate,
        invoice.IssuedAt,
        invoice.PaidAt,
        invoice.Lines.Select(InvoiceLineDto.From).ToList());
}

public sealed record InvoiceLineDto(string Description, int Quantity, decimal UnitPrice, decimal LineTotal)
{
    public static InvoiceLineDto From(InvoiceLine line) =>
        new(line.Description, line.Quantity, line.UnitPrice.Amount, line.LineTotal.Amount);
}

public sealed record PaymentDto(
    Guid Id,
    Guid InvoiceId,
    decimal Amount,
    string Currency,
    string Status,
    string? ProviderReference,
    DateTimeOffset ReceivedAt,
    DateTimeOffset? SettledAt)
{
    public static PaymentDto From(Payment payment) => new(
        payment.Id,
        payment.InvoiceId,
        payment.Amount,
        payment.Currency,
        payment.Status.ToString(),
        payment.ProviderReference,
        payment.ReceivedAt,
        payment.SettledAt);
}

public sealed record PayInvoiceRequest(string PaymentMethodToken);
