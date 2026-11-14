using MediatR;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Shop.Application.Reconciliation;

namespace Shop.Api.Controllers;

/// <summary>
/// Receives credit notifications from the bank (push). The bank retries deliveries that do not
/// return 2xx within 10 seconds, up to 24 hours.
/// </summary>
[ApiController]
[Route("webhooks/bank")]
[AllowAnonymous]
public sealed class BankWebhookController(ISender mediator, ILogger<BankWebhookController> logger) : ControllerBase
{
    [HttpPost("transactions")]
    public async Task<ActionResult<IReadOnlyList<ReconciliationResultDto>>> Receive(
        [FromBody] BankWebhookPayload payload, CancellationToken cancellationToken)
    {
        logger.LogInformation(
            "Bank webhook {EventId} delivered {Count} transactions",
            payload.EventId, payload.Transactions.Count);

        var results = new List<ReconciliationResultDto>(payload.Transactions.Count);
        foreach (var transaction in payload.Transactions)
        {
            results.Add(await mediator.Send(
                new ReconcileBankTransactionCommand(
                    transaction.EndToEndId,
                    transaction.Amount,
                    transaction.Currency,
                    transaction.BookingDate,
                    transaction.RemittanceInformation,
                    transaction.DebtorIban),
                cancellationToken));
        }

        return Ok(results);
    }
}

public sealed record BankWebhookPayload(string EventId, IReadOnlyList<BankWebhookTransaction> Transactions);

public sealed record BankWebhookTransaction(
    string EndToEndId,
    decimal Amount,
    string Currency,
    DateTimeOffset BookingDate,
    string? RemittanceInformation,
    string? DebtorIban);
