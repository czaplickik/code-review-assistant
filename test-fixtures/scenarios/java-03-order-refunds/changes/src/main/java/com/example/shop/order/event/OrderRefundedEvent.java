package com.example.shop.order.event;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/** Published to {@code shop.order.refunded.v1} after a refund was completed at the gateway. */
public record OrderRefundedEvent(
        UUID eventId,
        int schemaVersion,
        Long orderId,
        Long refundId,
        String currency,
        BigDecimal amount,
        BigDecimal totalRefundedAmount,
        Instant occurredAt) {

    public static final int SCHEMA_VERSION = 1;
}
