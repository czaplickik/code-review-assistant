using Shop.Domain.Common;
using Shop.Domain.Exceptions;

namespace Shop.Domain.Payments;

public enum BankTransactionStatus
{
    Unmatched,
    Matched,
    Ignored,
}

/// <summary>
/// An incoming credit on the shop's bank account, imported from the bank's webhook or statement API.
/// Bank transfers that reference an invoice number are matched to that invoice by reconciliation.
/// </summary>
public sealed class BankTransaction
{
    private BankTransaction()
    {
        // EF Core
    }

    public Guid Id { get; private set; }

    /// <summary>Bank-assigned, globally unique transaction reference (end-to-end id).</summary>
    public string BankReference { get; private set; } = default!;

    public decimal Amount { get; private set; }
    public string Currency { get; private set; } = default!;
    public DateTimeOffset BookedAt { get; private set; }
    public string? RemittanceInformation { get; private set; }
    public string? CounterpartyIban { get; private set; }
    public BankTransactionStatus Status { get; private set; }
    public Guid? MatchedInvoiceId { get; private set; }
    public DateTimeOffset ReceivedAt { get; private set; }

    public Money Value => new(Amount, Currency);

    public static BankTransaction Import(
        string bankReference,
        Money amount,
        DateTimeOffset bookedAt,
        string? remittanceInformation,
        string? counterpartyIban,
        DateTimeOffset receivedAt)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(bankReference);

        return new BankTransaction
        {
            Id = Guid.NewGuid(),
            BankReference = bankReference,
            Amount = amount.Amount,
            Currency = amount.Currency,
            BookedAt = bookedAt,
            RemittanceInformation = remittanceInformation?.Trim(),
            CounterpartyIban = counterpartyIban,
            Status = BankTransactionStatus.Unmatched,
            ReceivedAt = receivedAt,
        };
    }

    public void MarkMatched(Guid invoiceId)
    {
        if (Status == BankTransactionStatus.Matched)
        {
            throw new BankTransactionAlreadyMatchedException(BankReference);
        }

        Status = BankTransactionStatus.Matched;
        MatchedInvoiceId = invoiceId;
    }

    /// <summary>Debits, zero amounts and transfers finance has decided not to book.</summary>
    public void MarkIgnored()
    {
        if (Status == BankTransactionStatus.Matched)
        {
            throw new BankTransactionAlreadyMatchedException(BankReference);
        }

        Status = BankTransactionStatus.Ignored;
    }
}
