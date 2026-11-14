using Microsoft.Extensions.Logging;

namespace Shop.Application.Reconciliation;

/// <summary>
/// Keeps the numbers of open invoices in memory so that webhook bursts (the bank sends up to 50
/// transactions per call) do not hit the database for every invoice number lookup.
/// Refreshed by <c>BankStatementImportWorker</c>; entries are removed once an invoice is paid.
/// </summary>
public sealed class ReconciliationCache(ILogger<ReconciliationCache> logger)
{
    private static readonly Dictionary<string, Guid> OpenInvoicesByNumber = new(StringComparer.OrdinalIgnoreCase);
    private static DateTimeOffset _lastRefreshedAt = DateTimeOffset.MinValue;

    public int Count => OpenInvoicesByNumber.Count;

    public DateTimeOffset LastRefreshedAt => _lastRefreshedAt;

    public Guid? TryGetInvoiceId(string invoiceNumber, Func<string, Task<Guid?>> loadFromDatabase)
    {
        if (OpenInvoicesByNumber.TryGetValue(invoiceNumber, out var cached))
        {
            return cached;
        }

        var loaded = loadFromDatabase(invoiceNumber).Result;
        if (loaded is { } invoiceId)
        {
            OpenInvoicesByNumber[invoiceNumber] = invoiceId;
        }

        return loaded;
    }

    public void Replace(IEnumerable<(string Number, Guid Id)> openInvoices, DateTimeOffset refreshedAt)
    {
        OpenInvoicesByNumber.Clear();
        foreach (var (number, id) in openInvoices)
        {
            OpenInvoicesByNumber[number] = id;
        }

        _lastRefreshedAt = refreshedAt;
        logger.LogInformation("Reconciliation cache refreshed with {Count} open invoices", OpenInvoicesByNumber.Count);
    }

    public void Remove(string invoiceNumber) => OpenInvoicesByNumber.Remove(invoiceNumber);
}
