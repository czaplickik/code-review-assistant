package com.example.shop.order.repository;

import com.example.shop.order.domain.Refund;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface RefundRepository extends JpaRepository<Refund, Long> {

    List<Refund> findByOrderIdOrderByCreatedAtDesc(Long orderId);
}
