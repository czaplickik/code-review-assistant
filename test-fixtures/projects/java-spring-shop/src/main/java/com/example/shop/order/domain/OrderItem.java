package com.example.shop.order.domain;

import com.example.shop.common.Money;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.math.BigDecimal;

@Entity
@Table(name = "order_items")
public class OrderItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "order_id", nullable = false)
    private Order order;

    @Column(name = "product_id", nullable = false)
    private Long productId;

    @Column(name = "product_name", nullable = false, length = 200)
    private String productName;

    @Column(name = "unit_price_amount", nullable = false, precision = 12, scale = 2)
    private BigDecimal unitPriceAmount;

    @Column(nullable = false)
    private int quantity;

    @Column(name = "line_total_amount", nullable = false, precision = 12, scale = 2)
    private BigDecimal lineTotalAmount;

    protected OrderItem() {
        // JPA
    }

    OrderItem(Order order, Long productId, String productName, Money unitPrice, int quantity) {
        if (quantity <= 0) {
            throw new IllegalArgumentException("quantity must be positive");
        }
        this.order = order;
        this.productId = productId;
        this.productName = productName;
        this.unitPriceAmount = unitPrice.amount();
        this.quantity = quantity;
        this.lineTotalAmount = unitPrice.times(quantity).amount();
    }

    public Money getUnitPrice() {
        return Money.of(unitPriceAmount, order.getCurrency());
    }

    public Money getLineTotal() {
        return Money.of(lineTotalAmount, order.getCurrency());
    }

    public Long getId() {
        return id;
    }

    public Long getProductId() {
        return productId;
    }

    public String getProductName() {
        return productName;
    }

    public int getQuantity() {
        return quantity;
    }
}
