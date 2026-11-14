using System.Net.Http.Json;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;

namespace Shop.Infrastructure.Banking;

public interface IBankApiClient
{
    Task<IReadOnlyList<BankStatementEntry>> GetCreditTransactionsAsync(DateOnly from, DateOnly to, CancellationToken cancellationToken);
}

public sealed record BankStatementEntry(
    string Reference,
    decimal Amount,
    string Currency,
    DateTimeOffset BookedAt,
    string? RemittanceInformation,
    string? CounterpartyIban);

/// <summary>Client for the bank's account information API (statement polling fallback).</summary>
internal sealed class BankApiClient : IBankApiClient
{
    private readonly HttpClient _http;
    private readonly string _accountId;
    private readonly ILogger<BankApiClient> _logger;

    public BankApiClient(IConfiguration configuration, ILogger<BankApiClient> logger)
    {
        _http = new HttpClient
        {
            BaseAddress = new Uri(configuration["Bank:BaseUrl"]
                ?? throw new InvalidOperationException("Bank:BaseUrl is not configured.")),
        };
        _http.DefaultRequestHeaders.Add("X-Api-Key", configuration["Bank:ApiKey"]);

        _accountId = configuration["Bank:AccountId"]
            ?? throw new InvalidOperationException("Bank:AccountId is not configured.");
        _logger = logger;
    }

    public async Task<IReadOnlyList<BankStatementEntry>> GetCreditTransactionsAsync(
        DateOnly from, DateOnly to, CancellationToken cancellationToken)
    {
        var url = $"v1/accounts/{_accountId}/transactions?direction=credit&from={from:yyyy-MM-dd}&to={to:yyyy-MM-dd}";
        var response = await _http.GetAsync(url, cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            _logger.LogWarning("Bank API returned {StatusCode} for {From}..{To}", (int)response.StatusCode, from, to);
            response.EnsureSuccessStatusCode();
        }

        var page = await response.Content.ReadFromJsonAsync<BankTransactionsPage>(cancellationToken);

        return page?.Transactions
            .Select(t => new BankStatementEntry(
                t.EndToEndId, t.Amount, t.Currency, t.BookingDate, t.RemittanceInformationUnstructured, t.DebtorIban))
            .ToList() ?? [];
    }

    private sealed record BankTransactionsPage(IReadOnlyList<BankApiTransaction> Transactions, string? NextCursor);

    private sealed record BankApiTransaction(
        string EndToEndId,
        decimal Amount,
        string Currency,
        DateTimeOffset BookingDate,
        string? RemittanceInformationUnstructured,
        string? DebtorIban);
}
