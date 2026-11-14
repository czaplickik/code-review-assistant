CREATE TABLE users (
    id            BIGSERIAL    PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(100) NOT NULL,
    full_name     VARCHAR(200) NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'USER',
    enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE products (
    id             BIGSERIAL     PRIMARY KEY,
    sku            VARCHAR(32)   NOT NULL UNIQUE,
    name           VARCHAR(200)  NOT NULL,
    slug           VARCHAR(220)  NOT NULL UNIQUE,
    description    TEXT,
    price_amount   NUMERIC(12,2) NOT NULL CHECK (price_amount >= 0),
    price_currency CHAR(3)       NOT NULL,
    stock          INTEGER       NOT NULL DEFAULT 0 CHECK (stock >= 0),
    active         BOOLEAN       NOT NULL DEFAULT TRUE,
    version        BIGINT        NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE orders (
    id              BIGSERIAL     PRIMARY KEY,
    user_id         BIGINT        NOT NULL REFERENCES users (id),
    status          VARCHAR(20)   NOT NULL,
    currency        CHAR(3)       NOT NULL,
    subtotal_amount NUMERIC(12,2) NOT NULL,
    total_amount    NUMERIC(12,2) NOT NULL,
    version         BIGINT        NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE order_items (
    id                BIGSERIAL     PRIMARY KEY,
    order_id          BIGINT        NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    product_id        BIGINT        NOT NULL REFERENCES products (id),
    product_name      VARCHAR(200)  NOT NULL,
    unit_price_amount NUMERIC(12,2) NOT NULL,
    quantity          INTEGER       NOT NULL CHECK (quantity > 0),
    line_total_amount NUMERIC(12,2) NOT NULL
);

CREATE TABLE refresh_tokens (
    id         BIGSERIAL   PRIMARY KEY,
    token_hash CHAR(64)    NOT NULL UNIQUE,
    user_id    BIGINT      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked    BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_refresh_tokens_user ON refresh_tokens (user_id);
