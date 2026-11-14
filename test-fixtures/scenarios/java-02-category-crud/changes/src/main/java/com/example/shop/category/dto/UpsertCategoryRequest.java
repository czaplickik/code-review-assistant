package com.example.shop.category.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;

public record UpsertCategoryRequest(
        @NotBlank @Size(max = 120) String name,
        @Size(max = 1000) String description,
        @PositiveOrZero @Max(10_000) int position) {
}
