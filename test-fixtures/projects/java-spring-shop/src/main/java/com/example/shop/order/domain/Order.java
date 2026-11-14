package com.example.shop.order.domain;

import com.example.shop.common.Money;
import com.example.shop.common.error.BusinessRuleException;
import com.example.shop.product.domain.Product;
import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OrderBy;
import jakarta.persistence.Table;
import jakarta.persistence.Version;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

@Entity
@Table(name = "orders")
public class Order {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false, updatable = false)
    private Long userId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private OrderStatus status;

    @Column(nullable = false, length = 3)
    private String currency;

    @Column(name = "subtotal_amount", nullable = false, precision = 12, scale = 2)
    private BigDecimal subtotalAmount;

    @Column(name = "discount_percent", nullable = false, precision = 5, scale = 2)
    private BigDecimal discountPercent;

    @Column(name = "discount_amount", nullable = false, precision = 12, scale = 2)
    private BigDecimal discountAmount;

    @Column(name = "total_amount", nullable = false, precision = 12, scale = 2)
    private BigDecimal totalAmount;

    @Column(name = "payment_reference", length = 64)
    private String paymentReference;

    @Column(name = "paid_at")
    private Instant paidAt;

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("id")
    private List<OrderItem> items = new ArrayList<>();

    @Version
    private long version;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected Order() {
        // JPA
    }

    public static Order create(Long userId, String currency, Instant now) {
        Order order = new Order();
        order.userId = userId;
        order.currency = currency;
        order.status = OrderStatus.CREATED;
        order.subtotalAmount = BigDecimal.ZERO;
        order.discountPercent = BigDecimal.ZERO;
        order.discountAmount = BigDecimal.ZERO;
        order.totalAmount = BigDecimal.ZERO;
        order.createdAt = now;
        order.updatedAt = now;
        return order;
    }

    public void addItem(Product product, int quantity) {
        requireStatus(OrderStatus.CREATED);
        if (!product.getPrice().currencyCode().equals(currency)) {
            throw new BusinessRuleException("CURRENCY_MISMATCH",
                    "Product %s is priced in %s, order is in %s".formatted(product.getSku(), product.getPrice().currencyCode(), currency));
        }
        items.add(new OrderItem(this, product.getId(), product.getName(), product.getPrice(), quantity));
    }

    public void applyPricing(Money subtotal, BigDecimal discountPercent, Money discount) {
        requireStatus(OrderStatus.CREATED);
        if (discount.isGreaterThan(subtotal)) {
            throw new IllegalArgumentException("discount exceeds subtotal");
        }
        this.subtotalAmount = subtotal.amount();
        this.discountPercent = discountPercent;
        this.discountAmount = discount.amount();
        this.totalAmount = subtotal.minus(discount).amount();
    }

    public void markPaid(String paymentReference, Instant at) {
        transitionTo(OrderStatus.PAID, at);
        this.paymentReference = paymentReference;
        this.paidAt = at;
    }

    public void markShipped(Instant at) {
        transitionTo(OrderStatus.SHIPPED, at);
    }

    public void markDelivered(Instant at) {
        transitionTo(OrderStatus.DELIVERED, at);
    }

    public void cancel(Instant at) {
        transitionTo(OrderStatus.CANCELLED, at);
    }

    private void transitionTo(OrderStatus target, Instant at) {
        if (!status.canTransitionTo(target)) {
            throw new BusinessRuleException("INVALID_ORDER_TRANSITION",
                    "Order %d cannot move from %s to %s".formatted(id, status, target));
        }
        this.status = target;
        this.updatedAt = at;
    }

    private void requireStatus(OrderStatus expected) {
        if (status != expected) {
            throw new BusinessRuleException("INVALID_ORDER_STATE",
                    "Order %d must be %s but is %s".formatted(id, expected, status));
        }
    }

    public Money getSubtotal() {
        return Money.of(subtotalAmount, currency);
    }

    public Money getDiscount() {
        return Money.of(discountAmount, currency);
    }

    public Money getTotal() {
        return Money.of(totalAmount, currency);
    }

    public Long getId() {
        return id;
    }

    public Long getUserId() {
        return userId;
    }

    public OrderStatus getStatus() {
        return status;
    }

    public String getCurrency() {
        return currency;
    }

    public BigDecimal getDiscountPercent() {
        return discountPercent;
    }

    public String getPaymentReference() {
        return paymentReference;
    }

    public Instant getPaidAt() {
        return paidAt;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public List<OrderItem> getItems() {
        return Collections.unmodifiableList(items);
    }
}
