package com.example.shop.product.service;

import com.example.shop.common.Money;
import com.example.shop.common.error.BusinessRuleException;
import com.example.shop.common.error.ResourceNotFoundException;
import com.example.shop.common.util.Slugs;
import com.example.shop.product.domain.Product;
import com.example.shop.product.dto.ProductDto;
import com.example.shop.product.dto.UpsertProductRequest;
import com.example.shop.product.repository.ProductRepository;
import java.time.Clock;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ProductService {

    private static final Logger log = LoggerFactory.getLogger(ProductService.class);
    private static final int MAX_SLUG_ATTEMPTS = 20;

    private final ProductRepository productRepository;
    private final Clock clock;

    public ProductService(ProductRepository productRepository, Clock clock) {
        this.productRepository = productRepository;
        this.clock = clock;
    }

    @Transactional(readOnly = true)
    public Page<ProductDto> listActive(Pageable pageable) {
        return productRepository.findByActiveTrue(pageable).map(ProductService::mapToDTO);
    }

    @Transactional(readOnly = true)
    public ProductDto getBySlug(String slug) {
        return productRepository.findBySlugAndActiveTrue(slug)
                .map(ProductService::mapToDTO)
                .orElseThrow(() -> new ResourceNotFoundException("Product", slug));
    }

    @Transactional
    public ProductDto create(UpsertProductRequest request) {
        if (productRepository.existsBySku(request.sku())) {
            throw new BusinessRuleException("DUPLICATE_SKU", "Product with SKU " + request.sku() + " already exists");
        }
        Product product = new Product(
                request.sku(),
                request.name(),
                uniqueSlug(request.name()),
                request.description(),
                Money.of(request.price(), request.currency()),
                request.stock(),
                clock.instant());
        Product saved = productRepository.save(product);
        log.info("Product created productId={} sku={}", saved.getId(), saved.getSku());
        return mapToDTO(saved);
    }

    @Transactional
    public ProductDto update(Long productId, UpsertProductRequest request) {
        Product product = productRepository.findById(productId)
                .orElseThrow(() -> new ResourceNotFoundException("Product", productId));
        if (!product.getSku().equals(request.sku())) {
            throw new BusinessRuleException("SKU_IMMUTABLE", "SKU of an existing product cannot be changed");
        }
        product.update(request.name(), request.description(), Money.of(request.price(), request.currency()),
                request.stock(), clock.instant());
        log.info("Product updated productId={}", productId);
        return mapToDTO(product);
    }

    @Transactional
    public void deactivate(Long productId) {
        Product product = productRepository.findById(productId)
                .orElseThrow(() -> new ResourceNotFoundException("Product", productId));
        product.deactivate(clock.instant());
        log.info("Product deactivated productId={}", productId);
    }

    private String uniqueSlug(String name) {
        String base = Slugs.slugify(name);
        if (!productRepository.existsBySlug(base)) {
            return base;
        }
        for (int suffix = 2; suffix <= MAX_SLUG_ATTEMPTS; suffix++) {
            String candidate = Slugs.withSuffix(base, suffix);
            if (!productRepository.existsBySlug(candidate)) {
                return candidate;
            }
        }
        throw new BusinessRuleException("SLUG_EXHAUSTED", "Could not find a free slug for " + name);
    }

    private static ProductDto mapToDTO(Product product) {
        return new ProductDto(
                product.getId(),
                product.getSku(),
                product.getName(),
                product.getSlug(),
                product.getDescription(),
                product.getPrice().amount(),
                product.getPrice().currencyCode(),
                product.getStock());
    }
}
