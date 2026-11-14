using Microsoft.EntityFrameworkCore;
using Shop.Application.Abstractions;
using Shop.Domain.Payments;

namespace Shop.Infrastructure.Persistence.Repositories;

internal sealed class PaymentRepository(ShopDbContext db) : IPaymentRepository
{
    public async Task<IReadOnlyList<Payment>> GetByInvoiceIdAsync(Guid invoiceId, CancellationToken cancellationToken) =>
        await db.Payments
            .AsNoTracking()
            .Where(p => p.InvoiceId == invoiceId)
            .OrderBy(p => p.ReceivedAt)
            .ToListAsync(cancellationToken);

    public async Task<IReadOnlyList<Payment>> GetCapturedByProviderReferencesAsync(
        IReadOnlyCollection<string> providerReferences, CancellationToken cancellationToken)
    {
        if (providerReferences.Count == 0)
        {
            return [];
        }

        return await db.Payments
            .Where(p => p.Status == PaymentStatus.Captured && providerReferences.Contains(p.ProviderReference!))
            .ToListAsync(cancellationToken);
    }

    public void Add(Payment payment) => db.Payments.Add(payment);
}
