package com.example.shop.order.event;

import com.example.shop.order.domain.OrderStatus;
import java.time.Instant;
import java.util.UUID;

/**
 * Published to {@code shop.order.status-changed.v1}. Statuses are sent as strings so that
 * consumers do not break when a new status is added (they must ignore unknown values).
 */
public record OrderStatusChangedEvent(
        UUID eventId,
        int schemaVersion,
        Long orderId,
        String fromStatus,
        String toStatus,
        Instant occurredAt) {

    public static final int SCHEMA_VERSION = 1;

    public static OrderStatusChangedEvent of(Long orderId, OrderStatus from, OrderStatus to, Instant occurredAt) {
        return new OrderStatusChangedEvent(UUID.randomUUID(), SCHEMA_VERSION, orderId, from.name(), to.name(), occurredAt);
    }
}
