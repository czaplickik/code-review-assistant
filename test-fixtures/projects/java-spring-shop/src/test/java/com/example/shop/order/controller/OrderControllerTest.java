package com.example.shop.order.controller;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.example.shop.order.domain.OrderStatus;
import com.example.shop.order.dto.OrderDto;
import com.example.shop.order.service.OrderService;
import com.example.shop.security.AuthenticatedUser;
import com.example.shop.security.JwtService;
import com.example.shop.security.OrderSecurity;
import com.example.shop.security.SecurityConfig;
import com.example.shop.user.domain.Role;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(OrderController.class)
@Import(SecurityConfig.class)
class OrderControllerTest {

    private static final AuthenticatedUser ALICE = new AuthenticatedUser(7L, "alice@example.com", Role.USER);
    private static final AuthenticatedUser SAM = new AuthenticatedUser(9L, "sam@example.com", Role.SUPPORT);

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private OrderService orderService;
    @MockBean
    private JwtService jwtService;
    @MockBean(name = "orderSecurity")
    private OrderSecurity orderSecurity;

    @Test
    void should_return_201_with_location_when_customer_places_order() throws Exception {
        when(orderService.placeOrder(eq(7L), any())).thenReturn(order(55L));

        mockMvc.perform(post("/api/orders")
                        .with(authentication(auth(ALICE)))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"lines": [{"productId": 1, "quantity": 2}], "couponCode": "WELCOME10"}
                                """))
                .andExpect(status().isCreated())
                .andExpect(header().string("Location", "/api/orders/55"))
                .andExpect(jsonPath("$.id").value(55))
                .andExpect(jsonPath("$.total").value(161.82));
    }

    @Test
    void should_return_400_when_order_has_no_lines() throws Exception {
        mockMvc.perform(post("/api/orders")
                        .with(authentication(auth(ALICE)))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"lines\": []}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION_FAILED"))
                .andExpect(jsonPath("$.errors.lines").exists());
        verify(orderService, never()).placeOrder(any(), any());
    }

    @Test
    void should_return_401_when_request_has_no_token() throws Exception {
        mockMvc.perform(get("/api/orders/55"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void should_return_403_when_customer_reads_foreign_order() throws Exception {
        when(orderSecurity.isOwner(eq(55L), any())).thenReturn(false);

        mockMvc.perform(get("/api/orders/55").with(authentication(auth(ALICE))))
                .andExpect(status().isForbidden());
        verify(orderService, never()).getOrder(any());
    }

    @Test
    void should_return_order_when_owner_reads_it() throws Exception {
        when(orderSecurity.isOwner(eq(55L), any())).thenReturn(true);
        when(orderService.getOrder(55L)).thenReturn(order(55L));

        mockMvc.perform(get("/api/orders/55").with(authentication(auth(ALICE))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("CREATED"))
                .andExpect(jsonPath("$.items[0].quantity").value(2));
    }

    @Test
    void should_allow_support_to_read_any_order_when_not_owner() throws Exception {
        when(orderService.getOrder(55L)).thenReturn(order(55L));

        mockMvc.perform(get("/api/orders/55").with(authentication(auth(SAM))))
                .andExpect(status().isOk());
    }

    private static Authentication auth(AuthenticatedUser user) {
        return UsernamePasswordAuthenticationToken.authenticated(user, null, user.authorities());
    }

    private static OrderDto order(Long id) {
        return new OrderDto(id, OrderStatus.CREATED, "EUR",
                List.of(new OrderDto.Line(1L, "Mechanical Keyboard", new BigDecimal("89.90"), 2, new BigDecimal("179.80"))),
                new BigDecimal("179.80"), new BigDecimal("10"), new BigDecimal("17.98"), new BigDecimal("161.82"),
                null, Instant.parse("2026-11-02T09:30:00Z"));
    }
}
