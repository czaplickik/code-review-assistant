using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Shop.Domain.Customers;
using Shop.Domain.Invoices;

namespace Shop.Infrastructure.Persistence.Configurations;

internal sealed class InvoiceConfiguration : IEntityTypeConfiguration<Invoice>
{
    public void Configure(EntityTypeBuilder<Invoice> builder)
    {
        builder.ToTable("Invoices");
        builder.HasKey(i => i.Id);

        builder.Property(i => i.Number).HasMaxLength(32).IsRequired();
        builder.HasIndex(i => i.Number).IsUnique();

        builder.Property(i => i.OrderNumber).HasMaxLength(64);
        builder.Property(i => i.Status).HasConversion<string>().HasMaxLength(20);
        builder.Property(i => i.Currency).HasMaxLength(3).IsFixedLength().IsRequired();
        builder.Property(i => i.TotalAmount).HasPrecision(18, 2);
        builder.Property(i => i.PaidAmount).HasPrecision(18, 2);
        builder.Property(i => i.RowVersion).IsRowVersion();

        builder.Ignore(i => i.Total);
        builder.Ignore(i => i.AmountPaid);
        builder.Ignore(i => i.Outstanding);

        builder.HasOne<Customer>()
            .WithMany()
            .HasForeignKey(i => i.CustomerId)
            .OnDelete(DeleteBehavior.Restrict);

        builder.HasMany(i => i.Lines)
            .WithOne()
            .HasForeignKey("InvoiceId")
            .OnDelete(DeleteBehavior.Cascade);
        builder.Navigation(i => i.Lines).UsePropertyAccessMode(PropertyAccessMode.Field);

        builder.HasIndex(i => new { i.Status, i.DueDate });
    }
}
