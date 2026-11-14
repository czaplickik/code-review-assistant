using Shop.Domain.Common;

namespace Shop.Application.Abstractions;

public interface IPaymentGateway
{
    Task<ChargeResult> ChargeAsync(ChargeRequest request, CancellationToken cancellationToken);

    Task<IReadOnlyList<SettlementLine>> GetSettlementReportAsync(DateOnly settlementDate, CancellationToken cancellationToken);
}

public sealed record ChargeRequest(Guid InvoiceId, Money Amount, string PaymentMethodToken, string IdempotencyKey);

public sealed record ChargeResult(bool Succeeded, string? ProviderReference, string? FailureReason);

/// <summary>One line of the gateway's daily settlement report.</summary>
public sealed record SettlementLine(
    string ProviderReference,
    decimal GrossAmount,
    decimal FeePercent,
    decimal NetAmount,
    string Currency);
