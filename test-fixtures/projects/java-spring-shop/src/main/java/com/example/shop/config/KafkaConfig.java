package com.example.shop.config;

import org.apache.kafka.clients.admin.NewTopic;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.TopicBuilder;

@Configuration
public class KafkaConfig {

    private static final int PARTITIONS = 6;
    private static final int REPLICAS = 3;

    @Bean
    public NewTopic orderPlacedTopic(ShopKafkaProperties properties) {
        return TopicBuilder.name(properties.topics().orderPlaced())
                .partitions(PARTITIONS)
                .replicas(REPLICAS)
                .config("min.insync.replicas", "2")
                .build();
    }

    @Bean
    public NewTopic orderStatusChangedTopic(ShopKafkaProperties properties) {
        return TopicBuilder.name(properties.topics().orderStatusChanged())
                .partitions(PARTITIONS)
                .replicas(REPLICAS)
                .config("min.insync.replicas", "2")
                .build();
    }
}
