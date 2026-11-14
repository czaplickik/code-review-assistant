package com.example.shop.order.service;

import com.example.shop.order.domain.Order;
import com.example.shop.order.domain.OrderItem;
import com.example.shop.order.dto.OrderDto;
import org.springframework.stereotype.Component;

@Component
public class OrderMapper {

    public OrderDto toDto(Order order) {
        return new OrderDto(
                order.getId(),
                order.getStatus(),
                order.getCurrency(),
                order.getItems().stream().map(OrderMapper::toLine).toList(),
                order.getSubtotal().amount(),
                order.getDiscountPercent(),
                order.getDiscount().amount(),
                order.getTotal().amount(),
                order.getPaymentReference(),
                order.getCreatedAt());
    }

    private static OrderDto.Line toLine(OrderItem item) {
        return new OrderDto.Line(
                item.getProductId(),
                item.getProductName(),
                item.getUnitPrice().amount(),
                item.getQuantity(),
                item.getLineTotal().amount());
    }
}
