using Shop.Domain.Common;
using Shop.Domain.Exceptions;
using Shop.Domain.Payments;

namespace Shop.Tests.Domain;

public sealed class BankTransactionTests
{
    [Fact]
    public void Import_NewTransaction_IsUnmatched()
    {
        var transaction = Create();

        transaction.Status.Should().Be(BankTransactionStatus.Unmatched);
        transaction.MatchedInvoiceId.Should().BeNull();
        transaction.RemittanceInformation.Should().Be("INV-2026-000123");
    }

    [Fact]
    public void MarkMatched_Unmatched_SetsInvoice()
    {
        var transaction = Create();
        var invoiceId = Guid.NewGuid();

        transaction.MarkMatched(invoiceId);

        transaction.Status.Should().Be(BankTransactionStatus.Matched);
        transaction.MatchedInvoiceId.Should().Be(invoiceId);
    }

    [Fact]
    public void MarkMatched_AlreadyMatched_ThrowsBankTransactionAlreadyMatched()
    {
        var transaction = Create();
        transaction.MarkMatched(Guid.NewGuid());

        var act = () => transaction.MarkMatched(Guid.NewGuid());

        act.Should().Throw<BankTransactionAlreadyMatchedException>();
    }

    private static BankTransaction Create() => BankTransaction.Import(
        "E2E-20261110-0001",
        Money.Of(120m, "EUR"),
        new DateTimeOffset(2026, 11, 10, 8, 0, 0, TimeSpan.Zero),
        "  INV-2026-000123 ",
        "DE89370400440532013000",
        DateTimeOffset.UtcNow);
}
