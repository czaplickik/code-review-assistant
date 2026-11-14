using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Shop.Domain.Invoices;

namespace Shop.Infrastructure.Persistence.Configurations;

internal sealed class InvoiceLineConfiguration : IEntityTypeConfiguration<InvoiceLine>
{
    public void Configure(EntityTypeBuilder<InvoiceLine> builder)
    {
        builder.ToTable("InvoiceLines");
        builder.HasKey(l => l.Id);

        builder.Property(l => l.Description).HasMaxLength(500).IsRequired();
        builder.Property(l => l.UnitAmount).HasPrecision(18, 2);
        builder.Property(l => l.Currency).HasMaxLength(3).IsFixedLength().IsRequired();

        builder.Ignore(l => l.UnitPrice);
        builder.Ignore(l => l.LineTotal);
    }
}
