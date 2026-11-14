package com.example.shop.security;

import com.example.shop.order.repository.OrderRepository;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Component;

/** Ownership checks used from {@code @PreAuthorize} expressions as {@code @orderSecurity}. */
@Component("orderSecurity")
public class OrderSecurity {

    private final OrderRepository orderRepository;

    public OrderSecurity(OrderRepository orderRepository) {
        this.orderRepository = orderRepository;
    }

    public boolean isOwner(Long orderId, Authentication authentication) {
        if (orderId == null || authentication == null
                || !(authentication.getPrincipal() instanceof AuthenticatedUser user)) {
            return false;
        }
        return orderRepository.findOwnerIdById(orderId)
                .map(ownerId -> ownerId.equals(user.id()))
                .orElse(false);
    }
}
