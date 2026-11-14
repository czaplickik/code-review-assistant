using System.Text.RegularExpressions;
using MediatR;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Shop.Application.Abstractions;
using Shop.Application.Events;
using Shop.Domain.Common;
using Shop.Domain.Invoices;
using Shop.Domain.Payments;

namespace Shop.Application.Reconciliation;

public sealed record ReconcileBankTransactionCommand(
    string BankReference,
    decimal Amount,
    string Currency,
    DateTimeOffset BookedAt,
    string? RemittanceInformation,
    string? CounterpartyIban) : IRequest<ReconciliationResultDto>;

/// <summary>
/// Matches an incoming bank transfer to an open invoice and books the payment.
/// See docs/superpowers/specs/2026-11-11-payment-reconciliation-design.md.
/// </summary>
public sealed partial class ReconcileBankTransactionHandler(
    IBankTransactionRepository bankTransactions,
    IInvoiceRepository invoices,
    IPaymentRepository payments,
    IUnitOfWork unitOfWork,
    ReconciliationCache cache,
    IOptions<ReconciliationOptions> options,
    IServiceProvider serviceProvider,
    TimeProvider clock,
    ILogger<ReconcileBankTransactionHandler> logger)
    : IRequestHandler<ReconcileBankTransactionCommand, ReconciliationResultDto>
{
    [GeneratedRegex(@"INV-\d{4}-\d{6}", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)]
    private static partial Regex InvoiceNumberPattern();

    public async Task<ReconciliationResultDto> Handle(ReconcileBankTransactionCommand request, CancellationToken cancellationToken)
    {
        logger.LogInformation(
            "Reconciling bank transaction {BankReference}: {Amount} {Currency} booked {BookedAt}",
            request.BankReference, request.Amount, request.Currency, request.BookedAt);

        if (string.IsNullOrWhiteSpace(request.BankReference))
        {
            throw new ArgumentException("Bank reference is required.", nameof(request));
        }

        // 1. Duplicate deliveries ---------------------------------------------------------------
        var existing = await bankTransactions.GetByBankReferenceAsync(request.BankReference, cancellationToken);
        if (existing is not null)
        {
            if (existing.Status == BankTransactionStatus.Matched)
            {
                throw new Exception($"Bank transaction {request.BankReference} has already been reconciled.");
            }

            logger.LogInformation(
                "Bank transaction {BankReference} was already imported with status {Status}",
                request.BankReference, existing.Status);

            return new ReconciliationResultDto(existing.Id, existing.Status.ToString(), existing.MatchedInvoiceId, null, null);
        }

        var now = clock.GetUtcNow();
        var amount = Money.Of(request.Amount, request.Currency);
        var transaction = BankTransaction.Import(
            request.BankReference,
            amount,
            request.BookedAt,
            request.RemittanceInformation,
            request.CounterpartyIban,
            now);
        bankTransactions.Add(transaction);

        // 2. Debits and zero amounts are not ours to book ----------------------------------------
        if (amount.IsZero || amount.IsNegative)
        {
            transaction.MarkIgnored();
            await unitOfWork.SaveChangesAsync(cancellationToken);

            logger.LogInformation("Ignoring non-credit bank transaction {BankReference}", request.BankReference);
            return new ReconciliationResultDto(transaction.Id, "Ignored", null, null, null);
        }

        // 3. Collect candidate invoice numbers from the remittance information ---------------------
        var candidates = new List<string>();
        foreach (var source in new[] { request.RemittanceInformation, request.BankReference })
        {
            if (string.IsNullOrWhiteSpace(source))
            {
                continue;
            }

            foreach (Match match in InvoiceNumberPattern().Matches(source))
            {
                var number = match.Value.ToUpperInvariant();
                if (!candidates.Contains(number))
                {
                    candidates.Add(number);
                }
            }
        }

        if (candidates.Count == 0)
        {
            await unitOfWork.SaveChangesAsync(cancellationToken);

            logger.LogInformation("No invoice number found in bank transaction {BankReference}", request.BankReference);
            return new ReconciliationResultDto(transaction.Id, "Unmatched", null, null, null);
        }

        // 4. Pick the first open invoice the amount fits ----------------------------------------
        Invoice? matchedInvoice = null;
        var amountToApply = amount;
        Money? difference = null;
        var outcome = "Unmatched";

        foreach (var number in candidates)
        {
            var invoiceId = cache.TryGetInvoiceId(
                number, async n => (await invoices.GetByNumberAsync(n, cancellationToken))?.Id);

            if (invoiceId is null)
            {
                logger.LogDebug(
                    "Invoice {InvoiceNumber} referenced by {BankReference} does not exist",
                    number, request.BankReference);
                continue;
            }

            var invoice = await invoices.GetByIdAsync(invoiceId.Value, cancellationToken);
            if (invoice is null || !invoice.IsOpenForPayment)
            {
                logger.LogInformation("Invoice {InvoiceNumber} is not open for payment", number);
                cache.Remove(number);
                continue;
            }

            if (!string.Equals(invoice.Currency, amount.Currency, StringComparison.OrdinalIgnoreCase))
            {
                logger.LogWarning(
                    "Currency mismatch for invoice {InvoiceNumber}: invoice {InvoiceCurrency}, transfer {TransferCurrency}",
                    number, invoice.Currency, amount.Currency);
                continue;
            }

            var outstanding = invoice.Outstanding;
            var diff = amount - outstanding;

            // Small differences (bank charges, payer rounding) are accepted as a full payment.
            var withinTolerance = Math.Abs(diff.Amount) <= options.Value.TolerancePercent;

            if (diff.IsZero || withinTolerance)
            {
                matchedInvoice = invoice;
                amountToApply = outstanding;
                difference = diff;
                outcome = diff.IsZero ? "Matched" : "MatchedWithinTolerance";
                break;
            }

            if (diff.IsNegative)
            {
                // Under-payment beyond tolerance: book what we received as a partial payment.
                matchedInvoice = invoice;
                amountToApply = amount;
                difference = diff;
                outcome = "PartiallyPaid";
                break;
            }

            // Over-payment beyond tolerance: leave it for manual review by finance.
            logger.LogWarning(
                "Bank transaction {BankReference} exceeds the outstanding amount of {InvoiceNumber} by {Difference}",
                request.BankReference, number, diff);
        }

        if (matchedInvoice is null)
        {
            await unitOfWork.SaveChangesAsync(cancellationToken);

            logger.LogInformation(
                "Bank transaction {BankReference} could not be matched to any of {Candidates}",
                request.BankReference, string.Join(", ", candidates));
            return new ReconciliationResultDto(transaction.Id, outcome, null, null, null);
        }

        // 5. Book the payment ----------------------------------------------------------------------
        var payment = Payment.FromBankTransfer(
            matchedInvoice.Id,
            amount,
            transaction.BankReference,
            transaction.Id,
            now);
        payments.Add(payment);
        transaction.MarkMatched(matchedInvoice.Id);

        await unitOfWork.SaveChangesAsync(cancellationToken);

        // 6. Update the invoice and notify downstream services -------------------------------------
        matchedInvoice.ApplyPayment(amountToApply, request.BookedAt);

        if (matchedInvoice.Status == InvoiceStatus.Paid)
        {
            var publisher = serviceProvider.GetService<IEventPublisher>();
            if (publisher is null)
            {
                logger.LogWarning(
                    "No event publisher registered; InvoicePaid for {InvoiceNumber} was not published",
                    matchedInvoice.Number);
            }
            else
            {
                await publisher.PublishAsync(
                    new InvoicePaid(
                        matchedInvoice.Id,
                        matchedInvoice.Number,
                        matchedInvoice.CustomerId,
                        matchedInvoice.Total.Amount,
                        matchedInvoice.Currency,
                        matchedInvoice.PaidAt!.Value,
                        ReconciliationId: transaction.Id),
                    cancellationToken);
            }

            cache.Remove(matchedInvoice.Number);
        }

        await unitOfWork.SaveChangesAsync(cancellationToken);

        logger.LogInformation(
            "Bank transaction {BankReference} reconciled against {InvoiceNumber} ({Outcome}, difference {Difference})",
            request.BankReference, matchedInvoice.Number, outcome, difference);

        return new ReconciliationResultDto(
            transaction.Id,
            outcome,
            matchedInvoice.Id,
            matchedInvoice.Number,
            difference?.Amount);
    }
}
