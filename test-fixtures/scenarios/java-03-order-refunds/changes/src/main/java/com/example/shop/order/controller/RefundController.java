package com.example.shop.order.controller;

import com.example.shop.order.domain.Refund;
import com.example.shop.order.dto.RefundRequest;
import com.example.shop.order.service.RefundService;
import com.example.shop.security.AuthenticatedUser;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/orders/{orderId}/refunds")
public class RefundController {

    private final RefundService refundService;

    public RefundController(RefundService refundService) {
        this.refundService = refundService;
    }

    @PostMapping
    @PreAuthorize("hasRole('USER')")
    public ResponseEntity<Refund> createRefund(@PathVariable Long orderId,
                                               @Valid @RequestBody RefundRequest request,
                                               @AuthenticationPrincipal AuthenticatedUser user) {
        Refund refund = refundService.refund(orderId, request, user);
        return ResponseEntity.status(HttpStatus.CREATED).body(refund);
    }

    @GetMapping
    @PreAuthorize("hasRole('USER') or hasRole('SUPPORT')")
    public List<Refund> listRefunds(@PathVariable Long orderId) {
        return refundService.listRefunds(orderId);
    }
}
