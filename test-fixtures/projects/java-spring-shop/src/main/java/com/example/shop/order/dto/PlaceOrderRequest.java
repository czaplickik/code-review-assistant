package com.example.shop.order.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.List;

public record PlaceOrderRequest(
        @NotEmpty @Size(max = 50) List<@Valid Line> lines,
        @Size(max = 32) String couponCode) {

    public record Line(@NotNull Long productId, @Min(1) @Max(100) int quantity) {
    }
}
