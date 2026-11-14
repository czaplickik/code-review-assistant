using Shop.Domain.Common;
using Shop.Domain.Exceptions;
using Shop.Domain.Invoices;

namespace Shop.Tests.Domain;

public sealed class InvoiceTests
{
    private static readonly DateTimeOffset Now = new(2026, 10, 1, 9, 0, 0, TimeSpan.Zero);

    [Fact]
    public void Total_WithMultipleLines_SumsLineTotals()
    {
        var invoice = Invoice.Draft("INV-2026-000001", Guid.NewGuid(), "EUR", new DateOnly(2026, 10, 31));

        invoice.AddLine("Mechanical keyboard", 2, Money.Of(19.99m, "EUR"));
        invoice.AddLine("USB-C cable", 1, Money.Of(5.01m, "EUR"));

        invoice.Total.Should().Be(Money.Of(45.99m, "EUR"));
    }

    [Fact]
    public void Issue_WithoutLines_ThrowsInvalidInvoiceState()
    {
        var invoice = Invoice.Draft("INV-2026-000002", Guid.NewGuid(), "EUR", new DateOnly(2026, 10, 31));

        var act = () => invoice.Issue(Now);

        act.Should().Throw<InvalidInvoiceStateException>();
    }

    [Fact]
    public void ApplyPayment_FullOutstanding_MarksPaid()
    {
        var invoice = CreateIssued(100m);

        invoice.ApplyPayment(Money.Of(100m, "EUR"), Now);

        invoice.Status.Should().Be(InvoiceStatus.Paid);
        invoice.PaidAt.Should().Be(Now);
        invoice.Outstanding.IsZero.Should().BeTrue();
    }

    [Fact]
    public void ApplyPayment_PartialAmount_MarksPartiallyPaid()
    {
        var invoice = CreateIssued(100m);

        invoice.ApplyPayment(Money.Of(40m, "EUR"), Now);

        invoice.Status.Should().Be(InvoiceStatus.PartiallyPaid);
        invoice.Outstanding.Should().Be(Money.Of(60m, "EUR"));
        invoice.PaidAt.Should().BeNull();
    }

    [Fact]
    public void ApplyPayment_MoreThanOutstanding_ThrowsInvalidPaymentAmount()
    {
        var invoice = CreateIssued(100m);

        var act = () => invoice.ApplyPayment(Money.Of(100.01m, "EUR"), Now);

        act.Should().Throw<InvalidPaymentAmountException>();
        invoice.Status.Should().Be(InvoiceStatus.Issued);
    }

    [Fact]
    public void ApplyPayment_DifferentCurrency_ThrowsCurrencyMismatch()
    {
        var invoice = CreateIssued(100m);

        var act = () => invoice.ApplyPayment(Money.Of(100m, "USD"), Now);

        act.Should().Throw<CurrencyMismatchException>();
    }

    [Fact]
    public void ApplyPayment_OnDraft_ThrowsInvalidInvoiceState()
    {
        var invoice = Invoice.Draft("INV-2026-000003", Guid.NewGuid(), "EUR", new DateOnly(2026, 10, 31));
        invoice.AddLine("Monitor", 1, Money.Of(100m, "EUR"));

        var act = () => invoice.ApplyPayment(Money.Of(100m, "EUR"), Now);

        act.Should().Throw<InvalidInvoiceStateException>();
    }

    [Fact]
    public void MarkOverdue_PastDueDate_TransitionsToOverdue()
    {
        var invoice = CreateIssued(100m);

        invoice.MarkOverdue(new DateOnly(2026, 11, 1));

        invoice.Status.Should().Be(InvoiceStatus.Overdue);
    }

    [Fact]
    public void Cancel_WithPayments_ThrowsInvalidInvoiceState()
    {
        var invoice = CreateIssued(100m);
        invoice.ApplyPayment(Money.Of(10m, "EUR"), Now);

        var act = () => invoice.Cancel();

        act.Should().Throw<InvalidInvoiceStateException>();
    }

    private static Invoice CreateIssued(decimal amount)
    {
        var invoice = Invoice.Draft("INV-2026-000100", Guid.NewGuid(), "EUR", new DateOnly(2026, 10, 31));
        invoice.AddLine("Laptop stand", 1, Money.Of(amount, "EUR"));
        invoice.Issue(Now);
        return invoice;
    }
}
