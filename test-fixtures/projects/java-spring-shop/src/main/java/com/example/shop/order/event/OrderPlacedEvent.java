package com.example.shop.order.event;

import com.example.shop.order.domain.Order;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * Published to {@code shop.order.placed.v1}. Consumers: fulfilment, analytics, e-mail.
 * Only additive optional fields are allowed within version 1 (see conventions §6).
 */
public record OrderPlacedEvent(
        UUID eventId,
        int schemaVersion,
        Long orderId,
        Long userId,
        String currency,
        BigDecimal subtotalAmount,
        BigDecimal discountAmount,
        BigDecimal totalAmount,
        List<Line> lines,
        Instant occurredAt) {

    public static final int SCHEMA_VERSION = 1;

    public record Line(Long productId, int quantity, BigDecimal unitPrice) {
    }

    public static OrderPlacedEvent from(Order order, Instant occurredAt) {
        return new OrderPlacedEvent(
                UUID.randomUUID(),
                SCHEMA_VERSION,
                order.getId(),
                order.getUserId(),
                order.getCurrency(),
                order.getSubtotal().amount(),
                order.getDiscount().amount(),
                order.getTotal().amount(),
                order.getItems().stream()
                        .map(item -> new Line(item.getProductId(), item.getQuantity(), item.getUnitPrice().amount()))
                        .toList(),
                occurredAt);
    }
}
