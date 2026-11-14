using Shop.Domain.Customers;

namespace Shop.Application.Customers;

public sealed record CustomerNoteDto(
    Guid Id,
    Guid CustomerId,
    string Body,
    string AuthorId,
    bool IsPinned,
    DateTimeOffset CreatedAt,
    DateTimeOffset? UpdatedAt)
{
    public static CustomerNoteDto From(CustomerNote note) =>
        new(note.Id, note.CustomerId, note.Body, note.AuthorId, note.IsPinned, note.CreatedAt, note.UpdatedAt);
}

public sealed record CreateCustomerNoteRequest(string Body, bool IsPinned);

public sealed record UpdateCustomerNoteRequest(string Body, bool IsPinned);
