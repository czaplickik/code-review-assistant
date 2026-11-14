using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Shop.Domain.Customers;

namespace Shop.Infrastructure.Persistence.Configurations;

internal sealed class CustomerNoteConfiguration : IEntityTypeConfiguration<CustomerNote>
{
    public void Configure(EntityTypeBuilder<CustomerNote> builder)
    {
        builder.ToTable("CustomerNotes");
        builder.HasKey(n => n.Id);

        builder.Property(n => n.Body).HasMaxLength(CustomerNote.MaxBodyLength).IsRequired();
        builder.Property(n => n.AuthorId).HasMaxLength(64).IsRequired();

        builder.HasOne<Customer>()
            .WithMany()
            .HasForeignKey(n => n.CustomerId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasIndex(n => new { n.CustomerId, n.CreatedAt });
    }
}
