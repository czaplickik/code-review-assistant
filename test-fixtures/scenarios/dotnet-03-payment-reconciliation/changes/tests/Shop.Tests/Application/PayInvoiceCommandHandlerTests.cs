using Microsoft.Extensions.Logging.Abstractions;
using Shop.Application.Abstractions;
using Shop.Application.Events;
using Shop.Application.Invoices;
using Shop.Domain.Common;
using Shop.Domain.Exceptions;
using Shop.Domain.Invoices;
using Shop.Domain.Payments;

namespace Shop.Tests.Application;

public sealed class PayInvoiceCommandHandlerTests
{
    private readonly Mock<IInvoiceRepository> _invoices = new();
    private readonly Mock<IPaymentRepository> _payments = new();
    private readonly Mock<IPaymentGateway> _gateway = new();
    private readonly Mock<IUnitOfWork> _unitOfWork = new();
    private readonly Mock<IEventPublisher> _events = new();
    private readonly PayInvoiceCommandHandler _handler;

    public PayInvoiceCommandHandlerTests()
    {
        _unitOfWork
            .Setup(u => u.ExecuteInTransactionAsync(It.IsAny<Func<Task>>(), It.IsAny<CancellationToken>()))
            .Returns<Func<Task>, CancellationToken>((operation, _) => operation());

        _handler = new PayInvoiceCommandHandler(
            _invoices.Object,
            _payments.Object,
            _gateway.Object,
            _unitOfWork.Object,
            _events.Object,
            TimeProvider.System,
            NullLogger<PayInvoiceCommandHandler>.Instance);
    }

    [Fact]
    public async Task Handle_SuccessfulCharge_MarksInvoicePaidAndPublishesInvoicePaid()
    {
        var invoice = IssuedInvoice(250m);
        _invoices.Setup(r => r.GetByIdAsync(invoice.Id, It.IsAny<CancellationToken>())).ReturnsAsync(invoice);
        _gateway
            .Setup(g => g.ChargeAsync(It.IsAny<ChargeRequest>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new ChargeResult(true, "ch_123", null));

        var result = await _handler.Handle(new PayInvoiceCommand(invoice.Id, "pm_card"), CancellationToken.None);

        result.Amount.Should().Be(250m);
        result.ProviderReference.Should().Be("ch_123");
        invoice.Status.Should().Be(InvoiceStatus.Paid);
        _payments.Verify(r => r.Add(It.Is<Payment>(p => p.Amount == 250m)), Times.Once);
        _events.Verify(e => e.PublishAsync(
            It.Is<InvoicePaid>(evt => evt.InvoiceId == invoice.Id && evt.Amount == 250m),
            It.IsAny<CancellationToken>()), Times.Once);
        _unitOfWork.Verify(u => u.SaveChangesAsync(It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task Handle_DeclinedCharge_ThrowsPaymentDeclinedAndDoesNotSave()
    {
        var invoice = IssuedInvoice(250m);
        _invoices.Setup(r => r.GetByIdAsync(invoice.Id, It.IsAny<CancellationToken>())).ReturnsAsync(invoice);
        _gateway
            .Setup(g => g.ChargeAsync(It.IsAny<ChargeRequest>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new ChargeResult(false, null, "insufficient_funds"));

        var act = () => _handler.Handle(new PayInvoiceCommand(invoice.Id, "pm_card"), CancellationToken.None);

        await act.Should().ThrowAsync<PaymentDeclinedException>();
        invoice.Status.Should().Be(InvoiceStatus.Issued);
        _unitOfWork.Verify(u => u.SaveChangesAsync(It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task Handle_UnknownInvoice_ThrowsNotFound()
    {
        _invoices.Setup(r => r.GetByIdAsync(It.IsAny<Guid>(), It.IsAny<CancellationToken>())).ReturnsAsync((Invoice?)null);

        var act = () => _handler.Handle(new PayInvoiceCommand(Guid.NewGuid(), "pm_card"), CancellationToken.None);

        await act.Should().ThrowAsync<NotFoundException>();
        _gateway.VerifyNoOtherCalls();
    }

    private static Invoice IssuedInvoice(decimal amount)
    {
        var invoice = Invoice.Draft("INV-2026-000200", Guid.NewGuid(), "EUR", new DateOnly(2026, 12, 1));
        invoice.AddLine("Desk", 1, Money.Of(amount, "EUR"));
        invoice.Issue(DateTimeOffset.UtcNow);
        return invoice;
    }
}
