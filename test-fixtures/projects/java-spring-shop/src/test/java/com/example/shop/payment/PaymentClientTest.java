package com.example.shop.payment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.ExpectedCount.times;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withBadRequest;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withServiceUnavailable;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import com.example.shop.common.Money;
import java.net.URI;
import java.time.Duration;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class PaymentClientTest {

    private static final String BASE_URL = "https://gateway.test";
    private static final PaymentClient.CaptureCommand COMMAND =
            new PaymentClient.CaptureCommand(301L, Money.of("45.08", "EUR"), "order-301-capture");

    private MockRestServiceServer server;
    private PaymentClient client;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder().baseUrl(BASE_URL);
        server = MockRestServiceServer.bindTo(builder).build();
        PaymentProperties properties = new PaymentProperties(URI.create(BASE_URL), "test-key",
                Duration.ofSeconds(1), Duration.ofSeconds(1),
                new PaymentProperties.Retry(3, Duration.ofMillis(1), 1.0));
        client = new PaymentClient(builder.build(), properties);
    }

    @Test
    void should_return_payment_reference_when_gateway_captures() {
        server.expect(once(), requestTo(BASE_URL + "/v1/captures"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("Idempotency-Key", "order-301-capture"))
                .andExpect(jsonPath("$.merchantReference").value("order-301"))
                .andExpect(jsonPath("$.amount").value(45.08))
                .andExpect(jsonPath("$.currency").value("EUR"))
                .andRespond(withSuccess("{\"id\":\"pay_123\",\"status\":\"CAPTURED\"}", MediaType.APPLICATION_JSON));

        PaymentClient.CaptureResult result = client.capture(COMMAND);

        assertThat(result.paymentReference()).isEqualTo("pay_123");
        server.verify();
    }

    @Test
    void should_retry_with_same_idempotency_key_when_gateway_returns_503() {
        server.expect(once(), requestTo(BASE_URL + "/v1/captures"))
                .andExpect(header("Idempotency-Key", "order-301-capture"))
                .andRespond(withServiceUnavailable());
        server.expect(once(), requestTo(BASE_URL + "/v1/captures"))
                .andExpect(header("Idempotency-Key", "order-301-capture"))
                .andRespond(withSuccess("{\"id\":\"pay_124\",\"status\":\"CAPTURED\"}", MediaType.APPLICATION_JSON));

        PaymentClient.CaptureResult result = client.capture(COMMAND);

        assertThat(result.paymentReference()).isEqualTo("pay_124");
        server.verify();
    }

    @Test
    void should_not_retry_when_gateway_rejects_request() {
        server.expect(once(), requestTo(BASE_URL + "/v1/captures")).andRespond(withBadRequest());

        assertThatThrownBy(() -> client.capture(COMMAND))
                .isInstanceOf(PaymentFailedException.class)
                .extracting("code").isEqualTo(PaymentFailedException.REJECTED);
        server.verify();
    }

    @Test
    void should_fail_with_gateway_unavailable_when_retries_exhausted() {
        server.expect(times(3), requestTo(BASE_URL + "/v1/captures")).andRespond(withServiceUnavailable());

        assertThatThrownBy(() -> client.capture(COMMAND))
                .isInstanceOf(PaymentFailedException.class)
                .extracting("code").isEqualTo(PaymentFailedException.GATEWAY_UNAVAILABLE);
        server.verify();
    }

    @Test
    void should_reject_when_gateway_declines_capture() {
        server.expect(once(), requestTo(BASE_URL + "/v1/captures"))
                .andRespond(withSuccess("{\"id\":\"pay_125\",\"status\":\"DECLINED\",\"failureCode\":\"insufficient_funds\"}",
                        MediaType.APPLICATION_JSON));

        assertThatThrownBy(() -> client.capture(COMMAND))
                .isInstanceOf(PaymentFailedException.class)
                .hasMessageContaining("insufficient_funds");
    }
}
