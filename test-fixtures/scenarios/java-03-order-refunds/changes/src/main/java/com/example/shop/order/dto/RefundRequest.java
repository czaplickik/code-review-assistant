package com.example.shop.order.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.List;

public record RefundRequest(
        @NotBlank @Size(max = 500) String reason,
        @Size(max = 50) List<@Valid Line> lines) {

    public record Line(@NotNull Long productId, @Min(1) int quantity) {
    }
}
