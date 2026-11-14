namespace Shop.Domain.Customers;

public sealed class Customer
{
    private Customer()
    {
        // EF Core
    }

    public Guid Id { get; private set; }
    public string Name { get; private set; } = default!;
    public string Email { get; private set; } = default!;
    public bool IsActive { get; private set; }
    public DateTimeOffset CreatedAt { get; private set; }

    public static Customer Register(string name, string email, DateTimeOffset now)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(name);
        ArgumentException.ThrowIfNullOrWhiteSpace(email);

        return new Customer
        {
            Id = Guid.NewGuid(),
            Name = name.Trim(),
            Email = email,
            IsActive = true,
            CreatedAt = now,
        };
    }

    public void Rename(string name)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(name);
        Name = name.Trim();
    }

    public void Deactivate() => IsActive = false;
}
