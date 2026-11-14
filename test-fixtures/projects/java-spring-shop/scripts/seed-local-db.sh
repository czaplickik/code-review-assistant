#!/usr/bin/env bash
# Seeds the local development database with a handful of products and two users.
# Usage: ./scripts/seed-local-db.sh   (expects docker compose postgres to be running)
set -euo pipefail

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-shop}"
DB_USER="${DB_USER:-shop}"
export PGPASSWORD="${DB_PASSWORD:-shop}"

# bcrypt(12) of "password" - local only
DEV_HASH='$2a$12$R9h/cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss7KIUgO2t0jWMUW'

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<SQL
INSERT INTO users (email, password_hash, full_name, role)
VALUES ('alice@example.com', '$DEV_HASH', 'Alice Customer', 'USER'),
       ('sam.support@example.com', '$DEV_HASH', 'Sam Support', 'SUPPORT')
ON CONFLICT (email) DO NOTHING;

INSERT INTO products (sku, name, slug, description, price, stock, active)
VALUES ('KB-001', 'Mechanical Keyboard', 'mechanical-keyboard', 'Hot-swappable 75% keyboard', 89.90, 'EUR', 40, TRUE),
       ('MS-002', 'Wireless Mouse', 'wireless-mouse', 'Ergonomic 2.4 GHz mouse', 34.50, 'EUR', 120, TRUE),
       ('HB-003', 'USB-C Hub', 'usb-c-hub', '7-in-1 hub with HDMI', 49.00, 'EUR', 0, TRUE)
ON CONFLICT (sku) DO NOTHING;
SQL

echo "Seeded $DB_NAME on $DB_HOST:$DB_PORT"
