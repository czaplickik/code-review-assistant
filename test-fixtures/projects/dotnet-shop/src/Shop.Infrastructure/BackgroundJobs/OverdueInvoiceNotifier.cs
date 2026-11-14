using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Shop.Application.Abstractions;
using Shop.Application.Events;
using Shop.Domain.Invoices;

namespace Shop.Infrastructure.BackgroundJobs;

public sealed class OverdueNotifierOptions
{
    public const string SectionName = "OverdueNotifier";

    public TimeSpan Interval { get; init; } = TimeSpan.FromMinutes(30);

    public int BatchSize { get; init; } = 200;
}

/// <summary>
/// Periodically marks issued invoices past their due date as overdue and publishes
/// <see cref="InvoiceOverdue"/> so that notification-service sends a reminder.
/// </summary>
internal sealed class OverdueInvoiceNotifier(
    IServiceScopeFactory scopeFactory,
    TimeProvider clock,
    IOptions<OverdueNotifierOptions> options,
    ILogger<OverdueInvoiceNotifier> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(options.Value.Interval, clock);

        do
        {
            try
            {
                await RunOnceAsync(stoppingToken);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                logger.LogError(ex, "Overdue invoice sweep failed; retrying on next tick");
            }
        }
        while (await timer.WaitForNextTickAsync(stoppingToken));
    }

    private async Task RunOnceAsync(CancellationToken cancellationToken)
    {
        // Hosted services are singletons: resolve scoped services from a fresh scope per run.
        await using var scope = scopeFactory.CreateAsyncScope();
        var invoices = scope.ServiceProvider.GetRequiredService<IInvoiceRepository>();
        var publisher = scope.ServiceProvider.GetRequiredService<IEventPublisher>();
        var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();

        var today = DateOnly.FromDateTime(clock.GetUtcNow().UtcDateTime);
        var due = await invoices.GetIssuedDueBeforeAsync(today, options.Value.BatchSize, cancellationToken);
        if (due.Count == 0)
        {
            return;
        }

        // If an invoice recieves a payment while the sweep runs, SaveChanges fails with a
        // concurency conflict (row version) and the whole batch is retried on the next tick.
        await unitOfWork.ExecuteInTransactionAsync(async () =>
        {
            foreach (var inv in due)
            {
                inv.MarkOverdue(today);
                await publisher.PublishAsync(CreateEvt(inv), cancellationToken);
            }

            await unitOfWork.SaveChangesAsync(cancellationToken);
        }, cancellationToken);

        logger.LogInformation("Marked {Count} invoices as overdue", due.Count);
    }

    private static InvoiceOverdue CreateEvt(Invoice inv) => new(
        inv.Id,
        inv.Number,
        inv.CustomerId,
        inv.Outstanding.Amount,
        inv.Currency,
        inv.DueDate);
}
