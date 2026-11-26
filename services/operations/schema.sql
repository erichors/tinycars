CREATE TABLE IF NOT EXISTS purchase_orders (
  po_id text PRIMARY KEY,
  supplier text NOT NULL,
  destination text NOT NULL,
  status text NOT NULL CHECK (status IN ('open', 'partial', 'received')),
  created_at timestamptz NOT NULL DEFAULT now(),
  received_at timestamptz
);
CREATE TABLE IF NOT EXISTS purchase_order_items (
  po_id text NOT NULL REFERENCES purchase_orders(po_id),
  sku text NOT NULL REFERENCES products(sku),
  qty integer NOT NULL CHECK (qty > 0),
  received_qty integer NOT NULL DEFAULT 0 CHECK (received_qty >= 0 AND received_qty <= qty),
  unit_cost numeric(10,2) NOT NULL CHECK (unit_cost >= 0),
  PRIMARY KEY (po_id, sku)
);
CREATE TABLE IF NOT EXISTS inventory_movements (
  movement_id bigserial PRIMARY KEY,
  sku text NOT NULL REFERENCES products(sku),
  location text NOT NULL,
  delta integer NOT NULL CHECK (delta <> 0),
  kind text NOT NULL,
  reference text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_inventory_movements_recent ON inventory_movements(created_at DESC);
CREATE TABLE IF NOT EXISTS shipments (
  shipment_id text PRIMARY KEY,
  order_id text NOT NULL UNIQUE REFERENCES orders(order_id),
  carrier text NOT NULL,
  tracking_number text NOT NULL,
  status text NOT NULL CHECK (status IN ('shipped', 'delivered')),
  shipped_at timestamptz NOT NULL DEFAULT now(),
  delivered_at timestamptz
);
CREATE TABLE IF NOT EXISTS returns (
  return_id text PRIMARY KEY,
  order_id text NOT NULL REFERENCES orders(order_id),
  sku text NOT NULL REFERENCES products(sku),
  qty integer NOT NULL CHECK (qty > 0),
  reason text NOT NULL,
  status text NOT NULL CHECK (status IN ('requested', 'received', 'rejected')),
  refund_amount numeric(10,2) NOT NULL,
  refund_status text NOT NULL DEFAULT 'pending',
  restock_location text,
  requested_at timestamptz NOT NULL DEFAULT now(),
  received_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_returns_order_sku ON returns(order_id, sku);
