package com.example.shop.order.dto;

import com.example.shop.order.domain.OrderStatus;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

public record OrderDto(
        Long id,
        OrderStatus status,
        String currency,
        List<Line> items,
        BigDecimal subtotal,
        BigDecimal discountPercent,
        BigDecimal discount,
        BigDecimal totalAmount,
        BigDecimal refundedAmount,
        String paymentReference,
        Instant createdAt) {

    public record Line(Long productId, String productName, BigDecimal unitPrice, int quantity, BigDecimal lineTotal) {
    }
}
