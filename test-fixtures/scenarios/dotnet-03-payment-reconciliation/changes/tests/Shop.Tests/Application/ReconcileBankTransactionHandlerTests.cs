using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Shop.Application.Abstractions;
using Shop.Application.Events;
using Shop.Application.Reconciliation;
using Shop.Domain.Common;
using Shop.Domain.Invoices;
using Shop.Domain.Payments;

namespace Shop.Tests.Application;

public sealed class ReconcileBankTransactionHandlerTests
{
    private readonly Mock<IBankTransactionRepository> _bankTransactions = new();
    private readonly Mock<IInvoiceRepository> _invoices = new();
    private readonly Mock<IPaymentRepository> _payments = new();
    private readonly Mock<IUnitOfWork> _unitOfWork = new();
    private readonly Mock<IEventPublisher> _publisher = new();
    private readonly Mock<IServiceProvider> _serviceProvider = new();
    private readonly ReconcileBankTransactionHandler _handler;

    public ReconcileBankTransactionHandlerTests()
    {
        _serviceProvider.Setup(sp => sp.GetService(typeof(IEventPublisher))).Returns(_publisher.Object);

        _handler = new ReconcileBankTransactionHandler(
            _bankTransactions.Object,
            _invoices.Object,
            _payments.Object,
            _unitOfWork.Object,
            new ReconciliationCache(NullLogger<ReconciliationCache>.Instance),
            Options.Create(new ReconciliationOptions()),
            _serviceProvider.Object,
            TimeProvider.System,
            NullLogger<ReconcileBankTransactionHandler>.Instance);
    }

    [Fact]
    public async Task Handle_ExactAmountWithInvoiceNumber_MarksInvoicePaid()
    {
        var invoice = Invoice.Draft("INV-2026-000123", Guid.NewGuid(), "EUR", new DateOnly(2026, 11, 30));
        invoice.AddLine("Office chair", 1, Money.Of(120m, "EUR"));
        invoice.Issue(DateTimeOffset.UtcNow);
        _invoices.Setup(r => r.GetByNumberAsync("INV-2026-000123", It.IsAny<CancellationToken>())).ReturnsAsync(invoice);
        _invoices.Setup(r => r.GetByIdAsync(invoice.Id, It.IsAny<CancellationToken>())).ReturnsAsync(invoice);

        var result = await _handler.Handle(
            new ReconcileBankTransactionCommand(
                "E2E-0001", 120m, "EUR", DateTimeOffset.UtcNow, "Payment for INV-2026-000123", "DE89370400440532013000"),
            CancellationToken.None);

        result.Outcome.Should().Be("Matched");
        invoice.Status.Should().Be(InvoiceStatus.Paid);
        _payments.Verify(r => r.Add(It.IsAny<Payment>()), Times.Once);
        _publisher.Verify(p => p.PublishAsync(It.IsAny<InvoicePaid>(), It.IsAny<CancellationToken>()), Times.Once);
    }
}
