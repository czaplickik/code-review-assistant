package com.example.shop.order.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;
import java.math.BigDecimal;

@Embeddable
public class RefundLine {

    @Column(name = "product_id", nullable = false)
    private Long productId;

    @Column(nullable = false)
    private int quantity;

    @Column(nullable = false, precision = 12, scale = 2)
    private BigDecimal amount;

    protected RefundLine() {
        // JPA
    }

    public RefundLine(Long productId, int quantity, BigDecimal amount) {
        this.productId = productId;
        this.quantity = quantity;
        this.amount = amount;
    }

    public Long getProductId() {
        return productId;
    }

    public int getQuantity() {
        return quantity;
    }

    public BigDecimal getAmount() {
        return amount;
    }
}
