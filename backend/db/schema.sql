-- Customer Support Agent — Postgres schema
-- Mounted into docker-entrypoint-initdb.d so it runs once on cluster init.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       VARCHAR(100) NOT NULL,
    email      VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku            VARCHAR(50) UNIQUE NOT NULL,
    name           VARCHAR(200) NOT NULL,
    description    TEXT,
    price          DECIMAL(10, 2),
    in_stock       BOOLEAN NOT NULL DEFAULT TRUE,
    return_policy  VARCHAR(50) NOT NULL DEFAULT '30 days'
);

CREATE TABLE IF NOT EXISTS orders (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id            VARCHAR(20) UNIQUE NOT NULL,         -- e.g. ORD-2024-0001
    user_id             UUID REFERENCES users(id) ON DELETE SET NULL,
    status              VARCHAR(50) NOT NULL,                -- pending|processing|shipped|delivered|cancelled
    items               JSONB NOT NULL,
    total_amount        DECIMAL(10, 2),
    tracking_number     VARCHAR(100),
    estimated_delivery  DATE,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status  ON orders(status);

CREATE TABLE IF NOT EXISTS tickets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id       VARCHAR(20) UNIQUE NOT NULL,             -- e.g. TKT-2024-0001
    session_id      VARCHAR(100),
    issue_summary   TEXT NOT NULL,
    priority        VARCHAR(20) NOT NULL DEFAULT 'medium',   -- low|medium|high|urgent
    status          VARCHAR(20) NOT NULL DEFAULT 'open',     -- open|in_progress|resolved|closed
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tickets_session ON tickets(session_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status  ON tickets(status);
