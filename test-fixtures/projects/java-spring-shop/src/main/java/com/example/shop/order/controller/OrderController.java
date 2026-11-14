package com.example.shop.order.controller;

import com.example.shop.order.dto.OrderDto;
import com.example.shop.order.dto.PlaceOrderRequest;
import com.example.shop.order.service.OrderService;
import com.example.shop.security.AuthenticatedUser;
import jakarta.validation.Valid;
import java.net.URI;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.web.PageableDefault;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    @PostMapping
    @PreAuthorize("hasRole('USER')")
    public ResponseEntity<OrderDto> placeOrder(@AuthenticationPrincipal AuthenticatedUser user,
                                               @Valid @RequestBody PlaceOrderRequest request) {
        OrderDto order = orderService.placeOrder(user.id(), request);
        return ResponseEntity.created(URI.create("/api/orders/" + order.id())).body(order);
    }

    @GetMapping
    @PreAuthorize("hasRole('USER')")
    public Page<OrderDto> myOrders(@AuthenticationPrincipal AuthenticatedUser user,
                                   @PageableDefault(size = 20) Pageable pageable) {
        return orderService.listOrders(user.id(), pageable);
    }

    @GetMapping("/{orderId}")
    @PreAuthorize("hasAnyRole('SUPPORT', 'ADMIN') or @orderSecurity.isOwner(#orderId, authentication)")
    public OrderDto getOrder(@PathVariable Long orderId) {
        return orderService.getOrder(orderId);
    }

    @PostMapping("/{orderId}/payment")
    @PreAuthorize("@orderSecurity.isOwner(#orderId, authentication)")
    public OrderDto pay(@PathVariable Long orderId) {
        return orderService.payOrder(orderId);
    }

    @PostMapping("/{orderId}/cancellation")
    @PreAuthorize("hasRole('SUPPORT') or @orderSecurity.isOwner(#orderId, authentication)")
    public OrderDto cancel(@PathVariable Long orderId) {
        return orderService.cancelOrder(orderId);
    }
}
