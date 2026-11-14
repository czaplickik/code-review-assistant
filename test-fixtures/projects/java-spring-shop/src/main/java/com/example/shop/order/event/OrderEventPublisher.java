package com.example.shop.order.event;

import com.example.shop.config.ShopKafkaProperties;
import java.nio.charset.StandardCharsets;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

/**
 * Bridges domain events (published via {@code ApplicationEventPublisher} inside a transaction)
 * to Kafka after the transaction commits. Key = order id, so all events of an order are ordered.
 */
@Component
public class OrderEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(OrderEventPublisher.class);

    static final String HEADER_EVENT_TYPE = "event-type";
    static final String HEADER_SCHEMA_VERSION = "schema-version";

    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final ShopKafkaProperties properties;

    public OrderEventPublisher(KafkaTemplate<String, Object> kafkaTemplate, ShopKafkaProperties properties) {
        this.kafkaTemplate = kafkaTemplate;
        this.properties = properties;
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void on(OrderPlacedEvent event) {
        send(properties.topics().orderPlaced(), event.orderId(), "OrderPlaced", event.schemaVersion(), event);
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void on(OrderStatusChangedEvent event) {
        send(properties.topics().orderStatusChanged(), event.orderId(), "OrderStatusChanged", event.schemaVersion(), event);
    }

    private void send(String topic, Long orderId, String eventType, int schemaVersion, Object payload) {
        ProducerRecord<String, Object> record = new ProducerRecord<>(topic, String.valueOf(orderId), payload);
        record.headers().add(HEADER_EVENT_TYPE, eventType.getBytes(StandardCharsets.UTF_8));
        record.headers().add(HEADER_SCHEMA_VERSION, Integer.toString(schemaVersion).getBytes(StandardCharsets.UTF_8));
        kafkaTemplate.send(record).whenComplete((result, ex) -> {
            if (ex != null) {
                log.error("Order event publish failed topic={} orderId={} eventType={}", topic, orderId, eventType, ex);
            } else {
                log.debug("Order event published topic={} orderId={} eventType={} offset={}",
                        topic, orderId, eventType, result.getRecordMetadata().offset());
            }
        });
    }
}
