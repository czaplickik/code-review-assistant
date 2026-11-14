package com.example.shop.order.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

import com.example.shop.common.Money;
import com.example.shop.order.domain.Order;
import com.example.shop.order.domain.OrderStatus;
import com.example.shop.order.domain.Refund;
import com.example.shop.order.dto.RefundRequest;
import com.example.shop.order.repository.OrderRepository;
import com.example.shop.order.repository.RefundRepository;
import com.example.shop.payment.PaymentClient;
import com.example.shop.product.domain.Product;
import com.example.shop.product.repository.ProductRepository;
import com.example.shop.security.AuthenticatedUser;
import com.example.shop.user.domain.Role;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Spy;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class RefundServiceTest {

    private static final Instant NOW = Instant.parse("2026-11-12T10:00:00Z");
    private static final AuthenticatedUser ALICE = new AuthenticatedUser(7L, "alice@example.com", Role.USER);

    @Mock
    private OrderRepository orderRepository;
    @Mock
    private RefundRepository refundRepository;
    @Mock
    private ProductRepository productRepository;
    @Mock
    private PaymentClient paymentClient;
    @Mock
    private ApplicationEventPublisher events;
    @Spy
    private Clock clock = Clock.fixed(NOW, ZoneOffset.UTC);

    @InjectMocks
    private RefundService refundService;

    @Test
    void should_refund_whole_order_when_no_lines_given() {
        Order order = paidOrder(NOW.minus(3, ChronoUnit.DAYS));
        when(orderRepository.findWithItemsById(500L)).thenReturn(Optional.of(order));
        when(refundRepository.findByOrderIdOrderByCreatedAtDesc(500L)).thenReturn(List.of());
        when(paymentClient.refund(any())).thenReturn(new PaymentClient.RefundResult("rf_1", "SUCCEEDED"));
        when(refundRepository.save(any(Refund.class))).thenAnswer(inv -> inv.getArgument(0));

        Refund refund = refundService.refund(500L, new RefundRequest("Changed my mind", List.of()), ALICE);

        assertThat(refund.getAmount()).isEqualTo(Money.of("180.00", "EUR"));
        assertThat(order.getStatus()).isEqualTo(OrderStatus.REFUNDED);
    }

    @Test
    void should_reject_refund_when_window_expired() {
        Order order = paidOrder(NOW.minus(31, ChronoUnit.DAYS));
        when(orderRepository.findWithItemsById(500L)).thenReturn(Optional.of(order));

        assertThatThrownBy(() -> refundService.refund(500L, new RefundRequest("Too late", List.of()), ALICE))
                .isInstanceOf(RuntimeException.class);
    }

    /** One line, 2 x 100.00, 10% coupon -> total 180.00. */
    private static Order paidOrder(Instant paidAt) {
        Product product = new Product("HP-100", "Headphones", "headphones", null, Money.of("100.00", "EUR"), 5, NOW);
        ReflectionTestUtils.setField(product, "id", 1L);
        Order order = Order.create(7L, "EUR", paidAt);
        ReflectionTestUtils.setField(order, "id", 500L);
        order.addItem(product, 2);
        order.applyPricing(Money.of("200.00", "EUR"), new BigDecimal("10"), Money.of("20.00", "EUR"));
        order.markPaid("pay_500", paidAt);
        return order;
    }
}
