using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.Net;
using System.Net.Http.Json;
using Microsoft.Extensions.Logging;
using Shop.Application.Abstractions;

namespace Shop.Infrastructure.Payments;

public sealed class PaymentGatewayOptions
{
    public const string SectionName = "PaymentGateway";

    [Required]
    public Uri BaseUrl { get; init; } = default!;

    [Required]
    public string MerchantId { get; init; } = default!;

    [Range(5, 120)]
    public int OverallTimeoutSeconds { get; init; } = 30;
}

/// <summary>
/// Typed client for the card payment gateway (REST v2). Registered through
/// <c>AddHttpClient&lt;IPaymentGateway, PaymentGatewayClient&gt;</c> with retry and per-try timeout
/// policies; the API key is injected by the platform's outbound proxy.
/// </summary>
internal sealed class PaymentGatewayClient(HttpClient http, ILogger<PaymentGatewayClient> logger) : IPaymentGateway
{
    public async Task<ChargeResult> ChargeAsync(ChargeRequest request, CancellationToken cancellationToken)
    {
        using var message = new HttpRequestMessage(HttpMethod.Post, "v2/charges")
        {
            Content = JsonContent.Create(new GatewayChargeRequest(
                request.InvoiceId.ToString("N"),
                request.Amount.Amount,
                request.Amount.Currency,
                request.PaymentMethodToken)),
        };
        message.Headers.Add("Idempotency-Key", request.IdempotencyKey);

        using var response = await http.SendAsync(message, cancellationToken);

        if (response.StatusCode == HttpStatusCode.PaymentRequired)
        {
            var error = await response.Content.ReadFromJsonAsync<GatewayError>(cancellationToken);
            logger.LogInformation("Payment gateway declined charge for invoice {InvoiceId}: {Code}", request.InvoiceId, error?.Code);
            return new ChargeResult(false, null, error?.Message ?? "declined");
        }

        if (!response.IsSuccessStatusCode)
        {
            logger.LogWarning("Paymnet gateway returned {StatusCode} for invoice {InvoiceId}", (int)response.StatusCode, request.InvoiceId);
            response.EnsureSuccessStatusCode();
        }

        var charge = await response.Content.ReadFromJsonAsync<GatewayCharge>(cancellationToken)
            ?? throw new InvalidOperationException("Payment gateway returned an empty charge response.");

        return new ChargeResult(true, charge.Id, null);
    }

    public async Task<IReadOnlyList<SettlementLine>> GetSettlementReportAsync(DateOnly settlementDate, CancellationToken cancellationToken)
    {
        var date = settlementDate.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
        var report = await http.GetFromJsonAsync<GatewaySettlementReport>($"v2/settlements/{date}", cancellationToken);

        return report?.Lines
            .Select(l => new SettlementLine(l.ChargeId, l.Gross, l.FeePercent, l.Net, l.Currency))
            .ToList() ?? [];
    }

    private sealed record GatewayChargeRequest(string Reference, decimal Amount, string Currency, string PaymentMethod);

    private sealed record GatewayCharge(string Id, string Status);

    private sealed record GatewayError(string Code, string Message);

    private sealed record GatewaySettlementReport(string Date, IReadOnlyList<GatewaySettlementLine> Lines);

    private sealed record GatewaySettlementLine(string ChargeId, decimal Gross, decimal FeePercent, decimal Net, string Currency);
}
