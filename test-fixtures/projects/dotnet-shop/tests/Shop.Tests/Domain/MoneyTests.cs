using Shop.Domain.Common;
using Shop.Domain.Exceptions;

namespace Shop.Tests.Domain;

public sealed class MoneyTests
{
    [Theory]
    [InlineData(0.125, 0.12)]
    [InlineData(0.135, 0.14)]
    [InlineData(2.675, 2.68)]
    [InlineData(-0.125, -0.12)]
    public void Of_MidpointValue_UsesBankersRounding(decimal input, decimal expected)
    {
        Money.Of(input, "EUR").Amount.Should().Be(expected);
    }

    [Fact]
    public void Add_DifferentCurrencies_ThrowsCurrencyMismatch()
    {
        var act = () => Money.Of(10m, "EUR") + Money.Of(10m, "USD");

        act.Should().Throw<CurrencyMismatchException>();
    }

    [Fact]
    public void Allocate_ThreeParts_DistributesRemainderToFirstParts()
    {
        var parts = Money.Of(100m, "EUR").Allocate(3);

        parts.Select(p => p.Amount).Should().Equal(33.34m, 33.33m, 33.33m);
        parts.Aggregate(Money.Zero("EUR"), (sum, p) => sum + p).Should().Be(Money.Of(100m, "EUR"));
    }

    [Fact]
    public void Percentage_GatewayFee_RoundsToCents()
    {
        Money.Of(10.25m, "EUR").Percentage(2.9m).Should().Be(Money.Of(0.30m, "EUR"));
    }

    [Theory]
    [InlineData("")]
    [InlineData("EURO")]
    [InlineData("  ")]
    public void Constructor_InvalidCurrency_ThrowsInvalidCurrency(string currency)
    {
        var act = () => new Money(1m, currency);

        act.Should().Throw<InvalidCurrencyException>();
    }

    [Fact]
    public void Constructor_LowerCaseCurrency_NormalizesToUpperCase()
    {
        new Money(1m, "pln").Currency.Should().Be("PLN");
    }
}
