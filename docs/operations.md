# TinyCars operations workspace

Open `/operations` from the control room, or directly in the browser, and enter
the admin token. The page shows live data from Postgres and keeps its own
purchase orders, stock movements, shipments, and returns in the same database.
The operations service creates its tables at startup, including on existing
TinyCars installations; it does not reset customer or stock data.
For data to survive a Postgres pod replacement, enable the chart's
`postgres.persistence.enabled` setting. The current demo EKS deployment uses
ephemeral Postgres storage.

## Local store time

Boston uses `America/New_York`, Chicago uses `America/Chicago`, and London uses
`Europe/London`. The operations workspace shows each store's current local time
and its 10:00–20:00 opening window. Stock, purchase, order, shipment, movement,
and return timestamps display in the relevant location's time zone with an
abbreviation. Shopper order history uses the order's store time too. The online
warehouse uses UTC. PostgreSQL keeps timezone-aware timestamps so records can
be compared across locations. The store VM agent already uses each location's
time zone for store activity. In-cluster load generation sends in-store traffic
only to stores that are open at the current local time; online traffic remains
available around the clock. IANA zones handle daylight saving changes.

## Workflows

1. **Inventory:** See stock at the warehouse and all three stores. Filter low
   stock, create a replenishment purchase order for all low stock products at
   one location, record count corrections, or transfer units between locations. The
   quick replenishment form estimates supplier cost at 60% of the USD retail
   price; use the manual purchase order form when actual cost is known. Each
   staff change creates an inventory movement record. A transfer cannot make
   source stock negative.
2. **Buying:** Create a purchase order with a supplier, destination, and one or
   more products. Receive all or some remaining units. Receiving increases
   stock once and records the movement. A fully received order cannot be
   received again.
3. **Orders and shipping:** Browse and search customer orders. Ship a paid web
   order with a carrier and tracking number, then mark it delivered. Tracking
   numbers and shipment states are demo records; no carrier is contacted.
4. **Returns:** Search or enter a paid order, choose an item and quantity, and
   record a reason. The API prevents cumulative returns above the purchased
   quantity. Receive and optionally restock it, or reject the request. Refunds
   are recorded as demo statuses; no payment processor is called.

The operations API is reachable only through `/api/admin/ops/*` on the
storefront and requires the same admin token as the control room. The internal
operations service checks the token too. Change the demo token before exposing
the storefront outside a lab.
