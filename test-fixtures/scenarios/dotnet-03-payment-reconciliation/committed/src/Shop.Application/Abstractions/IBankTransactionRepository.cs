using Shop.Domain.Payments;

namespace Shop.Application.Abstractions;

public interface IBankTransactionRepository
{
    Task<BankTransaction?> GetByBankReferenceAsync(string bankReference, CancellationToken cancellationToken);

    Task<(IReadOnlyList<BankTransaction> Items, int TotalCount)> ListUnmatchedAsync(
        int skip, int take, CancellationToken cancellationToken);

    void Add(BankTransaction transaction);
}
