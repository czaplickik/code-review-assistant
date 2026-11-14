namespace Shop.Infrastructure.Messaging;

/// <summary>
/// Row in <c>billing.OutboxMessages</c>. Written in the same transaction as the business change and
/// dispatched to the message broker by the outbox relay (Shop.Outbox.Relay, separate deployment).
/// </summary>
public sealed class OutboxMessage
{
    public Guid Id { get; init; }
    public string EventType { get; init; } = default!;
    public int EventVersion { get; init; }
    public string Payload { get; init; } = default!;
    public DateTimeOffset OccurredAt { get; init; }
    public DateTimeOffset? ProcessedAt { get; set; }
}
