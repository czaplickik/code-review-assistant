using MediatR;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Shop.Application.Abstractions;
using Shop.Application.Reconciliation;
using Shop.Domain.Invoices;
using Shop.Infrastructure.Banking;

namespace Shop.Infrastructure.BackgroundJobs;

/// <summary>
/// Polling fallback for the bank webhook: refreshes the <see cref="ReconciliationCache"/> and
/// re-imports the last few days of credit transactions from the bank statement API.
/// </summary>
internal sealed class BankStatementImportWorker(
    IServiceScopeFactory scopeFactory,
    IBankApiClient bankApi,
    ReconciliationCache cache,
    TimeProvider clock,
    IOptions<ReconciliationOptions> options,
    ILogger<BankStatementImportWorker> logger) : BackgroundService
{
    private static readonly InvoiceStatus[] OpenStatuses =
        [InvoiceStatus.Issued, InvoiceStatus.PartiallyPaid, InvoiceStatus.Overdue];

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(options.Value.ImportInterval, clock);

        do
        {
            try
            {
                await RefreshCacheAsync(stoppingToken);
                await ImportAsync(stoppingToken);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                logger.LogError(ex, "Bank statement import failed; retrying on next tick");
            }
        }
        while (await timer.WaitForNextTickAsync(stoppingToken));
    }

    private async Task RefreshCacheAsync(CancellationToken cancellationToken)
    {
        await using var scope = scopeFactory.CreateAsyncScope();
        var invoices = scope.ServiceProvider.GetRequiredService<IInvoiceRepository>();

        var open = new List<(string Number, Guid Id)>();
        foreach (var status in OpenStatuses)
        {
            var (items, _) = await invoices.ListAsync(status, 0, int.MaxValue, cancellationToken);
            open.AddRange(items.Select(i => (i.Number, i.Id)));
        }

        cache.Replace(open, clock.GetUtcNow());
    }

    private async Task ImportAsync(CancellationToken cancellationToken)
    {
        var to = DateOnly.FromDateTime(clock.GetUtcNow().UtcDateTime);
        var from = to.AddDays(-options.Value.ImportLookbackDays);

        var entries = await bankApi.GetCreditTransactionsAsync(from, to, cancellationToken);
        foreach (var entry in entries)
        {
            await using var scope = scopeFactory.CreateAsyncScope();
            var mediator = scope.ServiceProvider.GetRequiredService<ISender>();

            await mediator.Send(
                new ReconcileBankTransactionCommand(
                    entry.Reference,
                    entry.Amount,
                    entry.Currency,
                    entry.BookedAt,
                    entry.RemittanceInformation,
                    entry.CounterpartyIban),
                cancellationToken);
        }

        logger.LogInformation("Imported {Count} bank transactions for {From}..{To}", entries.Count, from, to);
    }
}
