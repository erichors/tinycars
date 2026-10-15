"""TinyCars catalog service (Python / FastAPI).

Plain app code: no OpenTelemetry imports. Tracing comes from the OTel Operator
(inject-python annotation). Problem-pattern state is read from Redis (tc:flags).
"""
import json
import logging
import os
import random
import sys
import time
from contextlib import asynccontextmanager
from decimal import Decimal

import redis
from fastapi import FastAPI, HTTPException, Query
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "tinycars")
DB_USER = os.getenv("DB_USER", "tinycars")
DB_PASSWORD = os.getenv("DB_PASSWORD", "tinycars")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DSN = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


class JsonFormatter(logging.Formatter):
    def format(self, record):
        out = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"), "level": record.levelname,
               "service": "catalog", "msg": record.getMessage()}
        out.update(getattr(record, "extra_fields", {}))
        return json.dumps(out)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
log = logging.getLogger("catalog")
log.setLevel(logging.INFO)
log.handlers = [handler]
log.propagate = False


def event(msg, level=logging.INFO, **fields):
    log.log(level, msg, extra={"extra_fields": fields})


pool = ConnectionPool(DSN, min_size=1, max_size=8, kwargs={"row_factory": dict_row}, open=False)
rds = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=1, socket_connect_timeout=1)
_cache = {"t": 0.0, "v": {}}


def flag_level(name: str) -> int:
    """Return problem-pattern level (0 = off) from Redis, cached for 2 seconds."""
    now = time.time()
    if now - _cache["t"] > 2:
        try:
            _cache["v"] = {k: json.loads(v) for k, v in rds.hgetall("tc:flags").items()}
        except Exception as exc:  # keep serving with the last known flags
            event("flag refresh failed", logging.WARNING, error=str(exc))
        _cache["t"] = now
    f = _cache["v"].get(name)
    return int(f.get("level", 1)) if f and f.get("on") else 0


def clean(row: dict) -> dict:
    return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in row.items()}


@asynccontextmanager
async def lifespan(_: FastAPI):
    pool.open(wait=True, timeout=30)
    event("catalog started")
    yield
    pool.close()


app = FastAPI(title="tinycars-catalog", lifespan=lifespan)

COLS = "sku,name,category,body,era,color,description,price_usd,price_gbp,weight_class,image,new_arrival,specs"


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    with pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ready"}


@app.get("/categories")
def categories():
    with pool.connection() as conn:
        rows = conn.execute("SELECT category AS name, count(*) AS count FROM products GROUP BY category ORDER BY 1").fetchall()
    return [clean(r) for r in rows]


@app.get("/products")
def products(category: str | None = None, new: bool = False, limit: int = Query(100, le=200)):
    sql, args = f"SELECT {COLS} FROM products", []
    where = []
    if category:
        where.append("category = %s")
        args.append(category)
    if new:
        where.append("new_arrival")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY sku LIMIT %s"
    args.append(limit)
    with pool.connection() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [clean(r) for r in rows]


@app.get("/products/{sku}")
def product(sku: str):
    with pool.connection() as conn:
        row = conn.execute(f"SELECT {COLS} FROM products WHERE sku = %s", (sku,)).fetchone()
    if not row:
        raise HTTPException(404, "unknown sku")
    return clean(row)


@app.get("/search")
def search(q: str = Query(..., min_length=1), limit: int = Query(50, le=100)):
    level = flag_level("catalog_search_slowdown")
    if level:
        delay = 0.4 * level
        event("problem pattern active", logging.WARNING, pattern="catalog_search_slowdown", pattern_level=level, delay_s=delay)
        time.sleep(delay)
        if level >= 3 and random.random() < (level - 2) * 0.2:
            event("search upstream timeout", logging.ERROR, pattern="catalog_search_slowdown")
            raise HTTPException(503, "search aggregator timed out")
    like = f"%{q}%"
    with pool.connection() as conn:
        rows = conn.execute(
            f"SELECT {COLS} FROM products WHERE name ILIKE %s OR category ILIKE %s OR description ILIKE %s "
            "ORDER BY sku LIMIT %s", (like, like, like, limit)).fetchall()
    return [clean(r) for r in rows]
