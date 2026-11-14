using Shop.Domain.Payments;

namespace Shop.Application.Abstractions;

public interface IPaymentRepository
{
    Task<IReadOnlyList<Payment>> GetByInvoiceIdAsync(Guid invoiceId, CancellationToken cancellationToken);

    /// <summary>
    /// Loads captured (not yet settled) payments for the given gateway references in a single query.
    /// </summary>
    Task<IReadOnlyList<Payment>> GetCapturedByProviderReferencesAsync(
        IReadOnlyCollection<string> providerReferences, CancellationToken cancellationToken);

    void Add(Payment payment);
}
