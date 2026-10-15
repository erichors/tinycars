#!/usr/bin/env python3
"""TinyCars store agent: simulates the Boston, Chicago and London retail stores from ONE VM.

* Each store rings up in-store sales through the storefront API (channel=in_store), following its own
  local business hours, and writes structured JSON logs.
* Each store also writes syslog-style auth logs (benign noise) and audit-style logs.
* When the admin panel switches on a SIEM-style pattern, the agent emits the matching SYNTHETIC log
  lines (failed-login flood, file-integrity alert, impossible travel). It only writes log text to files;
  it does not touch SSH, the network, or any real system file.

Zero third-party dependencies (stdlib only, Python 3.9+).
Logs: $LOG_DIR/<store>/{store.log,security.log,audit.log}
"""
import json
import logging
import os
import random
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

BASE = os.getenv("STOREFRONT_URL", "http://localhost:8080").rstrip("/")
TOKEN = os.getenv("ADMIN_TOKEN", "tinycars")
LOG_DIR = os.getenv("LOG_DIR", "/var/log/tinycars")
RATE_SCALE = float(os.getenv("STORE_RATE_SCALE", "1.0"))

STORES = {
    "boston": dict(tz="America/New_York", currency="USD", city="Boston", country="US", host="boston-pos-01", ip="10.20.1.10", rate=1.6),
    "chicago": dict(tz="America/Chicago", currency="USD", city="Chicago", country="US", host="chicago-pos-01", ip="10.20.2.10", rate=1.4),
    "london": dict(tz="Europe/London", currency="GBP", city="London", country="GB", host="london-pos-01", ip="10.30.1.10", rate=1.2),
}
FIRST = ["alex", "sam", "jordan", "casey", "riley", "morgan", "taylor", "jamie", "drew", "avery", "quinn", "reese"]
LAST = ["smith", "patel", "nguyen", "garcia", "okafor", "kim", "murphy", "rossi", "chen", "brown", "walker", "singh"]
# RFC 5737 documentation ranges: guaranteed never to be real hosts.
TEST_NET = ["203.0.113.", "198.51.100.", "192.0.2."]
BAD_USERS = ["admin", "root", "test", "oracle", "pos_admin", "backup", "ubuntu", "git", "postgres", "support"]
WATCHED = ["/etc/tinycars/pos.conf", "/etc/ssh/sshd_config", "/etc/passwd", "/etc/sudoers.d/pos", "/opt/tinycars/agent.py"]

FLAGS = {}
PRODUCTS = []


def jlog(level, msg, **kw):
    print(json.dumps({"ts": datetime.now().astimezone().isoformat(timespec="seconds"), "level": level,
                      "service": "store-agent", "msg": msg, **kw}), flush=True)


def http(method, path, body=None, headers=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"content-type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"error": raw.decode(errors="replace")[:200]}


def file_logger(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lg = logging.getLogger(path)
    lg.setLevel(logging.INFO)
    lg.propagate = False
    if not lg.handlers:
        h = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=3)
        h.setFormatter(logging.Formatter("%(message)s"))
        lg.addHandler(h)
    return lg


def flag(name):
    f = FLAGS.get(name)
    return (int(f.get("level", 1)), f.get("store")) if f and f.get("on") else (0, None)


class Store(threading.Thread):
    def __init__(self, name, cfg):
        super().__init__(daemon=True, name=name)
        self.n, self.c = name, cfg
        d = os.path.join(LOG_DIR, name)
        self.applog = file_logger(os.path.join(d, "store.log"))
        self.seclog = file_logger(os.path.join(d, "security.log"))
        self.auditlog = file_logger(os.path.join(d, "audit.log"))
        self.tz = ZoneInfo(cfg["tz"])
        self.next_flood = self.next_fim = 0.0
        self.serial = random.randint(1000, 9000)

    # ---- log writers
    def app(self, level, event, **kw):
        rec = {"ts": datetime.now(self.tz).isoformat(timespec="seconds"), "level": level, "service": "store-pos",
               "store": self.n, "city": self.c["city"], "country": self.c["country"], "host": self.c["host"],
               "client_ip": self.c["ip"], "event": event}
        rec.update(kw)
        self.applog.info(json.dumps(rec))

    def sec(self, proc, text):
        ts = datetime.now(self.tz).strftime("%b %e %H:%M:%S")
        self.seclog.info(f"{ts} {self.c['host']} {proc}[{random.randint(1000, 60000)}]: {text}")

    def audit(self, text):
        self.serial += 1
        self.auditlog.info(f"type={text.split(' ', 1)[0]} msg=audit({time.time():.3f}:{self.serial}): {text.split(' ', 1)[1]}")

    # ---- business
    def sale(self, email=None, tag=None):
        email = email or f"{random.choice(FIRST)}.{random.choice(LAST)}{random.randint(1, 999)}@example.com"
        cart = f"{self.n}-{uuid.uuid4().hex[:10]}"
        extra = {"correlation": tag} if tag else {}
        try:
            for p in random.sample(PRODUCTS, random.randint(1, 3)):
                http("POST", f"/api/cart/{cart}/items", {"sku": p["sku"], "qty": random.choice([1, 1, 2]), "currency": self.c["currency"]})
            status, o = http("POST", "/api/checkout", {"cartId": cart, "email": email, "location": self.n, "channel": "in_store", "cardNumber": "4242424242424242"})
            if status == 201:
                self.app("INFO", "SALE_COMPLETED", order_id=o["order_id"], account=email, total=o["total"], currency=o["currency"], **extra)
            elif status == 402:
                self.app("WARN", "SALE_DECLINED", account=email, **extra)
            else:
                self.app("ERROR", "SALE_FAILED", account=email, http_status=status, error=(o or {}).get("error"), **extra)
        except Exception as exc:
            self.app("ERROR", "SALE_FAILED", account=email, error=type(exc).__name__, **extra)
            return
        if random.random() < 0.1:  # occasionally top up shelf stock
            p = random.choice(PRODUCTS)
            st, rows = http("GET", f"/api/stock/{p['sku']}?location={self.n}")
            if st == 200 and rows and rows[0]["qty"] < 12:
                http("POST", "/api/stock/restock", {"sku": p["sku"], "qty": 30, "location": self.n})
                self.app("INFO", "RESTOCK_REQUESTED", sku=p["sku"], qty=30)

    def benign_auth(self):
        r = random.random()
        ip = f"10.{self.c['ip'].split('.')[1]}.{random.randint(1, 3)}.{random.randint(20, 90)}"
        if r < 0.5:
            self.sec("sshd", f"Accepted publickey for pos_clerk from {ip} port {random.randint(40000, 60000)} ssh2: RSA SHA256:{uuid.uuid4().hex[:43]}")
        elif r < 0.8:
            self.sec("sudo", "pos_clerk : TTY=pts/0 ; PWD=/home/pos_clerk ; USER=root ; COMMAND=/usr/bin/systemctl status tinycars-pos")
        else:
            self.sec("sshd", f"Failed password for pos_clerk from {ip} port {random.randint(40000, 60000)} ssh2")  # a typo

    # ---- SIEM-style patterns (synthetic log lines only)
    def failed_login_flood(self, level):
        ip = random.choice(TEST_NET) + str(random.randint(2, 250))
        for _ in range(level * 15):
            user = random.choice(BAD_USERS)
            port = random.randint(30000, 65000)
            valid = user in ("root", "pos_admin")
            self.sec("sshd", f"Failed password for {'' if valid else 'invalid user '}{user} from {ip} port {port} ssh2")
            self.sec("sshd", f"pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 tty=ssh ruser= rhost={ip}  user={user}")
            time.sleep(0.05)
        self.sec("sshd", f"Disconnecting authenticating user root {ip} port {port}: Too many authentication failures [preauth]")
        self.app("WARN", "AUTH_ANOMALY_SIMULATED", pattern="store_failed_login_flood", source_ip=ip, attempts=level * 15)

    def file_integrity(self, level):
        path = random.choice(WATCHED)
        comm = random.choice(["vim", "sed", "tee", "nano"])
        self.audit(f'SYSCALL arch=c000003e syscall=257 success=yes exit=3 a0=ffffff9c items=2 ppid=2211 pid={random.randint(3000, 9000)} auid=1001 uid=0 gid=0 euid=0 comm="{comm}" exe="/usr/bin/{comm}" key="tinycars_config"')
        self.audit(f'PATH item=0 name="{path}" inode={random.randint(100000, 999999)} dev=fd:00 mode=0100640 ouid=0 ogid=0 nametype=NORMAL')
        self.app("WARN", "FILE_INTEGRITY_SIMULATED", pattern="store_file_integrity_alert", path=path, process=comm)

    # ---- main loop
    def run(self):
        while True:
            now_local = datetime.now(self.tz)
            factor = 1.0 if 10 <= now_local.hour < 20 else 0.08
            per_sec = self.c["rate"] * factor * RATE_SCALE / 60.0
            if random.random() < per_sec:
                self.sale()
            if random.random() < 1 / 90:
                self.benign_auth()
            lvl, store = flag("store_failed_login_flood")
            if lvl and store == self.n and time.time() >= self.next_flood:
                self.failed_login_flood(lvl)
                self.next_flood = time.time() + 30
            lvl, store = flag("store_file_integrity_alert")
            if lvl and store == self.n and time.time() >= self.next_fim:
                self.file_integrity(lvl)
                self.next_fim = time.time() + max(8, 30 - lvl * 5)
            time.sleep(1)


def poll_flags():
    while True:
        try:
            st, data = http("GET", "/api/admin/flags", headers={"x-admin-token": TOKEN}, timeout=5)
            if st == 200:
                FLAGS.clear()
                FLAGS.update(data.get("flags", {}))
        except Exception as exc:
            jlog("WARN", "flag poll failed", error=type(exc).__name__)
        time.sleep(3)


def travel_loop(stores):
    """impossible_travel: same account buys in a US store, then in London shortly after."""
    next_at = 0.0
    while True:
        lvl, _ = flag("impossible_travel")
        if lvl and time.time() >= next_at:
            email = f"{random.choice(FIRST)}.{random.choice(LAST)}{random.randint(1, 99)}@example.com"
            us = stores[random.choice(["boston", "chicago"])]
            us.sale(email=email, tag="impossible_travel_leg1")
            time.sleep(random.randint(20, 60))
            stores["london"].sale(email=email, tag="impossible_travel_leg2")
            jlog("INFO", "impossible travel pair emitted", account=email, from_store=us.n, to_store="london")
            next_at = time.time() + max(30, 180 - lvl * 30)
        time.sleep(2)


def main():
    jlog("INFO", "store agent starting", storefront=BASE, log_dir=LOG_DIR)
    while True:  # wait for the storefront + catalog
        try:
            st, data = http("GET", "/api/catalog/products?limit=200", timeout=10)
            if st == 200 and data:
                PRODUCTS.extend(data)
                break
        except Exception:
            pass
        jlog("WARN", "storefront not ready, retrying")
        time.sleep(5)
    stores = {n: Store(n, c) for n, c in STORES.items()}
    for s in stores.values():
        s.start()
    threading.Thread(target=poll_flags, daemon=True).start()
    threading.Thread(target=travel_loop, args=(stores,), daemon=True).start()
    jlog("INFO", "store agent running", stores=list(stores), products=len(PRODUCTS))
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
