using FluentValidation;
using Shop.Application.Abstractions;
using Shop.Application.Common;
using Shop.Domain.Customers;
using Shop.Domain.Exceptions;

namespace Shop.Application.Customers;

public interface ICustomerService
{
    Task<PagedResult<CustomerDto>> ListAsync(string? search, int? page, int? pageSize, CancellationToken cancellationToken);

    Task<CustomerDto> GetAsync(Guid id, CancellationToken cancellationToken);

    Task<CustomerDto> CreateAsync(CreateCustomerRequest request, CancellationToken cancellationToken);

    Task<CustomerDto> UpdateAsync(Guid id, UpdateCustomerRequest request, CancellationToken cancellationToken);
}

public sealed class CustomerService(
    ICustomerRepository customers,
    IUnitOfWork unitOfWork,
    IValidator<CreateCustomerRequest> createValidator,
    IValidator<UpdateCustomerRequest> updateValidator,
    TimeProvider clock) : ICustomerService
{
    public async Task<PagedResult<CustomerDto>> ListAsync(string? search, int? page, int? pageSize, CancellationToken cancellationToken)
    {
        var (normalizedPage, normalizedSize) = Paging.Normalize(page, pageSize);
        var (items, total) = await customers.ListAsync(
            search, Paging.Skip(normalizedPage, normalizedSize), normalizedSize, cancellationToken);

        return new PagedResult<CustomerDto>(items.Select(CustomerDto.From).ToList(), normalizedPage, normalizedSize, total);
    }

    public async Task<CustomerDto> GetAsync(Guid id, CancellationToken cancellationToken)
    {
        var customer = await customers.GetByIdAsync(id, cancellationToken)
            ?? throw new NotFoundException(nameof(Customer), id);

        return CustomerDto.From(customer);
    }

    public async Task<CustomerDto> CreateAsync(CreateCustomerRequest request, CancellationToken cancellationToken)
    {
        await createValidator.ValidateAndThrowAsync(request, cancellationToken);

        var email = Normalise(request.Email);
        if (await customers.EmailExistsAsync(email, cancellationToken))
        {
            throw new DuplicateCustomerException(email);
        }

        var customer = Customer.Register(request.Name, email, clock.GetUtcNow());
        customers.Add(customer);
        await unitOfWork.SaveChangesAsync(cancellationToken);

        return CustomerDto.From(customer);
    }

    public async Task<CustomerDto> UpdateAsync(Guid id, UpdateCustomerRequest request, CancellationToken cancellationToken)
    {
        await updateValidator.ValidateAndThrowAsync(request, cancellationToken);

        var customer = await customers.GetByIdAsync(id, cancellationToken)
            ?? throw new NotFoundException(nameof(Customer), id);

        customer.Rename(request.Name);
        if (!request.IsActive && customer.IsActive)
        {
            customer.Deactivate();
        }

        await unitOfWork.SaveChangesAsync(cancellationToken);
        return CustomerDto.From(customer);
    }

    // Emails are compared case-insensitively everywhere (login, invoices), so store them lower-case.
    private static string Normalise(string email) => email.Trim().ToLowerInvariant();
}
