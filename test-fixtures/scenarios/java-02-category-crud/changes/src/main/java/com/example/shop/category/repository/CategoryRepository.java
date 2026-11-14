package com.example.shop.category.repository;

import com.example.shop.category.domain.Category;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CategoryRepository extends JpaRepository<Category, Long> {

    Page<Category> findByActiveTrue(Pageable pageable);

    Optional<Category> findBySlugAndActiveTrue(String slug);

    Optional<Category> findByIdAndActiveTrue(Long id);

    boolean existsByNameIgnoreCase(String name);

    boolean existsByNameIgnoreCaseAndIdNot(String name, Long id);

    boolean existsBySlug(String slug);
}
