package com.example.shop.product.repository;

import com.example.shop.product.domain.Product;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ProductRepository extends JpaRepository<Product, Long> {

    Page<Product> findByActiveTrue(Pageable pageable);

    Optional<Product> findBySlugAndActiveTrue(String slug);

    List<Product> findAllByIdIn(Collection<Long> ids);

    boolean existsBySku(String sku);

    boolean existsBySlug(String slug);
}
