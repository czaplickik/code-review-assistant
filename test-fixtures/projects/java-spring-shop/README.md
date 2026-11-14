# shop

Spring Boot 3 e-shop backend servcie: catalogue, orders, payments and customer accounts.

## Requirements

- Java 21
- Docker (PostgreSQL 16 and Kafka for local development)
- Maven 3.9+

## Running locally

```bash
docker compose up -d postgres kafka
./scripts/seed-local-db.sh
mvn spring-boot:run -Dspring-boot.run.profiles=local
```

The API listens on `http://localhost:8080`. Obtain a token via `POST /api/auth/login`
and send it as `Authorization: Bearer <token>`.

## Tests

```bash
mvn test                 # unit + web slice tests
mvn verify -Dgroups=integration   # Testcontainers-based integration tests
```

## Project docs

- [Conventions](docs/architecture/conventions.md) — read before opening a PR.
- Design specs and implementation plans live in `docs/superpowers/`.

## Modules

| Package                          | Responsibility                                     |
|----------------------------------|----------------------------------------------------|
| `com.example.shop.order`         | Order placement, state machine, Kafka events       |
| `com.example.shop.payment`       | Payment gateway client (capture)                   |
| `com.example.shop.product`       | Product catalogue and stock                        |
| `com.example.shop.user`          | Customer and staff accounts                        |
| `com.example.shop.security`      | JWT authentication, refresh tokens, authorization  |
| `com.example.shop.common`        | `Money`, error handling, small utilities           |
| `com.example.shop.config`        | Cross-cutting Spring configuration                 |
