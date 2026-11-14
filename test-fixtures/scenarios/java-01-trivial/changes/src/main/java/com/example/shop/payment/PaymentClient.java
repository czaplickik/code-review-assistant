package com.example.shop.payment;

import com.example.shop.common.Money;
import java.math.BigDecimal;
import java.time.Duration;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.retry.support.RetryTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

/**
 * Client for the external payment gateway. Timeouts are configured on the underlying
 * {@link RestClient} (see {@link PaymentClientConfig}); retries are handled here.
 */
@Component
public class PaymentClient {

    private static final Logger log = LoggerFactory.getLogger(PaymentClient.class);
    private static final Duration MAX_BACKOFF = Duration.ofSeconds(2);
    private static final String STATUS_CAPTURED = "CAPTURED";

    public record CaptureCommand(Long orderId, Money amount, String idempotencyKey) {
    }

    public record CaptureResult(String paymentReference, String status) {
    }

    record GatewayCaptureRequest(String merchantReference, BigDecimal amount, String currency) {
    }

    record GatewayCaptureResponse(String id, String status, String failureCode) {
    }

    private final RestClient restClient;
    private final RetryTemplate retryTemplate;

    public PaymentClient(@Qualifier("paymentRestClient") RestClient restClient, PaymentProperties properties) {
        this.restClient = restClient;
        this.retryTemplate = RetryTemplate.builder()
                .maxAttempts(properties.retry().maxAttempts())
                .exponentialBackoff(properties.retry().initialBackoff(), properties.retry().multiplier(), MAX_BACKOFF)
                // only transport errors and 5xx; a 4xx is a definitive answer from the gateway
                .retryOn(List.of(ResourceAccessException.class, HttpServerErrorException.class))
                .build();
    }

    public CaptureResult capture(CaptureCommand command) {
        // Retries are only safe because the gateway deduplicates on the Idempotency-Key header.
        GatewayCaptureResponse response = retryTemplate.execute(context -> {
            if (context.getRetryCount() > 0) {
                log.warn("Retrying payment capture orderId={} attempt={}", command.orderId(), context.getRetryCount() + 1);
            }
            return restClient.post()
                    .uri("/v1/captures")
                    .header("Idempotency-Key", command.idempotencyKey())
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(new GatewayCaptureRequest(
                            "order-" + command.orderId(),
                            command.amount().amount(),
                            command.amount().currencyCode()))
                    .retrieve()
                    .onStatus(HttpStatusCode::is4xxClientError, (request, gatewayResponse) -> {
                        throw new PaymentFailedException(PaymentFailedException.REJECTED,
                                "Payment rejected by gateway status=" + gatewayResponse.getStatusCode().value());
                    })
                    .body(GatewayCaptureResponse.class);
        }, context -> {
            if (context.getLastThrowable() instanceof PaymentFailedException rejected) {
                throw rejected; // definitive 4xx answer, not an availability problem
            }
            log.error("Payment gateway unavailable orderId={} attempts={}", command.orderId(), context.getRetryCount(),
                    context.getLastThrowable());
            throw new PaymentFailedException(PaymentFailedException.GATEWAY_UNAVAILABLE,
                    "Payment gateway unavailable, please retry later");
        });

        if (response == null || !STATUS_CAPTURED.equals(response.status())) {
            String failureCode = response == null ? "EMPTY_RESPONSE" : response.failureCode();
            throw new PaymentFailedException(PaymentFailedException.REJECTED,
                    "Payment not captured for order " + command.orderId() + " failureCode=" + failureCode);
        }
        return new CaptureResult(response.id(), response.status());
    }
}
