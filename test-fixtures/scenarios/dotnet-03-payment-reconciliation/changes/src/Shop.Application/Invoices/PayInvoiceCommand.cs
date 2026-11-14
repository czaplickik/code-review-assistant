using MediatR;
using Microsoft.Extensions.Logging;
using Shop.Application.Abstractions;
using Shop.Application.Events;
using Shop.Domain.Exceptions;
using Shop.Domain.Invoices;
using Shop.Domain.Payments;

namespace Shop.Application.Invoices;

public sealed record PayInvoiceCommand(Guid InvoiceId, string PaymentMethodToken) : IRequest<PaymentDto>;

/// <summary>
/// Charges the outstanding amount of an invoice through the payment gateway and books the payment.
/// </summary>
public sealed class PayInvoiceCommandHandler(
    IInvoiceRepository invoices,
    IPaymentRepository payments,
    IPaymentGateway gateway,
    IUnitOfWork unitOfWork,
    IEventPublisher events,
    TimeProvider clock,
    ILogger<PayInvoiceCommandHandler> logger)
    : IRequestHandler<PayInvoiceCommand, PaymentDto>
{
    public async Task<PaymentDto> Handle(PayInvoiceCommand request, CancellationToken cancellationToken)
    {
        var invoice = await invoices.GetByIdAsync(request.InvoiceId, cancellationToken)
            ?? throw new NotFoundException(nameof(Invoice), request.InvoiceId);

        if (invoice.Status is not (InvoiceStatus.Issued or InvoiceStatus.PartiallyPaid or InvoiceStatus.Overdue))
        {
            throw new InvalidInvoiceStateException(invoice.Number, invoice.Status.ToString(), "pay");
        }

        var amount = invoice.Outstanding;

        // The idempotency key changes whenever the invoice changes (row version), so a retried HTTP
        // call for the same attempt never charges twice, but a new attempt after a partial payment does.
        var idempotencyKey = $"invoice-{invoice.Id:N}-{Convert.ToHexString(invoice.RowVersion)}";
        var charge = await gateway.ChargeAsync(
            new ChargeRequest(invoice.Id, amount, request.PaymentMethodToken, idempotencyKey), cancellationToken);

        if (!charge.Succeeded || charge.ProviderReference is null)
        {
            logger.LogInformation("Charge for invoice {InvoiceNumber} declined: {Reason}", invoice.Number, charge.FailureReason);
            throw new PaymentDeclinedException(charge.FailureReason ?? "unknown reason");
        }

        var payment = Payment.Capture(invoice.Id, amount, charge.ProviderReference, clock.GetUtcNow());

        await unitOfWork.ExecuteInTransactionAsync(async () =>
        {
            payments.Add(payment);
            invoice.ApplyPayment(amount, payment.ReceivedAt);

            if (invoice.Status == InvoiceStatus.Paid)
            {
                await events.PublishAsync(
                    new InvoicePaid(
                        invoice.Id,
                        invoice.Number,
                        invoice.CustomerId,
                        invoice.Total.Amount,
                        invoice.Currency,
                        invoice.PaidAt!.Value),
                    cancellationToken);
            }

            await unitOfWork.SaveChangesAsync(cancellationToken);
        }, cancellationToken);

        logger.LogInformation(
            "Invoice {InvoiceNumber} charged {Amount} (gateway reference {ProviderReference})",
            invoice.Number, amount, payment.ProviderReference);

        return PaymentDto.From(payment);
    }
}
