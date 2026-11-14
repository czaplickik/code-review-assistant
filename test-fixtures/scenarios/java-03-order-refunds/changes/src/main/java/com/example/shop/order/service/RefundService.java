package com.example.shop.order.service;

import com.example.shop.common.Money;
import com.example.shop.order.domain.Order;
import com.example.shop.order.domain.OrderItem;
import com.example.shop.order.domain.OrderStatus;
import com.example.shop.order.domain.Refund;
import com.example.shop.order.domain.RefundLine;
import com.example.shop.order.domain.RefundStatus;
import com.example.shop.order.dto.RefundRequest;
import com.example.shop.order.event.OrderRefundedEvent;
import com.example.shop.order.event.OrderStatusChangedEvent;
import com.example.shop.order.repository.OrderRepository;
import com.example.shop.order.repository.RefundRepository;
import com.example.shop.payment.PaymentClient;
import com.example.shop.product.domain.Product;
import com.example.shop.product.repository.ProductRepository;
import com.example.shop.security.AuthenticatedUser;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Full and partial refunds of paid orders.
 * See docs/superpowers/specs/2026-11-10-order-refunds-design.md.
 */
@Service
public class RefundService {

    private static final Logger log = LoggerFactory.getLogger(RefundService.class);

    private static final Duration REFUND_WINDOW = Duration.ofDays(30);
    private static final int MAX_REASON_LENGTH = 500;
    private static final Set<OrderStatus> REFUNDABLE_STATUSES = EnumSet.of(
            OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.PARTIALLY_REFUNDED);

    @Autowired
    private OrderRepository orderRepository;

    @Autowired
    private RefundRepository refundRepository;

    @Autowired
    private ProductRepository productRepository;

    @Autowired
    private PaymentClient paymentClient;

    @Autowired
    private ApplicationEventPublisher events;

    @Autowired
    private Clock clock;

    @Transactional
    public Refund refund(Long orderId, RefundRequest request, AuthenticatedUser requester) {
        Instant now = clock.instant();
        log.info("Refund requested orderId={} requestedBy={} lines={}", orderId, requester.id(),
                request.lines() == null ? 0 : request.lines().size());

        // --- 1. load and validate the order ---------------------------------------------------
        Order order = orderRepository.findWithItemsById(orderId)
                .orElseThrow(() -> new RuntimeException("Order not found: " + orderId));

        if (!REFUNDABLE_STATUSES.contains(order.getStatus())) {
            throw new RuntimeException("Order " + orderId + " cannot be refunded in status " + order.getStatus());
        }
        if (order.getPaidAt() == null || order.getPaymentReference() == null) {
            throw new RuntimeException("Order " + orderId + " has no captured payment");
        }
        Instant windowEnd = order.getPaidAt().plus(REFUND_WINDOW);
        if (now.isAfter(windowEnd)) {
            throw new RuntimeException("Refund window of " + REFUND_WINDOW.toDays() + " days expired for order " + orderId);
        }

        String reason = request.reason() == null ? null : request.reason().trim();
        if (reason == null || reason.isEmpty()) {
            throw new RuntimeException("Refund reason is required");
        }
        if (reason.length() > MAX_REASON_LENGTH) {
            reason = reason.substring(0, MAX_REASON_LENGTH);
        }

        // --- 2. what has already been refunded -----------------------------------------------
        List<Refund> previousRefunds = refundRepository.findByOrderIdOrderByCreatedAtDesc(orderId);
        Map<Long, Integer> alreadyRefundedQuantities = new HashMap<>();
        Money alreadyRefunded = Money.zero(order.getCurrency());
        for (Refund previous : previousRefunds) {
            if (previous.getStatus() != RefundStatus.COMPLETED) {
                continue;
            }
            alreadyRefunded = alreadyRefunded.plus(previous.getAmount());
            for (RefundLine line : previous.getLines()) {
                alreadyRefundedQuantities.merge(line.getProductId(), line.getQuantity(), Integer::sum);
            }
        }

        Map<Long, OrderItem> itemsByProduct = new LinkedHashMap<>();
        for (OrderItem item : order.getItems()) {
            itemsByProduct.put(item.getProductId(), item);
        }

        // --- 3. resolve requested lines (no lines = everything that is left) -----------------
        Map<Long, Integer> requestedQuantities = new LinkedHashMap<>();
        boolean fullRefund = request.lines() == null || request.lines().isEmpty();
        if (fullRefund) {
            for (OrderItem item : order.getItems()) {
                int remaining = item.getQuantity() - alreadyRefundedQuantities.getOrDefault(item.getProductId(), 0);
                if (remaining > 0) {
                    requestedQuantities.put(item.getProductId(), remaining);
                }
            }
            if (requestedQuantities.isEmpty()) {
                throw new RuntimeException("Order " + orderId + " is already fully refunded");
            }
        } else {
            for (RefundRequest.Line line : request.lines()) {
                if (line.productId() == null) {
                    throw new RuntimeException("Refund line without productId");
                }
                if (line.quantity() <= 0) {
                    throw new RuntimeException("Refund quantity must be positive for product " + line.productId());
                }
                requestedQuantities.merge(line.productId(), line.quantity(), Integer::sum);
            }
        }

        // --- 4. calculate the refund amount ------------------------------------------------
        Money discount = order.getDiscount();
        int totalUnits = 0;
        for (OrderItem item : order.getItems()) {
            totalUnits += item.getQuantity();
        }

        Money refundAmount = Money.zero(order.getCurrency());
        List<RefundLine> refundLines = new ArrayList<>();
        for (Map.Entry<Long, Integer> entry : requestedQuantities.entrySet()) {
            Long productId = entry.getKey();
            int quantity = entry.getValue();
            OrderItem item = itemsByProduct.get(productId);
            if (item == null) {
                throw new RuntimeException("Product " + productId + " is not part of order " + orderId);
            }
            int refundable = item.getQuantity() - alreadyRefundedQuantities.getOrDefault(productId, 0);
            if (quantity > refundable) {
                throw new RuntimeException("Cannot refund " + quantity + " units of product " + productId
                        + ", only " + refundable + " refundable");
            }

            Money lineGross = item.getUnitPrice().times(quantity);
            Money lineDiscount = Money.zero(order.getCurrency());
            if (!discount.isZero()) {
                // pro-rata: spread the order discount over the refunded units
                lineDiscount = discount.proportion(quantity, totalUnits);
            }
            Money lineRefund = lineGross.minus(lineDiscount);
            if (lineRefund.isNegative()) {
                lineRefund = Money.zero(order.getCurrency());
            }

            refundAmount = refundAmount.plus(lineRefund);
            refundLines.add(new RefundLine(productId, quantity, lineRefund.amount()));
            log.debug("Refund line calculated orderId={} productId={} quantity={} gross={} discount={} refund={}",
                    orderId, productId, quantity, lineGross, lineDiscount, lineRefund);
        }

        // --- 5. never refund more than was captured ----------------------------------------
        Money captured = order.getTotal();
        Money remainingRefundable = captured.minus(alreadyRefunded);
        if (refundAmount.isGreaterThan(remainingRefundable)) {
            log.warn("Refund amount clamped orderId={} requested={} remaining={}", orderId, refundAmount, remainingRefundable);
            refundAmount = remainingRefundable;
        }
        if (refundAmount.isZero() || refundAmount.isNegative()) {
            throw new RuntimeException("Nothing left to refund for order " + orderId);
        }

        // --- 6. refund at the payment gateway ----------------------------------------------
        String idempotencyKey = "order-" + orderId + "-refund-" + (previousRefunds.size() + 1);
        PaymentClient.RefundResult result = paymentClient.refund(
                new PaymentClient.RefundCommand(order.getPaymentReference(), refundAmount, idempotencyKey));
        if (result == null || result.refundReference() == null) {
            throw new RuntimeException("Payment gateway did not confirm refund for order " + orderId);
        }

        // --- 7. persist the refund and update the order ------------------------------------
        Refund refund = new Refund(order.getId(), requester.id(), refundAmount, reason, refundLines, now);
        refund.complete(result.refundReference(), now);
        refund = refundRepository.save(refund);

        OrderStatus previousStatus = order.getStatus();
        order.registerRefund(refundAmount, now);
        orderRepository.save(order);

        // --- 8. put goods back on stock if they never left the warehouse -------------------
        if (previousStatus == OrderStatus.PAID) {
            List<Product> products = productRepository.findAllByIdIn(requestedQuantities.keySet());
            for (Product product : products) {
                Integer quantity = requestedQuantities.get(product.getId());
                if (quantity != null && quantity > 0) {
                    product.releaseStock(quantity);
                }
            }
        }

        // --- 9. events ---------------------------------------------------------------------
        events.publishEvent(new OrderRefundedEvent(
                UUID.randomUUID(),
                OrderRefundedEvent.SCHEMA_VERSION,
                order.getId(),
                refund.getId(),
                order.getCurrency(),
                refundAmount.amount(),
                order.getRefundedAmount().amount(),
                now));
        events.publishEvent(OrderStatusChangedEvent.of(order.getId(), previousStatus, order.getStatus(),
                order.getRefundedAmount().amount(), now));

        log.info("Refund completed orderId={} refundId={} amount={} status={} gatewayReference={}",
                orderId, refund.getId(), refundAmount, order.getStatus(), result.refundReference());
        return refund;
    }

    @Transactional(readOnly = true)
    public List<Refund> listRefunds(Long orderId) {
        return refundRepository.findByOrderIdOrderByCreatedAtDesc(orderId);
    }
}
