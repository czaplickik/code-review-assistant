package com.example.shop.category.service;

import com.example.shop.category.domain.Category;
import com.example.shop.category.dto.CategoryDto;
import com.example.shop.category.dto.UpsertCategoryRequest;
import com.example.shop.category.repository.CategoryRepository;
import com.example.shop.common.error.BusinessRuleException;
import com.example.shop.common.error.ResourceNotFoundException;
import com.example.shop.common.util.Slugs;
import java.time.Clock;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CategoryService {

    private static final Logger log = LoggerFactory.getLogger(CategoryService.class);

    private final CategoryRepository categoryRepository;
    private final CategoryMapper categoryMapper;
    private final Clock clock;

    public CategoryService(CategoryRepository categoryRepository, CategoryMapper categoryMapper, Clock clock) {
        this.categoryRepository = categoryRepository;
        this.categoryMapper = categoryMapper;
        this.clock = clock;
    }

    @Transactional(readOnly = true)
    public Page<CategoryDto> listActive(Pageable pageable) {
        return categoryRepository.findByActiveTrue(pageable).map(categoryMapper::toDto);
    }

    @Transactional(readOnly = true)
    public CategoryDto getBySlug(String slug) {
        return categoryRepository.findBySlugAndActiveTrue(slug)
                .map(categoryMapper::toDto)
                .orElseThrow(() -> new ResourceNotFoundException("Category", slug));
    }

    /** For other features (product) that need to attach a category; never exposed to controllers. */
    @Transactional(readOnly = true)
    public Category requireActive(Long categoryId) {
        return categoryRepository.findByIdAndActiveTrue(categoryId)
                .orElseThrow(() -> new ResourceNotFoundException("Category", categoryId));
    }

    @Transactional
    public CategoryDto create(UpsertCategoryRequest request) {
        String name = request.name().trim();
        if (categoryRepository.existsByNameIgnoreCase(name)) {
            throw new BusinessRuleException("DUPLICATE_CATEGORY", "Category " + name + " already exists");
        }
        String slug = Slugs.slugify(name);
        if (categoryRepository.existsBySlug(slug)) {
            throw new BusinessRuleException("DUPLICATE_CATEGORY_SLUG", "Category slug " + slug + " is already taken");
        }
        Category saved = categoryRepository.save(
                new Category(name, slug, request.description(), request.position(), clock.instant()));
        log.info("Category created categoryId={} slug={}", saved.getId(), saved.getSlug());
        return categoryMapper.toDto(saved);
    }

    @Transactional
    public CategoryDto update(Long categoryId, UpsertCategoryRequest request) {
        Category category = categoryRepository.findById(categoryId)
                .orElseThrow(() -> new ResourceNotFoundException("Category", categoryId));
        String name = request.name().trim();
        if (categoryRepository.existsByNameIgnoreCaseAndIdNot(name, categoryId)) {
            throw new BusinessRuleException("DUPLICATE_CATEGORY", "Category " + name + " already exists");
        }
        // slug is intentionally kept stable on rename: it is part of public catalogue URLs
        category.update(name, request.description(), request.position(), clock.instant());
        log.info("Category updated categoryId={}", categoryId);
        return categoryMapper.toDto(category);
    }

    @Transactional
    public void deactivate(Long categoryId) {
        Category category = categoryRepository.findById(categoryId)
                .orElseThrow(() -> new ResourceNotFoundException("Category", categoryId));
        category.deactivate(clock.instant());
        log.info("Category deactivated categoryId={}", categoryId);
    }
}
