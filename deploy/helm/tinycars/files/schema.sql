-- TinyCars schema (Postgres). Applied automatically on first boot before seed.sql.
CREATE TABLE IF NOT EXISTS products (
  sku          text PRIMARY KEY,
  name         text NOT NULL,
  category     text NOT NULL,
  body         text,
  era          text,
  color        text,
  description  text,
  price_usd    numeric(8,2) NOT NULL,
  price_gbp    numeric(8,2) NOT NULL,
  weight_class text NOT NULL,
  image        text NOT NULL,
  new_arrival  boolean NOT NULL DEFAULT false,
  specs        jsonb NOT NULL DEFAULT '{}'::jsonb,   -- scale, finish, features, hotspots for the detail view
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

CREATE TABLE IF NOT EXISTS stock (
  sku        text NOT NULL REFERENCES products(sku),
  location   text NOT NULL,           -- warehouse | boston | chicago | london
  qty        integer NOT NULL CHECK (qty >= 0),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (sku, location)
);

CREATE TABLE IF NOT EXISTS orders (
  order_id       text PRIMARY KEY,
  created_at     timestamptz NOT NULL DEFAULT now(),
  channel        text NOT NULL,       -- web | in_store
  location       text NOT NULL,
  customer_email text NOT NULL,
  currency       text NOT NULL,
  total          numeric(10,2) NOT NULL,
  status         text NOT NULL,       -- completed | declined
  payment_status text NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);

CREATE TABLE IF NOT EXISTS order_items (
  id         serial PRIMARY KEY,
  order_id   text NOT NULL REFERENCES orders(order_id),
  sku        text NOT NULL,
  qty        integer NOT NULL,
  unit_price numeric(8,2) NOT NULL
);
-- intentionally no index on order_items(sku): the inventory_slow_query pattern scans it
