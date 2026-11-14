using FluentValidation;
using MediatR;
using Shop.Application.Abstractions;
using Shop.Domain.Common;
using Shop.Domain.Customers;
using Shop.Domain.Exceptions;
using Shop.Domain.Invoices;

namespace Shop.Application.Invoices;

public sealed record CreateInvoiceLine(string Description, int Quantity, decimal UnitPrice);

public sealed record CreateInvoiceCommand(
    Guid CustomerId,
    string? OrderNumber,
    string Currency,
    DateOnly DueDate,
    IReadOnlyList<CreateInvoiceLine> Lines) : IRequest<InvoiceDto>;

internal sealed class CreateInvoiceCommandValidator : AbstractValidator<CreateInvoiceCommand>
{
    public CreateInvoiceCommandValidator()
    {
        RuleFor(c => c.CustomerId).NotEmpty();
        RuleFor(c => c.Currency).NotEmpty().Length(3);
        RuleFor(c => c.OrderNumber).MaximumLength(64);
        RuleFor(c => c.Lines).NotEmpty();
        RuleForEach(c => c.Lines).ChildRules(line =>
        {
            line.RuleFor(l => l.Description).NotEmpty().MaximumLength(500);
            line.RuleFor(l => l.Quantity).GreaterThan(0);
            line.RuleFor(l => l.UnitPrice).GreaterThanOrEqualTo(0m);
        });
    }
}

public sealed class CreateInvoiceCommandHandler(
    IInvoiceRepository invoices,
    ICustomerRepository customers,
    IUnitOfWork unitOfWork,
    IValidator<CreateInvoiceCommand> validator,
    TimeProvider clock)
    : IRequestHandler<CreateInvoiceCommand, InvoiceDto>
{
    public async Task<InvoiceDto> Handle(CreateInvoiceCommand request, CancellationToken cancellationToken)
    {
        await validator.ValidateAndThrowAsync(request, cancellationToken);

        if (!await customers.ExistsAsync(request.CustomerId, cancellationToken))
        {
            throw new NotFoundException(nameof(Customer), request.CustomerId);
        }

        var now = clock.GetUtcNow();
        var sequence = await invoices.NextNumberSequenceAsync(cancellationToken);
        var number = $"INV-{now:yyyy}-{sequence:D6}";

        var invoice = Invoice.Draft(number, request.CustomerId, request.Currency, request.DueDate, request.OrderNumber);
        foreach (var line in request.Lines)
        {
            invoice.AddLine(line.Description, line.Quantity, Money.Of(line.UnitPrice, request.Currency));
        }

        invoice.Issue(now);
        invoices.Add(invoice);
        await unitOfWork.SaveChangesAsync(cancellationToken);

        return InvoiceDto.From(invoice);
    }
}
