using System.Text.Json;
using Shop.Application.Abstractions;
using Shop.Infrastructure.Persistence;

namespace Shop.Infrastructure.Messaging;

internal sealed class OutboxEventPublisher(ShopDbContext db, TimeProvider clock) : IEventPublisher
{
    private static readonly JsonSerializerOptions SerializerOptions = new(JsonSerializerDefaults.Web);

    public Task PublishAsync<TEvent>(TEvent integrationEvent, CancellationToken cancellationToken)
        where TEvent : IIntegrationEvent
    {
        cancellationToken.ThrowIfCancellationRequested();

        db.OutboxMessages.Add(new OutboxMessage
        {
            Id = Guid.NewGuid(),
            EventType = integrationEvent.EventType,
            EventVersion = integrationEvent.EventVersion,
            Payload = JsonSerializer.Serialize(integrationEvent, SerializerOptions),
            OccurredAt = clock.GetUtcNow(),
        });

        return Task.CompletedTask;
    }
}
