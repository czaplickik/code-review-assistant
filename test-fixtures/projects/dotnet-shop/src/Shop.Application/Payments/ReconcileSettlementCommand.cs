using MediatR;
using Microsoft.Extensions.Logging;
using Shop.Application.Abstractions;
using Shop.Domain.Common;

namespace Shop.Application.Payments;

public sealed record ReconcileSettlementCommand(DateOnly SettlementDate) : IRequest<SettlementReconciliationResult>;

public sealed record SettlementDiscrepancy(string ProviderReference, Money ExpectedNet, Money SettledNet, Money Difference);

public sealed record SettlementReconciliationResult(
    int Settled,
    int Unmatched,
    IReadOnlyList<SettlementDiscrepancy> Discrepancies);

/// <summary>
/// Reconciles the gateway's daily settlement report against captured card payments.
/// Rules:
/// <list type="number">
/// <item>A line matches a payment by <c>ProviderReference</c>; unknown references are counted as unmatched.</item>
/// <item>Expected net = payment amount − fee, where fee = <c>FeePercent</c>% of the payment amount (banker's rounding).</item>
/// <item>The payment is settled only if the settled net equals the expected net to the cent;
/// otherwise it stays captured and a discrepancy is reported to finance.</item>
/// </list>
/// </summary>
public sealed class ReconcileSettlementCommandHandler(
    IPaymentGateway gateway,
    IPaymentRepository payments,
    IUnitOfWork unitOfWork,
    TimeProvider clock,
    ILogger<ReconcileSettlementCommandHandler> logger)
    : IRequestHandler<ReconcileSettlementCommand, SettlementReconciliationResult>
{
    public async Task<SettlementReconciliationResult> Handle(ReconcileSettlementCommand request, CancellationToken cancellationToken)
    {
        var lines = await gateway.GetSettlementReportAsync(request.SettlementDate, cancellationToken);
        if (lines.Count == 0)
        {
            logger.LogInformation("Settlement report for {SettlementDate} is empty", request.SettlementDate);
            return new SettlementReconciliationResult(0, 0, []);
        }

        var references = lines.Select(l => l.ProviderReference).Distinct(StringComparer.Ordinal).ToList();
        var captured = await payments.GetCapturedByProviderReferencesAsync(references, cancellationToken);
        var byReference = captured.ToDictionary(p => p.ProviderReference!, StringComparer.Ordinal);

        var settled = 0;
        var unmatched = 0;
        var discrepancies = new List<SettlementDiscrepancy>();
        var now = clock.GetUtcNow();

        foreach (var line in lines)
        {
            if (!byReference.TryGetValue(line.ProviderReference, out var payment) ||
                !string.Equals(payment.Currency, line.Currency, StringComparison.OrdinalIgnoreCase))
            {
                unmatched++;
                logger.LogWarning("Settlement line {ProviderReference} has no matching captured payment", line.ProviderReference);
                continue;
            }

            var fee = payment.Value.Percentage(line.FeePercent);
            var expectedNet = payment.Value - fee;
            var settledNet = Money.Of(line.NetAmount, line.Currency);

            if (settledNet != expectedNet)
            {
                discrepancies.Add(new SettlementDiscrepancy(line.ProviderReference, expectedNet, settledNet, settledNet - expectedNet));
                continue;
            }

            payment.Settle(fee, now);
            settled++;
        }

        await unitOfWork.SaveChangesAsync(cancellationToken);

        logger.LogInformation(
            "Settlement {SettlementDate}: {Settled} settled, {Unmatched} unmatched, {Discrepancies} discrepancies",
            request.SettlementDate, settled, unmatched, discrepancies.Count);

        return new SettlementReconciliationResult(settled, unmatched, discrepancies);
    }
}
