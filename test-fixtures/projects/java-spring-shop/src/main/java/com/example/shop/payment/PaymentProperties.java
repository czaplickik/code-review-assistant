package com.example.shop.payment;

import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.net.URI;
import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties("shop.payment")
public record PaymentProperties(
        @NotNull URI baseUrl,
        @NotBlank String apiKey,
        @NotNull Duration connectTimeout,
        @NotNull Duration readTimeout,
        @Valid @NotNull Retry retry) {

    public record Retry(
            @Min(1) @Max(5) int maxAttempts,
            @NotNull Duration initialBackoff,
            @DecimalMin("1.0") double multiplier) {
    }
}
