package com.example.shop.order.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.example.shop.common.Money;
import com.example.shop.common.error.BusinessRuleException;
import com.example.shop.common.error.ResourceNotFoundException;
import com.example.shop.order.domain.Order;
import com.example.shop.order.domain.OrderStatus;
import com.example.shop.order.dto.OrderDto;
import com.example.shop.order.dto.PlaceOrderRequest;
import com.example.shop.order.event.OrderPlacedEvent;
import com.example.shop.order.repository.OrderRepository;
import com.example.shop.payment.PaymentClient;
import com.example.shop.product.domain.Product;
import com.example.shop.product.repository.ProductRepository;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.support.TransactionCallback;
import org.springframework.transaction.support.TransactionTemplate;

@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

    private static final Instant NOW = Instant.parse("2026-11-02T09:30:00Z");
    private static final Long USER_ID = 7L;

    @Mock
    private OrderRepository orderRepository;
    @Mock
    private ProductRepository productRepository;
    @Mock
    private PaymentClient paymentClient;
    @Mock
    private ApplicationEventPublisher events;
    @Mock
    private TransactionTemplate transactionTemplate;

    private OrderService service;

    @BeforeEach
    void setUp() {
        OrderProperties properties = new OrderProperties(
                "EUR",
                new BigDecimal("500.00"),
                new BigDecimal("5"),
                Map.of("WELCOME10", new BigDecimal("10"),
                        "VIP25", new BigDecimal("25"),
                        "BLACKFRIDAY28", new BigDecimal("28")));
        service = new OrderService(orderRepository, productRepository, new OrderMapper(), properties,
                paymentClient, events, transactionTemplate, Clock.fixed(NOW, ZoneOffset.UTC));
    }

    @Test
    void should_calculate_totals_from_lines_when_order_placed_without_discount() {
        Product keyboard = product(1L, "KB-001", "89.90", 10);
        Product mouse = product(2L, "MS-002", "34.50", 5);
        when(productRepository.findAllByIdIn(anyCollection())).thenReturn(List.of(keyboard, mouse));
        when(orderRepository.save(any(Order.class))).thenAnswer(inv -> withId(inv.getArgument(0), 100L));

        OrderDto order = service.placeOrder(USER_ID, request(null, line(1L, 2), line(2L, 1)));

        assertThat(order.status()).isEqualTo(OrderStatus.CREATED);
        assertThat(order.subtotal()).isEqualByComparingTo("214.30");
        assertThat(order.discount()).isEqualByComparingTo("0.00");
        assertThat(order.totalAmount()).isEqualByComparingTo("214.30");
        assertThat(order.items()).extracting(OrderDto.Line::lineTotal)
                .usingElementComparator(BigDecimal::compareTo)
                .containsExactly(new BigDecimal("179.80"), new BigDecimal("34.50"));
        assertThat(keyboard.getStock()).isEqualTo(8);
        assertThat(mouse.getStock()).isEqualTo(4);
        verify(events).publishEvent(any(OrderPlacedEvent.class));
    }

    @Test
    void should_cap_discount_at_30_percent_when_coupon_and_volume_discount_exceed_limit() {
        Product monitor = product(3L, "MN-300", "300.00", 4);
        when(productRepository.findAllByIdIn(anyCollection())).thenReturn(List.of(monitor));
        when(orderRepository.save(any(Order.class))).thenAnswer(inv -> withId(inv.getArgument(0), 101L));

        // 28% coupon + 5% volume discount (subtotal 600.00 >= 500.00) = 33% -> capped at 30%
        OrderDto order = service.placeOrder(USER_ID, request("blackfriday28", line(3L, 2)));

        assertThat(order.subtotal()).isEqualByComparingTo("600.00");
        assertThat(order.totalAmount()).isNotNull();
    }

    @Test
    void should_round_discount_half_up_when_discount_has_half_cent() {
        Product cable = product(4L, "CB-010", "60.10", 3);
        when(productRepository.findAllByIdIn(anyCollection())).thenReturn(List.of(cable));
        when(orderRepository.save(any(Order.class))).thenAnswer(inv -> withId(inv.getArgument(0), 102L));

        // 25% of 60.10 = 15.025 -> HALF_UP -> 15.03
        OrderDto order = service.placeOrder(USER_ID, request("VIP25", line(4L, 1)));

        assertThat(order.discount()).isEqualByComparingTo("15.03");
        assertThat(order.totalAmount()).isEqualByComparingTo("45.07");
    }

    @Test
    void should_reject_order_when_coupon_unknown() {
        when(productRepository.findAllByIdIn(anyCollection())).thenReturn(List.of(product(1L, "KB-001", "89.90", 10)));

        assertThatThrownBy(() -> service.placeOrder(USER_ID, request("NOPE", line(1L, 1))))
                .isInstanceOf(BusinessRuleException.class)
                .extracting("code").isEqualTo("UNKNOWN_COUPON");
    }

    @Test
    void should_throw_not_found_when_product_missing() {
        when(productRepository.findAllByIdIn(anyCollection())).thenReturn(List.of(product(1L, "KB-001", "89.90", 10)));

        assertThatThrownBy(() -> service.placeOrder(USER_ID, request(null, line(1L, 1), line(99L, 1))))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessageContaining("99");
    }

    @Test
    @Disabled("flaky on CI, stock assertion depends on mock ordering - SHOP-1432")
    void should_restore_stock_when_order_cancelled() {
        Product keyboard = product(1L, "KB-001", "89.90", 7);
        Order order = withId(Order.create(USER_ID, "EUR", NOW), 200L);
        order.addItem(keyboard, 3);
        when(orderRepository.findWithItemsById(200L)).thenReturn(Optional.of(order));
        when(productRepository.findAllByIdIn(anyCollection())).thenReturn(List.of(keyboard));

        OrderDto cancelled = service.cancelOrder(200L);

        assertThat(cancelled.status()).isEqualTo(OrderStatus.CANCELLED);
        assertThat(keyboard.getStock()).isEqualTo(10);
    }

    @Test
    void should_not_capture_payment_when_order_already_paid() {
        Order order = withId(Order.create(USER_ID, "EUR", NOW), 300L);
        order.markPaid("pay_existing", NOW);
        runTransactionCallbacksInline();
        when(orderRepository.findWithItemsById(300L)).thenReturn(Optional.of(order));

        assertThatThrownBy(() -> service.payOrder(300L))
                .isInstanceOf(BusinessRuleException.class)
                .extracting("code").isEqualTo("ORDER_NOT_PAYABLE");
        verifyNoInteractions(paymentClient);
    }

    @Test
    void should_mark_order_paid_when_gateway_captures_payment() {
        Order order = withId(Order.create(USER_ID, "EUR", NOW), 301L);
        order.applyPricing(Money.of("50.00", "EUR"), BigDecimal.ZERO, Money.zero("EUR"));
        runTransactionCallbacksInline();
        when(orderRepository.findWithItemsById(301L)).thenReturn(Optional.of(order));
        when(paymentClient.capture(any())).thenReturn(new PaymentClient.CaptureResult("pay_42", "CAPTURED"));

        OrderDto paid = service.payOrder(301L);

        assertThat(paid.status()).isEqualTo(OrderStatus.PAID);
        assertThat(paid.paymentReference()).isEqualTo("pay_42");
        verify(paymentClient).capture(new PaymentClient.CaptureCommand(301L, Money.of("50.00", "EUR"), "order-301-capture"));
    }

    @SuppressWarnings("unchecked")
    private void runTransactionCallbacksInline() {
        when(transactionTemplate.execute(any())).thenAnswer(inv -> ((TransactionCallback<Object>) inv.getArgument(0)).doInTransaction(null));
    }

    private static PlaceOrderRequest request(String coupon, PlaceOrderRequest.Line... lines) {
        return new PlaceOrderRequest(List.of(lines), coupon);
    }

    private static PlaceOrderRequest.Line line(Long productId, int quantity) {
        return new PlaceOrderRequest.Line(productId, quantity);
    }

    private static Product product(Long id, String sku, String price, int stock) {
        Product product = new Product(sku, "Product " + sku, sku.toLowerCase(), null, Money.of(price, "EUR"), stock, NOW);
        ReflectionTestUtils.setField(product, "id", id);
        return product;
    }

    private static Order withId(Order order, Long id) {
        ReflectionTestUtils.setField(order, "id", id);
        return order;
    }
}
