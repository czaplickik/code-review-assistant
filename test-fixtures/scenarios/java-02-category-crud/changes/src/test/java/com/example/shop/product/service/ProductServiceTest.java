package com.example.shop.product.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.example.shop.category.domain.Category;
import com.example.shop.category.service.CategoryService;
import com.example.shop.common.Money;
import com.example.shop.common.error.BusinessRuleException;
import com.example.shop.common.error.ResourceNotFoundException;
import com.example.shop.product.domain.Product;
import com.example.shop.product.dto.ProductDto;
import com.example.shop.product.dto.UpsertProductRequest;
import com.example.shop.product.repository.ProductRepository;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class ProductServiceTest {

    private static final Instant NOW = Instant.parse("2026-10-15T12:00:00Z");

    @Mock
    private ProductRepository productRepository;
    @Mock
    private CategoryService categoryService;

    private ProductService service;

    @BeforeEach
    void setUp() {
        service = new ProductService(productRepository, categoryService, Clock.fixed(NOW, ZoneOffset.UTC));
    }

    @Test
    void should_generate_slug_from_name_when_creating_product() {
        when(productRepository.existsBySku("MS-002")).thenReturn(false);
        when(productRepository.existsBySlug(any())).thenReturn(false);
        when(productRepository.save(any(Product.class))).thenAnswer(inv -> inv.getArgument(0));

        ProductDto created = service.create(request("MS-002", "Wireless  Mouse"));

        ArgumentCaptor<Product> saved = ArgumentCaptor.forClass(Product.class);
        verify(productRepository).save(saved.capture());
        assertThat(saved.getValue().getSlug()).isEqualTo("Wireless-Mouse");
        assertThat(created.price()).isEqualByComparingTo("34.50");
    }

    @Test
    void should_append_numeric_suffix_when_slug_already_taken() {
        when(productRepository.existsBySku("HB-003")).thenReturn(false);
        when(productRepository.existsBySlug("usb-c-hub")).thenReturn(true);
        when(productRepository.existsBySlug("usb-c-hub-2")).thenReturn(false);
        when(productRepository.save(any(Product.class))).thenAnswer(inv -> inv.getArgument(0));

        ProductDto created = service.create(request("HB-003", "USB-C Hub"));

        assertThat(created.slug()).isEqualTo("usb-c-hub-2");
    }

    @Test
    void should_assign_category_when_category_id_given() {
        Category peripherals = new Category("Peripherals", "peripherals", null, 1, NOW);
        ReflectionTestUtils.setField(peripherals, "id", 5L);
        when(productRepository.existsBySku("MS-002")).thenReturn(false);
        when(productRepository.existsBySlug(any())).thenReturn(false);
        when(categoryService.requireActive(5L)).thenReturn(peripherals);
        when(productRepository.save(any(Product.class))).thenAnswer(inv -> inv.getArgument(0));

        ProductDto created = service.create(new UpsertProductRequest("MS-002", "Wireless Mouse", null,
                new BigDecimal("34.50"), "EUR", 10, 5L));

        assertThat(created.categoryId()).isEqualTo(5L);
    }

    @Test
    void should_not_touch_categories_when_category_id_absent() {
        when(productRepository.existsBySku("MS-002")).thenReturn(false);
        when(productRepository.existsBySlug(any())).thenReturn(false);
        when(productRepository.save(any(Product.class))).thenAnswer(inv -> inv.getArgument(0));

        ProductDto created = service.create(request("MS-002", "Wireless Mouse"));

        assertThat(created.categoryId()).isNull();
        verifyNoInteractions(categoryService);
    }

    @Test
    void should_reject_create_when_sku_already_exists() {
        when(productRepository.existsBySku("KB-001")).thenReturn(true);

        assertThatThrownBy(() -> service.create(request("KB-001", "Keyboard")))
                .isInstanceOf(BusinessRuleException.class)
                .extracting("code").isEqualTo("DUPLICATE_SKU");
        verify(productRepository, never()).save(any());
    }

    @Test
    void should_throw_not_found_when_slug_unknown() {
        when(productRepository.findBySlugAndActiveTrue("missing")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.getBySlug("missing"))
                .isInstanceOf(ResourceNotFoundException.class)
                .hasMessage("Product missing not found");
    }

    @Test
    void should_reject_update_when_sku_changes() {
        Product existing = new Product("KB-001", "Keyboard", "keyboard", null, Money.of("89.90", "EUR"), 5, NOW);
        ReflectionTestUtils.setField(existing, "id", 1L);
        when(productRepository.findById(1L)).thenReturn(Optional.of(existing));

        assertThatThrownBy(() -> service.update(1L, request("KB-999", "Keyboard")))
                .isInstanceOf(BusinessRuleException.class)
                .extracting("code").isEqualTo("SKU_IMMUTABLE");
    }

    private static UpsertProductRequest request(String sku, String name) {
        return new UpsertProductRequest(sku, name, "desc", new BigDecimal("34.50"), "EUR", 10, null);
    }
}
