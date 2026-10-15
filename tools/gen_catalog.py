#!/usr/bin/env python3
"""Generate TinyCars catalog: 66 SKUs, SVG art, and db/seed.sql.

Usage: python3 tools/gen_catalog.py
Writes:
  db/seed.sql                       (also copied into the Helm chart files/)
  services/storefront/public/img/cars/TC-###.svg
  docs/contact-sheet.png            (if pillow + resvg-py or cairosvg are installed)
Deterministic: same output every run.
"""
import json
import os
import random
import shutil
import sys

sys.path.insert(0, os.path.dirname(__file__))
import carart  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# palette
RED, BLK, MINT, YEL, WHT, BLU, ORG, PUR, TEAL, GRN, CRM = (
    "#b3221c", "#1d1f23", "#8fbfae", "#dcae2a", "#e7e7e2", "#24508f", "#cc621c",
    "#5b3b8c", "#1f6f6d", "#3a6b34", "#e3d8bb")
OLV, TAN, DSRT, SLV, NAVY, BRN, LIME, PINK = (
    "#4b5530", "#b39d6c", "#c2a878", "#a9afb7", "#1d2f4f", "#5e3b26", "#8fae2c", "#d77d99")
RUST, FOREST, SLATE, VINYL, GRAPH = "#8a4424", "#24503c", "#3e5670", "#2b2f38", "#3c4148"

# (name, category, template, era, body, accent, class, blurb)
CATALOG = [
    # Classics & Muscle (9)
    ("'67 Thunder Coupe", "Classics & Muscle", "muscle_coupe", "1960s", RED, WHT, "premium", "Big-block attitude with a racing stripe and hood scoop."),
    ("Boulevard Cruiser", "Classics & Muscle", "sedan", "1950s", TEAL, CRM, "basic", "A four-door sedan with chrome trim and a lazy Sunday cruise."),
    ("Land Yacht", "Classics & Muscle", "boxy_sedan", "1980s", BRN, VINYL, "premium", "Formal full-size sedan with a vinyl roof and an opera window."),
    ("Woody Wagon", "Classics & Muscle", "wagon", "1960s", CRM, RED, "basic", "Wood-grain sides and a roof rack loaded for the lake house."),
    ("Family Hauler", "Classics & Muscle", "wagon_modern", "1990s", BLU, SLV, "basic", "Long-roof wagon with rails, a spoiler and room for everyone."),
    ("GT Continental", "Classics & Muscle", "gt_coupe", "1960s", FOREST, CRM, "premium", "Grand-touring fastback with wire wheels and teardrop glass."),
    ("Gasser Hot Rod", "Classics & Muscle", "hot_rod", "1950s", PUR, YEL, "premium", "Supercharged street rod with painted flames."),
    ("Rat Pack Rod", "Classics & Muscle", "rat_rod", "1950s", RUST, SLV, "premium", "Patina, primer and an engine you can see from across the lot."),
    ("Boulevard Convertible", "Classics & Muscle", "convertible", "1960s", BLU, CRM, "premium", "Top down, tail fins up, whitewalls shining."),
    # Imports & Compacts (8)
    ("Autobahn Fastback", "Imports & Compacts", "rear_engine", "1970s", SLV, RED, "premium", "Rounded rear-engine fastback with a duck-tail and round lamps."),
    ("Milano Spider", "Imports & Compacts", "spider", "1960s", RED, CRM, "premium", "Open two-seater with a shield grille and wire wheels."),
    ("Piccolo City Mini", "Imports & Compacts", "city_mini", "1970s", MINT, WHT, "basic", "Tiny, zippy, and always finds a parking space."),
    ("Rally Hatch", "Imports & Compacts", "hatch", "1980s", WHT, BLU, "basic", "Pocket-sized rally hero with a sporty stripe."),
    ("Bubble Bug", "Imports & Compacts", "bug", "1960s", YEL, ORG, "basic", "Round, friendly, and beloved by every collector."),
    ("Cruiser Microbus", "Imports & Compacts", "microbus", "1960s", MINT, WHT, "basic", "Two-tone split-window bus; seats nine, never in a hurry."),
    ("Kei Hauler", "Imports & Compacts", "kei_3wheel", "1960s", BLU, TAN, "basic", "Three-wheel mini truck that squeezes down any alley."),
    ("Trike Cruiser", "Imports & Compacts", "trike_bike", "1990s", TEAL, CRM, "premium", "Touring trike with a trunk, chrome pipes and two rear wheels."),
    # Off-Roaders (7)
    ("Trailblazer 4x4", "Off-Roaders", "offroader", "1970s", ORG, BLK, "premium", "Boxy original with a roof rack and a spare on the back."),
    ("Rock Crawler", "Off-Roaders", "trail_jeep", "1990s", RED, TAN, "premium", "Open-top trail runner with a slotted grille and a soft top."),
    ("Trailmaster", "Off-Roaders", "boxy_suv", "1990s", FOREST, SLV, "premium", "Boxy four-wheel-drive wagon with flares and side steps."),
    ("Highland Classic", "Off-Roaders", "classic_luxury_suv", "1980s", SLATE, CRM, "premium", "Two-tone luxury 4x4 with a long flat hood."),
    ("Beach Buggy", "Off-Roaders", "dune_buggy", "1970s", ORG, YEL, "basic", "Roll cage, open seats and an engine out back."),
    ("Mud Giant", "Off-Roaders", "mud_truck", "2000s", BLU, ORG, "premium", "Lifted pickup on oversized tires."),
    ("Bog Stomper", "Off-Roaders", "monster_truck", "2000s", GRN, YEL, "premium", "Giant-wheel show truck that crushes anything."),
    # Pickups (3)
    ("Farm Hauler", "Pickups", "pickup_classic", "1950s", RED, CRM, "premium", "Step-side classic with a wood bed and bucket lamps."),
    ("Work Horse", "Pickups", "pickup", "1970s", WHT, ORG, "basic", "Never complains, always shows up."),
    ("Crew Cab Classic", "Pickups", "pickup_crew", "2010s", NAVY, SLV, "premium", "Four doors, a covered bed and room for the whole crew."),
    # Everyday & Emergency (10)
    ("City Cab", "Everyday & Emergency", "taxi", "1980s", YEL, BLK, "basic", "Checker stripe, roof sign, always on the clock."),
    ("Patrol Cruiser", "Everyday & Emergency", "patrol", "1980s", BLK, WHT, "premium", "Light bar and two-tone doors."),
    ("Hose & Ladder", "Everyday & Emergency", "fire_truck", "1970s", RED, YEL, "premium", "Ladder on top and compartment doors down the side."),
    ("Rescue Van", "Everyday & Emergency", "rescue_van", "1990s", WHT, ORG, "basic", "Chevron stripes and a roof light bar."),
    ("Schoolyard Bus", "Everyday & Emergency", "school_bus", "1970s", YEL, BLK, "basic", "Six windows and a ride to class."),
    ("Parcel Runner", "Everyday & Emergency", "delivery_van", "1980s", BRN, WHT, "basic", "Box truck with a stripe and a package on the door."),
    ("Cone Cruiser", "Everyday & Emergency", "ice_cream_truck", "1970s", PINK, CRM, "premium", "Serving window, striped awning and a giant cone."),
    ("Hook & Haul", "Everyday & Emergency", "tow_truck", "1980s", WHT, RED, "premium", "Boom, hook and an amber beacon."),
    ("Trash Titan", "Everyday & Emergency", "garbage_truck", "1990s", GRN, WHT, "basic", "Rear lifter arm and a hopper that never sleeps."),
    ("Open Road Motorhome", "Everyday & Emergency", "motorhome", "1980s", CRM, ORG, "premium", "Class-A motorhome with swoosh stripes."),
    # Sports & Racing (6)
    ("Apex Roadster", "Sports & Racing", "sports_car", "2010s", RED, BLK, "premium", "Low, wide, and quick off the line."),
    ("Coastline Spyder", "Sports & Racing", "roadster", "1990s", TEAL, WHT, "premium", "Top down along the coast road."),
    ("Velocity Wedge", "Sports & Racing", "wedge", "1980s", LIME, BLK, "premium", "A neon wedge with a big wing."),
    ("Grand Prix Racer", "Sports & Racing", "open_wheel", "1970s", RED, WHT, "premium", "Open-wheel racer with front and rear wings."),
    ("Quarter-Mile Dragster", "Sports & Racing", "dragster", "1970s", YEL, ORG, "premium", "Supercharged and built for eight seconds of glory."),
    ("Nitro Funny Car", "Sports & Racing", "funny_car", "1980s", ORG, YEL, "premium", "Long body, giant wing and flames from the headers."),
    # Military & Army (6)
    ("Field Commander", "Military & Army", "military_truck", "1990s", OLV, TAN, "premium", "Wide-stance utility truck built for rough ground."),
    ("Troop Mover", "Military & Army", "troop_transport", "1980s", OLV, TAN, "premium", "Canvas-covered transport with three axles."),
    ("Fuel Hauler", "Military & Army", "fuel_tanker", "1980s", DSRT, OLV, "premium", "Keeps the convoy moving."),
    ("Recon Scout", "Military & Army", "recon", "1970s", OLV, BLK, "premium", "Open-top scout with a roll bar and spare."),
    ("Iron Guardian", "Military & Army", "tank", "1980s", OLV, TAN, "limited", "Heavy tank with a long barrel and rolling treads."),
    ("Armored Escort", "Military & Army", "armored_carrier", "1990s", OLV, SLV, "premium", "Four-axle armored carrier with a roof turret."),
    # Construction (6)
    ("Rock Hauler", "Construction", "dump_truck", "1970s", YEL, RED, "basic", "Dump bed up, dust flying."),
    ("Dig Master", "Construction", "excavator", "1980s", YEL, BLK, "premium", "Tracked excavator with a poseable-looking arm."),
    ("Earth Pusher", "Construction", "bulldozer", "1970s", YEL, GRAPH, "premium", "Pushes mountains before breakfast."),
    ("Concrete Spinner", "Construction", "cement_mixer", "1980s", ORG, SLV, "basic", "Always turning, never settling."),
    ("Sky Lift", "Construction", "crane_truck", "1990s", RED, YEL, "premium", "Truck-mounted crane that reaches for the clouds."),
    ("Load Lugger", "Construction", "front_loader", "1980s", YEL, BLK, "basic", "Scoops, lifts, and dumps all day."),
    # Limited Edition (5) - gold variants of fan favorites
    ("Gold Thunder Coupe", "Limited Edition", "muscle_coupe", "1960s", "gold", "gold", "limited", "Numbered gold edition of the '67 Thunder Coupe."),
    ("Golden Fastback", "Limited Edition", "rear_engine", "1970s", "gold", "gold", "limited", "Gold-plated fastback, numbered run."),
    ("Golden Trailblazer", "Limited Edition", "offroader", "1970s", "gold", "gold", "limited", "Collector gold finish on the beloved 4x4."),
    ("Chrome Guardian", "Limited Edition", "tank", "1980s", "gold", "gold", "limited", "Gilded tank, limited to a tiny run."),
    ("Gilded Hauler", "Limited Edition", "pickup_classic", "1950s", "gold", "gold", "limited", "The farm hauler dressed for the gala."),
    # Sixth row (6) - added later, appended so existing SKUs keep their numbers
    ("Stainless Wedge", "Pickups", "wedge_pickup", "2020s", SLV, BLK, "premium", "Flat steel planes, a light-bar nose and a sail-panel bed. Pure angles."),
    ("Line Crew Bucket Truck", "Everyday & Emergency", "bucket_truck", "1990s", WHT, YEL, "premium", "Service body, outrigger and a boom that lifts the crew to the wires."),
    ("Desert Sand Rail", "Off-Roaders", "sand_rail", "2000s", ORG, BLK, "premium", "Long-travel tube-frame rail with paddle tires and a whip flag."),
    ("Flatbed Hauler", "Construction", "flatbed", "1980s", BLU, SLV, "basic", "Steel deck, headache rack and a strapped load of crates."),
    ("Farmhand Tractor", "Construction", "tractor", "1960s", RED, CRM, "basic", "Giant ribbed rear tires, a long hood and an exhaust stack."),
    ("Dig & Load Backhoe", "Construction", "backhoe", "1980s", YEL, GRAPH, "premium", "Loader up front, digger out back, stabilizers down."),
]

PRICES = {
    "basic": [3.99, 4.49, 4.99, 5.49, 5.99, 6.49, 6.99, 7.99, 8.99],
    "premium": [12.99, 14.99, 16.99, 18.99, 19.99, 22.99, 24.99],
    "limited": [29.99, 34.99, 39.99, 44.99, 49.99, 54.99, 59.99],
}
LOCATIONS = ["warehouse", "boston", "chicago", "london"]
FX_GBP = 0.79
NEW_ARRIVAL_NAMES = {"Stainless Wedge", "Line Crew Bucket Truck", "Desert Sand Rail", "Flatbed Hauler", "Farmhand Tractor", "Dig & Load Backhoe", "Cone Cruiser", "Bog Stomper", "Nitro Funny Car", "Milano Spider", "Trike Cruiser", "Kei Hauler", "Boulevard Convertible"}
FIRST = ["alex", "sam", "jordan", "casey", "riley", "morgan", "taylor", "jamie", "drew", "avery",
         "quinn", "reese", "blake", "harper", "skyler", "rowan", "devon", "emery", "finley", "logan"]
LAST = ["smith", "patel", "nguyen", "garcia", "okafor", "kim", "murphy", "rossi", "chen", "brown",
        "walker", "singh", "lopez", "hughes", "novak"]


def esc(s):
    return s.replace("'", "''")


LENGTH_IN = {"limo": 4.1, "motorhome": 3.9, "school_bus": 3.8, "fire_truck": 3.8, "troop_transport": 3.7, "fuel_tanker": 3.7,
             "crane_truck": 3.8, "dump_truck": 3.6, "garbage_truck": 3.6, "cement_mixer": 3.6, "tow_truck": 3.6, "delivery_van": 3.5,
             "dragster": 4.0, "funny_car": 3.9, "boxy_sedan": 3.5, "city_mini": 2.3, "kei_3wheel": 2.6, "trike_bike": 2.8, "dune_buggy": 2.7,
             "bucket_truck": 3.7, "flatbed": 3.7, "tractor": 2.6, "backhoe": 3.3, "sand_rail": 2.9, "wedge_pickup": 3.3}
FINISHES = ["Gloss enamel", "Metallic", "Pearl", "Satin", "Candy"]


def make_specs(rnd, name, tpl, cat, era, cls, body):
    what, feats, wheels = carart.META[tpl]
    year = int(era[:4]) + rnd.randint(0, 9)
    limited = cat == "Limited Edition" or cls == "limited"
    finish = "24k-style gold plate" if cat == "Limited Edition" else ("Patina" if tpl == "rat_rod" else rnd.choice(FINISHES))
    specs = {
        "class": what,
        "scale": "1:64",
        "length_in": round(LENGTH_IN.get(tpl, 3.0) + rnd.choice([-0.1, 0, 0.1]), 1),
        "era": era,
        "model_year": year,
        "finish": finish,
        "wheels": wheels,
        "material": "Die-cast metal body, plastic base",
        "features": feats,
        "rarity": "Limited" if limited else ("Collector" if cls == "premium" else "Common"),
        "pack": "Blister card",
        "hotspots": carart.hotspots(tpl),
    }
    if limited:
        specs["edition"] = f"No. {rnd.randint(11, 480):03d} of 500"
    return specs


def build():
    rnd = random.Random(60)
    counters = {"basic": 0, "premium": 0, "limited": 0}
    products = []
    for i, (name, cat, tpl, era, body, accent, cls, blurb) in enumerate(CATALOG, 1):
        sku = f"TC-{i:03d}"
        usd = PRICES[cls][counters[cls] % len(PRICES[cls])]
        counters[cls] += 1
        gbp = round(usd * FX_GBP * 2) / 2 - 0.01 if usd >= 10 else round(usd * FX_GBP, 2)
        limited = cat == "Limited Edition"
        svg = carart.render(tpl, cat, body, accent, sku.replace("-", ""), limited=limited)
        products.append(dict(sku=sku, name=name, cat=cat, tpl=tpl, era=era,
                             color=("Gold" if limited else body), desc=blurb, cls=cls,
                             usd=usd, gbp=round(gbp, 2), svg=svg, image=f"/img/cars/{sku}.svg",
                             new=name in NEW_ARRIVAL_NAMES, specs=make_specs(rnd, name, tpl, cat, era, cls, body)))
    return rnd, products


def write_files(rnd, products):
    img_dir = os.path.join(ROOT, "services", "storefront", "public", "img", "cars")
    os.makedirs(img_dir, exist_ok=True)
    for p in products:
        with open(os.path.join(img_dir, p["sku"] + ".svg"), "w") as f:
            f.write(p["svg"])

    sql = ["-- TinyCars seed data (generated by tools/gen_catalog.py; do not edit by hand)", "BEGIN;"]
    for p in products:
        sql.append(
            "INSERT INTO products(sku,name,category,body,era,color,description,price_usd,price_gbp,weight_class,image,new_arrival,specs) VALUES "
            f"('{p['sku']}','{esc(p['name'])}','{esc(p['cat'])}','{p['tpl']}','{p['era']}','{p['color']}',"
            f"'{esc(p['desc'])}',{p['usd']},{p['gbp']},'{p['cls']}','{p['image']}',{'true' if p['new'] else 'false'},'{esc(json.dumps(p['specs']))}'::jsonb);")
    for p in products:
        for loc in LOCATIONS:
            if p["cls"] == "limited":
                q = rnd.randint(8, 30) if loc == "warehouse" else rnd.randint(1, 6)
            else:
                q = rnd.randint(40, 220) if loc == "warehouse" else rnd.randint(3, 30)
            sql.append(f"INSERT INTO stock(sku,location,qty) VALUES ('{p['sku']}','{loc}',{q});")

    # historical orders over the last 30 days
    for n in range(1, 421):
        channel = rnd.choices(["web", "in_store"], weights=[55, 45])[0]
        loc = "warehouse" if channel == "web" else rnd.choice(["boston", "chicago", "london"])
        currency = "GBP" if loc == "london" or (channel == "web" and rnd.random() < 0.12) else "USD"
        email = f"{rnd.choice(FIRST)}.{rnd.choice(LAST)}{rnd.randint(1, 99)}@example.com"
        items = rnd.sample(products, rnd.randint(1, 4))
        lines, total = [], 0.0
        oid = f"ORD-H{n:04d}"
        for it in items:
            qty = rnd.choices([1, 2, 3, 5], weights=[60, 25, 10, 5])[0]
            unit = it["gbp"] if currency == "GBP" else it["usd"]
            total += unit * qty
            lines.append(f"INSERT INTO order_items(order_id,sku,qty,unit_price) VALUES ('{oid}','{it['sku']}',{qty},{unit});")
        mins = rnd.randint(5, 30 * 24 * 60)
        status = rnd.choices(["completed", "declined"], weights=[95, 5])[0]
        sql.append(
            "INSERT INTO orders(order_id,created_at,channel,location,customer_email,currency,total,status,payment_status) VALUES "
            f"('{oid}', now() - interval '{mins} minutes','{channel}','{loc}','{email}','{currency}',{total:.2f},"
            f"'{status}','{'approved' if status == 'completed' else 'declined'}');")
        sql.extend(lines)
    sql.append("COMMIT;")
    seed = "\n".join(sql) + "\n"

    os.makedirs(os.path.join(ROOT, "db"), exist_ok=True)
    with open(os.path.join(ROOT, "db", "seed.sql"), "w") as f:
        f.write(seed)
    chart_files = os.path.join(ROOT, "deploy", "helm", "tinycars", "files")
    os.makedirs(chart_files, exist_ok=True)
    for fn in ("schema.sql", "seed.sql"):
        src = os.path.join(ROOT, "db", fn)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(chart_files, fn))
    return seed


def contact_sheet(products):
    try:
        import io
        from PIL import Image
        try:
            import resvg_py  # full SVG filter support (matches browsers)

            def to_png(svg, w, h):
                return bytes(resvg_py.svg_to_bytes(svg_string=svg, width=w, height=h))
        except ImportError:
            import cairosvg  # no filter support: lighting is skipped in the sheet

            def to_png(svg, w, h):
                return cairosvg.svg2png(bytestring=svg.encode(), output_width=w, output_height=h)
    except Exception as e:  # pragma: no cover
        print("skip contact sheet:", e)
        return
    cols, w, h = 6, 300, 195
    rows = (len(products) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), "#e4e6e9")
    for i, p in enumerate(products):
        png = to_png(p["svg"], w, h)
        tile = Image.open(io.BytesIO(png)).convert("RGBA")
        bg = Image.new("RGBA", tile.size, "white")
        sheet.paste(Image.alpha_composite(bg, tile).convert("RGB"), ((i % cols) * w, (i // cols) * h))
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    sheet.save(os.path.join(ROOT, "docs", "contact-sheet.png"))


if __name__ == "__main__":
    r, prods = build()
    assert len(prods) == 66, len(prods)
    write_files(r, prods)
    contact_sheet(prods)
    print(f"wrote {len(prods)} SKUs, svgs, db/seed.sql")
