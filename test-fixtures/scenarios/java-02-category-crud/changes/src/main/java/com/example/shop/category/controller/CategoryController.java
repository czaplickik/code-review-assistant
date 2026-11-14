package com.example.shop.category.controller;

import com.example.shop.category.dto.CategoryDto;
import com.example.shop.category.dto.UpsertCategoryRequest;
import com.example.shop.category.service.CategoryService;
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
public class CategoryController {

    private final CategoryService categoryService;

    public CategoryController(CategoryService categoryService) {
        this.categoryService = categoryService;
    }

    @GetMapping("/categories")
    public Page<CategoryDto> list(@PageableDefault(size = 50, sort = "position", direction = Sort.Direction.ASC) Pageable pageable) {
        return categoryService.listActive(pageable);
    }

    @GetMapping("/categories/{slug}")
    public CategoryDto get(@PathVariable String slug) {
        return categoryService.getBySlug(slug);
    }

    @PostMapping("/admin/categories")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<CategoryDto> create(@Valid @RequestBody UpsertCategoryRequest request) {
        CategoryDto created = categoryService.create(request);
        return ResponseEntity.created(URI.create("/api/categories/" + created.slug())).body(created);
    }

    @PutMapping("/admin/categories/{categoryId}")
    @PreAuthorize("hasRole('ADMIN')")
    public CategoryDto update(@PathVariable Long categoryId, @Valid @RequestBody UpsertCategoryRequest request) {
        return categoryService.update(categoryId, request);
    }

    @DeleteMapping("/admin/categories/{categoryId}")
    @PreAuthorize("hasRole('ADMIN')")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deactivate(@PathVariable Long categoryId) {
        categoryService.deactivate(categoryId);
    }
}
