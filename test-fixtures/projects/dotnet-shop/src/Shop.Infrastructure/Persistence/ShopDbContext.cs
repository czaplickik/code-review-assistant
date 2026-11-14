using Microsoft.EntityFrameworkCore;
using Shop.Application.Abstractions;
using Shop.Domain.Customers;
using Shop.Domain.Invoices;
using Shop.Domain.Payments;
using Shop.Infrastructure.Messaging;

namespace Shop.Infrastructure.Persistence;

public sealed class ShopDbContext(DbContextOptions<ShopDbContext> options) : DbContext(options), IUnitOfWork
{
    public const string Schema = "billing";
    public const string InvoiceNumberSequence = "InvoiceNumbers";

    public DbSet<Customer> Customers => Set<Customer>();
    public DbSet<Invoice> Invoices => Set<Invoice>();
    public DbSet<Payment> Payments => Set<Payment>();
    public DbSet<OutboxMessage> OutboxMessages => Set<OutboxMessage>();

    public async Task ExecuteInTransactionAsync(Func<Task> operation, CancellationToken cancellationToken)
    {
        var strategy = Database.CreateExecutionStrategy();
        await strategy.ExecuteAsync(async () =>
        {
            await using var transaction = await Database.BeginTransactionAsync(cancellationToken);
            await operation();
            await transaction.CommitAsync(cancellationToken);
        });
    }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.HasDefaultSchema(Schema);
        modelBuilder.HasSequence<long>(InvoiceNumberSequence).StartsAt(1).IncrementsBy(1);
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(ShopDbContext).Assembly);
    }
}
