-- Customer Support Agent — SQLite schema (HuggingFace Spaces deployment)
-- Functionally equivalent to schema.sql but adapted for SQLite syntax.

CREATE TABLE IF NOT EXISTS users (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    id             TEXT PRIMARY KEY,
    sku            TEXT UNIQUE NOT NULL,
    name           TEXT NOT NULL,
    description    TEXT,
    price          REAL,
    in_stock       INTEGER NOT NULL DEFAULT 1,
    return_policy  TEXT NOT NULL DEFAULT '30 days'
);

CREATE TABLE IF NOT EXISTS orders (
    id                  TEXT PRIMARY KEY,
    order_id            TEXT UNIQUE NOT NULL,
    user_id             TEXT REFERENCES users(id) ON DELETE SET NULL,
    status              TEXT NOT NULL,
    items               TEXT NOT NULL,
    total_amount        REAL,
    tracking_number     TEXT,
    estimated_delivery  TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status  ON orders(status);

CREATE TABLE IF NOT EXISTS tickets (
    id              TEXT PRIMARY KEY,
    ticket_id       TEXT UNIQUE NOT NULL,
    session_id      TEXT,
    issue_summary   TEXT NOT NULL,
    priority        TEXT NOT NULL DEFAULT 'medium',
    status          TEXT NOT NULL DEFAULT 'open',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tickets_session ON tickets(session_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status  ON tickets(status);
