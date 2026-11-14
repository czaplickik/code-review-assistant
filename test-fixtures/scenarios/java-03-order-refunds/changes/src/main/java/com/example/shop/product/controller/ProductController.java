package com.example.shop.product.controller;

import com.example.shop.product.dto.ProductDto;
import com.example.shop.product.dto.UpsertProductRequest;
import com.example.shop.product.service.ProductService;
import jakarta.validation.Valid;
import java.net.URI;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.web.PageableDefault;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class ProductController {

    private final ProductService productService;

    public ProductController(ProductService productService) {
        this.productService = productService;
    }

    @GetMapping("/products")
    public Page<ProductDto> list(
            @PageableDefault(size = 24, sort = "name", direction = Sort.Direction.ASC) Pageable pageable
    ) {
        return productService.listActive(pageable);
    }

    @GetMapping("/products/{slug}")
    public ProductDto get(@PathVariable String slug) {
        return productService.getBySlug(slug);
    }

    @PostMapping("/admin/products")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ProductDto> create(@Valid @RequestBody UpsertProductRequest request) {
        ProductDto created = productService.create(request);
        return ResponseEntity
                .created(URI.create("/api/products/" + created.slug()))
                .body(created);
    }

    @PutMapping("/admin/products/{productId}")
    @PreAuthorize("hasRole('ADMIN')")
    public ProductDto update(@PathVariable Long productId,
                             @Valid @RequestBody UpsertProductRequest request) {
        return productService.update(productId, request);
    }

    @DeleteMapping("/admin/products/{productId}")
    @PreAuthorize("hasRole('ADMIN')")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deactivate(@PathVariable Long productId) {
        productService.deactivate(productId);
    }
}
