package com.example.shop.order.domain;

import java.util.EnumMap;
import java.util.EnumSet;
import java.util.Map;
import java.util.Set;

/**
 * Order lifecycle. Transitions not listed in {@link #ALLOWED} are rejected by {@link Order}.
 *
 * <pre>
 * CREATED --> PAID --> SHIPPED --> DELIVERED
 *    \         \          \           \
 *     \         +----------+-----------+--> PARTIALLY_REFUNDED --> REFUNDED
 *      +--> CANCELLED
 * </pre>
 */
public enum OrderStatus {
    CREATED,
    PAID,
    SHIPPED,
    DELIVERED,
    CANCELLED,
    PARTIALLY_REFUNDED,
    REFUNDED;

    private static final Map<OrderStatus, Set<OrderStatus>> ALLOWED = new EnumMap<>(OrderStatus.class);

    static {
        ALLOWED.put(CREATED, EnumSet.of(PAID, CANCELLED));
        ALLOWED.put(PAID, EnumSet.of(SHIPPED, PARTIALLY_REFUNDED, REFUNDED));
        ALLOWED.put(SHIPPED, EnumSet.of(DELIVERED, PARTIALLY_REFUNDED, REFUNDED));
        ALLOWED.put(DELIVERED, EnumSet.of(PARTIALLY_REFUNDED, REFUNDED));
        ALLOWED.put(CANCELLED, EnumSet.noneOf(OrderStatus.class));
        ALLOWED.put(PARTIALLY_REFUNDED, EnumSet.of(PARTIALLY_REFUNDED, REFUNDED));
        ALLOWED.put(REFUNDED, EnumSet.noneOf(OrderStatus.class));
    }

    public boolean canTransitionTo(OrderStatus target) {
        return ALLOWED.get(this).contains(target);
    }

    public boolean isTerminal() {
        return ALLOWED.get(this).isEmpty();
    }
}
