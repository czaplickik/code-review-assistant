using Shop.Domain.Customers;

namespace Shop.Application.Abstractions;

public interface ICustomerNoteRepository
{
    /// <summary>Returns the note only if it belongs to <paramref name="customerId"/>.</summary>
    Task<CustomerNote?> GetAsync(Guid customerId, Guid noteId, CancellationToken cancellationToken);

    /// <summary>Pinned notes first, then newest first.</summary>
    Task<(IReadOnlyList<CustomerNote> Items, int TotalCount)> ListAsync(
        Guid customerId, int skip, int take, CancellationToken cancellationToken);

    void Add(CustomerNote note);

    void Remove(CustomerNote note);
}
