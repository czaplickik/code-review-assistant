using Shop.Domain.Common;
using Shop.Domain.Exceptions;

namespace Shop.Domain.Payments;

public enum PaymentStatus
{
    Captured,
    Settled,
    Failed,
    Refunded,
}

/// <summary>
/// A payment collected for an invoice. Card payments are <see cref="PaymentStatus.Captured"/> by the
/// gateway and become <see cref="PaymentStatus.Settled"/> once they appear in the daily settlement
/// report with the expected net amount.
/// </summary>
public sealed class Payment
{
    private Payment()
    {
        // EF Core
    }

    public Guid Id { get; private set; }
    public Guid InvoiceId { get; private set; }
    public decimal Amount { get; private set; }
    public string Currency { get; private set; } = default!;
    public PaymentStatus Status { get; private set; }

    /// <summary>Gateway charge id, used to match settlement report lines.</summary>
    public string? ProviderReference { get; private set; }

    public decimal? FeeAmount { get; private set; }
    public DateTimeOffset ReceivedAt { get; private set; }
    public DateTimeOffset? SettledAt { get; private set; }

    public Money Value => new(Amount, Currency);

    public static Payment Capture(Guid invoiceId, Money amount, string providerReference, DateTimeOffset receivedAt)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(providerReference);

        if (amount.IsZero || amount.IsNegative)
        {
            throw new InvalidPaymentAmountException(amount);
        }

        return new Payment
        {
            Id = Guid.NewGuid(),
            InvoiceId = invoiceId,
            Amount = amount.Amount,
            Currency = amount.Currency,
            Status = PaymentStatus.Captured,
            ProviderReference = providerReference,
            ReceivedAt = receivedAt,
        };
    }

    public void Settle(Money fee, DateTimeOffset settledAt)
    {
        if (Status != PaymentStatus.Captured)
        {
            throw new InvalidPaymentStateException(Id, Status.ToString(), "settle");
        }

        if (fee.Currency != Currency)
        {
            throw new CurrencyMismatchException(Currency, fee.Currency);
        }

        FeeAmount = fee.Amount;
        SettledAt = settledAt;
        Status = PaymentStatus.Settled;
    }
}
