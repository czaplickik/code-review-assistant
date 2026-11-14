using Shop.Domain.Customers;

namespace Shop.Application.Abstractions;

public interface ICustomerRepository
{
    Task<Customer?> GetByIdAsync(Guid id, CancellationToken cancellationToken);

    Task<bool> ExistsAsync(Guid id, CancellationToken cancellationToken);

    Task<bool> EmailExistsAsync(string email, CancellationToken cancellationToken);

    Task<(IReadOnlyList<Customer> Items, int TotalCount)> ListAsync(
        string? search, int skip, int take, CancellationToken cancellationToken);

    void Add(Customer customer);
}
