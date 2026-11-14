using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Shop.Domain.Invoices;
using Shop.Domain.Payments;

namespace Shop.Infrastructure.Persistence.Configurations;

internal sealed class PaymentConfiguration : IEntityTypeConfiguration<Payment>
{
    public void Configure(EntityTypeBuilder<Payment> builder)
    {
        builder.ToTable("Payments");
        builder.HasKey(p => p.Id);

        builder.Property(p => p.Amount).HasPrecision(18, 2);
        builder.Property(p => p.FeeAmount).HasPrecision(18, 2);
        builder.Property(p => p.Currency).HasMaxLength(3).IsFixedLength().IsRequired();
        builder.Property(p => p.Status).HasConversion<string>().HasMaxLength(20);
        builder.Property(p => p.ProviderReference).HasMaxLength(64);

        builder.Ignore(p => p.Value);

        builder.HasOne<Invoice>()
            .WithMany()
            .HasForeignKey(p => p.InvoiceId)
            .OnDelete(DeleteBehavior.Restrict);

        builder.HasIndex(p => p.ProviderReference).HasFilter("[ProviderReference] IS NOT NULL");
    }
}
