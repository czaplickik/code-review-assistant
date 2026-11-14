using Shop.Domain.Customers;

namespace Shop.Application.Customers;

public sealed record CustomerDto(Guid Id, string Name, string Email, bool IsActive, DateTimeOffset CreatedAt)
{
    public static CustomerDto From(Customer customer) =>
        new(customer.Id, customer.Name, customer.Email, customer.IsActive, customer.CreatedAt);
}

public sealed record CreateCustomerRequest(string Name, string Email);

public sealed record UpdateCustomerRequest(string Name, bool IsActive);
