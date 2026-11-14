package com.example.shop.common;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Currency;
import java.util.Objects;

/**
 * Immutable monetary amount with a fixed scale of two decimal places.
 * <p>
 * All arithmetic rounds HALF_UP, which is what the payment gateway uses for captures and
 * refunds, so our amounts match the gateway's to the cent. Two {@code Money}
 * values can only be combined or compared when they share the same currency.
 */
public final class Money implements Comparable<Money> {

    public static final int SCALE = 2;
    public static final RoundingMode ROUNDING = RoundingMode.HALF_UP;

    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);

    private final BigDecimal amount;
    private final Currency currency;

    private Money(BigDecimal amount, Currency currency) {
        this.amount = Objects.requireNonNull(amount, "amount").setScale(SCALE, ROUNDING);
        this.currency = Objects.requireNonNull(currency, "currency");
    }

    public static Money of(BigDecimal amount, String currencyCode) {
        return new Money(amount, Currency.getInstance(currencyCode));
    }

    public static Money of(String amount, String currencyCode) {
        return of(new BigDecimal(amount), currencyCode);
    }

    public static Money zero(String currencyCode) {
        return of(BigDecimal.ZERO, currencyCode);
    }

    public Money plus(Money other) {
        requireSameCurrency(other);
        return new Money(amount.add(other.amount), currency);
    }

    public Money minus(Money other) {
        requireSameCurrency(other);
        return new Money(amount.subtract(other.amount), currency);
    }

    public Money times(int quantity) {
        return new Money(amount.multiply(BigDecimal.valueOf(quantity)), currency);
    }

    /**
     * Returns {@code percent} percent of this amount, e.g. {@code percentage(15)} of 200.00 is 30.00.
     */
    public Money percentage(BigDecimal percent) {
        return new Money(amount.multiply(percent).divide(HUNDRED, SCALE, ROUNDING), currency);
    }

    /**
     * Returns {@code numerator / denominator} of this amount, e.g. the share of an order discount
     * that belongs to a subset of lines. Multiplies first and divides last to keep precision.
     */
    public Money proportion(long numerator, long denominator) {
        if (denominator <= 0) {
            throw new IllegalArgumentException("denominator must be positive");
        }
        return new Money(amount.multiply(BigDecimal.valueOf(numerator))
                .divide(BigDecimal.valueOf(denominator), SCALE, ROUNDING), currency);
    }

    public Money proportion(Money numerator, Money denominator) {
        requireSameCurrency(numerator);
        requireSameCurrency(denominator);
        if (denominator.isZero()) {
            throw new IllegalArgumentException("denominator must not be zero");
        }
        return new Money(amount.multiply(numerator.amount).divide(denominator.amount, SCALE, ROUNDING), currency);
    }

    public Money min(Money other) {
        requireSameCurrency(other);
        return compareTo(other) <= 0 ? this : other;
    }

    public boolean isZero() {
        return amount.signum() == 0;
    }

    public boolean isNegative() {
        return amount.signum() < 0;
    }

    public boolean isGreaterThan(Money other) {
        return compareTo(other) > 0;
    }

    public boolean isLessThan(Money other) {
        return compareTo(other) < 0;
    }

    public BigDecimal amount() {
        return amount;
    }

    public String currencyCode() {
        return currency.getCurrencyCode();
    }

    @Override
    public int compareTo(Money other) {
        requireSameCurrency(other);
        return amount.compareTo(other.amount);
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) {
            return true;
        }
        if (!(o instanceof Money other)) {
            return false;
        }
        return amount.equals(other.amount) && currency.equals(other.currency);
    }

    @Override
    public int hashCode() {
        return Objects.hash(amount, currency);
    }

    @Override
    public String toString() {
        return amount.toPlainString() + " " + currency.getCurrencyCode();
    }

    private void requireSameCurrency(Money other) {
        if (!currency.equals(other.currency)) {
            throw new IllegalArgumentException("Currency mismatch: " + currency + " vs " + other.currency);
        }
    }
}
