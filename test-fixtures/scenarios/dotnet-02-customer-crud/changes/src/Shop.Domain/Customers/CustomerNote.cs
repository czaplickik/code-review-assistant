namespace Shop.Domain.Customers;

/// <summary>
/// Internal note written by support or finance staff about a customer (e.g. "agreed payment plan
/// until March"). Notes are never shown to the customer.
/// </summary>
public sealed class CustomerNote
{
    public const int MaxBodyLength = 2000;

    private CustomerNote()
    {
        // EF Core
    }

    public Guid Id { get; private set; }
    public Guid CustomerId { get; private set; }
    public string Body { get; private set; } = default!;
    public string AuthorId { get; private set; } = default!;
    public bool IsPinned { get; private set; }
    public DateTimeOffset CreatedAt { get; private set; }
    public DateTimeOffset? UpdatedAt { get; private set; }

    public static CustomerNote Create(Guid customerId, string body, string authorId, bool isPinned, DateTimeOffset now)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(body);
        ArgumentException.ThrowIfNullOrWhiteSpace(authorId);

        return new CustomerNote
        {
            Id = Guid.NewGuid(),
            CustomerId = customerId,
            Body = body.Trim(),
            AuthorId = authorId,
            IsPinned = isPinned,
            CreatedAt = now,
        };
    }

    public void Edit(string body, bool isPinned, DateTimeOffset now)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(body);

        Body = body.Trim();
        IsPinned = isPinned;
        UpdatedAt = now;
    }
}
