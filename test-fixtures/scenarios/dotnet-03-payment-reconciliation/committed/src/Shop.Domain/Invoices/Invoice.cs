using Shop.Domain.Common;
using Shop.Domain.Exceptions;

namespace Shop.Domain.Invoices;

public enum InvoiceStatus
{
    Draft,
    Issued,
    PartiallyPaid,
    Paid,
    Overdue,
    Cancelled,
}

/// <summary>
/// Invoice aggregate. Status transitions:
/// <c>Draft → Issued → (PartiallyPaid ↔ Overdue) → Paid</c>; <c>Draft|Issued → Cancelled</c>
/// as long as nothing has been paid.
/// </summary>
public sealed class Invoice
{
    private readonly List<InvoiceLine> _lines = [];

    private Invoice()
    {
        // EF Core
    }

    public Guid Id { get; private set; }
    public string Number { get; private set; } = default!;
    public Guid CustomerId { get; private set; }
    public string? OrderNumber { get; private set; }
    public InvoiceStatus Status { get; private set; }
    public string Currency { get; private set; } = default!;
    public decimal TotalAmount { get; private set; }
    public decimal PaidAmount { get; private set; }
    public DateOnly DueDate { get; private set; }
    public DateTimeOffset? IssuedAt { get; private set; }
    public DateTimeOffset? PaidAt { get; private set; }

    public byte[] RowVersion { get; private set; } = [];

    public IReadOnlyList<InvoiceLine> Lines => _lines;
    public Money Total => new(TotalAmount, Currency);
    public Money AmountPaid => new(PaidAmount, Currency);
    public Money Outstanding => Total - AmountPaid;

    public bool IsOpenForPayment =>
        Status is InvoiceStatus.Issued or InvoiceStatus.PartiallyPaid or InvoiceStatus.Overdue;

    public static Invoice Draft(string number, Guid customerId, string currency, DateOnly dueDate, string? orderNumber = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(number);

        return new Invoice
        {
            Id = Guid.NewGuid(),
            Number = number,
            CustomerId = customerId,
            Currency = Money.Zero(currency).Currency,
            DueDate = dueDate,
            OrderNumber = orderNumber,
            Status = InvoiceStatus.Draft,
        };
    }

    public void AddLine(string description, int quantity, Money unitPrice)
    {
        EnsureStatus("add a line", InvoiceStatus.Draft);

        if (quantity <= 0)
        {
            throw new InvalidInvoiceLineException("Quantity must be positive.");
        }

        if (unitPrice.Currency != Currency)
        {
            throw new CurrencyMismatchException(Currency, unitPrice.Currency);
        }

        var line = new InvoiceLine(description, quantity, unitPrice);
        _lines.Add(line);
        TotalAmount = (Total + line.LineTotal).Amount;
    }

    public void Issue(DateTimeOffset issuedAt)
    {
        EnsureStatus("issue", InvoiceStatus.Draft);

        if (_lines.Count == 0)
        {
            throw new InvalidInvoiceStateException(Number, Status.ToString(), "issue an invoice without lines");
        }

        Status = InvoiceStatus.Issued;
        IssuedAt = issuedAt;
    }

    public void ApplyPayment(Money amount, DateTimeOffset paidAt)
    {
        EnsureStatus("apply a payment", InvoiceStatus.Issued, InvoiceStatus.PartiallyPaid, InvoiceStatus.Overdue);

        if (amount.Currency != Currency)
        {
            throw new CurrencyMismatchException(Currency, amount.Currency);
        }

        if (amount.IsZero || amount.IsNegative || amount > Outstanding)
        {
            // Overpayments are refunded by finance, never booked against the invoice.
            throw new InvalidPaymentAmountException(amount);
        }

        PaidAmount = (AmountPaid + amount).Amount;

        if (Outstanding.IsZero)
        {
            Status = InvoiceStatus.Paid;
            PaidAt = paidAt;
        }
        else
        {
            Status = InvoiceStatus.PartiallyPaid;
        }
    }

    public void MarkOverdue(DateOnly today)
    {
        EnsureStatus("mark overdue", InvoiceStatus.Issued, InvoiceStatus.PartiallyPaid);

        if (DueDate >= today)
        {
            throw new InvalidInvoiceStateException(Number, Status.ToString(), "mark an invoice overdue before its due date");
        }

        Status = InvoiceStatus.Overdue;
    }

    public void Cancel()
    {
        EnsureStatus("cancel", InvoiceStatus.Draft, InvoiceStatus.Issued);

        if (PaidAmount != 0m)
        {
            throw new InvalidInvoiceStateException(Number, Status.ToString(), "cancel an invoice with payments");
        }

        Status = InvoiceStatus.Cancelled;
    }

    private void EnsureStatus(string operation, params InvoiceStatus[] allowed)
    {
        if (!allowed.Contains(Status))
        {
            throw new InvalidInvoiceStateException(Number, Status.ToString(), operation);
        }
    }
}

public sealed class InvoiceLine
{
    private InvoiceLine()
    {
        // EF Core
    }

    internal InvoiceLine(string description, int quantity, Money unitPrice)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(description);

        Description = description;
        Quantity = quantity;
        UnitAmount = unitPrice.Amount;
        Currency = unitPrice.Currency;
    }

    public int Id { get; private set; }
    public string Description { get; private set; } = default!;
    public int Quantity { get; private set; }
    public decimal UnitAmount { get; private set; }
    public string Currency { get; private set; } = default!;

    public Money UnitPrice => new(UnitAmount, Currency);
    public Money LineTotal => UnitPrice.Multiply(Quantity);
}
