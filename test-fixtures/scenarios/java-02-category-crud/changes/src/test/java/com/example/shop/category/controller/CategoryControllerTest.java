package com.example.shop.category.controller;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.example.shop.category.dto.CategoryDto;
import com.example.shop.category.service.CategoryService;
import com.example.shop.security.AuthenticatedUser;
import com.example.shop.security.JwtService;
import com.example.shop.security.SecurityConfig;
import com.example.shop.user.domain.Role;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(CategoryController.class)
@Import(SecurityConfig.class)
class CategoryControllerTest {

    private static final AuthenticatedUser ADMIN = new AuthenticatedUser(1L, "admin@example.com", Role.ADMIN);
    private static final AuthenticatedUser ALICE = new AuthenticatedUser(7L, "alice@example.com", Role.USER);

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private CategoryService categoryService;
    @MockBean
    private JwtService jwtService;

    @Test
    void should_return_201_with_location_when_admin_creates_category() throws Exception {
        when(categoryService.create(any())).thenReturn(new CategoryDto(3L, "Gaming Gear", "gaming-gear", null, 2));

        mockMvc.perform(post("/api/admin/categories")
                        .with(authentication(auth(ADMIN)))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\": \"Gaming Gear\", \"position\": 2}"))
                .andExpect(status().isCreated())
                .andExpect(header().string("Location", "/api/categories/gaming-gear"))
                .andExpect(jsonPath("$.slug").value("gaming-gear"));
    }

    @Test
    void should_return_403_when_customer_creates_category() throws Exception {
        mockMvc.perform(post("/api/admin/categories")
                        .with(authentication(auth(ALICE)))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\": \"Gaming Gear\", \"position\": 2}"))
                .andExpect(status().isForbidden());
        verify(categoryService, never()).create(any());
    }

    @Test
    void should_return_400_when_name_blank() throws Exception {
        mockMvc.perform(post("/api/admin/categories")
                        .with(authentication(auth(ADMIN)))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\": \" \", \"position\": -1}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errors.name").exists())
                .andExpect(jsonPath("$.errors.position").exists());
    }

    @Test
    void should_return_category_when_customer_reads_by_slug() throws Exception {
        when(categoryService.getBySlug("audio")).thenReturn(new CategoryDto(4L, "Audio", "audio", "Headphones", 1));

        mockMvc.perform(get("/api/categories/audio").with(authentication(auth(ALICE))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.name").value("Audio"));
    }

    private static Authentication auth(AuthenticatedUser user) {
        return UsernamePasswordAuthenticationToken.authenticated(user, null, user.authorities());
    }
}
