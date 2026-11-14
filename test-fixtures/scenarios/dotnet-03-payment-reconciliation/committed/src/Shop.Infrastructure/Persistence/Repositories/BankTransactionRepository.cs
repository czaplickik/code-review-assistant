using Microsoft.EntityFrameworkCore;
using Shop.Application.Abstractions;
using Shop.Domain.Payments;

namespace Shop.Infrastructure.Persistence.Repositories;

internal sealed class BankTransactionRepository(ShopDbContext db) : IBankTransactionRepository
{
    public Task<BankTransaction?> GetByBankReferenceAsync(string bankReference, CancellationToken cancellationToken) =>
        db.Set<BankTransaction>().FirstOrDefaultAsync(t => t.BankReference == bankReference, cancellationToken);

    public async Task<(IReadOnlyList<BankTransaction> Items, int TotalCount)> ListUnmatchedAsync(
        int skip, int take, CancellationToken cancellationToken)
    {
        var query = db.Set<BankTransaction>()
            .AsNoTracking()
            .Where(t => t.Status == BankTransactionStatus.Unmatched);

        var total = await query.CountAsync(cancellationToken);
        var items = await query
            .OrderByDescending(t => t.BookedAt)
            .Skip(skip)
            .Take(take)
            .ToListAsync(cancellationToken);

        return (items, total);
    }

    public void Add(BankTransaction transaction) => db.Set<BankTransaction>().Add(transaction);
}
