using System.Globalization;
using Shop.Domain.Exceptions;

namespace Shop.Domain.Common;

/// <summary>
/// Immutable monetery amount in a single ISO 4217 currency.
/// </summary>
/// <remarks>
/// Results of multiplication, percentage and allocation are rounded to <see cref="DecimalPlaces"/>
/// using banker's rounding (<see cref="MidpointRounding.ToEven"/>). The ledger and the payment
/// gateway settlement files round the same way, so changing this breaks reconciliation.
/// Addition and subtraction never round: operands are already rounded.
/// </remarks>
public readonly record struct Money : IComparable<Money>
{
    public const int DecimalPlaces = 2;
    private const MidpointRounding Rounding = MidpointRounding.ToEven;

    public decimal Amount { get; }
    public string Currency { get; }

    public Money(decimal amount, string currency)
    {
        if (string.IsNullOrWhiteSpace(currency) || currency.Length != 3)
        {
            throw new InvalidCurrencyException(currency);
        }

        Amount = amount;
        Currency = currency.ToUpperInvariant();
    }

    public static Money Zero(string currency) => new(0m, currency);

    /// <summary>Creates an amount rounded to <see cref="DecimalPlaces"/>.</summary>
    public static Money Of(decimal amount, string currency) =>
        new(decimal.Round(amount, DecimalPlaces, Rounding), currency);

    public bool IsZero => Amount == 0m;
    public bool IsNegative => Amount < 0m;

    public Money Add(Money other)
    {
        EnsureSameCurrency(other);
        return new Money(Amount + other.Amount, Currency);
    }

    public Money Subtract(Money other)
    {
        EnsureSameCurrency(other);
        return new Money(Amount - other.Amount, Currency);
    }

    public Money Multiply(decimal factor) => Of(Amount * factor, Currency);

    /// <summary>Returns <paramref name="percent"/>% of this amount, e.g. <c>Percentage(2.9m)</c>.</summary>
    public Money Percentage(decimal percent) => Of(Amount * percent / 100m, Currency);

    public Money Abs() => new(Math.Abs(Amount), Currency);

    /// <summary>
    /// Splits the amount into <paramref name="parts"/> amounts that sum up exactly to the original.
    /// The remainder cents are distribued to the first parts.
    /// </summary>
    public IReadOnlyList<Money> Allocate(int parts)
    {
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(parts);

        var unit = 1m / (decimal)Math.Pow(10, DecimalPlaces);
        var baseShare = decimal.Floor(Amount / parts / unit) * unit;
        var remainder = Amount - baseShare * parts;

        var result = new Money[parts];
        for (var i = 0; i < parts; i++)
        {
            var share = baseShare;
            if (remainder > 0m)
            {
                share += unit;
                remainder -= unit;
            }

            result[i] = new Money(share, Currency);
        }

        return result;
    }

    public int CompareTo(Money other)
    {
        EnsureSameCurrency(other);
        return Amount.CompareTo(other.Amount);
    }

    public static Money operator +(Money left, Money right) => left.Add(right);
    public static Money operator -(Money left, Money right) => left.Subtract(right);
    public static bool operator <(Money left, Money right) => left.CompareTo(right) < 0;
    public static bool operator >(Money left, Money right) => left.CompareTo(right) > 0;
    public static bool operator <=(Money left, Money right) => left.CompareTo(right) <= 0;
    public static bool operator >=(Money left, Money right) => left.CompareTo(right) >= 0;

    public override string ToString() =>
        $"{Amount.ToString("0.00", CultureInfo.InvariantCulture)} {Currency}";

    private void EnsureSameCurrency(Money other)
    {
        if (!string.Equals(Currency, other.Currency, StringComparison.Ordinal))
        {
            throw new CurrencyMismatchException(Currency, other.Currency);
        }
    }
}
