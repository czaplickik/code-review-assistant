package com.example.shop.order.service;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;
import java.util.Map;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties("shop.orders")
public record OrderProperties(
        @NotBlank String currency,
        @NotNull BigDecimal volumeDiscountThreshold,
        @NotNull BigDecimal volumeDiscountPercent,
        Map<String, BigDecimal> discountCodes) {

    public OrderProperties {
        discountCodes = discountCodes == null ? Map.of() : Map.copyOf(discountCodes);
    }
}
