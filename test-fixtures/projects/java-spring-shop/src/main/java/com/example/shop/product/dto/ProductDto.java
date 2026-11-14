package com.example.shop.product.dto;

import java.math.BigDecimal;

public record ProductDto(
        Long id,
        String sku,
        String name,
        String slug,
        String description,
        BigDecimal price,
        String currency,
        int stock) {
}
