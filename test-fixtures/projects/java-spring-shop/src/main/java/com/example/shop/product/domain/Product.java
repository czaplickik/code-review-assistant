package com.example.shop.product.domain;

import com.example.shop.common.Money;
import com.example.shop.common.error.BusinessRuleException;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.Version;
import java.math.BigDecimal;
import java.time.Instant;

@Entity
@Table(name = "products")
public class Product {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 32)
    private String sku;

    @Column(nullable = false, length = 200)
    private String name;

    @Column(nullable = false, unique = true, length = 220)
    private String slug;

    @Column(columnDefinition = "text")
    private String description;

    @Column(name = "price_amount", nullable = false, precision = 12, scale = 2)
    private BigDecimal priceAmount;

    @Column(name = "price_currency", nullable = false, length = 3)
    private String priceCurrency;

    @Column(nullable = false)
    private int stock;

    @Column(nullable = false)
    private boolean active = true;

    @Version
    private long version;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected Product() {
        // JPA
    }

    public Product(String sku, String name, String slug, String description, Money price, int stock, Instant now) {
        this.sku = sku;
        this.name = name;
        this.slug = slug;
        this.description = description;
        this.priceAmount = price.amount();
        this.priceCurrency = price.currencyCode();
        this.stock = stock;
        this.createdAt = now;
        this.updatedAt = now;
    }

    public void update(String name, String description, Money price, int stock, Instant now) {
        this.name = name;
        this.description = description;
        this.priceAmount = price.amount();
        this.priceCurrency = price.currencyCode();
        this.stock = stock;
        this.updatedAt = now;
    }

    public void reserveStock(int quantity) {
        if (quantity <= 0) {
            throw new IllegalArgumentException("quantity must be positive");
        }
        if (stock < quantity) {
            throw new BusinessRuleException("INSUFFICIENT_STOCK",
                    "Only %d units of %s available, requested %d".formatted(stock, sku, quantity));
        }
        stock -= quantity;
    }

    public void releaseStock(int quantity) {
        if (quantity <= 0) {
            throw new IllegalArgumentException("quantity must be positive");
        }
        stock += quantity;
    }

    public void deactivate(Instant now) {
        this.active = false;
        this.updatedAt = now;
    }

    public Money getPrice() {
        return Money.of(priceAmount, priceCurrency);
    }

    public Long getId() {
        return id;
    }

    public String getSku() {
        return sku;
    }

    public String getName() {
        return name;
    }

    public String getSlug() {
        return slug;
    }

    public String getDescription() {
        return description;
    }

    public int getStock() {
        return stock;
    }

    public boolean isActive() {
        return active;
    }
}
