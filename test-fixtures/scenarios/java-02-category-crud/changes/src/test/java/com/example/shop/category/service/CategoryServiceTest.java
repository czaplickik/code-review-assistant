package com.example.shop.category.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.example.shop.category.domain.Category;
import com.example.shop.category.dto.CategoryDto;
import com.example.shop.category.dto.UpsertCategoryRequest;
import com.example.shop.category.repository.CategoryRepository;
import com.example.shop.common.error.BusinessRuleException;
import com.example.shop.common.error.ResourceNotFoundException;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class CategoryServiceTest {

    private static final Instant NOW = Instant.parse("2026-11-05T08:00:00Z");

    @Mock
    private CategoryRepository categoryRepository;

    private CategoryService service;

    @BeforeEach
    void setUp() {
        service = new CategoryService(categoryRepository, new CategoryMapper(), Clock.fixed(NOW, ZoneOffset.UTC));
    }

    @Test
    void should_create_category_with_slug_when_name_is_unique() {
        when(categoryRepository.existsByNameIgnoreCase("Gaming Gear")).thenReturn(false);
        when(categoryRepository.existsBySlug("gaming-gear")).thenReturn(false);
        when(categoryRepository.save(any(Category.class))).thenAnswer(inv -> withId(inv.getArgument(0), 3L));

        CategoryDto created = service.create(new UpsertCategoryRequest("  Gaming Gear ", "Keyboards, mice, headsets", 2));

        assertThat(created.id()).isEqualTo(3L);
        assertThat(created.name()).isEqualTo("Gaming Gear");
        assertThat(created.slug()).isEqualTo("gaming-gear");
        assertThat(created.position()).isEqualTo(2);
    }

    @Test
    void should_reject_create_when_name_exists_ignoring_case() {
        when(categoryRepository.existsByNameIgnoreCase("audio")).thenReturn(true);

        assertThatThrownBy(() -> service.create(new UpsertCategoryRequest("audio", null, 0)))
                .isInstanceOf(BusinessRuleException.class)
                .extracting("code").isEqualTo("DUPLICATE_CATEGORY");
        verify(categoryRepository, never()).save(any());
    }

    @Test
    void should_keep_slug_when_category_renamed() {
        Category audio = withId(new Category("Audio", "audio", null, 1, NOW), 4L);
        when(categoryRepository.findById(4L)).thenReturn(Optional.of(audio));
        when(categoryRepository.existsByNameIgnoreCaseAndIdNot("Audio & Video", 4L)).thenReturn(false);

        CategoryDto updated = service.update(4L, new UpsertCategoryRequest("Audio & Video", null, 1));

        assertThat(updated.name()).isEqualTo("Audio & Video");
        assertThat(updated.slug()).isEqualTo("audio");
    }

    @Test
    void should_return_page_of_active_categories_when_listing() {
        Pageable pageable = PageRequest.of(0, 2);
        when(categoryRepository.findByActiveTrue(pageable)).thenReturn(new PageImpl<>(List.of(
                withId(new Category("Audio", "audio", null, 1, NOW), 1L),
                withId(new Category("Cables", "cables", null, 2, NOW), 2L)), pageable, 5));

        var page = service.listActive(pageable);

        assertThat(page.getContent()).extracting(CategoryDto::slug).containsExactly("audio", "cables");
        assertThat(page.getTotalElements()).isEqualTo(5);
    }

    @Test
    void should_throw_not_found_when_required_category_inactive() {
        when(categoryRepository.findByIdAndActiveTrue(9L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.requireActive(9L))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessage("Category 9 not found");
    }

    @Test
    void should_deactivate_category_when_it_exists() {
        Category audio = withId(new Category("Audio", "audio", null, 1, NOW), 4L);
        when(categoryRepository.findById(4L)).thenReturn(Optional.of(audio));

        service.deactivate(4L);

        assertThat(audio.isActive()).isFalse();
    }

    private static Category withId(Category category, Long id) {
        ReflectionTestUtils.setField(category, "id", id);
        return category;
    }
}
