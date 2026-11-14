package com.example.shop.order.domain;

import com.example.shop.common.Money;
import jakarta.persistence.CollectionTable;
import jakarta.persistence.Column;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "refunds")
public class Refund {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "order_id", nullable = false, updatable = false)
    private Long orderId;

    @Column(name = "requested_by", nullable = false, updatable = false)
    private Long requestedBy;

    @Column(nullable = false, precision = 12, scale = 2)
    private BigDecimal amount;

    @Column(nullable = false, length = 3)
    private String currency;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private RefundStatus status;

    @Column(nullable = false, length = 500)
    private String reason;

    @Column(name = "gateway_reference", length = 64)
    private String gatewayReference;

    @ElementCollection(fetch = FetchType.EAGER)
    @CollectionTable(name = "refund_lines", joinColumns = @JoinColumn(name = "refund_id"))
    private List<RefundLine> lines = new ArrayList<>();

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "completed_at")
    private Instant completedAt;

    protected Refund() {
        // JPA
    }

    public Refund(Long orderId, Long requestedBy, Money amount, String reason, List<RefundLine> lines, Instant now) {
        this.orderId = orderId;
        this.requestedBy = requestedBy;
        this.amount = amount.amount();
        this.currency = amount.currencyCode();
        this.reason = reason;
        this.lines = new ArrayList<>(lines);
        this.status = RefundStatus.PENDING;
        this.createdAt = now;
    }

    public void complete(String gatewayReference, Instant at) {
        this.gatewayReference = gatewayReference;
        this.status = RefundStatus.COMPLETED;
        this.completedAt = at;
    }

    public Long getId() {
        return id;
    }

    public Long getOrderId() {
        return orderId;
    }

    public Long getRequestedBy() {
        return requestedBy;
    }

    public Money getAmount() {
        return Money.of(amount, currency);
    }

    public RefundStatus getStatus() {
        return status;
    }

    public String getReason() {
        return reason;
    }

    public String getGatewayReference() {
        return gatewayReference;
    }

    public List<RefundLine> getLines() {
        return lines;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getCompletedAt() {
        return completedAt;
    }
}
