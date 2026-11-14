using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Shop.Infrastructure.Messaging;

namespace Shop.Infrastructure.Persistence.Configurations;

internal sealed class OutboxMessageConfiguration : IEntityTypeConfiguration<OutboxMessage>
{
    public void Configure(EntityTypeBuilder<OutboxMessage> builder)
    {
        builder.ToTable("OutboxMessages");
        builder.HasKey(m => m.Id);

        builder.Property(m => m.EventType).HasMaxLength(200).IsRequired();
        builder.Property(m => m.Payload).IsRequired();
        builder.HasIndex(m => m.ProcessedAt);
    }
}
