package com.example.shop.order.service;

import com.example.shop.common.Money;
import com.example.shop.common.error.BusinessRuleException;
import com.example.shop.common.error.ResourceNotFoundException;
import com.example.shop.order.domain.Order;
import com.example.shop.order.domain.OrderItem;
import com.example.shop.order.domain.OrderStatus;
import com.example.shop.order.dto.OrderDto;
import com.example.shop.order.dto.PlaceOrderRequest;
import com.example.shop.order.event.OrderPlacedEvent;
import com.example.shop.order.event.OrderStatusChangedEvent;
import com.example.shop.order.repository.OrderRepository;
import com.example.shop.payment.PaymentClient;
import com.example.shop.product.domain.Product;
import com.example.shop.product.repository.ProductRepository;
import java.math.BigDecimal;
import java.time.Clock;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class OrderService {

    private static final Logger log = LoggerFactory.getLogger(OrderService.class);

    /** BR-7: the combined discount (coupon + volume) never exceeds 30% of the subtotal. */
    static final BigDecimal MAX_DISCOUNT_PERCENT = new BigDecimal("30");

    private final OrderRepository orderRepository;
    private final ProductRepository productRepository;
    private final OrderMapper orderMapper;
    private final OrderProperties properties;
    private final PaymentClient paymentClient;
    private final ApplicationEventPublisher events;
    private final TransactionTemplate transactionTemplate;
    private final Clock clock;

    public OrderService(OrderRepository orderRepository,
                        ProductRepository productRepository,
                        OrderMapper orderMapper,
                        OrderProperties properties,
                        PaymentClient paymentClient,
                        ApplicationEventPublisher events,
                        TransactionTemplate transactionTemplate,
                        Clock clock) {
        this.orderRepository = orderRepository;
        this.productRepository = productRepository;
        this.orderMapper = orderMapper;
        this.properties = properties;
        this.paymentClient = paymentClient;
        this.events = events;
        this.transactionTemplate = transactionTemplate;
        this.clock = clock;
    }

    @Transactional
    public OrderDto placeOrder(Long userId, PlaceOrderRequest request) {
        Map<Long, Integer> quantities = request.lines().stream()
                .collect(Collectors.toMap(PlaceOrderRequest.Line::productId, PlaceOrderRequest.Line::quantity,
                        Integer::sum, LinkedHashMap::new));
        Map<Long, Product> products = productRepository.findAllByIdIn(quantities.keySet()).stream()
                .collect(Collectors.toMap(Product::getId, Function.identity()));
        if (products.size() != quantities.size()) {
            Set<Long> missing = quantities.keySet().stream()
                    .filter(id -> !products.containsKey(id))
                    .collect(Collectors.toCollection(TreeSet::new));
            throw new ResourceNotFoundException("Product", missing);
        }

        Order order = Order.create(userId, properties.currency(), clock.instant());
        quantities.forEach((productId, quantity) -> {
            Product product = products.get(productId);
            if (!product.isActive()) {
                throw new BusinessRuleException("PRODUCT_INACTIVE", "Product " + product.getSku() + " is no longer sold");
            }
            product.reserveStock(quantity);
            order.addItem(product, quantity);
        });

        Money subtotal = calcSubtotal(order);
        BigDecimal discountPercent = resolveDiscountPercent(subtotal, request.couponCode());
        order.applyPricing(subtotal, discountPercent, subtotal.percentage(discountPercent));

        Order saved = orderRepository.save(order);
        events.publishEvent(OrderPlacedEvent.from(saved, clock.instant()));
        log.info("Order placed orderId={} userId={} total={} discountPercent={}",
                saved.getId(), userId, saved.getTotal(), discountPercent);
        return orderMapper.toDto(saved);
    }

    @Transactional(readOnly = true)
    public OrderDto getOrder(Long orderId) {
        return orderMapper.toDto(loadWithItems(orderId));
    }

    @Transactional(readOnly = true)
    public Page<OrderDto> listOrders(Long userId, Pageable pageable) {
        return orderRepository.findByUserIdOrderByCreatedAtDesc(userId, pageable).map(orderMapper::toDto);
    }

    /**
     * Captures the payment for a CREATED order. Deliberately not a single transaction: we never
     * keep a DB transaction (and the order row lock) open while waiting for the gateway.
     * The capture is idempotent on the gateway side, so a retry after a crash between the
     * two transactions is safe.
     */
    public OrderDto payOrder(Long orderId) {
        Order order = transactionTemplate.execute(status -> {
            Order loaded = loadWithItems(orderId);
            if (loaded.getStatus() != OrderStatus.CREATED) {
                throw new BusinessRuleException("ORDER_NOT_PAYABLE",
                        "Order " + orderId + " cannot be paid in status " + loaded.getStatus());
            }
            return loaded;
        });

        PaymentClient.CaptureResult result = paymentClient.capture(
                new PaymentClient.CaptureCommand(order.getId(), order.getTotal(), "order-" + order.getId() + "-capture"));

        OrderDto paid = transactionTemplate.execute(status -> {
            Order current = loadWithItems(orderId);
            OrderStatus previous = current.getStatus();
            current.markPaid(result.paymentReference(), clock.instant());
            events.publishEvent(OrderStatusChangedEvent.of(current.getId(), previous, current.getStatus(), clock.instant()));
            return orderMapper.toDto(current);
        });
        log.info("Order payment captured orderId={} paymentReference={}", orderId, result.paymentReference());
        return paid;
    }

    @Transactional
    public OrderDto cancelOrder(Long orderId) {
        Order order = loadWithItems(orderId);
        OrderStatus previous = order.getStatus();
        order.cancel(clock.instant());

        List<Long> productIds = order.getItems().stream().map(OrderItem::getProductId).toList();
        Map<Long, Product> products = productRepository.findAllByIdIn(productIds).stream()
                .collect(Collectors.toMap(Product::getId, Function.identity()));
        for (OrderItem item : order.getItems()) {
            Product product = products.get(item.getProductId());
            if (product != null) {
                product.releaseStock(item.getQuantity());
            }
        }

        events.publishEvent(OrderStatusChangedEvent.of(order.getId(), previous, order.getStatus(), clock.instant()));
        log.info("Order cancelled orderId={} previousStatus={}", orderId, previous);
        return orderMapper.toDto(order);
    }

    BigDecimal resolveDiscountPercent(Money subtotal, String couponCode) {
        BigDecimal percent = BigDecimal.ZERO;
        if (couponCode != null && !couponCode.isBlank()) {
            BigDecimal couponPercent = properties.discountCodes().get(couponCode.trim().toUpperCase(Locale.ROOT));
            if (couponPercent == null) {
                throw new BusinessRuleException("UNKNOWN_COUPON", "Coupon " + couponCode + " is not valid");
            }
            percent = percent.add(couponPercent);
        }
        Money threshold = Money.of(properties.volumeDiscountThreshold(), subtotal.currencyCode());
        if (!subtotal.isLessThan(threshold)) {
            percent = percent.add(properties.volumeDiscountPercent());
        }
        return percent.min(MAX_DISCOUNT_PERCENT);
    }

    private Money calcSubtotal(Order order) {
        return order.getItems().stream()
                .map(OrderItem::getLineTotal)
                .reduce(Money.zero(order.getCurrency()), Money::plus);
    }

    private Order loadWithItems(Long orderId) {
        return orderRepository.findWithItemsById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order", orderId));
    }
}
