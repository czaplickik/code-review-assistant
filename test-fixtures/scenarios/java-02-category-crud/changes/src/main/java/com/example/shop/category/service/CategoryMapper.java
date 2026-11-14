package com.example.shop.category.service;

import com.example.shop.category.domain.Category;
import com.example.shop.category.dto.CategoryDto;
import org.springframework.stereotype.Component;

@Component
public class CategoryMapper {

    public CategoryDto toDto(Category category) {
        return new CategoryDto(
                category.getId(),
                category.getName(),
                category.getSlug(),
                category.getDescription(),
                category.getPosition());
    }
}
