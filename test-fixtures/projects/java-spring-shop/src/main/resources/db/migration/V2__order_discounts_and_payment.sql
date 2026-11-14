ALTER TABLE orders
    ADD COLUMN discount_percent  NUMERIC(5,2)  NOT NULL DEFAULT 0,
    ADD COLUMN discount_amount   NUMERIC(12,2) NOT NULL DEFAULT 0,
    ADD COLUMN payment_reference VARCHAR(64),
    ADD COLUMN paid_at           TIMESTAMPTZ;

ALTER TABLE orders
    ADD CONSTRAINT chk_orders_discount_percent CHECK (discount_percent BETWEEN 0 AND 30);

CREATE INDEX idx_orders_user_created ON orders (user_id, created_at DESC);
CREATE INDEX idx_order_items_order ON order_items (order_id);
