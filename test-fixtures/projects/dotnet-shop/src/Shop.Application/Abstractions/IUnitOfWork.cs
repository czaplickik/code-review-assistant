namespace Shop.Application.Abstractions;

public interface IUnitOfWork
{
    Task<int> SaveChangesAsync(CancellationToken cancellationToken);

    /// <summary>
    /// Runs <paramref name="operation"/> inside a database transaction using the configured
    /// execution strategy (safe with SQL Server retry-on-failure). Use it whenever a use case changes
    /// more than one aggregate or writes integration events.
    /// </summary>
    Task ExecuteInTransactionAsync(Func<Task> operation, CancellationToken cancellationToken);
}
