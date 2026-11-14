package com.example.shop.order.repository;

import com.example.shop.order.domain.Order;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface OrderRepository extends JpaRepository<Order, Long> {

    @Query("select o.userId from Order o where o.id = :id")
    Optional<Long> findOwnerIdById(@Param("id") Long id);

    @EntityGraph(attributePaths = "items")
    Optional<Order> findWithItemsById(Long id);

    // items are loaded in batches (hibernate.default_batch_fetch_size), not via fetch join + paging
    Page<Order> findByUserIdOrderByCreatedAtDesc(Long userId, Pageable pageable);
}
