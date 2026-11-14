using Shop.Domain.Invoices;

namespace Shop.Application.Abstractions;

public interface IInvoiceRepository
{
    Task<Invoice?> GetByIdAsync(Guid id, CancellationToken cancellationToken);

    Task<Invoice?> GetByNumberAsync(string number, CancellationToken cancellationToken);

    Task<(IReadOnlyList<Invoice> Items, int TotalCount)> ListAsync(
        InvoiceStatus? status, int skip, int take, CancellationToken cancellationToken);

    Task<IReadOnlyList<Invoice>> GetIssuedDueBeforeAsync(DateOnly date, int maxCount, CancellationToken cancellationToken);

    Task<long> NextNumberSequenceAsync(CancellationToken cancellationToken);

    void Add(Invoice invoice);
}
