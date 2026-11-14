using Shop.Domain.Invoices;

namespace Shop.Application.Abstractions;

/// <summary>Persistence port for the <see cref="Invoice"/> aggregate.</summary>
public interface IInvoiceRepository
{
    /// <summary>Loads an invoice with its lines, tracked for updates.</summary>
    Task<Invoice?> GetByIdAsync(Guid id, CancellationToken cancellationToken);

    /// <summary>Loads an invoice by its human readable number (e.g. <c>INV-2026-000123</c>).</summary>
    Task<Invoice?> GetByNumberAsync(string number, CancellationToken cancellationToken);

    /// <summary>Returns one page of invoices (read-only) and the total count for the filter.</summary>
    Task<(IReadOnlyList<Invoice> Items, int TotalCount)> ListAsync(
        InvoiceStatus? status, int skip, int take, CancellationToken cancellationToken);

    /// <summary>Issued or partially paid invoices whose due date is before <paramref name="date"/>.</summary>
    Task<IReadOnlyList<Invoice>> GetIssuedDueBeforeAsync(DateOnly date, int maxCount, CancellationToken cancellationToken);

    /// <summary>Next value of the <c>billing.InvoiceNumbers</c> sequence.</summary>
    Task<long> NextNumberSequenceAsync(CancellationToken cancellationToken);

    /// <summary>Adds a new invoice; persisted by the next <c>SaveChangesAsync</c>.</summary>
    void Add(Invoice invoice);
}
