"""Staff operations API for TinyCars demo stores."""

from __future__ import annotations

import hmac
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import Literal

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field
from psycopg.rows import dict_row


log = logging.getLogger("tinycars.operations")
logging.basicConfig(level=logging.INFO)
LOCATIONS = ("warehouse", "boston", "chicago", "london")
Location = Literal["warehouse", "boston", "chicago", "london"]
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "tinycars")


def db():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "postgres"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "tinycars"),
        user=os.getenv("DB_USER", "tinycars"),
        password=os.getenv("DB_PASSWORD", "tinycars"),
        row_factory=dict_row,
    )


def require_admin(x_admin_token: str = Header(default="")):
    if not hmac.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(401, "unauthorized")


def fail(status: int, message: str):
    raise HTTPException(status, message)


def ident(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def rows(cursor):
    return cursor.fetchall()


@asynccontextmanager
async def lifespan(_: FastAPI):
    schema = Path(__file__).with_name("schema.sql").read_text()
    for attempt in range(30):
        try:
            with db() as conn:
                for statement in schema.split(";"):
                    if statement.strip():
                        conn.execute(statement)
            break
        except psycopg.Error:
            if attempt == 29:
                raise
            time.sleep(2)
    log.info("operations schema ready")
    yield


app = FastAPI(title="tinycars-operations", lifespan=lifespan)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/ops/summary", dependencies=[Depends(require_admin)])
def summary():
    with db() as conn:
        result = conn.execute("""
          SELECT
            (SELECT count(*) FROM stock WHERE qty < 8) AS low_stock,
            (SELECT count(*) FROM purchase_orders WHERE status <> 'received') AS open_purchase_orders,
            (SELECT count(*) FROM returns WHERE status = 'requested') AS open_returns,
            (SELECT count(*) FROM orders o LEFT JOIN shipments s USING(order_id)
              WHERE o.channel = 'web' AND o.status = 'completed' AND s.order_id IS NULL) AS awaiting_shipping,
            (SELECT coalesce(sum(total), 0) FROM orders
              WHERE status = 'completed' AND currency = 'USD'
                AND created_at >= now() - interval '30 days') AS sales_30d_usd,
            (SELECT coalesce(sum(total), 0) FROM orders
              WHERE status = 'completed' AND currency = 'GBP'
                AND created_at >= now() - interval '30 days') AS sales_30d_gbp
        """).fetchone()
    return result


@app.get("/ops/products", dependencies=[Depends(require_admin)])
def products():
    with db() as conn:
        return rows(conn.execute("SELECT sku, name, category, price_usd, price_gbp FROM products ORDER BY sku"))


@app.get("/ops/stock", dependencies=[Depends(require_admin)])
def stock(location: Location | None = None, low_only: bool = False):
    with db() as conn:
        return rows(conn.execute("""
          SELECT s.sku, p.name, p.category, s.location, s.qty, s.updated_at
          FROM stock s JOIN products p USING(sku)
          WHERE (%s::text IS NULL OR s.location = %s) AND (NOT %s OR s.qty < 8)
          ORDER BY s.qty, s.location, s.sku LIMIT 500
        """, (location, location, low_only)))


@app.get("/ops/movements", dependencies=[Depends(require_admin)])
def movements(limit: int = Query(30, ge=1, le=100)):
    with db() as conn:
        return rows(conn.execute("""
          SELECT movement_id, sku, location, delta, kind, reference, created_at
          FROM inventory_movements ORDER BY movement_id DESC LIMIT %s
        """, (limit,)))


class Adjustment(BaseModel):
    sku: str
    location: Location
    delta: int = Field(ge=-10000, le=10000)
    reason: str = Field(min_length=3, max_length=160)


def add_movement(conn, sku: str, location: str, delta: int, kind: str, reference: str):
    conn.execute("""
      INSERT INTO inventory_movements(sku, location, delta, kind, reference)
      VALUES (%s, %s, %s, %s, %s)
    """, (sku, location, delta, kind, reference))


def add_stock(conn, sku: str, location: str, qty: int):
    conn.execute("""
      INSERT INTO stock(sku, location, qty) VALUES (%s, %s, %s)
      ON CONFLICT (sku, location) DO UPDATE SET qty = stock.qty + EXCLUDED.qty, updated_at = now()
    """, (sku, location, qty))


def take_stock(conn, sku: str, location: str, qty: int):
    result = conn.execute("""
      UPDATE stock SET qty = qty - %s, updated_at = now()
      WHERE sku = %s AND location = %s AND qty >= %s RETURNING qty
    """, (qty, sku, location, qty)).fetchone()
    if not result:
        fail(409, "insufficient stock")


@app.post("/ops/stock/adjust", dependencies=[Depends(require_admin)])
def adjust(req: Adjustment):
    if req.delta == 0:
        fail(400, "delta must not be zero")
    with db() as conn:
        if not conn.execute("SELECT 1 FROM products WHERE sku = %s", (req.sku,)).fetchone():
            fail(404, "unknown SKU")
        if req.delta > 0:
            add_stock(conn, req.sku, req.location, req.delta)
        else:
            take_stock(conn, req.sku, req.location, -req.delta)
        add_movement(conn, req.sku, req.location, req.delta, "adjustment", req.reason)
    return {"sku": req.sku, "location": req.location, "delta": req.delta}


class Transfer(BaseModel):
    sku: str
    source: Location
    destination: Location
    qty: int = Field(gt=0, le=10000)


@app.post("/ops/stock/transfer", dependencies=[Depends(require_admin)])
def transfer(req: Transfer):
    if req.source == req.destination:
        fail(400, "source and destination must differ")
    with db() as conn:
        take_stock(conn, req.sku, req.source, req.qty)
        add_stock(conn, req.sku, req.destination, req.qty)
        reference = ident("MOVE")
        add_movement(conn, req.sku, req.source, -req.qty, "transfer", reference)
        add_movement(conn, req.sku, req.destination, req.qty, "transfer", reference)
    return {"reference": reference, **req.model_dump()}


class PurchaseItem(BaseModel):
    sku: str
    qty: int = Field(gt=0, le=10000)
    unit_cost: Decimal = Field(ge=0, max_digits=10, decimal_places=2)


class PurchaseOrder(BaseModel):
    supplier: str = Field(min_length=2, max_length=120)
    destination: Location
    items: list[PurchaseItem] = Field(min_length=1, max_length=100)


@app.get("/ops/purchase-orders", dependencies=[Depends(require_admin)])
def purchase_orders():
    with db() as conn:
        orders = rows(conn.execute("""
          SELECT po_id, supplier, destination, status, created_at, received_at
          FROM purchase_orders ORDER BY created_at DESC LIMIT 100
        """))
        for order in orders:
            order["items"] = rows(conn.execute("""
              SELECT i.sku, p.name, i.qty, i.received_qty, i.unit_cost
              FROM purchase_order_items i JOIN products p USING(sku)
              WHERE i.po_id = %s ORDER BY i.sku
            """, (order["po_id"],)))
    return orders


@app.post("/ops/purchase-orders", status_code=201, dependencies=[Depends(require_admin)])
def create_purchase_order(req: PurchaseOrder):
    skus = [item.sku for item in req.items]
    if len(set(skus)) != len(skus):
        fail(400, "duplicate SKU in purchase order")
    po_id = ident("PO")
    with db() as conn:
        found = {r["sku"] for r in rows(conn.execute("SELECT sku FROM products WHERE sku = ANY(%s)", (skus,)))}
        if found != set(skus):
            fail(404, f"unknown SKU: {', '.join(sorted(set(skus) - found))}")
        conn.execute("INSERT INTO purchase_orders(po_id, supplier, destination, status) VALUES (%s, %s, %s, 'open')",
                     (po_id, req.supplier, req.destination))
        for item in req.items:
            conn.execute("INSERT INTO purchase_order_items(po_id, sku, qty, unit_cost) VALUES (%s, %s, %s, %s)",
                         (po_id, item.sku, item.qty, item.unit_cost))
    log.info("purchase order created po_id=%s supplier=%s", po_id, req.supplier)
    return {"po_id": po_id, "status": "open"}


class ReceiveItem(BaseModel):
    sku: str
    qty: int = Field(gt=0, le=10000)


class ReceivePurchaseOrder(BaseModel):
    items: list[ReceiveItem] | None = None  # omitted = receive all remaining units


@app.post("/ops/purchase-orders/{po_id}/receive", dependencies=[Depends(require_admin)])
def receive_purchase_order(po_id: str, req: ReceivePurchaseOrder):
    with db() as conn:
        order = conn.execute("SELECT * FROM purchase_orders WHERE po_id = %s FOR UPDATE", (po_id,)).fetchone()
        if not order:
            fail(404, "purchase order not found")
        if order["status"] == "received":
            fail(409, "purchase order already received")
        lines = {r["sku"]: r for r in rows(conn.execute(
            "SELECT sku, qty, received_qty FROM purchase_order_items WHERE po_id = %s FOR UPDATE", (po_id,)))}
        incoming = ({item.sku: item.qty for item in req.items} if req.items is not None
                    else {sku: line["qty"] - line["received_qty"] for sku, line in lines.items()})
        if not incoming or (req.items is not None and len(incoming) != len(req.items)):
            fail(400, "choose one or more distinct items")
        for sku, qty in incoming.items():
            line = lines.get(sku)
            if not line or qty <= 0 or qty > line["qty"] - line["received_qty"]:
                fail(409, f"invalid remaining quantity for {sku}")
        for sku, qty in incoming.items():
            conn.execute("UPDATE purchase_order_items SET received_qty = received_qty + %s WHERE po_id = %s AND sku = %s",
                         (qty, po_id, sku))
            add_stock(conn, sku, order["destination"], qty)
            add_movement(conn, sku, order["destination"], qty, "purchase receipt", po_id)
        remaining = conn.execute("""
          SELECT count(*) AS count FROM purchase_order_items WHERE po_id = %s AND received_qty < qty
        """, (po_id,)).fetchone()["count"]
        status = "partial" if remaining else "received"
        conn.execute("UPDATE purchase_orders SET status = %s, received_at = CASE WHEN %s = 'received' THEN now() ELSE NULL END WHERE po_id = %s",
                     (status, status, po_id))
    log.info("purchase order received po_id=%s status=%s", po_id, status)
    return {"po_id": po_id, "status": status, "received": incoming}


def order_lines(conn, order_id: str):
    return rows(conn.execute("""
      SELECT oi.sku, p.name, oi.qty, oi.unit_price
      FROM order_items oi JOIN products p USING(sku) WHERE oi.order_id = %s
    """, (order_id,)))


@app.get("/ops/orders", dependencies=[Depends(require_admin)])
def customer_orders(limit: int = Query(80, ge=1, le=200), search: str = Query("", max_length=100)):
    pattern = f"%{search.strip()}%"
    with db() as conn:
        orders = rows(conn.execute("""
          SELECT o.order_id, o.created_at, o.channel, o.location, o.customer_email,
                 o.currency, o.total, o.status, o.payment_status,
                 s.shipment_id, s.carrier, s.tracking_number, s.status AS shipping_status
          FROM orders o LEFT JOIN shipments s USING(order_id)
          WHERE (%s = '' OR o.order_id ILIKE %s OR o.customer_email ILIKE %s OR o.location ILIKE %s)
          ORDER BY o.created_at DESC LIMIT %s
        """, (search.strip(), pattern, pattern, pattern, limit)))
        if orders:
            lines = rows(conn.execute("""
              SELECT oi.order_id, oi.sku, p.name, oi.qty, oi.unit_price
              FROM order_items oi JOIN products p USING(sku)
              WHERE oi.order_id = ANY(%s)
            """, ([order["order_id"] for order in orders],)))
            by_order = {order["order_id"]: [] for order in orders}
            for line in lines:
                by_order[line.pop("order_id")].append(line)
            for order in orders:
                order["items"] = by_order[order["order_id"]]
    return orders


@app.get("/ops/orders/{order_id}", dependencies=[Depends(require_admin)])
def customer_order(order_id: str):
    with db() as conn:
        order = conn.execute("""
          SELECT order_id, created_at, channel, location, customer_email, currency,
                 total, status, payment_status FROM orders WHERE order_id = %s
        """, (order_id,)).fetchone()
        if not order:
            fail(404, "order not found")
        order["items"] = order_lines(conn, order_id)
    return order


class ShipOrder(BaseModel):
    order_id: str
    carrier: str = Field(min_length=2, max_length=80)
    tracking_number: str | None = Field(default=None, max_length=80)


@app.get("/ops/shipments", dependencies=[Depends(require_admin)])
def shipments():
    with db() as conn:
        return rows(conn.execute("""
          SELECT s.shipment_id, s.order_id, s.carrier, s.tracking_number, s.status,
                 s.shipped_at, s.delivered_at, o.customer_email, o.location
          FROM shipments s JOIN orders o USING(order_id) ORDER BY shipped_at DESC LIMIT 100
        """))


@app.post("/ops/shipments", status_code=201, dependencies=[Depends(require_admin)])
def ship_order(req: ShipOrder):
    shipment_id = ident("SHIP")
    tracking = req.tracking_number or ident("TC")
    with db() as conn:
        order = conn.execute("SELECT order_id, channel, status, payment_status FROM orders WHERE order_id = %s FOR UPDATE",
                             (req.order_id,)).fetchone()
        if not order:
            fail(404, "order not found")
        if order["channel"] != "web" or order["status"] != "completed" or order["payment_status"] != "approved":
            fail(409, "only paid web orders can be shipped")
        if conn.execute("SELECT 1 FROM shipments WHERE order_id = %s", (req.order_id,)).fetchone():
            fail(409, "order already shipped")
        conn.execute("""
          INSERT INTO shipments(shipment_id, order_id, carrier, tracking_number, status)
          VALUES (%s, %s, %s, %s, 'shipped')
        """, (shipment_id, req.order_id, req.carrier, tracking))
    log.info("order shipped order_id=%s shipment_id=%s", req.order_id, shipment_id)
    return {"shipment_id": shipment_id, "order_id": req.order_id, "tracking_number": tracking, "status": "shipped"}


@app.post("/ops/shipments/{shipment_id}/deliver", dependencies=[Depends(require_admin)])
def deliver_shipment(shipment_id: str):
    with db() as conn:
        result = conn.execute("""
          UPDATE shipments SET status = 'delivered', delivered_at = now()
          WHERE shipment_id = %s AND status = 'shipped' RETURNING shipment_id, order_id, status
        """, (shipment_id,)).fetchone()
        if not result:
            fail(409, "shipment not found or already delivered")
    return result


class RequestReturn(BaseModel):
    order_id: str
    sku: str
    qty: int = Field(gt=0, le=10000)
    reason: str = Field(min_length=3, max_length=200)


@app.get("/ops/returns", dependencies=[Depends(require_admin)])
def returns():
    with db() as conn:
        return rows(conn.execute("""
          SELECT r.return_id, r.order_id, r.sku, p.name, r.qty, r.reason, r.status,
                 r.refund_amount, r.refund_status, r.restock_location,
                 r.requested_at, r.received_at, o.currency, o.location, o.customer_email
          FROM returns r JOIN orders o USING(order_id) JOIN products p USING(sku)
          ORDER BY r.requested_at DESC LIMIT 100
        """))


@app.post("/ops/returns", status_code=201, dependencies=[Depends(require_admin)])
def request_return(req: RequestReturn):
    return_id = ident("RET")
    with db() as conn:
        order = conn.execute("SELECT status, payment_status FROM orders WHERE order_id = %s FOR UPDATE",
                             (req.order_id,)).fetchone()
        if not order:
            fail(404, "order not found")
        if order["status"] != "completed" or order["payment_status"] != "approved":
            fail(409, "only paid orders can be returned")
        purchased = conn.execute("""
          SELECT coalesce(sum(qty),0) AS qty, coalesce(sum(qty * unit_price),0) AS total
          FROM order_items WHERE order_id = %s AND sku = %s
        """, (req.order_id, req.sku)).fetchone()
        committed = conn.execute("""
          SELECT coalesce(sum(qty),0) AS qty FROM returns
          WHERE order_id = %s AND sku = %s AND status <> 'rejected'
        """, (req.order_id, req.sku)).fetchone()["qty"]
        if purchased["qty"] < req.qty + committed:
            fail(409, "return quantity exceeds purchased quantity")
        refund = (purchased["total"] * req.qty / purchased["qty"]).quantize(Decimal("0.01"))
        conn.execute("""
          INSERT INTO returns(return_id, order_id, sku, qty, reason, status, refund_amount)
          VALUES (%s, %s, %s, %s, %s, 'requested', %s)
        """, (return_id, req.order_id, req.sku, req.qty, req.reason, refund))
    log.info("return requested return_id=%s order_id=%s", return_id, req.order_id)
    return {"return_id": return_id, "status": "requested", "refund_amount": refund}


class ReceiveReturn(BaseModel):
    restock: bool = True
    location: Location | None = None


@app.post("/ops/returns/{return_id}/receive", dependencies=[Depends(require_admin)])
def receive_return(return_id: str, req: ReceiveReturn):
    with db() as conn:
        item = conn.execute("""
          SELECT r.*, o.channel, o.location AS order_location FROM returns r
          JOIN orders o USING(order_id) WHERE r.return_id = %s FOR UPDATE
        """, (return_id,)).fetchone()
        if not item:
            fail(404, "return not found")
        if item["status"] != "requested":
            fail(409, "return already processed")
        location = req.location or ("warehouse" if item["channel"] == "web" else item["order_location"])
        if location not in LOCATIONS:
            fail(400, "invalid restock location")
        if req.restock:
            add_stock(conn, item["sku"], location, item["qty"])
            add_movement(conn, item["sku"], location, item["qty"], "return", return_id)
        conn.execute("""
          UPDATE returns SET status = 'received', refund_status = 'recorded',
            restock_location = %s, received_at = now() WHERE return_id = %s
        """, (location if req.restock else None, return_id))
    log.info("return received return_id=%s restock=%s", return_id, req.restock)
    return {"return_id": return_id, "status": "received", "refund_status": "recorded", "restock_location": location if req.restock else None}


@app.post("/ops/returns/{return_id}/reject", dependencies=[Depends(require_admin)])
def reject_return(return_id: str):
    with db() as conn:
        result = conn.execute("""
          UPDATE returns SET status = 'rejected', refund_status = 'cancelled'
          WHERE return_id = %s AND status = 'requested' RETURNING return_id, status
        """, (return_id,)).fetchone()
        if not result:
            fail(409, "return not found or already processed")
    return result
