namespace Shop.Application.Abstractions;

/// <summary>Marker for versioned integration events published to other services.</summary>
public interface IIntegrationEvent
{
    string EventType { get; }

    int EventVersion { get; }
}

public interface IEventPublisher
{
    /// <summary>
    /// Writes the event to the transactional outbox. The event is persisted by the next
    /// <see cref="IUnitOfWork.SaveChangesAsync"/> and dispatched by the outbox relay.
    /// </summary>
    Task PublishAsync<TEvent>(TEvent integrationEvent, CancellationToken cancellationToken)
        where TEvent : IIntegrationEvent;
}
