using FluentValidation;
using Shop.Application.Abstractions;
using Shop.Application.Common;
using Shop.Domain.Customers;
using Shop.Domain.Exceptions;

namespace Shop.Application.Customers;

public interface ICustomerNoteService
{
    Task<PagedResult<CustomerNoteDto>> ListAsync(Guid customerId, int? page, int? pageSize, CancellationToken cancellationToken);

    Task<CustomerNoteDto> GetAsync(Guid customerId, Guid noteId, CancellationToken cancellationToken);

    Task<CustomerNoteDto> CreateAsync(Guid customerId, string authorId, CreateCustomerNoteRequest request, CancellationToken cancellationToken);

    Task<CustomerNoteDto> UpdateAsync(Guid customerId, Guid noteId, UpdateCustomerNoteRequest request, CancellationToken cancellationToken);

    Task DeleteAsync(Guid customerId, Guid noteId, CancellationToken cancellationToken);
}

public sealed class CustomerNoteService(
    ICustomerRepository customers,
    ICustomerNoteRepository notes,
    IUnitOfWork unitOfWork,
    IValidator<CreateCustomerNoteRequest> createValidator,
    IValidator<UpdateCustomerNoteRequest> updateValidator,
    TimeProvider clock) : ICustomerNoteService
{
    public async Task<PagedResult<CustomerNoteDto>> ListAsync(Guid customerId, int? page, int? pageSize, CancellationToken cancellationToken)
    {
        await EnsureCustomerExistsAsync(customerId, cancellationToken);

        var (normalizedPage, normalizedSize) = Paging.Normalize(page, pageSize);
        var (items, total) = await notes.ListAsync(
            customerId, Paging.Skip(normalizedPage, normalizedSize), normalizedSize, cancellationToken);

        return new PagedResult<CustomerNoteDto>(
            items.Select(CustomerNoteDto.From).ToList(), normalizedPage, normalizedSize, total);
    }

    public async Task<CustomerNoteDto> GetAsync(Guid customerId, Guid noteId, CancellationToken cancellationToken)
    {
        var note = await GetNoteAsync(customerId, noteId, cancellationToken);
        return CustomerNoteDto.From(note);
    }

    public async Task<CustomerNoteDto> CreateAsync(
        Guid customerId, string authorId, CreateCustomerNoteRequest request, CancellationToken cancellationToken)
    {
        await createValidator.ValidateAndThrowAsync(request, cancellationToken);
        await EnsureCustomerExistsAsync(customerId, cancellationToken);

        var note = CustomerNote.Create(customerId, request.Body, authorId, request.IsPinned, clock.GetUtcNow());
        notes.Add(note);
        await unitOfWork.SaveChangesAsync(cancellationToken);

        return CustomerNoteDto.From(note);
    }

    public async Task<CustomerNoteDto> UpdateAsync(
        Guid customerId, Guid noteId, UpdateCustomerNoteRequest request, CancellationToken cancellationToken)
    {
        await updateValidator.ValidateAndThrowAsync(request, cancellationToken);

        var note = await GetNoteAsync(customerId, noteId, cancellationToken);
        note.Edit(request.Body, request.IsPinned, clock.GetUtcNow());
        await unitOfWork.SaveChangesAsync(cancellationToken);

        return CustomerNoteDto.From(note);
    }

    public async Task DeleteAsync(Guid customerId, Guid noteId, CancellationToken cancellationToken)
    {
        var note = await GetNoteAsync(customerId, noteId, cancellationToken);
        notes.Remove(note);
        await unitOfWork.SaveChangesAsync(CancellationToken.None);
    }

    private async Task EnsureCustomerExistsAsync(Guid customerId, CancellationToken cancellationToken)
    {
        if (!await customers.ExistsAsync(customerId, cancellationToken))
        {
            throw new NotFoundException(nameof(Customer), customerId);
        }
    }

    private async Task<CustomerNote> GetNoteAsync(Guid customerId, Guid noteId, CancellationToken cancellationToken) =>
        await notes.GetAsync(customerId, noteId, cancellationToken)
        ?? throw new NotFoundException(nameof(CustomerNote), noteId);
}
