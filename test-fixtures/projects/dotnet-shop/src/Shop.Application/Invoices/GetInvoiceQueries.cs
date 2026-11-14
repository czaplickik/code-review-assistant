using MediatR;
using Shop.Application.Abstractions;
using Shop.Application.Common;
using Shop.Domain.Exceptions;
using Shop.Domain.Invoices;

namespace Shop.Application.Invoices;

public sealed record GetInvoiceQuery(Guid InvoiceId) : IRequest<InvoiceDto>;

public sealed record GetInvoicePaymentsQuery(Guid InvoiceId) : IRequest<IReadOnlyList<PaymentDto>>;

public sealed record ListInvoicesQuery(InvoiceStatus? Status, int? Page, int? PageSize) : IRequest<PagedResult<InvoiceDto>>;

public sealed class GetInvoiceQueryHandler(IInvoiceRepository invoices)
    : IRequestHandler<GetInvoiceQuery, InvoiceDto>
{
    public async Task<InvoiceDto> Handle(GetInvoiceQuery request, CancellationToken cancellationToken)
    {
        var invoice = await invoices.GetByIdAsync(request.InvoiceId, cancellationToken)
            ?? throw new NotFoundException(nameof(Invoice), request.InvoiceId);

        return InvoiceDto.From(invoice);
    }
}

public sealed class GetInvoicePaymentsQueryHandler(IPaymentRepository payments)
    : IRequestHandler<GetInvoicePaymentsQuery, IReadOnlyList<PaymentDto>>
{
    public async Task<IReadOnlyList<PaymentDto>> Handle(GetInvoicePaymentsQuery request, CancellationToken cancellationToken)
    {
        var result = await payments.GetByInvoiceIdAsync(request.InvoiceId, cancellationToken);
        return result.Select(PaymentDto.From).ToList();
    }
}

public sealed class ListInvoicesQueryHandler(IInvoiceRepository invoices)
    : IRequestHandler<ListInvoicesQuery, PagedResult<InvoiceDto>>
{
    public async Task<PagedResult<InvoiceDto>> Handle(ListInvoicesQuery request, CancellationToken cancellationToken)
    {
        var (page, pageSize) = Paging.Normalize(request.Page, request.PageSize);
        var (items, total) = await invoices.ListAsync(
            request.Status, Paging.Skip(page, pageSize), pageSize, cancellationToken);

        return new PagedResult<InvoiceDto>(items.Select(InvoiceDto.From).ToList(), page, pageSize, total);
    }
}
