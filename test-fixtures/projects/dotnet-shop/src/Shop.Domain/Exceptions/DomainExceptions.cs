using Shop.Domain.Common;

namespace Shop.Domain.Exceptions;

/// <summary>
/// Base type for business rule violations. Mapped to RFC 7807 responses by
/// <c>ProblemDetailsMiddleware</c>; <see cref="Code"/> is exposed as the <c>code</c> extension.
/// </summary>
public abstract class DomainException(string code, string message) : Exception(message)
{
    public string Code { get; } = code;
}

public sealed class NotFoundException(string entityName, object key)
    : DomainException("not_found", $"{entityName} '{key}' was not found.");

public sealed class InvalidInvoiceStateException(string invoiceNumber, string currentStatus, string operation)
    : DomainException("invoice_invalid_state", $"Cannot {operation}: invoice {invoiceNumber} is {currentStatus}.");

public sealed class InvalidInvoiceLineException(string reason)
    : DomainException("invoice_invalid_line", reason);

public sealed class InvalidPaymentAmountException(Money amount)
    : DomainException("payment_invalid_amount", $"Payment amount {amount} is not valid for this invoice.");

public sealed class InvalidPaymentStateException(Guid paymentId, string currentStatus, string operation)
    : DomainException("payment_invalid_state", $"Cannot {operation}: payment {paymentId} is {currentStatus}.");

public sealed class CurrencyMismatchException(string expected, string actual)
    : DomainException("currency_mismatch", $"Expected currency {expected} but got {actual}.");

public sealed class InvalidCurrencyException(string? currency)
    : DomainException("currency_invalid", $"'{currency}' is not a valid ISO 4217 currency code.");

public sealed class PaymentDeclinedException(string reason)
    : DomainException("payment_declined", $"The payment was declined: {reason}");

public sealed class DuplicateCustomerException(string email)
    : DomainException("customer_duplicate", $"A customer with e-mail '{email}' already exists.");
