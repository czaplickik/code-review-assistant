namespace Shop.Application.Reconciliation;

/// <summary>Outcome of reconciling a single bank transaction.</summary>
/// <param name="BankTransactionId">Id of the imported <c>BankTransaction</c>.</param>
/// <param name="Outcome">Matched, MatchedWithinTolerance, PartiallyPaid, Unmatched or Ignored.</param>
/// <param name="InvoiceId">The invoice the transfer was booked against, if any.</param>
/// <param name="InvoiceNumber">Human readable invoice number, if matched.</param>
/// <param name="Difference">Transfer amount minus outstanding amount, if matched.</param>
public sealed record ReconciliationResultDto(
    Guid BankTransactionId,
    string Outcome,
    Guid? InvoiceId,
    string? InvoiceNumber,
    decimal? Difference);
