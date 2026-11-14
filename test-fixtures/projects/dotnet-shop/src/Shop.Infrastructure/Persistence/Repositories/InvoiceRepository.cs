using Microsoft.EntityFrameworkCore;
using Shop.Application.Abstractions;
using Shop.Domain.Invoices;

namespace Shop.Infrastructure.Persistence.Repositories;

internal sealed class InvoiceRepository(ShopDbContext db) : IInvoiceRepository
{
    public Task<Invoice?> GetByIdAsync(Guid id, CancellationToken cancellationToken) =>
        db.Invoices.Include(i => i.Lines).FirstOrDefaultAsync(i => i.Id == id, cancellationToken);

    public Task<Invoice?> GetByNumberAsync(string number, CancellationToken cancellationToken) =>
        db.Invoices.Include(i => i.Lines).FirstOrDefaultAsync(i => i.Number == number, cancellationToken);

    public async Task<(IReadOnlyList<Invoice> Items, int TotalCount)> ListAsync(
        InvoiceStatus? status, int skip, int take, CancellationToken cancellationToken)
    {
        var query = db.Invoices.AsNoTracking();
        if (status is not null)
        {
            query = query.Where(i => i.Status == status);
        }

        var total = await query.CountAsync(cancellationToken);
        var items = await query
            .OrderByDescending(i => i.IssuedAt)
            .ThenBy(i => i.Number)
            .Skip(skip)
            .Take(take)
            .Include(i => i.Lines)
            .AsSplitQuery()
            .ToListAsync(cancellationToken);

        return (items, total);
    }

    public async Task<IReadOnlyList<Invoice>> GetIssuedDueBeforeAsync(DateOnly date, int maxCount, CancellationToken cancellationToken) =>
        await db.Invoices
            .Where(i => (i.Status == InvoiceStatus.Issued || i.Status == InvoiceStatus.PartiallyPaid) && i.DueDate < date)
            .OrderBy(i => i.DueDate)
            .Take(maxCount)
            .ToListAsync(cancellationToken);

    public Task<long> NextNumberSequenceAsync(CancellationToken cancellationToken) =>
        db.Database
            .SqlQuery<long>($"SELECT NEXT VALUE FOR [billing].[InvoiceNumbers] AS [Value]")
            .SingleAsync(cancellationToken);

    public void Add(Invoice invoice) => db.Invoices.Add(invoice);
}
