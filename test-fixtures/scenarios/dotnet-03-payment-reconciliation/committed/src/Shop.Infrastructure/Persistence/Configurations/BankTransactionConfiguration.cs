using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Shop.Domain.Payments;

namespace Shop.Infrastructure.Persistence.Configurations;

internal sealed class BankTransactionConfiguration : IEntityTypeConfiguration<BankTransaction>
{
    public void Configure(EntityTypeBuilder<BankTransaction> builder)
    {
        builder.ToTable("BankTransactions");
        builder.HasKey(t => t.Id);

        builder.Property(t => t.BankReference).HasMaxLength(64).IsRequired();
        builder.HasIndex(t => t.BankReference).IsUnique();

        builder.Property(t => t.Amount).HasPrecision(18, 2);
        builder.Property(t => t.Currency).HasMaxLength(3).IsFixedLength().IsRequired();
        builder.Property(t => t.RemittanceInformation).HasMaxLength(500);
        builder.Property(t => t.CounterpartyIban).HasMaxLength(34);
        builder.Property(t => t.Status).HasConversion<string>().HasMaxLength(20);
        builder.HasIndex(t => t.Status);

        builder.Ignore(t => t.Value);
    }
}
