"""TinyCars in-cluster load generator.

Reads its target from Redis (hash tc:load: running, rpm, web_pct) which the admin panel writes,
and drives realistic shopper sessions through the storefront API. Plain app code (no OTel imports);
the OTel Operator (inject-python) instruments it so load shows up as real traces.
"""
import asyncio
import json
import math
import os
import random
import sys
import time
import uuid
from collections import Counter

import httpx
import redis.asyncio as aioredis

BASE = os.getenv("STOREFRONT_URL", "http://storefront:8080")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
MAX_INFLIGHT = int(os.getenv("MAX_INFLIGHT", "150"))
STORES = ["boston", "chicago", "london"]
TERMS = ["truck", "coupe", "tank", "gold", "van", "racer", "dozer", "4x4", "classic", "army", "crane", "hatch"]
FIRST = ["alex", "sam", "jordan", "casey", "riley", "morgan", "taylor", "jamie", "drew", "avery"]
# Demo accounts seeded by tools/gen_catalog.py (password "tinycars"); ~30% of web shoppers sign in.
DEMO_USERS = ["alex.rivera", "priya.patel", "sam.okafor", "jordan.kim", "casey.nguyen", "morgan.rossi",
              "taylor.brooks", "riley.chen", "jamie.walker", "avery.lopez", "drew.murphy", "harper.singh"]
SIGN_IN_PCT = float(os.getenv("SIGN_IN_PCT", "30"))
AI_MATCH_PCT = float(os.getenv("AI_MATCH_PCT", "3"))
AI_PROMPTS = [
    ("personality", "Outdoorsy, adventurous, and happiest on a muddy trail"),
    ("personality", "Quiet, practical, and always prepared to help"),
    ("gift", "A gift for a competitive kid who loves speed and bright colors"),
    ("gift", "A retirement gift for a firefighter who collects unusual vehicles"),
    ("occasion", "A glamorous centerpiece for a milestone birthday"),
    ("occasion", "A playful car for a beach-themed summer party"),
    ("collection", "My collection has racers but needs a hardworking utility vehicle"),
    ("collection", "I collect classics and need one quirky centerpiece"),
    ("adventure", "A rough mountain camping trip with mud and no paved roads"),
    ("adventure", "A relaxed family road trip across the country"),
    ("nostalgia", "Chrome, diners, whitewalls, and memories of the 1950s"),
    ("nostalgia", "Colorful 1970s music festivals and carefree road trips"),
]
stats = Counter()


def log(level, msg, **kw):
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "level": level, "service": "loadgen", "msg": msg, **kw}), flush=True)


def poisson(lam: float) -> int:
    if lam <= 0:
        return 0
    limit, k, p = math.exp(-lam), 0, 1.0
    while p > limit:
        k += 1
        p *= random.random()
    return k - 1


async def session(client: httpx.AsyncClient, web: bool):
    cart = str(uuid.uuid4())
    if web:
        channel, location = "web", "warehouse"
        currency = "GBP" if random.random() < 0.12 else "USD"
    else:
        channel, location = "in_store", random.choice(STORES)
        currency = "GBP" if location == "london" else "USD"
    headers = {}
    try:
        if web and random.random() * 100 < SIGN_IN_PCT:
            user = random.choice(DEMO_USERS) + "@example.com"
            pw = "tinycars" if random.random() > 0.05 else "hunter2"  # a few fat-fingered passwords
            r = await client.post("/api/auth/login", json={"email": user, "password": pw, "remember": False})
            stats[f"login_{r.status_code}"] += 1
            if r.status_code == 200:
                headers = {"x-tc-session": r.json()["token"]}
                if random.random() < 0.3:
                    await client.get("/api/account/orders", headers=headers)
        cats = (await client.get("/api/catalog/categories")).json()
        if web and random.random() * 100 < AI_MATCH_PCT:
            scenario, prompt = random.choice(AI_PROMPTS)
            ai = await client.post("/api/catalog/match", json={"scenario": scenario, "text": prompt})
            stats[f"ai_{scenario}_{ai.status_code}"] += 1
        cat = random.choice(cats)["name"]
        prods = (await client.get("/api/catalog/products", params={"category": cat})).json()
        if random.random() < 0.25:
            await client.get("/api/catalog/search", params={"q": random.choice(TERMS)})
        picks = random.sample(prods, min(len(prods), random.randint(1, 3)))
        for p in picks:
            await client.get(f"/api/catalog/products/{p['sku']}")
            r = await client.post(f"/api/cart/{cart}/items", json={"sku": p["sku"], "qty": random.choice([1, 1, 1, 2, 3]), "currency": currency})
            stats[f"add_{r.status_code}"] += 1
        if random.random() < 0.7:
            r = await client.post("/api/checkout", json={
                "cartId": cart, "email": f"{random.choice(FIRST)}{random.randint(1, 999)}@example.com",
                "location": location, "channel": channel, "cardNumber": "4242424242424242"}, headers=headers)
            stats[f"checkout_{r.status_code}"] += 1
        else:
            stats["abandoned"] += 1
    except Exception as exc:
        stats["errors"] += 1
        log("WARN", "session failed", error=type(exc).__name__)


async def delayed(client, web, sem):
    await asyncio.sleep(random.random())
    async with sem:
        await session(client, web)


async def main():
    rds = aioredis.from_url(REDIS_URL, decode_responses=True)
    await rds.hsetnx("tc:load", "running", "1")
    await rds.hsetnx("tc:load", "rpm", "20")
    await rds.hsetnx("tc:load", "web_pct", "70")
    sem = asyncio.Semaphore(MAX_INFLIGHT)
    last_report = time.time()
    async with httpx.AsyncClient(base_url=BASE, timeout=30, headers={"x-load-source": "loadgen"}) as client:
        log("INFO", "loadgen started", target=BASE)
        while True:
            try:
                cfg = await rds.hgetall("tc:load")
                running, rpm, web_pct = cfg.get("running") == "1", float(cfg.get("rpm", 0)), float(cfg.get("web_pct", 70))
            except Exception as exc:
                log("WARN", "redis unavailable", error=type(exc).__name__)
                running, rpm, web_pct = False, 0, 70
            if running and rpm > 0:
                for _ in range(poisson(rpm / 60.0)):
                    asyncio.create_task(delayed(client, random.random() * 100 < web_pct, sem))
            if time.time() - last_report > 30:
                log("INFO", "loadgen stats", running=running, rpm=rpm, web_pct=web_pct, **dict(stats))
                stats.clear()
                last_report = time.time()
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
