namespace Shop.Application.Reconciliation;

public sealed class ReconciliationOptions
{
    public const string SectionName = "Reconciliation";

    /// <summary>
    /// Accepted difference between a transfer and the outstanding amount, as a percentage of the
    /// outstanding amount (design FR-7: 0.5 %).
    /// </summary>
    public decimal TolerancePercent { get; init; } = 0.5m;

    /// <summary>Upper bound of the tolerance in invoice currency (design FR-7: 5.00).</summary>
    public decimal MaxToleranceAmount { get; init; } = 5.00m;

    /// <summary>How often the statement import worker polls the bank API (design FR-4).</summary>
    public TimeSpan ImportInterval { get; init; } = TimeSpan.FromMinutes(15);

    public int ImportLookbackDays { get; init; } = 3;
}
