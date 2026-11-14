using Microsoft.EntityFrameworkCore;
using Shop.Application.Abstractions;
using Shop.Domain.Customers;

namespace Shop.Infrastructure.Persistence.Repositories;

internal sealed class CustomerNoteRepository(ShopDbContext db) : ICustomerNoteRepository
{
    public Task<CustomerNote?> GetAsync(Guid customerId, Guid noteId, CancellationToken cancellationToken) =>
        db.CustomerNotes.FirstOrDefaultAsync(n => n.Id == noteId && n.CustomerId == customerId, cancellationToken);

    public async Task<(IReadOnlyList<CustomerNote> Items, int TotalCount)> ListAsync(
        Guid customerId, int skip, int take, CancellationToken cancellationToken)
    {
        var query = db.CustomerNotes.AsNoTracking().Where(n => n.CustomerId == customerId);

        var total = await query.CountAsync(cancellationToken);
        var items = await query
            .OrderByDescending(n => n.IsPinned)
            .ThenByDescending(n => n.CreatedAt)
            .Skip(skip)
            .Take(take)
            .ToListAsync(cancellationToken);

        return (items, total);
    }

    public void Add(CustomerNote note) => db.CustomerNotes.Add(note);

    public void Remove(CustomerNote note) => db.CustomerNotes.Remove(note);
}
