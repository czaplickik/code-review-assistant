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
 *    \
 *     +--> CANCELLED
 * </pre>
 */
public enum OrderStatus {
    CREATED,
    PAID,
    SHIPPED,
    DELIVERED,
    CANCELLED;

    private static final Map<OrderStatus, Set<OrderStatus>> ALLOWED = new EnumMap<>(OrderStatus.class);

    static {
        ALLOWED.put(CREATED, EnumSet.of(PAID, CANCELLED));
        ALLOWED.put(PAID, EnumSet.of(SHIPPED));
        ALLOWED.put(SHIPPED, EnumSet.of(DELIVERED));
        ALLOWED.put(DELIVERED, EnumSet.noneOf(OrderStatus.class));
        ALLOWED.put(CANCELLED, EnumSet.noneOf(OrderStatus.class));
    }

    public boolean canTransitionTo(OrderStatus target) {
        return ALLOWED.get(this).contains(target);
    }

    public boolean isTerminal() {
        return ALLOWED.get(this).isEmpty();
    }
}
