CREATE TABLE refunds (
    id                BIGSERIAL     PRIMARY KEY,
    order_id          BIGINT        NOT NULL REFERENCES orders (id),
    requested_by      BIGINT        NOT NULL REFERENCES users (id),
    amount            NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    currency          CHAR(3)       NOT NULL,
    status            VARCHAR(20)   NOT NULL,
    reason            VARCHAR(500)  NOT NULL,
    gateway_reference VARCHAR(64),
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
    completed_at      TIMESTAMPTZ
);

CREATE TABLE refund_lines (
    refund_id  BIGINT        NOT NULL REFERENCES refunds (id) ON DELETE CASCADE,
    product_id BIGINT        NOT NULL,
    quantity   INTEGER       NOT NULL CHECK (quantity > 0),
    amount     NUMERIC(12,2) NOT NULL
);

CREATE INDEX idx_refunds_order ON refunds (order_id);
