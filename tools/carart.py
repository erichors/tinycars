"""Studio-rendered die-cast vehicle art for TinyCars. Pure Python, no dependencies.

Every vehicle is drawn on a 400x260 canvas, ground line at y=204.
All designs are original generic silhouettes (no real makes, logos or insignia).
"""

import math

GLASS = "url(#glass)"          # gradient defined in every SVG by render()
DARK = "#2a2d34"
TIRE = "url(#tire)"
HUB = "#d9dde3"
CHROME = "url(#chrome)"
SLV = "#b9c0cc"
GOLD_A, GOLD_B = "#f7d774", "#c9962b"

BG = {  # category -> (backdrop circle, ground band)
    "Classics & Muscle": ("#ffe3d1", "#f4c7a8"),
    "Imports & Compacts": ("#e6e1fb", "#c5bdf0"),
    "Off-Roaders": ("#e3f0d0", "#bcd69a"),
    "Pickups": ("#fdebc2", "#efd08a"),
    "Everyday & Emergency": ("#dcf1ee", "#a9d8d2"),
    "Sports & Racing": ("#d9e6ff", "#aec6f2"),
    "Military & Army": ("#e4e8d5", "#c2c9a3"),
    "Construction": ("#fff0b8", "#f0d572"),
    "Limited Edition": ("#fbeecb", "#e6c56e"),
}


_WHEELS = []   # (cx, cy, r) of every wheel drawn, for floor contact shadows
_ARCHES = {}   # cx -> arch radius, so wheel() can cut a wheel well into the body
_STYLE = {"style": "mag", "hub": None}   # per-category default wheel finish, set by render()


def track(x, y, w, h, wheels, wr):
    """Rubber track with tread links, drive sprockets and shaded road wheels."""
    r = h / 2
    _WHEELS.append((x + w / 2, y + h, w / 2 - 4, r))
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="url(#rubber)"/>'
    s += f'<rect x="{x + 1.5}" y="{y + 1.5}" width="{w - 3}" height="{h - 3}" rx="{r - 1.5}" fill="none" stroke="#3b3e44" stroke-width="2.6" stroke-dasharray="3.2 2.6"/>'
    s += f'<rect x="{x + 6}" y="{y + 6}" width="{w - 12}" height="{h - 12}" rx="{r - 6}" fill="#141518"/>'
    cy = y + h / 2
    for i, cx in enumerate(wheels):
        s += f'<circle cx="{cx}" cy="{cy}" r="{wr}" fill="url(#gunmetal)"/><circle cx="{cx}" cy="{cy}" r="{wr}" fill="url(#dish)"/>'
        s += f'<circle cx="{cx}" cy="{cy}" r="{wr * 0.38:.1f}" fill="url(#rim)"/><circle cx="{cx - wr * 0.12:.1f}" cy="{cy - wr * 0.14:.1f}" r="{wr * 0.1:.1f}" fill="#fff" opacity=".7"/>'
    return s


def wheel(cx, cy=178, r=27, hub=HUB, style=None, white=False):
    """Studio-rendered wheel: wheel well, rubber tyre with tread and sidewall, metal rim by style, hub and lugs."""
    _WHEELS.append((cx, cy + r, r * 0.95, r))
    if style is None:
        style = _STYLE["style"]
        if _STYLE["hub"] and hub == HUB:
            hub = _STYLE["hub"]
    s = ""
    ar = _ARCHES.get(cx)
    if ar:  # wheel well: dark upper half-disc cut into the body, with a lit fender lip
        s += (f'<path d="M{cx - ar} {cy} A{ar} {ar} 0 0 1 {cx + ar} {cy} Z" fill="url(#well)"/>'
              f'<path d="M{cx - ar} {cy} A{ar} {ar} 0 0 1 {cx + ar} {cy}" fill="none" stroke="#fff" stroke-width="1.1" opacity=".28"/>')
    # tyre
    s += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#tire)"/>'
    s += f'<circle cx="{cx}" cy="{cy}" r="{r - 1.2:.1f}" fill="none" stroke="#0b0c0e" stroke-width="2.2" stroke-dasharray="{r * 0.16:.1f} {r * 0.09:.1f}" opacity=".9"/>'
    s += f'<circle cx="{cx}" cy="{cy}" r="{r * 0.84:.1f}" fill="none" stroke="#3a3d43" stroke-width=".8" stroke-dasharray="{r * 0.35:.1f} {r * 0.5:.1f}" opacity=".7"/>'
    if white:
        s += f'<circle cx="{cx}" cy="{cy}" r="{r * 0.78:.1f}" fill="none" stroke="url(#whitewall)" stroke-width="{max(2.4, r * 0.15):.1f}"/>'
    rr = r * (0.6 if not white else 0.56)
    # rim barrel and lip
    s += f'<circle cx="{cx}" cy="{cy}" r="{rr + 0.8:.1f}" fill="#1a1c20"/>'
    if style in ("steel", "disc"):
        s += f'<circle cx="{cx}" cy="{cy}" r="{rr:.1f}" fill="{hub if hub != HUB else "url(#rim)"}"/>'
        s += f'<circle cx="{cx}" cy="{cy}" r="{rr:.1f}" fill="url(#dish)"/>'
        if style == "steel":
            for i in range(6):
                t = math.radians(i * 60 + 30)
                s += f'<ellipse cx="{cx + math.cos(t) * rr * 0.6:.1f}" cy="{cy + math.sin(t) * rr * 0.6:.1f}" rx="{max(1.5, r * 0.085):.1f}" ry="{max(1.1, r * 0.06):.1f}" fill="#16181b" opacity=".85" transform="rotate({i * 60 + 30} {cx + math.cos(t) * rr * 0.6:.1f} {cy + math.sin(t) * rr * 0.6:.1f})"/>'
        else:
            s += f'<circle cx="{cx}" cy="{cy}" r="{rr * 0.78:.1f}" fill="none" stroke="#fff" stroke-width=".9" opacity=".45"/><circle cx="{cx}" cy="{cy}" r="{rr * 0.74:.1f}" fill="none" stroke="#000" stroke-width=".9" opacity=".25"/>'
    else:
        # open wheel: dark interior with brake disc, then spokes
        s += f'<circle cx="{cx}" cy="{cy}" r="{rr:.1f}" fill="url(#rimwell)"/>'
        s += f'<circle cx="{cx}" cy="{cy}" r="{rr * 0.72:.1f}" fill="none" stroke="#6f747b" stroke-width="{rr * 0.28:.1f}" opacity=".55"/>'
        if style == "wire":
            for i in range(24):
                t = math.radians(i * 15)
                s += f'<path d="M{cx + math.cos(t) * rr * 0.22:.1f} {cy + math.sin(t) * rr * 0.22:.1f} L{cx + math.cos(t + 0.35) * rr * 0.97:.1f} {cy + math.sin(t + 0.35) * rr * 0.97:.1f}" stroke="#d9dee4" stroke-width=".7"/>'
        elif style == "chunky":
            s += f'<circle cx="{cx}" cy="{cy}" r="{rr * 0.86:.1f}" fill="url(#gunmetal)"/>'
            for i in range(8):
                t = math.radians(i * 45 + 22.5)
                s += f'<circle cx="{cx + math.cos(t) * rr * 0.55:.1f}" cy="{cy + math.sin(t) * rr * 0.55:.1f}" r="{max(1.5, r * 0.08):.1f}" fill="#0f1012"/>'
            for i in range(14):
                t = math.radians(i * 360 / 14)
                s += f'<circle cx="{cx + math.cos(t) * rr * 0.9:.1f}" cy="{cy + math.sin(t) * rr * 0.9:.1f}" r=".9" fill="#c9ced5"/>'
        else:  # mag: five tapered spokes with shadow side
            w = max(2.4, r * 0.2)
            for i in range(5):
                t = math.radians(i * 72 - 90)
                ex, ey = cx + math.cos(t) * rr * 0.96, cy + math.sin(t) * rr * 0.96
                s += f'<path d="M{cx + 0.9} {cy + 0.9} L{ex + 0.9:.1f} {ey + 0.9:.1f}" stroke="#121316" stroke-width="{w:.1f}" stroke-linecap="round" opacity=".8"/>'
                s += f'<path d="M{cx} {cy} L{ex:.1f} {ey:.1f}" stroke="url(#spoke)" stroke-width="{w:.1f}" stroke-linecap="round"/>'
        s += f'<circle cx="{cx}" cy="{cy}" r="{rr:.1f}" fill="none" stroke="url(#rim)" stroke-width="{max(1.6, rr * 0.13):.1f}"/>'
    # hub, lugs, highlight
    s += f'<circle cx="{cx}" cy="{cy}" r="{r * 0.2:.1f}" fill="url(#rim)"/><circle cx="{cx}" cy="{cy}" r="{r * 0.2:.1f}" fill="none" stroke="#2b2e33" stroke-width=".8"/>'
    for i in range(5):
        t = math.radians(i * 72 - 54)
        s += f'<circle cx="{cx + math.cos(t) * r * 0.13:.1f}" cy="{cy + math.sin(t) * r * 0.13:.1f}" r="{max(0.7, r * 0.03):.1f}" fill="#33363c"/>'
    s += f'<circle cx="{cx - r * 0.04:.1f}" cy="{cy - r * 0.05:.1f}" r="{r * 0.07:.1f}" fill="#fff" opacity=".85"/>'
    s += f'<path d="M{cx - r * 0.8:.1f} {cy - r * 0.42:.1f} A{r * 0.9:.1f} {r * 0.9:.1f} 0 0 1 {cx - r * 0.2:.1f} {cy - r * 0.88:.1f}" fill="none" stroke="#fff" stroke-width="1" opacity=".14" stroke-linecap="round"/>'
    return s


def spare_edge(xr, cy, r):
    """Spare tyre on a tailgate/rear panel, seen edge-on from the side: tread profile only, with its mount."""
    x = xr - 13
    s = f'<rect x="{xr - 3}" y="{cy - 5}" width="6" height="10" rx="1" fill="#141518"/>'
    s += f'<rect x="{x}" y="{cy - r}" width="13" height="{2 * r}" rx="6" fill="url(#treadg)"/>'
    s += "".join(f'<path d="M{x + 2} {y:.1f} H{x + 11}" stroke="#08090a" stroke-width="1.6" opacity=".8"/>' for y in [cy - r + 5 + i * 4.2 for i in range(int((2 * r - 8) / 4.2) + 1)])
    s += f'<path d="M{x + 4} {cy - r + 4} V{cy + r - 4}" stroke="#fff" stroke-width="1" opacity=".12"/>'
    return s


def arch(cx, cy=178, r=31):
    """Register a wheel well; the well itself is drawn by wheel() on top of the body."""
    _ARCHES[cx] = r
    return ""


def poly(points, fill, extra=""):
    return f'<path d="{points}" fill="{fill}" {extra}/>'


def shade(hexcolor, f):
    """Lighten (f>0) or darken (f<0) a #rrggbb colour."""
    h = hexcolor.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    if f >= 0:
        r, g, b = (int(v + (255 - v) * f) for v in (r, g, b))
    else:
        r, g, b = (int(v * (1 + f)) for v in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


# ---------------------------------------------------------------- templates
def muscle_coupe(c):
    b, a = c["body"], c["accent"]
    s = arch(110) + arch(300)
    s += poly("M38 176 L38 156 Q38 144 52 142 L108 136 L142 106 Q148 100 158 100 L240 100 Q252 100 260 108 L290 136 L350 142 Q364 144 364 158 L364 176 Z", b)
    s += poly("M150 110 L240 110 L268 134 L126 134 Z", GLASS)
    s += f'<rect x="194" y="110" width="4" height="24" fill="{b}"/>'
    s += f'<path d="M50 152 H354" stroke="{a}" stroke-width="7" fill="none"/>'
    s += f'<rect x="296" y="136" width="30" height="5" rx="2" fill="{DARK}"/>'
    s += f'<rect x="34" y="170" width="334" height="7" rx="3" fill="{CHROME}"/>'
    s += '<circle cx="354" cy="154" r="6" fill="#ffe36b"/><rect x="38" y="148" width="7" height="12" rx="2" fill="#e03b3b"/>'
    return s + wheel(110) + wheel(300)


def microbus(c):
    b, a = c["body"], c["accent"]
    s = arch(112) + arch(296)
    s += f'<rect x="48" y="96" width="306" height="82" rx="24" fill="{b}"/>'
    s += f'<path d="M48 124 Q48 96 72 96 L330 96 Q354 96 354 124 L354 128 L48 128 Z" fill="{a}"/>'
    for x in (66, 128, 190, 252):
        s += f'<rect x="{x}" y="104" width="52" height="26" rx="6" fill="{GLASS}"/>'
    s += f'<rect x="306" y="104" width="38" height="30" rx="8" fill="{GLASS}"/>'
    s += f'<path d="M290 130 L330 158 L354 130" fill="none" stroke="{a}" stroke-width="7"/>'
    s += f'<rect x="44" y="170" width="314" height="7" rx="3" fill="{CHROME}"/>'
    s += '<circle cx="340" cy="152" r="8" fill="#ffe36b"/><rect x="50" y="146" width="7" height="14" rx="2" fill="#e03b3b"/>'
    return s + wheel(112) + wheel(296)


def hatch(c):
    b, a = c["body"], c["accent"]
    s = arch(118) + arch(290)
    s += poly("M58 176 L58 148 Q58 138 72 136 L110 132 L138 100 Q144 94 154 94 L248 94 Q262 94 268 102 L298 134 L338 140 Q352 142 352 156 L352 176 Z", b)
    s += poly("M148 104 L248 104 L276 132 L120 132 Z", GLASS)
    s += f'<rect x="196" y="104" width="4" height="28" fill="{b}"/>'
    s += f'<rect x="60" y="150" width="290" height="6" fill="{a}"/>'
    s += f'<rect x="54" y="170" width="300" height="7" rx="3" fill="{CHROME}"/>'
    s += '<circle cx="342" cy="154" r="6" fill="#ffe36b"/><rect x="60" y="148" width="7" height="12" rx="2" fill="#e03b3b"/>'
    return s + wheel(118) + wheel(290)


def offroader(c):
    b, a = c["body"], c["accent"]
    s = spare_edge(62, 140, 21)
    s += arch(116, 176, 38) + arch(290, 176, 38)
    s += poly("M62 176 L62 112 Q62 104 70 104 L250 104 L262 128 L338 134 Q348 136 348 148 L348 176 Z", b)
    s += poly("M80 112 L236 112 L248 132 L80 132 Z", GLASS)
    for x in (140, 196):
        s += f'<rect x="{x}" y="112" width="5" height="20" fill="{b}"/>'
    s += f'<rect x="88" y="94" width="140" height="6" rx="3" fill="{DARK}"/><rect x="100" y="98" width="4" height="8" fill="{DARK}"/><rect x="210" y="98" width="4" height="8" fill="{DARK}"/>'
    s += f'<rect x="150" y="82" width="54" height="10" rx="4" fill="{a}"/>'
    s += f'<rect x="62" y="150" width="286" height="7" fill="{a}"/>'
    s += f'<rect x="334" y="164" width="16" height="12" fill="{DARK}"/><circle cx="338" cy="146" r="6" fill="#ffe36b"/>'
    return s + wheel(116, 176, 32) + wheel(290, 176, 32)


def pickup(c):
    b, a = c["body"], c["accent"]
    s = arch(112) + arch(300)
    s += f'<rect x="50" y="124" width="150" height="52" rx="4" fill="{b}"/>'
    s += f'<rect x="58" y="130" width="134" height="40" rx="3" fill="{DARK}" opacity="0.55"/>'
    s += poly("M200 176 L200 124 L224 96 L292 96 L320 126 L352 132 Q362 134 362 148 L362 176 Z", b)
    s += poly("M230 104 L288 104 L310 128 L226 128 Z", GLASS)
    s += f'<rect x="50" y="150" width="312" height="6" fill="{a}"/>'
    s += f'<rect x="46" y="170" width="320" height="7" rx="3" fill="{CHROME}"/>'
    s += '<circle cx="352" cy="146" r="6" fill="#ffe36b"/><rect x="50" y="130" width="6" height="10" rx="2" fill="#e03b3b"/>'
    return s + wheel(112) + wheel(300)


def sports_car(c):
    b, a = c["body"], c["accent"]
    s = arch(108, 180, 29) + arch(296, 180, 29)
    s += poly("M36 178 L36 160 Q36 150 50 148 L130 138 Q165 112 205 110 Q250 110 280 130 L340 142 Q362 146 364 160 L364 178 Z", b)
    s += poly("M172 130 Q192 116 216 116 Q240 118 258 132 Z", GLASS)
    s += f'<path d="M60 156 L340 156" stroke="{a}" stroke-width="6"/>'
    s += f'<rect x="38" y="128" width="40" height="6" rx="2" fill="{a}"/><rect x="46" y="132" width="5" height="16" fill="{DARK}"/><rect x="66" y="132" width="5" height="16" fill="{DARK}"/>'
    s += '<path d="M340 146 L362 152 L352 160 L330 154 Z" fill="#ffe36b"/>'
    return s + wheel(108, 180, 25) + wheel(296, 180, 25)


def military_truck(c):  # wide-track military utility vehicle (generic): flat roof, long flat hood, narrow windows, big tyres
    b, a = c["body"], c["accent"]
    s = f'<path d="M70 80 L60 20" stroke="{DARK}" stroke-width="1.6"/>'
    s += poly("M44 166 L44 88 Q44 82 50 82 L236 82 L252 116 L338 118 L356 128 L356 166 Z", b)
    s += f'<rect x="120" y="76" width="54" height="7" rx="2" fill="{DARK}"/>'
    s += poly("M60 92 L102 92 L102 112 L60 112 Z", GLASS) + poly("M114 92 L158 92 L158 112 L114 112 Z", GLASS) + poly("M170 92 L210 92 L210 112 L170 112 Z", GLASS) + poly("M218 92 L232 92 L242 112 L218 112 Z", GLASS)
    s += "".join(f'<path d="M{x} 88 V150" stroke="#000" stroke-width="1.4" opacity=".3"/>' for x in (108, 164, 214, 250))
    s += "".join(f'<rect x="{x}" y="124" width="12" height="3.4" rx="1.7" fill="{DARK}"/>' for x in (140, 194))
    s += f'<rect x="44" y="150" width="312" height="16" fill="#2a2e22"/>'
    for cx in (98, 312):
        s += poly(f"M{cx - 42} 166 L{cx - 34} 132 L{cx + 34} 132 L{cx + 42} 166 Z", "#16180f")
    s += "".join(f'<path d="M{x} 118 L{x + 22} 119" stroke="#000" stroke-width="1.2" opacity=".3"/>' for x in (270, 300))
    s += f'<rect x="350" y="126" width="6" height="22" rx="1" fill="{DARK}"/><rect x="342" y="128" width="8" height="6" rx="1" fill="#ffe9a0"/>'
    s += f'<rect x="44" y="104" width="5" height="10" rx="1" fill="#e03b3b"/><rect x="348" y="160" width="14" height="8" rx="1" fill="{DARK}"/><rect x="36" y="160" width="12" height="8" rx="1" fill="{DARK}"/>'
    return s + wheel(98, 175, 30) + wheel(312, 175, 30)


def troop_transport(c):
    b, a = c["body"], c["accent"]
    s = arch(90, 180, 28) + arch(160, 180, 28) + arch(302, 180, 28)
    s += poly("M44 178 L44 110 Q44 84 74 84 L250 84 Q258 84 258 96 L258 178 Z", a)
    for x in (80, 120, 160, 200):
        s += f'<path d="M{x} 86 L{x} 170" stroke="{DARK}" stroke-width="2" opacity="0.35"/>'
    s += poly("M258 178 L258 112 L274 96 L330 96 L352 124 L360 132 L360 178 Z", b)
    s += poly("M280 104 L326 104 L344 124 L278 124 Z", GLASS)
    s += f'<rect x="44" y="168" width="316" height="8" fill="{DARK}"/>'
    s += '<circle cx="350" cy="144" r="6" fill="#ffe36b"/>'
    return s + wheel(90, 180, 24) + wheel(160, 180, 24) + wheel(302, 180, 24)


def recon(c):  # WWII-style quarter-ton scout (generic): short tub, flat hood, upright windshield, open seats, rear spare, jerry can
    b, a = c["body"], c["accent"]
    s = spare_edge(92, 142, 22)  # rear-mounted spare, edge-on
    s += f'<path d="M102 134 L94 40" stroke="{DARK}" stroke-width="1.6"/><rect x="98" y="128" width="8" height="8" rx="1" fill="{DARK}"/>'
    s += arch(130, 180, 29) + arch(272, 180, 29)
    s += poly("M92 178 L92 134 L252 134 L256 130 L312 130 Q318 130 318 137 L318 178 Z", b)
    s += poly("M178 134 L182 150 Q185 157 195 157 L226 157 Q234 157 236 149 L240 134 Z", "#1f2219")
    s += f'<rect x="120" y="112" width="16" height="24" rx="3" fill="#4a4630"/><rect x="198" y="110" width="16" height="26" rx="3" fill="#4a4630"/>'
    s += f'<path d="M238 132 L230 112" stroke="{DARK}" stroke-width="2.6"/><ellipse cx="230" cy="112" rx="8" ry="2.5" fill="{DARK}"/>'
    s += poly("M244 86 L252 86 L258 134 L250 134 Z", b) + poly("M246.5 90 L250 90 L255 130 L251.5 130 Z", GLASS)
    s += f'<rect x="96" y="116" width="18" height="20" rx="2" fill="#3b4423"/><path d="M99 120 H111 M99 126 H111" stroke="#000" stroke-width="1" opacity=".35"/>'
    s += f'<path d="M112 152 L170 152" stroke="#6d4524" stroke-width="3.4" stroke-linecap="round"/><path d="M170 148 L182 148 L184 156 L170 156 Z" fill="{DARK}"/>'
    s += "".join(f'<path d="M{x} 134 L{x} 144" stroke="#000" stroke-width="1.2" opacity=".3"/>' for x in (270, 278, 286, 294))
    s += f'<rect x="302" y="125" width="10" height="5" rx="1" fill="{DARK}"/><circle cx="312" cy="144" r="5" fill="#ffe36b"/>'
    s += f'<rect x="314" y="170" width="12" height="6" rx="1" fill="{DARK}"/><rect x="84" y="170" width="12" height="6" rx="1" fill="{DARK}"/><rect x="92" y="138" width="5" height="9" rx="1" fill="#e03b3b"/>'
    return s + wheel(130, 180, 25) + wheel(272, 180, 25)


def tank(c):
    b, a = c["body"], c["accent"]
    s = track(52, 146, 296, 52, (88, 124, 160, 196, 232, 268, 312), 13)
    s += poly("M66 148 L92 120 L318 120 L344 148 Z", b)
    s += poly("M150 120 L168 90 L262 90 L280 120 Z", b)
    s += f'<rect x="272" y="98" width="96" height="9" rx="2" fill="{DARK}"/><rect x="362" y="94" width="14" height="17" rx="3" fill="{DARK}"/>'
    s += f'<circle cx="206" cy="86" r="9" fill="{a}"/><rect x="204" y="64" width="4" height="22" fill="{DARK}"/>'
    s += f'<path d="M100 130 Q120 124 140 132 L120 140 Z" fill="{a}" opacity="0.8"/><path d="M290 132 Q310 126 328 134 L312 142 Z" fill="{a}" opacity="0.8"/>'
    return s


def armored_carrier(c):
    b, a = c["body"], c["accent"]
    s = "".join(arch(x, 180, 26) for x in (90, 140, 250, 310))
    s += poly("M44 178 L44 126 L66 108 L300 108 L336 134 L360 138 L360 178 Z", b)
    for x in (84, 130, 176):
        s += f'<rect x="{x}" y="120" width="30" height="9" rx="3" fill="{GLASS}"/>'
    s += poly("M254 114 L292 114 L318 134 L254 134 Z", GLASS)
    s += f'<rect x="170" y="90" width="64" height="18" rx="5" fill="{a}"/><rect x="226" y="95" width="42" height="6" fill="{DARK}"/>'
    s += f'<rect x="44" y="150" width="316" height="8" fill="{a}"/>'
    return s + "".join(wheel(x, 180, 22) for x in (90, 140, 250, 310))


def dump_truck(c):
    b, a = c["body"], c["accent"]
    s = arch(94, 180, 29) + arch(170, 180, 29) + arch(310, 180, 29)
    s += f'<rect x="44" y="164" width="318" height="14" fill="{DARK}"/>'
    s += poly("M48 162 L52 104 L246 90 L246 162 Z", b)
    for x in (90, 130, 170, 210):
        s += f'<path d="M{x} 100 L{x} 160" stroke="{DARK}" stroke-width="2" opacity="0.3"/>'
    s += poly("M250 176 L250 120 L270 100 L322 100 L346 130 L360 134 L360 176 Z", a)
    s += poly("M274 108 L318 108 L336 128 L272 128 Z", GLASS)
    s += f'<path d="M200 164 L226 110" stroke="{DARK}" stroke-width="5"/>'
    s += '<circle cx="350" cy="146" r="6" fill="#ffe36b"/>'
    return s + wheel(94, 180, 25) + wheel(170, 180, 25) + wheel(310, 180, 25)


def excavator(c):
    b, a = c["body"], c["accent"]
    s = track(96, 168, 200, 36, (122, 156, 190, 224, 264), 9)
    s += f'<rect x="112" y="138" width="26" height="30" rx="4" fill="{DARK}"/>'
    s += f'<rect x="130" y="128" width="116" height="42" rx="6" fill="{b}"/>'
    s += f'<rect x="184" y="98" width="56" height="38" rx="6" fill="{b}"/><rect x="192" y="106" width="40" height="22" rx="3" fill="{GLASS}"/>'
    s += f'<path d="M238 136 L292 74 L346 134" stroke="{b}" stroke-width="13" fill="none" stroke-linejoin="round"/>'
    s += f'<path d="M240 126 L284 96" stroke="{DARK}" stroke-width="5"/>'
    s += poly("M334 128 L372 134 L368 172 L346 176 L338 156 Z", DARK)
    s += f'<circle cx="292" cy="74" r="6" fill="{a}"/><circle cx="346" cy="134" r="6" fill="{a}"/>'
    return s


def bulldozer(c):
    b, a = c["body"], c["accent"]
    s = track(70, 150, 234, 54, (100, 140, 180, 220, 262), 12)
    s += f'<rect x="170" y="118" width="124" height="38" rx="6" fill="{b}"/>'
    s += f'<rect x="100" y="94" width="78" height="62" rx="6" fill="{b}"/><rect x="110" y="102" width="56" height="30" rx="3" fill="{GLASS}"/>'
    s += f'<rect x="262" y="92" width="9" height="28" fill="{DARK}"/><rect x="258" y="88" width="17" height="6" fill="{DARK}"/>'
    s += f'<path d="M300 150 L334 150 M300 168 L334 168" stroke="{DARK}" stroke-width="7"/>'
    s += poly("M318 112 L350 112 L358 192 L326 192 Z", a)
    s += f'<rect x="84" y="104" width="12" height="6" fill="{a}"/>'
    return s


def cement_mixer(c):
    b, a = c["body"], c["accent"]
    s = arch(96, 180, 29) + arch(160, 180, 29) + arch(306, 180, 29)
    s += f'<rect x="44" y="164" width="318" height="14" fill="{DARK}"/>'
    s += poly("M60 150 L74 100 Q104 82 176 88 L246 112 L246 160 Z", a)
    s += f'<path d="M84 96 L120 156 M120 90 L156 158 M158 92 L194 158 M196 96 L232 156" stroke="{b}" stroke-width="8" opacity="0.9"/>'
    s += f'<path d="M48 156 L36 176 L70 176" fill="none" stroke="{DARK}" stroke-width="7"/>'
    s += poly("M250 176 L250 120 L270 100 L322 100 L346 130 L360 134 L360 176 Z", b)
    s += poly("M274 108 L318 108 L336 128 L272 128 Z", GLASS)
    s += '<circle cx="350" cy="146" r="6" fill="#ffe36b"/>'
    return s + wheel(96, 180, 25) + wheel(160, 180, 25) + wheel(306, 180, 25)


def crane_truck(c):
    b, a = c["body"], c["accent"]
    s = arch(92, 180, 29) + arch(152, 180, 29) + arch(306, 180, 29)
    s += f'<rect x="44" y="160" width="318" height="18" fill="{DARK}"/>'
    s += f'<rect x="60" y="136" width="170" height="26" rx="4" fill="{a}"/>'
    s += f'<rect x="96" y="112" width="44" height="26" rx="4" fill="{b}"/>'
    s += f'<path d="M112 120 L292 36" stroke="{b}" stroke-width="14" stroke-linecap="round"/>'
    s += f'<path d="M126 128 L142 108 L158 122 L176 98 L192 112 L212 82 L228 96 L252 64" stroke="{DARK}" stroke-width="2" fill="none"/>'
    s += f'<path d="M292 40 L292 112" stroke="{DARK}" stroke-width="3"/><path d="M286 112 L298 112 L298 124 Q292 130 286 124 Z" fill="{DARK}"/>'
    s += poly("M250 176 L250 120 L270 100 L322 100 L346 130 L360 134 L360 176 Z", b)
    s += poly("M274 108 L318 108 L336 128 L272 128 Z", GLASS)
    s += '<circle cx="350" cy="146" r="6" fill="#ffe36b"/>'
    return s + wheel(92, 180, 25) + wheel(152, 180, 25) + wheel(306, 180, 25)


def front_loader(c):  # wheel loader: rear engine hood and counterweight, tall glass cab, Z-bar lift arms, big bucket
    b, a = c["body"], c["accent"]
    s = arch(112, 168, 40) + arch(282, 168, 40)
    s += f'<rect x="36" y="126" width="18" height="40" rx="4" fill="{DARK}"/>'
    s += poly("M48 166 L48 120 Q48 112 56 112 L168 112 L176 120 L176 166 Z", b)
    s += "".join(f'<path d="M{x} 118 V140" stroke="#000" stroke-width="2" opacity=".3"/>' for x in (64, 74, 84, 94))
    s += f'<rect x="132" y="88" width="8" height="26" fill="{DARK}"/><rect x="130" y="85" width="12" height="4" fill="{CHROME}"/>'
    s += poly("M150 120 L156 66 L230 66 L238 120 Z", b) + poly("M160 74 L224 74 L230 116 L156 116 Z", GLASS)
    s += f'<rect x="150" y="60" width="90" height="8" rx="3" fill="{a}"/><path d="M192 74 V116" stroke="{DARK}" stroke-width="3"/>'
    s += poly("M176 166 L176 124 L250 124 L262 150 L262 166 Z", b)
    s += f'<path d="M240 130 L330 118 L348 150" stroke="{b}" stroke-width="12" fill="none" stroke-linejoin="round" stroke-linecap="round"/>'
    s += f'<path d="M246 146 L320 134" stroke="{CHROME}" stroke-width="4"/><path d="M306 116 L322 102 L340 124" stroke="{DARK}" stroke-width="5" fill="none"/>'
    s += poly("M332 120 L382 112 L388 186 L340 196 L336 170 Z", a) + f'<path d="M340 194 L388 184" stroke="{DARK}" stroke-width="3"/>'
    s += '<circle cx="246" cy="132" r="5" fill="#ffe36b"/><rect x="48" y="146" width="5" height="9" rx="1" fill="#e03b3b"/>'
    return s + wheel(112, 168, 36) + wheel(282, 168, 36)


# ------------------------------------------------ v2 templates: more silhouettes, not just recolors
def _lights(front_x=352, y=150, rear_x=46):
    return (f'<circle cx="{front_x}" cy="{y}" r="6" fill="#ffe36b"/>'
            f'<rect x="{rear_x}" y="{y - 4}" width="7" height="12" rx="2" fill="#e03b3b"/>')


def sedan(c, extra=""):
    b, a = c["body"], c["accent"]
    s = arch(108) + arch(300)
    s += poly("M40 176 L40 152 Q40 142 54 140 L100 136 L126 110 Q132 104 142 104 L254 104 Q266 104 272 110 L300 136 L348 142 Q362 144 362 158 L362 176 Z", b)
    s += poly("M138 112 L192 112 L192 134 L118 134 Z", GLASS) + poly("M200 112 L252 112 L278 134 L200 134 Z", GLASS)
    s += f'<path d="M196 112 L196 160" stroke="{DARK}" stroke-width="2" opacity=".35"/>'
    s += f'<rect x="56" y="148" width="296" height="4" fill="{CHROME}"/><rect x="40" y="158" width="322" height="6" fill="{a}"/>'
    s += f'<rect x="36" y="170" width="330" height="7" rx="3" fill="{CHROME}"/>' + _lights(352, 152, 44)
    return s + extra + wheel(108) + wheel(300)


def taxi(c):
    extra = f'<rect x="172" y="92" width="48" height="13" rx="3" fill="#fff7e6" stroke="{DARK}" stroke-width="2"/><rect x="180" y="96" width="32" height="4" fill="{DARK}"/>'
    for i in range(29):
        extra += f'<rect x="{58 + i * 10}" y="{150 if i % 2 == 0 else 155}" width="10" height="5" fill="{DARK}"/>'
    return sedan(c, extra)


def patrol(c):
    extra = (f'<rect x="168" y="94" width="26" height="9" rx="2" fill="#e03b3b"/><rect x="194" y="94" width="26" height="9" rx="2" fill="#3d7be0"/>'
             f'<path d="M116 138 L284 138 L290 170 L110 170 Z" fill="{c["accent"]}"/><rect x="120" y="150" width="160" height="5" fill="{DARK}" opacity=".5"/>')
    return sedan(c, extra)


def wagon(c):
    b, a = c["body"], c["accent"]
    s = arch(112) + arch(292)
    s += poly("M44 176 L44 130 Q44 118 58 116 L290 114 L304 136 L346 142 Q358 144 358 158 L358 176 Z", b)
    s += poly("M68 120 L286 120 L298 136 L68 136 Z", GLASS)
    for x in (128, 190, 240):
        s += f'<rect x="{x}" y="120" width="5" height="16" fill="{b}"/>'
    s += '<rect x="44" y="146" width="314" height="20" fill="#9a6a3e"/>'
    for x in range(52, 350, 22):
        s += f'<path d="M{x} 146 V166" stroke="#6d4524" stroke-width="2"/>'
    s += f'<rect x="80" y="108" width="196" height="4" fill="{DARK}"/><rect x="104" y="94" width="64" height="14" rx="3" fill="{a}"/><rect x="176" y="98" width="40" height="10" rx="3" fill="{a}" opacity=".8"/>'
    s += f'<rect x="40" y="170" width="322" height="7" rx="3" fill="{CHROME}"/>' + _lights(346, 154, 48)
    return s + wheel(112) + wheel(292)


def roadster(c):
    b, a = c["body"], c["accent"]
    s = arch(108, 178, 29) + arch(296, 178, 29)
    s += poly("M36 178 L36 162 Q36 152 50 150 L150 146 L176 136 L298 138 L338 146 Q364 150 364 164 L364 178 Z", b)
    s += poly("M180 138 L296 140 L296 152 L180 150 Z", DARK)
    for x in (206, 252):
        s += f'<rect x="{x}" y="122" width="28" height="30" rx="9" fill="{a}"/>'
    s += poly("M168 142 L184 112 L192 112 L182 142 Z", GLASS)
    s += f'<path d="M52 164 H350" stroke="{a}" stroke-width="5"/>' + _lights(350, 156, 40)
    return s + wheel(108, 178, 26) + wheel(296, 178, 26)


def wedge(c):
    b, a = c["body"], c["accent"]
    s = arch(100, 182, 29) + arch(300, 182, 29)
    s += f'<rect x="34" y="124" width="54" height="6" rx="2" fill="{a}"/><rect x="44" y="130" width="5" height="26" fill="{DARK}"/><rect x="72" y="130" width="5" height="26" fill="{DARK}"/>'
    s += poly("M32 184 L32 168 L120 154 L196 126 Q222 114 252 118 L304 136 L352 148 Q368 152 368 166 L368 184 Z", b)
    s += poly("M202 130 Q222 120 246 124 L288 138 L196 142 Z", GLASS)
    s += poly("M168 156 L214 150 L214 168 L168 170 Z", DARK)
    s += f'<path d="M40 170 H360" stroke="{a}" stroke-width="5"/><path d="M338 150 L366 156 L350 162 Z" fill="#ffe36b"/>'
    return s + wheel(100, 182, 25) + wheel(300, 182, 25)


def open_wheel(c):
    b, a = c["body"], c["accent"]
    s = f'<rect x="50" y="118" width="40" height="8" rx="2" fill="{a}"/><rect x="50" y="116" width="4" height="40" fill="{DARK}"/><rect x="86" y="116" width="4" height="40" fill="{DARK}"/><rect x="66" y="126" width="5" height="34" fill="{DARK}"/>'
    s += poly("M80 172 L120 156 L190 146 L214 134 L240 134 L254 150 L330 160 L378 170 L378 178 L80 180 Z", b)
    s += f'<rect x="196" y="124" width="16" height="14" rx="3" fill="{DARK}"/><circle cx="228" cy="132" r="11" fill="{a}"/><rect x="226" y="128" width="14" height="6" rx="2" fill="{GLASS}"/>'
    s += f'<circle cx="150" cy="160" r="9" fill="#fff"/><rect x="352" y="178" width="46" height="7" rx="2" fill="{a}"/><rect x="390" y="168" width="4" height="18" fill="{DARK}"/>'
    return s + wheel(104, 170, 34) + wheel(324, 177, 26)


def dragster(c):
    b, a = c["body"], c["accent"]
    s = f'<rect x="60" y="110" width="42" height="7" rx="2" fill="{a}"/><rect x="76" y="117" width="5" height="40" fill="{DARK}"/>'
    s += poly("M110 178 L110 166 L350 160 L390 171 L390 180 L110 180 Z", b)
    s += f'<rect x="188" y="136" width="48" height="30" rx="4" fill="{CHROME}"/>' + poly("M196 136 L230 136 L226 118 L200 118 Z", a)
    s += f'<path d="M182 150 H150 M182 158 H150" stroke="{CHROME}" stroke-width="5"/>'
    s += f'<rect x="252" y="148" width="40" height="16" rx="6" fill="{DARK}"/><circle cx="272" cy="144" r="9" fill="{a}"/>'
    return s + wheel(96, 164, 40) + wheel(364, 191, 13) + wheel(336, 191, 13)


def fire_truck(c):
    b, a = c["body"], c["accent"]
    s = arch(96, 180, 28) + arch(168, 180, 28) + arch(316, 180, 28)
    s += f'<rect x="44" y="164" width="322" height="14" fill="{DARK}"/>'
    s += f'<rect x="48" y="112" width="210" height="52" rx="4" fill="{b}"/>'
    for x in (60, 108, 156, 204):
        s += f'<rect x="{x}" y="122" width="40" height="34" rx="3" fill="{DARK}" opacity=".28"/><path d="M{x} 132 H{x + 40} M{x} 142 H{x + 40}" stroke="{DARK}" stroke-width="1.5" opacity=".4"/>'
    s += f'<path d="M60 104 L250 98 M60 96 L250 90" stroke="{a}" stroke-width="3"/>'
    for x in range(70, 250, 16):
        s += f'<path d="M{x} 104 L{x} 96" stroke="{a}" stroke-width="2"/>'
    s += poly("M258 176 L258 108 L276 92 L326 92 L346 118 L362 124 Q368 126 368 140 L368 176 Z", b)
    s += poly("M280 100 L322 100 L338 118 L278 118 Z", GLASS)
    s += '<rect x="284" y="85" width="16" height="6" fill="#e03b3b"/><rect x="300" y="85" width="16" height="6" fill="#3d7be0"/>'
    s += f'<rect x="48" y="140" width="210" height="5" fill="{a}"/>' + '<circle cx="356" cy="144" r="6" fill="#ffe36b"/>'
    return s + wheel(96, 180, 25) + wheel(168, 180, 25) + wheel(316, 180, 25)


def rescue_van(c):
    b, a = c["body"], c["accent"]
    s = arch(112) + arch(296)
    s += poly("M46 176 L46 112 Q46 96 64 96 L282 96 Q300 96 312 112 L336 132 L358 138 Q366 140 366 152 L366 176 Z", b)
    s += poly("M290 102 L304 102 L328 130 L286 130 Z", GLASS) + f'<rect x="226" y="108" width="46" height="26" rx="4" fill="{GLASS}"/>'
    s += f'<rect x="46" y="140" width="320" height="12" fill="{a}"/>'
    for x in range(54, 200, 26):
        s += f'<path d="M{x} 112 L{x + 14} 112 L{x + 28} 134 L{x + 14} 134 Z" fill="{a}"/>'
    s += '<rect x="176" y="88" width="23" height="8" rx="2" fill="#e03b3b"/><rect x="199" y="88" width="23" height="8" rx="2" fill="#3d7be0"/>'
    s += _lights(354, 152, 48)
    return s + wheel(112) + wheel(296)


def school_bus(c):
    b = c["body"]
    s = arch(108, 178, 29) + arch(300, 178, 29)
    s += poly("M44 176 L44 98 Q44 90 52 90 L286 90 L300 118 L364 124 Q368 126 368 140 L368 176 Z", b)
    for i in range(6):
        s += f'<rect x="{58 + i * 37}" y="100" width="29" height="26" rx="4" fill="{GLASS}"/>'
    s += poly("M292 98 L298 98 L316 120 L290 120 Z", GLASS)
    s += f'<rect x="44" y="132" width="322" height="5" fill="{DARK}"/><rect x="44" y="152" width="322" height="5" fill="{DARK}"/>'
    s += '<circle cx="356" cy="148" r="6" fill="#ffe36b"/><rect x="48" y="104" width="8" height="12" fill="#e03b3b"/>'
    return s + wheel(108, 178, 26) + wheel(300, 178, 26)


def delivery_van(c):
    b, a = c["body"], c["accent"]
    s = arch(112) + arch(300)
    s += f'<rect x="44" y="80" width="206" height="90" rx="6" fill="{b}"/>'
    s += f'<rect x="44" y="120" width="206" height="14" fill="{a}"/><rect x="108" y="92" width="70" height="22" rx="4" fill="#fff7e6" opacity=".9"/><path d="M124 103 H162 M143 96 V110" stroke="{DARK}" stroke-width="3"/>'
    s += poly("M250 176 L250 112 L270 96 L324 96 L346 124 L360 130 Q366 132 366 146 L366 176 Z", a)
    s += poly("M274 104 L320 104 L338 124 L272 124 Z", GLASS)
    s += f'<rect x="44" y="164" width="322" height="12" fill="{DARK}"/>' + '<circle cx="356" cy="146" r="6" fill="#ffe36b"/>'
    return s + wheel(112) + wheel(300)


def ice_cream_truck(c):
    b, a = c["body"], c["accent"]
    s = arch(112) + arch(296)
    s += poly("M158 98 L182 98 L170 70 Z", "#d9a15b") + '<circle cx="170" cy="62" r="15" fill="#f6a5c0"/><circle cx="170" cy="49" r="11" fill="#fff7e6"/><circle cx="174" cy="38" r="4" fill="#e03b3b"/>'
    s += f'<rect x="50" y="96" width="300" height="80" rx="22" fill="{b}"/>'
    s += f'<rect x="120" y="116" width="82" height="34" rx="4" fill="{DARK}" opacity=".75"/>'
    for i, x in enumerate(range(112, 210, 14)):
        s += f'<path d="M{x} 110 L{x + 14} 110 L{x + 17} 124 L{x + 3} 124 Z" fill="{a if i % 2 == 0 else "#fff7e6"}"/>'
    s += f'<rect x="116" y="150" width="90" height="5" fill="{CHROME}"/><rect x="290" y="108" width="44" height="30" rx="8" fill="{GLASS}"/>'
    s += f'<rect x="50" y="160" width="300" height="8" fill="{a}"/>' + _lights(340, 150, 54)
    return s + wheel(112, 178, 26) + wheel(296, 178, 26)


def tow_truck(c):
    b, a = c["body"], c["accent"]
    s = arch(96, 180, 28) + arch(160, 180, 28) + arch(300, 180, 28)
    s += f'<rect x="44" y="160" width="322" height="18" fill="{DARK}"/>'
    s += f'<rect x="64" y="138" width="96" height="22" rx="3" fill="{a}"/>'
    s += f'<path d="M84 140 L160 90" stroke="{a}" stroke-width="12" stroke-linecap="round"/><path d="M160 92 L160 140" stroke="{DARK}" stroke-width="3"/><circle cx="160" cy="146" r="6" fill="none" stroke="{DARK}" stroke-width="3"/>'
    s += poly("M236 176 L236 112 L256 94 L312 94 L338 122 L358 128 Q364 130 364 144 L364 176 Z", b)
    s += poly("M260 102 L308 102 L328 122 L258 122 Z", GLASS) + '<rect x="262" y="86" width="40" height="7" rx="2" fill="#ffb020"/>'
    s += '<circle cx="354" cy="146" r="6" fill="#ffe36b"/>'
    return s + wheel(96, 180, 25) + wheel(160, 180, 25) + wheel(300, 180, 25)


def garbage_truck(c):
    b, a = c["body"], c["accent"]
    s = arch(112, 180, 28) + arch(300, 180, 28)
    s += f'<rect x="44" y="164" width="322" height="14" fill="{DARK}"/>'
    s += poly("M44 176 L44 98 Q44 84 70 84 L240 84 Q252 84 252 100 L252 176 Z", b)
    for y in (104, 124, 144):
        s += f'<path d="M48 {y} H250" stroke="{DARK}" stroke-width="2" opacity=".3"/>'
    s += f'<rect x="48" y="146" width="44" height="22" rx="3" fill="{DARK}"/><path d="M44 150 L28 118 L28 172" fill="none" stroke="{DARK}" stroke-width="7" stroke-linejoin="round"/>'
    s += poly("M252 176 L252 110 L270 94 L322 94 L346 122 L362 128 Q368 130 368 144 L368 176 Z", a)
    s += poly("M274 102 L318 102 L336 122 L272 122 Z", GLASS) + '<circle cx="358" cy="146" r="6" fill="#ffe36b"/>'
    s += f'<rect x="252" y="140" width="116" height="6" fill="{b}"/>'
    return s + wheel(112, 180, 25) + wheel(300, 180, 25)


def camper(c):
    b, a = c["body"], c["accent"]
    s = arch(108, 178, 29) + arch(300, 178, 29)
    s += f'<rect x="44" y="86" width="226" height="90" rx="12" fill="{b}"/><rect x="110" y="76" width="42" height="10" rx="3" fill="{SLV if False else "#b9c0cc"}"/>'
    s += poly("M270 176 L270 118 L284 104 L316 104 L342 130 L362 134 Q366 136 366 150 L366 176 Z", a)
    s += poly("M288 112 L314 112 L330 130 L286 130 Z", GLASS)
    s += f'<rect x="64" y="104" width="52" height="30" rx="5" fill="{GLASS}"/><rect x="134" y="104" width="40" height="30" rx="5" fill="{GLASS}"/>'
    s += f'<rect x="196" y="106" width="38" height="56" rx="5" fill="{a}"/><rect x="202" y="112" width="26" height="20" rx="3" fill="{GLASS}"/>'
    s += f'<path d="M44 150 Q100 132 150 150 T270 150" stroke="{a}" stroke-width="8" fill="none"/>'
    s += f'<path d="M48 90 V170 M54 90 V170" stroke="{DARK}" stroke-width="2" opacity=".5"/><circle cx="356" cy="150" r="6" fill="#ffe36b"/>'
    return s + wheel(108, 178, 26) + wheel(300, 178, 26)


def dune_buggy(c):  # fiberglass-tub beach buggy: curved fenders, exposed rear engine, roll bar, bug-eye lamps, short wheelbase
    b, a = c["body"], c["accent"]
    s = f'<rect x="56" y="132" width="36" height="30" rx="4" fill="{CHROME}"/>' + "".join(f'<path d="M{x} 136 V158" stroke="{DARK}" stroke-width="2"/>' for x in (62, 70, 78, 86))
    s += f'<circle cx="74" cy="126" r="8" fill="{DARK}"/><path d="M60 156 Q46 150 44 136" stroke="{CHROME}" stroke-width="4" fill="none" stroke-linecap="round"/>'
    s += arch(118, 172, 36) + arch(290, 178, 30)
    s += f'<path d="M152 138 L162 98 L198 98 L204 150" stroke="{DARK}" stroke-width="5" fill="none" stroke-linejoin="round"/>'
    s += poly("M86 170 L88 142 Q116 116 154 136 L170 150 L234 150 Q246 130 268 128 L310 132 Q334 136 342 156 L342 170 Z", b)
    s += f'<rect x="188" y="118" width="16" height="34" rx="5" fill="{a}"/><rect x="214" y="122" width="14" height="30" rx="5" fill="{a}"/>'
    s += poly("M232 130 L240 106 L246 106 L242 132 Z", GLASS) + f'<path d="M240 106 L232 130" stroke="{DARK}" stroke-width="1.6"/>'
    s += f'<path d="M318 132 L318 124" stroke="{DARK}" stroke-width="2"/><circle cx="318" cy="120" r="7" fill="{CHROME}"/><circle cx="318" cy="120" r="5" fill="#ffe36b"/>'
    s += '<rect x="86" y="146" width="5" height="9" rx="1" fill="#e03b3b"/>'
    return s + wheel(118, 172, 32) + wheel(290, 178, 26)


def mud_truck(c):
    b, a = c["body"], c["accent"]
    s = arch(112, 166, 46) + arch(300, 166, 46)
    s += f'<rect x="96" y="150" width="220" height="12" rx="3" fill="{DARK}"/>'
    s += '<g transform="translate(0 -30)">'
    s += f'<rect x="50" y="124" width="150" height="52" rx="4" fill="{b}"/><rect x="58" y="130" width="134" height="40" rx="3" fill="{DARK}" opacity=".55"/>'
    s += poly("M200 176 L200 124 L224 96 L292 96 L320 126 L352 132 Q362 134 362 148 L362 176 Z", b)
    s += poly("M230 104 L288 104 L310 128 L226 128 Z", GLASS)
    s += f'<rect x="50" y="150" width="312" height="6" fill="{a}"/><rect x="234" y="86" width="52" height="8" rx="3" fill="{DARK}"/>'
    s += '<circle cx="352" cy="146" r="6" fill="#ffe36b"/></g>'
    for cx in (112, 300):
        s += wheel(cx, 166, 40) + f'<circle cx="{cx}" cy="166" r="36" fill="none" stroke="#3b3f48" stroke-width="5" stroke-dasharray="7 5"/>'
    return s


def hot_rod(c):
    b, a = c["body"], c["accent"]
    s = f'<rect x="48" y="140" width="104" height="36" rx="12" fill="{b}"/>'
    s += poly("M150 176 L150 118 Q150 106 164 104 L222 104 Q234 106 238 118 L240 176 Z", b)
    s += poly("M160 112 L226 112 L230 128 L160 128 Z", GLASS)
    s += poly("M240 176 L240 134 L322 134 L322 176 Z", b)
    for x in (252, 262, 272):
        s += f'<path d="M{x} 138 V150" stroke="{DARK}" stroke-width="2"/>'
    s += f'<rect x="268" y="116" width="38" height="18" rx="4" fill="{CHROME}"/><path d="M276 116 L296 108 L300 116" fill="{a}"/>'
    s += f'<rect x="322" y="128" width="14" height="48" rx="3" fill="{CHROME}"/><circle cx="318" cy="124" r="8" fill="#ffe36b" stroke="{CHROME}" stroke-width="3"/>'
    s += f'<path d="M246 164 Q270 142 262 154 Q290 144 280 158 Q310 150 300 168 L246 172 Z" fill="{a}"/>'
    s += f'<path d="M180 168 H300" stroke="{CHROME}" stroke-width="5"/>'
    return s + wheel(104, 170, 34) + wheel(300, 180, 24)


def bug(c):
    b, a = c["body"], c["accent"]
    s = arch(108) + arch(292)
    s += poly("M52 176 Q46 140 84 118 Q124 92 188 96 Q262 100 308 132 Q352 146 354 176 Z", b)
    s += poly("M120 118 Q160 100 204 104 Q248 110 276 134 L120 134 Z", GLASS)
    s += f'<rect x="196" y="104" width="4" height="30" fill="{b}"/>'
    s += f'<path d="M286 176 Q290 146 326 148 Q352 152 354 176 Z" fill="{a}"/><path d="M52 176 Q52 150 80 146 Q104 148 106 176 Z" fill="{a}"/>'
    s += f'<rect x="130" y="164" width="150" height="6" rx="3" fill="{DARK}"/>'
    s += f'<circle cx="338" cy="152" r="9" fill="{CHROME}"/><circle cx="338" cy="152" r="6" fill="#ffe36b"/><rect x="40" y="170" width="20" height="6" rx="3" fill="{CHROME}"/><rect x="346" y="170" width="18" height="6" rx="3" fill="{CHROME}"/>'
    return s + wheel(108) + wheel(292)


def limo(c):
    b, a = c["body"], c["accent"]
    s = arch(88) + arch(318)
    s += poly("M26 176 L26 152 Q26 142 40 140 L82 136 L106 112 Q112 106 122 106 L300 106 Q312 106 318 112 L340 136 L362 140 Q376 142 376 156 L376 176 Z", b)
    s += poly("M118 114 L168 114 L168 134 L98 134 Z", GLASS) + poly("M176 114 L224 114 L224 134 L176 134 Z", GLASS) + poly("M232 114 L296 114 L322 134 L232 134 Z", GLASS)
    s += f'<rect x="40" y="148" width="326" height="4" fill="{CHROME}"/><rect x="26" y="158" width="350" height="6" fill="{a}"/><rect x="22" y="170" width="358" height="7" rx="3" fill="{CHROME}"/>'
    s += _lights(364, 152, 32)
    return s + wheel(88) + wheel(318)


def trail_jeep(c):
    b, a = c["body"], c["accent"]
    s = f'<circle cx="48" cy="150" r="20" fill="{TIRE}"/><circle cx="48" cy="150" r="10" fill="{HUB}"/>'
    s += arch(116, 176, 38) + arch(292, 176, 38)
    s += poly("M58 176 L58 142 L152 140 L162 122 L290 126 L318 136 L346 142 Q356 144 356 158 L356 176 Z", b)
    s += poly("M60 142 Q62 100 100 98 L170 100 L172 138 Z", a) + poly("M84 112 L132 110 L132 128 L84 130 Z", GLASS)
    s += poly("M176 104 L192 104 L202 126 L178 128 Z", GLASS) + f'<path d="M176 104 L202 126" stroke="{DARK}" stroke-width="3"/>'
    for x in range(330, 352, 4):
        s += f'<rect x="{x}" y="144" width="2" height="20" fill="{DARK}"/>'
    s += '<circle cx="324" cy="150" r="7" fill="#ffe36b"/>'
    return s + wheel(116, 176, 32) + wheel(292, 176, 32)


def fuel_tanker(c):
    b, a = c["body"], c["accent"]
    s = arch(96, 180, 28) + arch(168, 180, 28) + arch(312, 180, 28)
    s += f'<rect x="44" y="164" width="322" height="14" fill="{DARK}"/>'
    s += f'<rect x="48" y="100" width="206" height="62" rx="31" fill="{b}"/>'
    for x in (90, 140, 190):
        s += f'<path d="M{x} 102 V160" stroke="{DARK}" stroke-width="2" opacity=".35"/>'
    s += f'<rect x="140" y="90" width="22" height="10" rx="3" fill="{DARK}"/><path d="M60 150 H240" stroke="{a}" stroke-width="5"/>'
    s += poly("M258 176 L258 114 L274 98 L326 98 L350 120 L362 126 Q368 128 368 142 L368 176 Z", a)
    s += poly("M278 106 L322 106 L338 120 L276 120 Z", GLASS) + '<circle cx="358" cy="146" r="6" fill="#ffe36b"/>'
    return s + wheel(96, 180, 25) + wheel(168, 180, 25) + wheel(312, 180, 25)


# ------------------------------------------------ v3 templates: classic silhouettes (all generic, no real makes)
def boxy_sedan(c):  # formal 80s "land yacht" with vinyl roof and opera window
    b, a = c["body"], c["accent"]
    s = arch(104, 178, 31) + arch(312, 178, 31)
    s += poly("M28 178 L28 150 Q28 140 42 138 L62 136 L88 114 L96 108 L292 108 L316 114 L344 136 L368 140 Q380 142 380 156 L380 178 Z", b)
    s += poly("M96 108 L292 108 L316 114 L320 126 L90 126 L86 118 Z", a)           # vinyl roof
    s += poly("M104 118 L186 118 L186 136 L96 136 Z", GLASS) + poly("M194 118 L286 118 L308 136 L194 136 Z", GLASS)
    s += f'<ellipse cx="96" cy="124" rx="7" ry="9" fill="{GLASS}"/>'                # opera window
    s += f'<rect x="28" y="150" width="352" height="4" fill="{CHROME}"/><rect x="28" y="160" width="352" height="9" fill="{a}" opacity=".85"/>'
    s += f'<rect x="22" y="171" width="366" height="8" rx="3" fill="{CHROME}"/>'
    s += f'<rect x="366" y="144" width="14" height="24" rx="2" fill="{CHROME}"/>' + "".join(f'<path d="M{x} 146 V166" stroke="{DARK}" stroke-width="1.4"/>' for x in (369, 372, 375))
    s += '<rect x="352" y="146" width="12" height="9" rx="2" fill="#ffe36b"/><rect x="26" y="146" width="9" height="14" rx="2" fill="#e03b3b"/>'
    return s + wheel(104, 178, 27, style="steel", white=True) + wheel(312, 178, 27, style="steel", white=True)


def wagon_modern(c):  # long-roof family wagon with roof rails and rear spoiler
    b, a = c["body"], c["accent"]
    s = arch(112) + arch(298)
    s += poly("M42 176 L42 138 L66 112 L298 106 L322 128 L350 138 Q364 142 364 158 L364 176 Z", b)
    s += poly("M72 116 L126 114 L126 134 L56 134 Z", GLASS) + poly("M132 114 L196 113 L196 134 L132 134 Z", GLASS) + poly("M202 113 L294 111 L312 134 L202 134 Z", GLASS)
    s += f'<rect x="66" y="104" width="232" height="4" rx="2" fill="{DARK}"/><rect x="50" y="108" width="26" height="4" fill="{a}"/>'
    s += f'<rect x="42" y="152" width="320" height="4" fill="{CHROME}" opacity=".9"/><rect x="42" y="162" width="320" height="6" fill="{a}"/>'
    s += f'<rect x="38" y="170" width="328" height="7" rx="3" fill="{DARK}"/>' + _lights(352, 154, 44)
    return s + wheel(112, 178, 27) + wheel(298, 178, 27)


def rear_engine(c):  # rounded rear-engine fastback with duck-tail and round lamps (Stuttgart-style, generic)
    b, a = c["body"], c["accent"]
    s = arch(108, 178, 31) + arch(290, 178, 29)
    s += poly("M40 176 Q34 152 62 136 Q108 104 170 100 Q228 100 264 118 Q302 134 342 146 Q364 152 364 176 Z", b)
    s += poly("M148 108 Q200 104 244 120 L274 134 L122 134 Q128 116 148 108 Z", GLASS)
    s += f'<path d="M40 150 Q36 138 56 136 L72 140" fill="{a}"/><path d="M52 164 H350" stroke="{a}" stroke-width="5"/>'
    s += f'<circle cx="338" cy="148" r="11" fill="{CHROME}"/><circle cx="338" cy="148" r="8" fill="#ffe9a0"/><circle cx="335" cy="145" r="3" fill="#fff"/>'
    s += f'<path d="M230 150 L262 146" stroke="{DARK}" stroke-width="3" stroke-linecap="round"/><rect x="40" y="168" width="14" height="7" rx="3" fill="{DARK}"/>'
    return s + wheel(108, 178, 28, style="mag") + wheel(290, 178, 26, style="mag")


def spider(c):  # small open 2-seater, rounded boat-tail, shield-style nose (Milano-style, generic)
    b, a = c["body"], c["accent"]
    s = arch(112, 178, 29) + arch(290, 178, 29)
    s += poly("M40 178 L40 160 Q42 148 70 144 L150 142 L186 128 L300 134 Q348 140 364 156 Q370 164 366 178 Z", b)
    s += poly("M186 134 L296 138 L296 150 L186 148 Z", DARK)
    for x in (214, 256):
        s += f'<rect x="{x}" y="120" width="26" height="30" rx="9" fill="{a}"/>'
    s += poly("M176 144 L188 116 L196 116 L186 144 Z", GLASS)
    s += poly("M352 152 L368 158 L352 172 Z", CHROME) + f'<circle cx="340" cy="152" r="8" fill="{CHROME}"/><circle cx="340" cy="152" r="5" fill="#ffe9a0"/>'
    s += f'<path d="M56 160 Q150 152 230 160 T350 160" stroke="{a}" stroke-width="4" fill="none"/>'
    return s + wheel(112, 178, 26, style="wire") + wheel(290, 178, 26, style="wire")


def rat_rod(c):  # patina hot rod: rust, primer patches, exposed engine, exhaust stacks
    b, a = c["body"], c["accent"]
    s = ""
    s += f'<rect x="150" y="150" width="124" height="22" rx="3" fill="{DARK}"/>'
    s += f'<rect x="212" y="126" width="46" height="26" rx="3" fill="{CHROME}"/>' + "".join(f'<rect x="{x}" y="116" width="6" height="12" fill="{CHROME}"/>' for x in (218, 230, 242))
    s += f'<path d="M270 160 V92 M284 160 V100" stroke="{CHROME}" stroke-width="6" stroke-linecap="round"/>'
    s += poly("M104 176 L104 130 L120 112 L188 112 L202 128 L204 176 Z", b)
    s += poly("M124 118 L184 118 L194 130 L116 130 Z", GLASS)
    s += poly("M110 140 L142 134 L150 150 L112 158 Z", "#9aa0a8") + poly("M164 150 L194 146 L196 168 L166 170 Z", "#8a8d94")
    s += f'<rect x="44" y="150" width="62" height="26" rx="4" fill="{b}"/><path d="M50 154 L82 152 L84 168 L52 170 Z" fill="#7a3f1c" opacity=".8"/>'
    s += f'<rect x="272" y="128" width="16" height="48" rx="3" fill="{CHROME}"/><circle cx="296" cy="146" r="8" fill="#ffe36b" stroke="{CHROME}" stroke-width="3"/>'
    s += f'<path d="M148 172 H278" stroke="#c2682f" stroke-width="5"/>'
    s += f'<path d="M210 108 L236 100 M64 140 H98" stroke="{a}" stroke-width="3"/>'
    return s + wheel(88, 170, 34, style="steel") + wheel(300, 180, 24, style="steel")


def motorhome(c):  # class-A motorhome with swoosh stripes (Winnebago-style, generic)
    b, a = c["body"], c["accent"]
    s = arch(104, 178, 31) + arch(298, 178, 31)
    s += f'<rect x="36" y="70" width="336" height="104" rx="16" fill="{b}"/>'
    s += poly("M318 76 L366 82 L368 128 L318 126 Z", GLASS)
    for x in (58, 114, 170):
        s += f'<rect x="{x}" y="90" width="46" height="28" rx="5" fill="{GLASS}"/>'
    s += f'<rect x="232" y="88" width="38" height="70" rx="5" fill="{a}"/><rect x="238" y="94" width="26" height="24" rx="3" fill="{GLASS}"/><rect x="276" y="92" width="34" height="26" rx="5" fill="{GLASS}"/>'
    s += poly("M36 150 L290 126 L372 130 L372 142 L290 138 L36 164 Z", a) + poly("M36 164 L290 138 L372 142 L372 148 L290 144 L36 170 Z", DARK)
    s += f'<rect x="120" y="60" width="52" height="10" rx="4" fill="{SLV}"/><rect x="32" y="168" width="344" height="9" rx="3" fill="{DARK}"/>'
    s += '<rect x="356" y="152" width="14" height="10" rx="3" fill="#ffe36b"/><rect x="38" y="148" width="8" height="14" rx="2" fill="#e03b3b"/>'
    return s + wheel(104, 178, 27, style="disc") + wheel(298, 178, 27, style="disc")


def boxy_suv(c):  # tall boxy 90s SUV with roof rails, flares and side steps (Trooper-style, generic)
    b, a = c["body"], c["accent"]
    s = arch(118, 178, 33) + arch(288, 178, 33)
    s += poly("M52 176 L52 118 Q52 106 64 104 L268 102 L296 126 L340 134 Q352 138 352 152 L352 176 Z", b)
    s += poly("M72 110 L122 110 L122 130 L64 130 Z", GLASS) + poly("M128 110 L186 110 L186 130 L128 130 Z", GLASS) + poly("M192 110 L262 109 L286 130 L192 130 Z", GLASS)
    s += f'<rect x="70" y="96" width="196" height="5" rx="2" fill="{DARK}"/><rect x="82" y="100" width="4" height="6" fill="{DARK}"/><rect x="250" y="100" width="4" height="6" fill="{DARK}"/>'
    s += f'<rect x="52" y="148" width="300" height="5" fill="{a}"/><rect x="150" y="166" width="90" height="6" rx="2" fill="{CHROME}"/>'
    s += f'<rect x="330" y="140" width="22" height="24" rx="3" fill="{DARK}"/><rect x="334" y="146" width="14" height="4" fill="{CHROME}"/><rect x="334" y="154" width="14" height="4" fill="{CHROME}"/>'
    s += '<rect x="338" y="132" width="12" height="8" rx="2" fill="#ffe36b"/><rect x="50" y="138" width="8" height="14" rx="2" fill="#e03b3b"/>'
    return s + wheel(118, 178, 29, style="steel") + wheel(288, 178, 29, style="steel")


def kei_3wheel(c):  # Japanese three-wheel mini truck: one front wheel, open cab, slatted bed
    b, a = c["body"], c["accent"]
    s = ""
    s += f'<rect x="56" y="126" width="176" height="36" rx="3" fill="{a}"/>' + "".join(f'<path d="M{x} 128 V160" stroke="{DARK}" stroke-width="2" opacity=".35"/>' for x in range(72, 230, 16))
    s += f'<rect x="52" y="122" width="184" height="6" rx="2" fill="{DARK}"/>'
    s += poly("M232 162 L232 118 Q234 96 262 94 L296 94 Q318 96 322 124 L330 162 Z", b)
    s += f'<rect x="246" y="102" width="44" height="30" rx="8" fill="{GLASS}"/><rect x="238" y="96" width="62" height="6" rx="3" fill="{DARK}"/>'
    s += f'<path d="M296 132 L326 140" stroke="{DARK}" stroke-width="4"/><circle cx="330" cy="142" r="8" fill="{CHROME}"/><circle cx="330" cy="142" r="5" fill="#ffe9a0"/>'
    s += f'<path d="M300 160 Q318 120 340 160 Z" fill="{b}"/><rect x="52" y="160" width="284" height="8" rx="3" fill="{DARK}"/>'
    s += f'<path d="M224 114 L214 100" stroke="{DARK}" stroke-width="3"/><circle cx="212" cy="98" r="4" fill="{CHROME}"/>'
    return s + wheel(112, 178, 25, style="steel") + wheel(306, 178, 24, style="steel")


def trike_bike(c):  # US-style touring trike: front fork, tank, trunk, twin rear wheels, chrome pipes
    b, a = c["body"], c["accent"]
    s = wheel(98, 174, 30, style="wire") + wheel(112, 174, 30, style="wire")
    s += f'<path d="M80 150 Q110 124 150 150" fill="{CHROME}" opacity=".9"/>'
    s += f'<rect x="62" y="98" width="108" height="48" rx="14" fill="{b}"/><rect x="70" y="106" width="92" height="12" rx="6" fill="{a}"/><rect x="66" y="132" width="100" height="5" fill="{CHROME}"/>'
    s += f'<rect x="172" y="124" width="68" height="18" rx="8" fill="{DARK}"/>'
    s += f'<path d="M236 126 Q262 100 308 112 L300 136 Q262 140 236 138 Z" fill="{b}"/><path d="M246 124 Q268 108 298 116" stroke="#fff" stroke-width="3" opacity=".45" fill="none"/>'
    s += f'<rect x="214" y="148" width="62" height="28" rx="6" fill="{CHROME}"/>' + "".join(f'<path d="M{x} 150 V174" stroke="{DARK}" stroke-width="1.6"/>' for x in (226, 238, 250, 262))
    s += f'<path d="M210 168 H70" stroke="{CHROME}" stroke-width="9" stroke-linecap="round"/><path d="M210 176 H72" stroke="{DARK}" stroke-width="2" opacity=".5"/>'
    s += f'<path d="M334 176 L298 112" stroke="{CHROME}" stroke-width="6" stroke-linecap="round"/><path d="M296 112 L284 96 L306 92" stroke="{DARK}" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    s += f'<circle cx="314" cy="124" r="11" fill="{CHROME}"/><circle cx="314" cy="124" r="8" fill="#ffe9a0"/><path d="M300 100 Q312 80 330 96" fill="{GLASS}" opacity=".85"/>'
    return s + wheel(334, 174, 30, style="wire")


def city_mini(c):  # tiny rounded city car (Roman-style micro car, generic)
    b, a = c["body"], c["accent"]
    s = arch(112, 180, 27) + arch(290, 180, 27)
    s += poly("M80 178 Q68 150 90 130 Q112 100 172 98 Q228 100 264 126 Q300 136 318 156 Q328 178 318 178 Z", b)
    s += poly("M118 124 Q150 106 196 106 Q236 110 258 130 L120 134 Z", GLASS) + f'<rect x="188" y="106" width="4" height="28" fill="{b}"/>'
    s += f'<circle cx="312" cy="152" r="9" fill="{CHROME}"/><circle cx="312" cy="152" r="6" fill="#ffe9a0"/><rect x="302" y="164" width="22" height="6" rx="3" fill="{CHROME}"/>'
    s += f'<path d="M86 158 Q200 148 316 160" stroke="{a}" stroke-width="5" fill="none"/><rect x="76" y="166" width="20" height="6" rx="3" fill="{CHROME}"/>'
    s += f'<rect x="92" y="132" width="26" height="14" rx="3" fill="{DARK}" opacity=".6"/>' + "".join(f'<path d="M{x} 134 V144" stroke="{CHROME}" stroke-width="1.5"/>' for x in (98, 104, 110))
    return s + wheel(112, 180, 24, style="disc") + wheel(290, 180, 24, style="disc")


def classic_luxury_suv(c):  # two-door two-tone luxury 4x4 with long flat hood (Highland-style, generic)
    b, a = c["body"], c["accent"]
    s = arch(112, 178, 32) + arch(292, 178, 32)
    s += poly("M50 176 L50 118 L58 108 L268 106 L286 126 L346 130 Q356 134 356 148 L356 176 Z", b)
    s += poly("M50 138 L356 138 L356 176 L50 176 Z", a)
    s += poly("M66 112 L176 112 L176 130 L66 130 Z", GLASS) + poly("M182 112 L262 111 L278 130 L182 130 Z", GLASS)
    s += f'<rect x="60" y="98" width="196" height="5" rx="2" fill="{DARK}"/><path d="M40 138 H362" stroke="{CHROME}" stroke-width="3"/>'
    s += f'<rect x="326" y="142" width="30" height="22" rx="3" fill="{DARK}"/>' + "".join(f'<path d="M{x} 144 V162" stroke="{CHROME}" stroke-width="1.5"/>' for x in (332, 338, 344, 350))
    s += '<rect x="326" y="132" width="14" height="9" rx="2" fill="#ffe36b"/><rect x="48" y="142" width="8" height="14" rx="2" fill="#e03b3b"/>'
    s += f'<rect x="44" y="168" width="318" height="8" rx="3" fill="{DARK}"/><path d="M200 144 H230 M200 150 H230" stroke="{DARK}" stroke-width="2" opacity=".5"/>'
    return s + wheel(112, 178, 29, style="steel") + wheel(292, 178, 29, style="steel")


def gt_coupe(c):  # low 60s grand-touring fastback, wire wheels, plexi lamps
    b, a = c["body"], c["accent"]
    s = arch(110, 178, 29) + arch(300, 178, 29)
    s += poly("M36 176 L36 158 Q38 148 56 146 L150 142 Q186 112 246 112 Q290 114 316 138 L350 146 Q364 150 364 164 L364 176 Z", b)
    s += poly("M168 140 Q192 118 240 118 Q274 122 296 140 Z", GLASS)
    s += f'<path d="M50 160 H352" stroke="{a}" stroke-width="5"/><path d="M262 132 L292 140" stroke="{DARK}" stroke-width="2" opacity=".4"/>'
    s += f'<circle cx="344" cy="152" r="10" fill="{CHROME}"/><circle cx="344" cy="152" r="7" fill="#ffe9a0"/><path d="M354 164 Q364 166 364 172 L346 172 Z" fill="{DARK}"/>'
    s += "".join(f'<path d="M{x} 128 L{x + 8} 138" stroke="{DARK}" stroke-width="2" opacity=".4"/>' for x in (108, 114, 120))
    s += f'<rect x="32" y="170" width="332" height="6" rx="3" fill="{CHROME}"/><rect x="40" y="150" width="8" height="12" rx="2" fill="#e03b3b"/>'
    return s + wheel(110, 178, 26, style="wire") + wheel(300, 178, 26, style="wire")


def pickup_classic(c):  # 1950s step-side: bulbous fenders, wood bed, running board, bucket headlamps
    b, a = c["body"], c["accent"]
    s = arch(100, 178, 32) + arch(306, 178, 32)
    s += f'<rect x="44" y="132" width="132" height="42" rx="3" fill="#a9743f"/>' + "".join(f'<path d="M44 {y} H176" stroke="#6d4524" stroke-width="2"/>' for y in (142, 152, 162))
    s += f'<rect x="40" y="126" width="140" height="8" rx="3" fill="{b}"/>'
    s += poly("M172 178 L172 126 Q174 104 198 100 L252 100 Q274 102 282 122 L288 150 L288 178 Z", b)
    s += poly("M182 112 Q184 106 198 106 L248 106 Q264 108 270 122 L182 122 Z", GLASS) + f'<rect x="180" y="126" width="104" height="3" fill="{a}"/>'
    s += poly("M284 178 L284 140 Q288 132 304 132 L344 134 Q358 138 358 152 L358 178 Z", b)
    s += f'<path d="M64 178 A38 38 0 0 1 138 178 Z" fill="{b}"/><path d="M270 178 A38 38 0 0 1 344 178 Z" fill="{b}"/>'
    s += f'<circle cx="340" cy="140" r="11" fill="{CHROME}"/><circle cx="340" cy="140" r="8" fill="#ffe9a0"/><path d="M354 148 Q362 152 362 164 L352 164 Z" fill="{CHROME}"/>'
    s += f'<rect x="150" y="170" width="140" height="6" rx="3" fill="{a}"/><rect x="34" y="170" width="22" height="7" rx="3" fill="{CHROME}"/><rect x="346" y="170" width="22" height="7" rx="3" fill="{CHROME}"/>'
    return s + wheel(100, 178, 28, style="steel", white=True) + wheel(306, 178, 28, style="steel", white=True)


def pickup_crew(c):  # modern crew-cab: four doors, tonneau cover, side steps, fender flares, roof lamps
    b, a = c["body"], c["accent"]
    s = arch(112, 178, 34) + arch(306, 178, 34)
    s += f'<rect x="40" y="128" width="136" height="48" rx="4" fill="{b}"/><rect x="44" y="124" width="130" height="10" rx="4" fill="{a}"/>' + "".join(f'<path d="M{x} 134 V172" stroke="{DARK}" stroke-width="1.5" opacity=".35"/>' for x in (80, 120, 156))
    s += poly("M170 176 L170 120 L196 92 L302 92 L330 120 L358 128 Q368 132 368 148 L368 176 Z", b)
    s += poly("M198 100 L246 100 L246 122 L180 122 Z", GLASS) + poly("M252 100 L298 100 L318 122 L252 122 Z", GLASS)
    s += f'<path d="M248 100 V176 M200 124 V176" stroke="{DARK}" stroke-width="1.6" opacity=".4"/><rect x="226" y="130" width="14" height="3" rx="1.5" fill="{CHROME}"/><rect x="274" y="130" width="14" height="3" rx="1.5" fill="{CHROME}"/>'
    for x in (212, 232, 252, 272):
        s += f'<rect x="{x}" y="84" width="14" height="7" rx="2" fill="#ffe36b"/>'
    s += f'<rect x="190" y="166" width="120" height="7" rx="3" fill="{CHROME}"/><rect x="340" y="136" width="28" height="30" rx="4" fill="{DARK}"/>' + "".join(f'<path d="M344 {y} H364" stroke="{CHROME}" stroke-width="3"/>' for y in (142, 150, 158))
    s += '<rect x="344" y="128" width="16" height="8" rx="2" fill="#ffe9a0"/><rect x="38" y="140" width="7" height="14" rx="2" fill="#e03b3b"/><rect x="30" y="168" width="22" height="8" rx="2" fill="#6b727e"/>'
    return s + wheel(112, 178, 30, style="mag") + wheel(306, 178, 30, style="mag")


def monster_truck(c):  # giant-wheel show truck: small shell, big springs and shocks (generic, not any branded truck)
    b, a = c["body"], c["accent"]
    s = ""
    for cx in (104, 304):
        s += f'<path d="M{cx - 26} 128 L{cx - 8} 154 M{cx + 26} 128 L{cx + 8} 154" stroke="{CHROME}" stroke-width="6" stroke-linecap="round"/>'
    s += f'<rect x="84" y="124" width="240" height="12" rx="4" fill="{DARK}"/>'
    s += f'<rect x="56" y="82" width="120" height="42" rx="6" fill="{b}"/><rect x="62" y="90" width="108" height="28" rx="4" fill="{DARK}" opacity=".55"/>'
    s += poly("M172 124 L172 88 L192 62 L262 62 L286 88 L336 94 Q348 98 348 112 L348 124 Z", b)
    s += poly("M198 70 L258 70 L274 90 L192 90 Z", GLASS)
    s += poly("M178 112 Q230 96 340 106 L344 118 L178 122 Z", a)                    # flame stripe
    s += poly("M186 118 Q214 98 230 112 Q238 96 262 110 Q280 98 300 116 L186 122 Z", "#ffd34e")
    s += f'<rect x="196" y="50" width="62" height="10" rx="3" fill="{DARK}"/>' + "".join(f'<circle cx="{x}" cy="55" r="3.5" fill="#ffe36b"/>' for x in (208, 222, 236, 250))
    s += f'<rect x="326" y="96" width="22" height="26" rx="4" fill="{DARK}"/>' + '<rect x="332" y="100" width="12" height="8" rx="2" fill="#ffe36b"/>'
    s += f'<path d="M124 124 L116 156 M286 124 L294 156" stroke="{a}" stroke-width="5" stroke-linecap="round"/>'
    return s + wheel(104, 152, 52, style="chunky") + wheel(304, 152, 52, style="chunky")


def convertible(c):  # big 1960s convertible: top down, boot cover, tail fins, whitewalls, chrome spear
    b, a = c["body"], c["accent"]
    s = arch(106, 178, 31) + arch(304, 178, 31)
    s += poly("M26 176 L26 142 L40 120 L56 118 L66 140 L104 144 L176 140 L198 118 L212 118 L292 134 L346 140 Q372 144 374 160 L374 176 Z", b)
    s += poly("M66 140 L180 138 L180 150 L72 152 Z", DARK)                          # cockpit
    s += f'<path d="M72 140 Q120 126 178 138 L178 144 L74 144 Z" fill="{a}"/>'     # folded top boot
    for x in (112, 152):
        s += f'<rect x="{x}" y="118" width="26" height="26" rx="9" fill="{a}"/>'
    s += poly("M186 140 L200 112 L210 112 L198 140 Z", GLASS)
    s += f'<path d="M30 156 L368 158" stroke="{CHROME}" stroke-width="3"/><path d="M44 164 Q200 170 360 164" stroke="{a}" stroke-width="5" fill="none"/>'
    s += f'<rect x="20" y="170" width="362" height="8" rx="3" fill="{CHROME}"/><circle cx="350" cy="150" r="9" fill="{CHROME}"/><circle cx="350" cy="150" r="6" fill="#ffe9a0"/><rect x="26" y="146" width="9" height="14" rx="2" fill="#e03b3b"/>'
    return s + wheel(106, 178, 27, style="steel", white=True) + wheel(304, 178, 27, style="steel", white=True)


def glam_convertible(c):  # modern four-seat cabriolet with realistic doors, glass, seats and wheelbase
    b, a = c["body"], c["accent"]
    s = arch(108, 180, 29) + arch(300, 180, 29)
    s += poly("M38 176 L42 154 Q44 144 58 140 L92 134 L126 124 L186 122 L218 132 L320 138 Q350 140 362 152 L366 176 Z", b)
    s += poly("M126 124 L142 102 L154 102 L146 126 Z", GLASS)                  # raked windshield
    s += poly("M145 128 Q176 114 216 126 L230 139 L136 139 Z", DARK)          # open cabin
    s += f'<rect x="158" y="112" width="25" height="27" rx="9" fill="{a}"/><rect x="194" y="116" width="25" height="23" rx="9" fill="{a}"/>'
    s += f'<path d="M136 140 Q181 130 230 140" fill="none" stroke="{a}" stroke-width="5"/>'
    s += f'<path d="M42 154 Q192 142 360 156" fill="none" stroke="{CHROME}" stroke-width="2.5" opacity=".8"/>'
    s += f'<path d="M151 143 L145 172 M226 141 L232 172" stroke="{DARK}" stroke-width="1.5" opacity=".42"/><rect x="184" y="147" width="14" height="3" rx="1.5" fill="{CHROME}"/>'
    s += f'<ellipse cx="139" cy="105" rx="5" ry="3" fill="{CHROME}"/><path d="M136 107 L142 119" stroke="{DARK}" stroke-width="2"/>'
    s += f'<path d="M52 166 H350" stroke="{a}" stroke-width="4"/><path d="M38 174 H366" stroke="{CHROME}" stroke-width="4"/>'
    s += f'<path d="M334 143 Q356 145 362 153 L342 157 Z" fill="url(#lamp)"/><rect x="42" y="148" width="8" height="11" rx="2" fill="url(#tail)"/>'
    return s + wheel(108, 180, 25, style="mag") + wheel(300, 180, 25, style="mag")


def glam_suv(c):  # modern five-door crossover with a believable greenhouse and short overhangs
    b, a = c["body"], c["accent"]
    s = arch(106, 180, 31) + arch(302, 180, 31)
    s += poly("M42 176 L42 112 Q42 100 56 96 L126 86 Q138 80 152 80 L250 80 Q264 80 274 92 L306 120 L344 130 Q360 134 364 150 L364 176 Z", b)
    s += poly("M56 102 L128 92 L148 88 L148 116 L56 116 Z", GLASS)             # cargo glass
    s += poly("M155 88 L204 88 L204 116 L155 116 Z", GLASS)                    # rear door glass
    s += poly("M211 88 L244 88 Q253 88 260 98 L282 119 L211 116 Z", GLASS)     # front door glass
    s += f'<path d="M151 86 V172 M207 86 V172 M264 98 L269 172 M56 118 L58 172" stroke="{DARK}" stroke-width="1.6" opacity=".42"/>'
    s += f'<rect x="174" y="126" width="14" height="3" rx="1.5" fill="{CHROME}"/><rect x="226" y="126" width="14" height="3" rx="1.5" fill="{CHROME}"/>'
    s += f'<path d="M134 79 H252" stroke="{CHROME}" stroke-width="3"/><path d="M138 76 V84 M248 76 V84" stroke="{DARK}" stroke-width="3"/>'
    s += f'<path d="M278 112 L270 122" stroke="{DARK}" stroke-width="2"/><ellipse cx="280" cy="109" rx="7" ry="4" fill="{b}"/>'
    s += f'<path d="M50 151 Q200 141 358 153" fill="none" stroke="{a}" stroke-width="4"/><path d="M48 173 H360" stroke="{DARK}" stroke-width="7"/>'
    s += '<path d="M337 132 Q358 136 363 146 L342 150 Z" fill="url(#lamp)"/><rect x="44" y="130" width="8" height="17" rx="2" fill="url(#tail)"/>'
    return s + wheel(106, 180, 28, style="mag") + wheel(302, 180, 28, style="mag")


def glam_pickup(c):  # modern crew-cab short-bed pickup with distinct cab, bed and four doors
    b, a = c["body"], c["accent"]
    s = arch(104, 180, 32) + arch(304, 180, 32)
    s += poly("M38 176 L40 126 L156 126 L160 176 Z", b)                       # separate short bed
    s += f'<path d="M42 129 H154" stroke="{a}" stroke-width="7"/><path d="M48 137 H151" stroke="{DARK}" stroke-width="1.5" opacity=".35"/>'
    s += poly("M156 176 L158 116 L188 88 Q194 82 204 82 L278 82 Q289 82 296 92 L320 120 L350 128 Q366 134 368 150 L368 176 Z", b)
    s += poly("M178 116 L197 92 L232 92 L232 118 Z", GLASS)
    s += poly("M239 92 L274 92 Q282 92 287 100 L303 119 L239 118 Z", GLASS)
    s += f'<path d="M235 90 V174 M292 101 L298 174 M177 119 L181 174" stroke="{DARK}" stroke-width="1.6" opacity=".45"/>'
    s += f'<rect x="202" y="128" width="13" height="3" rx="1.5" fill="{CHROME}"/><rect x="254" y="128" width="13" height="3" rx="1.5" fill="{CHROME}"/>'
    s += f'<path d="M306 112 L298 122" stroke="{DARK}" stroke-width="2"/><ellipse cx="308" cy="109" rx="7" ry="4" fill="{b}"/>'
    s += f'<rect x="174" y="168" width="126" height="6" rx="3" fill="{CHROME}"/><path d="M42 153 H364" stroke="{a}" stroke-width="4"/>'
    s += '<path d="M343 130 Q363 135 368 145 L347 149 Z" fill="url(#lamp)"/><rect x="39" y="137" width="8" height="16" rx="2" fill="url(#tail)"/>'
    return s + wheel(104, 180, 29, style="mag") + wheel(304, 180, 29, style="mag")


def funny_car(c):  # drag-strip "funny car": long tilt-body shell, giant rear wing, huge slicks, header flames
    b, a = c["body"], c["accent"]
    s = f'<rect x="38" y="92" width="64" height="9" rx="2" fill="{a}"/><rect x="38" y="86" width="5" height="34" fill="{DARK}"/><rect x="97" y="86" width="5" height="34" fill="{DARK}"/><rect x="66" y="101" width="6" height="36" fill="{DARK}"/>'
    s += poly("M70 178 L78 152 L120 142 L166 128 Q196 112 236 114 L274 130 L346 150 Q372 156 374 170 L374 182 Z", b)
    s += poly("M176 134 Q196 120 228 122 L262 134 Z", GLASS)
    s += poly("M96 150 L132 146 L130 160 L96 164 Z", DARK) + f'<path d="M84 168 H366" stroke="{a}" stroke-width="5"/>'
    for i, x in enumerate((150, 178, 206, 234)):
        s += f'<rect x="{x}" y="158" width="6" height="14" rx="2" fill="{CHROME}"/><path d="M{x + 3} 172 Q{x - 4} 188 {x - 16} 192 Q{x + 4} 190 {x + 3} 176 Z" fill="#ff9a1f"/><path d="M{x + 3} 172 Q{x} 182 {x - 8} 186 Q{x + 3} 184 {x + 3} 176 Z" fill="#ffe36b"/>'
    s += '<path d="M352 152 L374 160 L360 168 Z" fill="#ffe36b"/>'
    return s + wheel(100, 164, 40, style="disc") + wheel(332, 188, 17, style="disc")




# ------------------------------------------------ v3 templates: the sixth-row additions
def wedge_pickup(c):  # angular stainless pickup: flat planes, light-bar nose, sail-panel bed (generic, deliberately hard-edged)
    b, a = c["body"], c["accent"]
    s = poly("M34 178 L34 124 L214 84 L372 130 L374 178 Z", b)
    s += poly("M34 178 L34 164 L374 164 L374 178 Z", "#33373d")
    for cx in (100, 300):
        s += poly(f"M{cx - 40} 178 L{cx - 31} 146 L{cx + 31} 146 L{cx + 40} 178 Z", "#0c0d0f")
    s += poly("M146 110 L214 94 L294 117 L294 124 L146 124 Z", GLASS)
    s += f'<path d="M40 122 L212 86" stroke="#fff" stroke-width="1.2" opacity=".35"/><path d="M216 87 L370 131" stroke="#fff" stroke-width="1.2" opacity=".3"/>'
    s += f'<path d="M212 98 V162 M148 112 V162 M298 120 V162" stroke="#000" stroke-width="1.3" opacity=".28"/>'
    s += '<rect x="346" y="129" width="27" height="3" fill="#f4f7ff"/><rect x="346" y="128" width="27" height="5" fill="#cfe3ff" opacity=".35"/>'
    s += '<rect x="34" y="125" width="5" height="12" fill="#e03b3b"/>'
    return s + wheel(100, 178, 28, style="disc") + wheel(300, 178, 28, style="disc")


def bucket_truck(c):  # utility line truck: service body with compartments, outriggers, articulating boom and work bucket
    b, a = c["body"], c["accent"]
    s = arch(110, 180, 30) + arch(312, 180, 30)
    s += f'<rect x="40" y="164" width="322" height="14" fill="{DARK}"/>'
    s += f'<path d="M58 160 L58 194" stroke="{DARK}" stroke-width="7"/><rect x="46" y="194" width="24" height="6" rx="2" fill="{DARK}"/>'
    s += f'<rect x="40" y="118" width="200" height="50" rx="3" fill="{b}"/>'
    for x in (46, 150, 194):
        s += f'<rect x="{x}" y="124" width="40" height="36" rx="2" fill="none" stroke="#000" stroke-width="1.3" opacity=".3"/><rect x="{x + 15}" y="139" width="10" height="3" rx="1.5" fill="{CHROME}"/>'
    s += poly("M244 176 L244 120 L264 100 L316 100 L340 130 L356 134 L356 176 Z", b)
    s += poly("M268 108 L312 108 L330 128 L266 128 Z", GLASS)
    s += '<rect x="282" y="94" width="18" height="6" rx="2" fill="#ffb020"/><circle cx="346" cy="146" r="6" fill="#ffe36b"/><rect x="40" y="130" width="6" height="12" rx="2" fill="#e03b3b"/>'
    s += f'<rect x="62" y="104" width="40" height="16" rx="3" fill="{DARK}"/>'
    s += f'<path d="M92 116 L150 78" stroke="{CHROME}" stroke-width="4" stroke-linecap="round"/>'
    s += f'<path d="M82 108 L184 54" stroke="{a}" stroke-width="11" stroke-linecap="round"/><path d="M184 54 L124 36" stroke="{a}" stroke-width="8" stroke-linecap="round"/>'
    s += f'<circle cx="184" cy="54" r="7" fill="{DARK}"/><circle cx="82" cy="108" r="6" fill="{DARK}"/>'
    s += f'<rect x="96" y="24" width="30" height="26" rx="3" fill="{a}"/><rect x="94" y="21" width="34" height="5" rx="2" fill="{DARK}"/>'
    return s + wheel(110, 180, 26) + wheel(312, 180, 26)


def sand_rail(c):  # long-travel desert sand rail: skinned tube frame, rear engine, coil-overs, paddle tyres, light bar, whip flag
    b, a = c["body"], c["accent"]
    s = f'<path d="M144 22 L152 100" stroke="{DARK}" stroke-width="1.6"/>' + poly("M144 22 L170 28 L145 36 Z", a)
    s += f'<rect x="80" y="112" width="44" height="32" rx="4" fill="{CHROME}"/><path d="M88 116 V140 M98 116 V140 M108 116 V140 M118 116 V140" stroke="{DARK}" stroke-width="2"/><circle cx="102" cy="104" r="9" fill="{DARK}"/>'
    s += f'<path d="M82 136 Q60 132 56 114" stroke="{CHROME}" stroke-width="4" fill="none" stroke-linecap="round"/>'
    s += f'<path d="M100 168 L176 150 M314 172 L262 150" stroke="{DARK}" stroke-width="6" stroke-linecap="round"/>'
    s += f'<path d="M126 158 L152 112 M300 160 L282 120" stroke="{CHROME}" stroke-width="7" stroke-linecap="round"/>'
    s += poly("M130 152 L152 104 L198 102 L198 152 Z", a) + poly("M204 102 L246 100 L294 130 L300 152 L204 152 Z", a)
    s += poly("M122 150 L322 146 L350 154 L338 166 L128 166 Z", b)
    s += f'<path d="M126 152 L152 100 L248 98 L300 130 L348 152 M152 100 L132 152 M201 100 L201 152 M248 98 L250 150 M132 126 L300 130" stroke="{b}" stroke-width="6.5" fill="none" stroke-linejoin="round" stroke-linecap="round"/>'
    s += poly("M300 130 L348 152 L356 160 L300 154 Z", b)
    s += f'<rect x="206" y="116" width="28" height="34" rx="8" fill="{DARK}"/>'
    s += f'<rect x="166" y="90" width="76" height="8" rx="2" fill="{DARK}"/>' + "".join(f'<circle cx="{x}" cy="94" r="2.8" fill="#ffe36b"/>' for x in (176, 192, 208, 224, 236))
    s += '<rect x="122" y="140" width="5" height="9" rx="1" fill="#e03b3b"/>'
    return s + wheel(118, 168, 36, style="chunky") + wheel(314, 174, 30, style="chunky")


def flatbed(c):  # flatbed truck: long steel deck with stake pockets, headache rack and a strapped load of crates
    b, a = c["body"], c["accent"]
    s = arch(94, 180, 29) + arch(160, 180, 29) + arch(312, 180, 29)
    s += f'<rect x="40" y="164" width="322" height="14" fill="{DARK}"/>'
    s += f'<rect x="34" y="150" width="212" height="14" fill="{a}"/>' + "".join(f'<rect x="{x}" y="153" width="5" height="8" fill="{DARK}" opacity=".6"/>' for x in range(44, 240, 26))
    for x, y, w, h in ((52, 104, 62, 46), (118, 114, 58, 36), (180, 122, 50, 28)):
        s += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2" fill="url(#wood)"/>' + "".join(f'<path d="M{x} {yy} H{x + w}" stroke="#4a2c16" stroke-width="1.2" opacity=".6"/>' for yy in range(y + 9, y + h, 9))
        s += f'<path d="M{x + w / 2} {y} V150" stroke="#e8a317" stroke-width="3"/>'
    s += f'<rect x="234" y="100" width="8" height="50" fill="{CHROME}"/>' + "".join(f'<path d="M234 {y} H244" stroke="{DARK}" stroke-width="1.4"/>' for y in (112, 124, 136))
    s += poly("M246 176 L246 120 L266 100 L318 100 L342 130 L358 134 L358 176 Z", b)
    s += poly("M270 108 L314 108 L332 128 L268 128 Z", GLASS)
    s += '<circle cx="348" cy="146" r="6" fill="#ffe36b"/><rect x="34" y="152" width="6" height="10" rx="2" fill="#e03b3b"/>'
    return s + wheel(94, 180, 25) + wheel(160, 180, 25) + wheel(312, 180, 25)


def tractor(c):  # farm tractor: giant ribbed rear tyres, small front wheel, long hood, exhaust stack, roll-over cab
    b, a = c["body"], c["accent"]
    s = f'<rect x="160" y="148" width="172" height="24" rx="4" fill="{DARK}"/><rect x="298" y="174" width="30" height="8" fill="{DARK}"/>'
    s += poly("M168 152 L168 118 L320 116 Q342 116 346 134 L348 156 Z", b)
    s += f'<rect x="336" y="122" width="11" height="32" rx="2" fill="{DARK}"/>' + "".join(f'<path d="M337 {y} H346" stroke="{CHROME}" stroke-width="1.6"/>' for y in (128, 134, 140, 146))
    s += "".join(f'<path d="M{x} 126 L{x + 8} 126" stroke="#000" stroke-width="2" opacity=".35"/>' for x in (230, 244, 258))
    s += f'<rect x="290" y="72" width="7" height="46" fill="{DARK}"/><rect x="288" y="69" width="11" height="5" rx="1" fill="{CHROME}"/><rect x="268" y="90" width="8" height="28" rx="3" fill="{CHROME}"/>'
    s += poly("M132 70 L196 70 L202 118 L128 118 Z", GLASS)
    s += f'<path d="M124 150 L130 64 L200 64 L208 120" stroke="{DARK}" stroke-width="5" fill="none" stroke-linejoin="round"/>'
    s += f'<rect x="118" y="56" width="94" height="10" rx="3" fill="{a}"/>'
    s += f'<rect x="150" y="104" width="24" height="14" rx="3" fill="{DARK}"/><path d="M186 106 L196 90" stroke="{DARK}" stroke-width="3"/><ellipse cx="196" cy="90" rx="7" ry="2.5" fill="{DARK}"/>'
    s += f'<path d="M66 152 A58 58 0 0 1 180 152 L168 152 A46 46 0 0 0 78 152 Z" fill="{b}"/>'
    s += '<circle cx="340" cy="114" r="5" fill="#ffe36b"/>'
    s += wheel(122, 156, 48, hub=a, style="steel")
    for i in range(18):
        t = math.radians(i * 20)
        x1, y1 = 122 + math.cos(t) * 40, 156 + math.sin(t) * 40
        x2, y2 = 122 + math.cos(t + 0.18) * 48, 156 + math.sin(t + 0.18) * 48
        s += f'<path d="M{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f}" stroke="#08090a" stroke-width="4" stroke-linecap="round" opacity=".85"/>'
    return s + wheel(312, 182, 22, hub=a, style="steel")


def backhoe(c):  # backhoe loader: front loader bucket, glass cab, rear digging arm and stabiliser legs
    b, a = c["body"], c["accent"]
    s = f'<path d="M100 150 L74 196" stroke="{DARK}" stroke-width="7"/><rect x="60" y="194" width="28" height="6" rx="2" fill="{DARK}"/>'
    s += f'<rect x="70" y="118" width="22" height="40" rx="3" fill="{DARK}"/>'
    s += f'<path d="M84 140 L52 84" stroke="{CHROME}" stroke-width="4" stroke-linecap="round"/><path d="M44 72 L30 112" stroke="{CHROME}" stroke-width="3" stroke-linecap="round"/>'
    s += f'<path d="M80 124 L42 60" stroke="{b}" stroke-width="12" stroke-linecap="round"/><path d="M42 60 L24 128" stroke="{b}" stroke-width="8" stroke-linecap="round"/>'
    s += f'<circle cx="42" cy="60" r="5" fill="{DARK}"/>' + poly("M12 126 L36 124 L38 150 L18 158 Z", a) + f'<path d="M14 156 L18 162 M22 156 L26 162 M30 154 L34 160" stroke="{DARK}" stroke-width="2"/>'
    s += poly("M90 166 L90 128 L244 128 L320 134 Q336 136 336 150 L336 168 Z", b)
    s += poly("M128 128 L136 68 L224 68 L234 128 Z", b) + poly("M142 76 L218 76 L226 124 L138 124 Z", GLASS)
    s += f'<path d="M180 76 V124" stroke="{DARK}" stroke-width="3"/><rect x="130" y="62" width="100" height="8" rx="3" fill="{a}"/>'
    s += f'<rect x="262" y="98" width="6" height="32" fill="{DARK}"/><rect x="260" y="95" width="10" height="4" fill="{CHROME}"/>'
    s += f'<path d="M238 134 L332 122 L352 148" stroke="{b}" stroke-width="9" fill="none" stroke-linejoin="round" stroke-linecap="round"/>'
    s += f'<path d="M250 146 L330 132" stroke="{CHROME}" stroke-width="3"/>'
    s += poly("M344 128 L380 124 L384 168 L350 176 Z", a) + f'<path d="M350 174 L384 166" stroke="{DARK}" stroke-width="3"/>'
    s += '<circle cx="326" cy="142" r="5" fill="#ffe36b"/><rect x="90" y="134" width="5" height="10" rx="2" fill="#e03b3b"/>'
    return s + wheel(132, 166, 38) + wheel(292, 178, 26)



def hot_dog(c):  # novelty promo car: a giant sausage riding in a toasted bun, mustard on top (generic, no brand)
    b, a = c["body"], c["accent"]
    s = arch(104, 182, 25) + arch(300, 182, 25)
    s += f'<rect x="20" y="74" width="366" height="64" rx="32" fill="{b}"/>'
    s += f'<path d="M48 86 Q66 76 84 86 T120 86 T156 86 T192 86 T228 86 T264 86 T300 86 T336 86 T360 86" stroke="#e8b81e" stroke-width="5" fill="none" stroke-linecap="round"/>'
    s += f'<path d="M48 86 Q66 76 84 86 T120 86 T156 86 T192 86 T228 86 T264 86 T300 86 T336 86 T360 86" stroke="#fff3b0" stroke-width="1.4" fill="none" stroke-linecap="round" opacity=".6" transform="translate(0 -1.2)"/>'
    s += f'<rect x="34" y="120" width="338" height="60" rx="28" fill="{a}"/>'
    s += f'<path d="M44 132 Q200 124 362 132" stroke="#fff" stroke-width="1.6" fill="none" opacity=".35"/>'
    for x in (92, 146, 200, 254):
        s += f'<rect x="{x}" y="134" width="42" height="16" rx="8" fill="{GLASS}"/>'
    s += poly("M314 132 Q350 130 364 150 L316 150 Z", GLASS)
    s += f'<path d="M140 134 V176 M196 134 V176" stroke="#000" stroke-width="1.3" opacity=".25"/><rect x="176" y="156" width="14" height="3.4" rx="1.7" fill="{CHROME}"/>'
    s += f'<rect x="40" y="170" width="326" height="6" rx="3" fill="{CHROME}"/>'
    s += '<circle cx="360" cy="160" r="6" fill="#ffe36b"/><rect x="36" y="152" width="6" height="12" rx="2" fill="#e03b3b"/>'
    return s + wheel(104, 182, 22, style="disc", white=True) + wheel(300, 182, 22, style="disc", white=True)



def formula_racer(c):  # modern open-wheel formula car: long nose, front wing, halo, sidepods, shark fin, big rear wing (generic)
    b, a = c["body"], c["accent"]
    s = f'<rect x="44" y="96" width="9" height="60" rx="2" fill="{DARK}"/><path d="M74 104 L92 150" stroke="{DARK}" stroke-width="4"/>'
    s += f'<rect x="40" y="90" width="66" height="9" rx="2" fill="{a}"/><rect x="42" y="102" width="62" height="6" rx="2" fill="{b}"/>'
    s += f'<rect x="60" y="168" width="300" height="7" rx="2" fill="{DARK}"/>'
    s += poly("M108 166 L112 134 L146 106 L194 104 L204 122 L240 132 L250 150 L250 168 Z", b)
    s += poly("M146 106 L120 132 L112 134 L118 112 Z", a)
    s += poly("M226 148 L374 158 L378 166 L226 170 Z", b)
    s += f'<path d="M130 152 L246 152" stroke="{a}" stroke-width="7" stroke-linecap="round"/><path d="M250 160 L372 162" stroke="{a}" stroke-width="3"/>'
    s += f'<circle cx="214" cy="122" r="10" fill="{a}"/><rect x="214" y="117" width="10" height="5" rx="2" fill="{GLASS}"/>'
    s += f'<path d="M196 112 Q232 102 254 134" stroke="{DARK}" stroke-width="4.5" fill="none" stroke-linecap="round"/>'
    s += poly("M330 172 L392 166 L394 180 L328 182 Z", a) + f'<rect x="386" y="158" width="6" height="24" rx="1" fill="{DARK}"/>'
    s += f'<path d="M282 158 L316 172 M276 162 L300 178" stroke="{DARK}" stroke-width="2.5"/><path d="M118 150 L96 174 M130 156 L104 176" stroke="{DARK}" stroke-width="2.5"/>'
    s += '<rect x="40" y="140" width="5" height="10" rx="1" fill="#e03b3b"/>'
    return s + wheel(96, 177, 28, style="disc") + wheel(318, 179, 26, style="disc")


def stock_car(c):  # oval-track stock car: low fastback, door number, window net, big spoiler, decal strip, splitter (generic livery)
    b, a = c["body"], c["accent"]
    s = arch(104, 178, 31) + arch(306, 178, 31)
    s += poly("M34 178 L34 150 Q36 138 50 136 L118 128 L160 102 Q166 98 176 98 L236 98 Q246 98 254 104 L300 128 L354 134 Q372 138 374 156 L376 178 Z", b)
    s += poly("M36 152 Q38 140 52 138 L118 130 L196 130 L120 178 L36 178 Z", a)
    s += f'<path d="M200 132 L128 178" stroke="#f4f4f0" stroke-width="4"/>'
    s += f'<rect x="30" y="118" width="40" height="7" rx="2" fill="{DARK}"/><path d="M38 125 L42 136 M62 125 L60 134" stroke="{DARK}" stroke-width="3"/>'
    s += poly("M172 106 L214 106 L214 126 L152 126 Z", GLASS) + poly("M220 106 L246 106 L272 126 L220 126 Z", GLASS)
    s += "".join(f'<path d="M{x} 107 L{x - 6} 125" stroke="{DARK}" stroke-width="1.4" opacity=".75"/>' for x in (180, 192, 204, 214)) + f'<path d="M160 116 H214" stroke="{DARK}" stroke-width="1.4" opacity=".75"/>'
    s += f'<rect x="196" y="96" width="34" height="3" rx="1.5" fill="{DARK}" opacity=".6"/>'
    s += '<circle cx="236" cy="150" r="19" fill="#f4f4f0"/><circle cx="236" cy="150" r="19" fill="none" stroke="#000" stroke-width="1.5" opacity=".35"/>'
    s += '<text x="236" y="158" text-anchor="middle" font-family="Arial Black,Arial,Helvetica,sans-serif" font-weight="900" font-size="22" fill="#17191d">64</text>'
    for i, x in enumerate(range(268, 340, 12)):
        s += f'<rect x="{x}" y="160" width="10" height="5" rx="1" fill="{"#f4f4f0" if i % 2 == 0 else "#9aa1ab"}" opacity=".9"/>'
    s += f'<rect x="336" y="175" width="44" height="4" rx="1" fill="{DARK}"/><rect x="356" y="152" width="18" height="5" rx="1" fill="{DARK}" opacity=".7"/>'
    s += '<rect x="352" y="143" width="16" height="6" rx="2" fill="#ffe9a0"/><rect x="34" y="142" width="6" height="10" rx="2" fill="#e03b3b"/>'
    return s + wheel(104, 178, 27, hub="#1d1f23", style="steel") + wheel(306, 178, 27, hub="#1d1f23", style="steel")

def _utility_suv(c, lights, extra, wheel_style, hub=HUB):
    """Modern pursuit-style SUV base shared by the police and fire SUVs."""
    b, a = c["body"], c["accent"]
    s = arch(104, 178, 31) + arch(300, 178, 31)
    s += poly("M38 176 L38 120 Q38 108 50 106 L250 104 L290 128 L346 134 Q366 138 366 156 L366 176 Z", b)
    s += extra
    s += poly("M58 112 L116 112 L116 128 L58 128 Z", GLASS) + poly("M124 112 L184 112 L184 128 L124 128 Z", GLASS) + poly("M190 112 L246 112 L272 128 L190 128 Z", GLASS)
    s += f'<path d="M120 112 V170 M187 112 V170" stroke="#000" stroke-width="1.4" opacity=".3"/><rect x="160" y="136" width="14" height="3.4" rx="1.7" fill="{CHROME}"/><rect x="226" y="136" width="14" height="3.4" rx="1.7" fill="{CHROME}"/>'
    s += f'<rect x="132" y="96" width="44" height="9" rx="3" fill="{lights[0]}"/><rect x="178" y="96" width="44" height="9" rx="3" fill="{lights[1]}"/><rect x="130" y="103" width="94" height="3" fill="{DARK}"/>'
    s += f'<rect x="362" y="134" width="9" height="38" rx="3" fill="{DARK}"/><path d="M362 146 H371 M362 158 H371" stroke="#4a4e55" stroke-width="2"/>'
    s += f'<rect x="56" y="100" width="190" height="4" rx="2" fill="{DARK}" opacity=".8"/>'
    s += '<rect x="340" y="138" width="18" height="7" rx="2" fill="#ffe9a0"/><rect x="38" y="122" width="6" height="18" rx="2" fill="#e03b3b"/>'
    s += f'<path d="M282 118 L276 126" stroke="{DARK}" stroke-width="2"/><ellipse cx="282" cy="116" rx="6" ry="4" fill="{DARK}"/>'
    return s + wheel(104, 178, 27, hub=hub, style=wheel_style) + wheel(300, 178, 27, hub=hub, style=wheel_style)


def police_suv(c):  # pursuit-rated SUV: two-tone doors, split light bar, push bumper, spotlight
    a = c["accent"]
    extra = (f'<path d="M120 130 L272 130 L290 140 L290 170 L120 170 Z" fill="{a}"/>'
             '<text x="205" y="157" text-anchor="middle" font-family="Arial Black,Arial,Helvetica,sans-serif" font-weight="900" font-size="15" fill="#17191d">POLICE</text>'
             f'<rect x="250" y="106" width="8" height="5" rx="1" fill="{CHROME}"/>')
    return _utility_suv(c, ("#e03b3b", "#2457b5"), extra, "steel", hub="#1d1f23")


def fire_suv(c):  # fire command SUV: red with reflective stripe, all-red light bar, door crest
    extra = ('<rect x="38" y="146" width="328" height="7" fill="#f4f4f0"/><rect x="38" y="155" width="328" height="3" fill="#e8b81e"/>'
             '<circle cx="216" cy="134" r="0" fill="none"/>'
             '<text x="205" y="172" text-anchor="middle" font-family="Arial Black,Arial,Helvetica,sans-serif" font-weight="900" font-size="11" fill="#f4f4f0">FIRE CHIEF</text>')
    return _utility_suv(c, ("#e03b3b", "#e03b3b"), extra, "mag")


def steam_roller(c):  # vintage steam road roller: front drum, boiler, tall chimney, canopy, flywheel, big spoked rear wheels
    b, a = c["body"], c["accent"]
    s = f'<path d="M72 48 V112 M182 48 V104" stroke="{DARK}" stroke-width="3.5"/><rect x="58" y="40" width="136" height="9" rx="3" fill="{a}"/>'
    s += f'<rect x="80" y="100" width="82" height="72" rx="5" fill="{b}"/><rect x="92" y="112" width="26" height="22" rx="3" fill="#1b1d21"/>'
    s += f'<rect x="150" y="104" width="160" height="42" rx="21" fill="{b}"/>' + "".join(f'<rect x="{x}" y="104" width="5" height="42" fill="#c9a24a"/>' for x in (190, 236, 282))
    s += f'<rect x="300" y="100" width="18" height="50" rx="6" fill="{DARK}"/>'
    s += f'<rect x="288" y="50" width="14" height="56" fill="{DARK}"/><rect x="284" y="44" width="22" height="8" rx="2" fill="#c9a24a"/>'
    s += f'<rect x="296" y="124" width="48" height="22" rx="4" fill="{b}"/><path d="M304 146 L300 170 M336 146 L340 170" stroke="{DARK}" stroke-width="5"/>'
    s += f'<circle cx="214" cy="92" r="18" fill="{DARK}"/>' + "".join(f'<path d="M214 92 L{214 + math.cos(math.radians(t)) * 16:.1f} {92 + math.sin(math.radians(t)) * 16:.1f}" stroke="#c9a24a" stroke-width="2"/>' for t in range(0, 360, 60))
    _WHEELS.append((320, 204, 30, 32))
    s += '<circle cx="320" cy="172" r="32" fill="url(#gunmetal)"/><circle cx="320" cy="172" r="32" fill="url(#dish)"/><circle cx="320" cy="172" r="9" fill="url(#rim)"/>'
    s += '<circle cx="320" cy="172" r="27" fill="none" stroke="#1a1c20" stroke-width="1.4" opacity=".6"/>'
    return s + wheel(110, 158, 46, hub=a, style="steel")


def pinto_compact(c):  # 1970s subcompact fastback: sloping hatch, big bumpers, side tape stripe, small hubcaps
    b, a = c["body"], c["accent"]
    s = arch(108, 180, 28) + arch(296, 180, 28)
    s += poly("M44 176 L44 148 Q46 138 58 136 L96 132 L150 104 Q156 100 166 100 L232 100 Q242 100 248 106 L276 128 L340 136 Q358 140 358 156 L358 176 Z", b)
    s += poly("M106 130 L152 106 L180 106 L180 128 Z", GLASS) + poly("M186 106 L230 106 L256 128 L186 128 Z", GLASS)
    s += f'<path d="M183 106 V170" stroke="#000" stroke-width="1.4" opacity=".3"/><rect x="222" y="136" width="14" height="3.4" rx="1.7" fill="{CHROME}"/>'
    s += f'<rect x="56" y="144" width="296" height="4" fill="{a}"/><rect x="56" y="150" width="296" height="2" fill="{a}"/>'
    s += f'<rect x="36" y="166" width="22" height="9" rx="3" fill="{CHROME}"/><rect x="344" y="166" width="22" height="9" rx="3" fill="{CHROME}"/>'
    s += f'<path d="M262 120 L256 128" stroke="{DARK}" stroke-width="2"/><ellipse cx="264" cy="118" rx="5" ry="3.5" fill="{CHROME}"/>'
    s += '<circle cx="348" cy="148" r="6" fill="#ffe36b"/><rect x="44" y="146" width="7" height="12" rx="2" fill="#e03b3b"/>'
    return s + wheel(108, 180, 24, style="disc") + wheel(296, 180, 24, style="disc")


def gullwing(c):  # 1980s stainless wedge coupe: gullwing door raised, louvred rear glass, black lower band
    b, a = c["body"], c["accent"]
    s = arch(104, 178, 30) + arch(306, 178, 30)
    s += poly("M40 174 L40 140 L60 130 L130 124 L170 102 L246 100 L300 124 L362 138 L366 150 L366 174 Z", b)
    s += f'<rect x="40" y="160" width="326" height="14" fill="#2a2d33"/>'
    s += poly("M178 104 L244 102 L284 124 L276 150 L182 150 Z", "#24272c") + f'<rect x="206" y="122" width="28" height="28" rx="5" fill="#40444b"/><path d="M262 130 L250 122" stroke="#5a5f67" stroke-width="3"/>'
    s += poly("M134 124 L170 104 L176 104 L176 124 Z", DARK) + "".join(f'<path d="M{x} {124 - (x - 134) * 0.55:.1f} V124" stroke="#4a4e55" stroke-width="1.5"/>' for x in range(142, 176, 6))
    # raised door = the opening mirrored above the roof hinge (x unchanged, height foreshortened), so it fits when closed
    s += poly("M180 102 L244 100 L284 80 L276 56 L182 56 Z", b) + poly("M186 99 L242 98 L276 81 L186 80 Z", GLASS)
    s += f'<path d="M183 61 L275 61" stroke="#000" stroke-width="1" opacity=".25"/><path d="M180 102 L244 100" stroke="#000" stroke-width="2" opacity=".5"/>'
    s += f'<path d="M180 102 L244 100" stroke="{DARK}" stroke-width="2"/>'
    s += f'<rect x="344" y="142" width="20" height="5" rx="1" fill="#ffe9a0"/><rect x="40" y="142" width="8" height="10" rx="1" fill="#e03b3b"/>'
    s += f'<path d="M60 150 H160 M300 148 H360" stroke="#000" stroke-width="1" opacity=".25"/>'
    return s + wheel(104, 178, 26, style="mag") + wheel(306, 178, 26, style="mag")


def _open_frame_4x4(c, four):
    """Upright-windshield 4x4 (generic): flat hood, exposed hinges, flat flares, rock rails, rear spare, steel bumpers."""
    b, a = c["body"], c["accent"]
    if four:
        L, R, w1, w2, ws = 44, 362, 100, 300, 246
        wins = [(54, 94), (102, 158), (168, None)]
        seams, hinges = (98, 164), (166, 100)
    else:
        L, R, w1, w2, ws = 64, 352, 116, 294, 236
        wins = [(76, 136), (154, None)]
        seams, hinges = (148,), (150,)
    s = spare_edge(L, 128, 24)  # tailgate spare, edge-on
    s += arch(w1, 174, 33) + arch(w2, 174, 33)
    s += poly(f"M{L} 166 L{L} 88 Q{L} 80 {L + 8} 80 L{ws - 10} 80 L{ws} 120 L{R - 10} 120 Q{R} 122 {R} 132 L{R} 166 Z", b)
    if four:  # hardtop
        s += poly(f"M{L} 92 L{L} 86 Q{L} 80 {L + 8} 80 L{ws - 10} 80 L{ws - 7} 92 Z", a)
    else:     # soft top with a rounded rear bow
        s += poly(f"M{L} 120 L{L} 92 Q{L} 76 {L + 16} 76 L{ws - 12} 78 L{ws - 6} 94 L{ws - 50} 94 L{ws - 50} 120 Z", a)
    for x1, x2 in wins:
        x2 = x2 if x2 else ws - 8
        if x2 == ws - 8:
            s += poly(f"M{x1} 96 L{x2 - 4} 96 L{x2 + 3} 118 L{x1} 118 Z", GLASS)
        else:
            s += poly(f"M{x1} 96 L{x2} 96 L{x2} 118 L{x1} 118 Z", GLASS if four else "#9fb1c1")
    s += poly(f"M{ws - 9} 84 L{ws - 4} 84 L{ws + 4} 120 L{ws - 1} 120 Z", GLASS)
    s += "".join(f'<path d="M{x} 94 V158" stroke="#000" stroke-width="1.5" opacity=".32"/>' for x in seams + (ws,))
    for x in hinges:
        s += f'<rect x="{x}" y="126" width="5" height="7" rx="1" fill="{DARK}"/><rect x="{x}" y="148" width="5" height="7" rx="1" fill="{DARK}"/>'
    for x in ((150, 228) if four else (222,)):
        s += f'<rect x="{x}" y="125" width="13" height="3.4" rx="1.7" fill="{DARK}"/>'
    for cx in (w1, w2):
        s += poly(f"M{cx - 44} 154 L{cx - 34} 136 L{cx + 34} 136 L{cx + 44} 154 L{cx + 38} 158 L{cx - 38} 158 Z", "#25282d")
    s += f'<rect x="{w1 + 40}" y="158" width="{w2 - w1 - 80}" height="9" rx="2" fill="#25282d"/>'
    s += f'<rect x="{R - 10}" y="156" width="22" height="12" rx="2" fill="#25282d"/><rect x="{L - 16}" y="156" width="20" height="12" rx="2" fill="#25282d"/>'
    s += f'<rect x="{R + 6}" y="160" width="5" height="5" rx="1" fill="#e03b3b"/>'
    s += f'<rect x="{R - 6}" y="124" width="6" height="30" rx="1" fill="#25282d"/>' + "".join(f'<path d="M{R - 6} {y} H{R}" stroke="#555a62" stroke-width="1.4"/>' for y in (130, 136, 142, 148))
    s += f'<circle cx="{R - 12}" cy="133" r="7" fill="#ffe36b"/><rect x="{R - 20}" y="146" width="8" height="4" rx="1" fill="#ffb020"/>'
    s += f'<rect x="{L}" y="124" width="6" height="14" rx="2" fill="#e03b3b"/>'
    s += f'<path d="M{ws + 4} 112 L{ws - 2} 120" stroke="{DARK}" stroke-width="2"/><rect x="{ws}" y="104" width="10" height="8" rx="2" fill="{DARK}"/>'
    return s + wheel(w1, 174, 30, style="chunky") + wheel(w2, 174, 30, style="chunky")


def four_door_4x4(c):  # four-door open-frame 4x4 with hardtop
    return _open_frame_4x4(c, True)


def two_door_4x4(c):  # short-wheelbase two-door open-frame 4x4 with soft top
    return _open_frame_4x4(c, False)

def open_top_4x4(c):  # civilian open-top 4x4 (generic): folded soft top, black roll bars, four seats, black interior, flares, rear spare
    b, a = c["body"], c["accent"]
    s = spare_edge(92, 140, 23)  # rear spare, edge-on
    s += arch(130, 178, 31) + arch(276, 178, 31)
    s += poly("M92 176 L92 132 L254 132 L258 128 L316 128 Q322 128 322 135 L322 176 Z", b)
    s += poly("M176 132 L180 150 Q183 157 193 157 L228 157 Q236 157 238 149 L242 132 Z", "#121316")
    s += f'<rect x="124" y="108" width="17" height="26" rx="4" fill="#17181b"/><rect x="200" y="106" width="17" height="28" rx="4" fill="#17181b"/>'
    s += f'<rect x="126" y="110" width="4" height="22" rx="2" fill="#2c2e33"/><rect x="202" y="108" width="4" height="24" rx="2" fill="#2c2e33"/>'
    s += f'<path d="M240 130 L232 110" stroke="#111" stroke-width="2.6"/><ellipse cx="232" cy="110" rx="8" ry="2.5" fill="#111"/>'
    s += poly("M94 132 L94 118 Q96 110 106 110 L118 110 Q124 112 124 120 L124 132 Z", a)
    s += "".join(f'<path d="M{x} 113 L{x} 131" stroke="#000" stroke-width="1" opacity=".45"/>' for x in (102, 110, 118))
    s += f'<path d="M118 132 L124 92 L250 88" stroke="#141518" stroke-width="5" fill="none" stroke-linejoin="round" stroke-linecap="round"/>'
    s += f'<path d="M186 132 L190 90" stroke="#141518" stroke-width="5" stroke-linecap="round"/><path d="M124 104 L186 102" stroke="#141518" stroke-width="3"/>'
    s += poly("M246 84 L254 84 L260 132 L252 132 Z", "#141518") + poly("M248.5 88 L252 88 L257 128 L253.5 128 Z", GLASS)
    for cx in (130, 276):
        s += poly(f"M{cx - 42} 156 L{cx - 33} 140 L{cx + 33} 140 L{cx + 42} 156 L{cx + 37} 160 L{cx - 37} 160 Z", "#1a1b1f")
    s += f'<rect x="168" y="160" width="68" height="8" rx="2" fill="#1a1b1f"/>'
    s += "".join(f'<path d="M{x} 132 L{x} 142" stroke="#000" stroke-width="1.2" opacity=".3"/>' for x in (272, 280, 288, 296))
    s += f'<circle cx="314" cy="141" r="7" fill="{CHROME}"/><circle cx="314" cy="141" r="5" fill="#ffe36b"/><rect x="306" y="152" width="8" height="4" rx="1" fill="#ffb020"/>'
    s += f'<rect x="318" y="166" width="16" height="10" rx="2" fill="#1a1b1f"/><rect x="80" y="166" width="16" height="10" rx="2" fill="#1a1b1f"/><rect x="92" y="136" width="5" height="12" rx="1" fill="#e03b3b"/>'
    s += f'<path d="M262 120 L256 128" stroke="#111" stroke-width="2"/><rect x="258" y="112" width="10" height="8" rx="2" fill="#111"/>'
    return s + wheel(130, 178, 28, style="chunky") + wheel(276, 178, 28, style="chunky")


TEMPLATES = {
    "open_top_4x4": open_top_4x4,
    "four_door_4x4": four_door_4x4, "two_door_4x4": two_door_4x4,
    "police_suv": police_suv, "fire_suv": fire_suv, "steam_roller": steam_roller,
    "pinto_compact": pinto_compact, "gullwing": gullwing,
    "formula_racer": formula_racer, "stock_car": stock_car,
    "hot_dog": hot_dog,
    "wedge_pickup": wedge_pickup, "bucket_truck": bucket_truck, "sand_rail": sand_rail,
    "flatbed": flatbed, "tractor": tractor, "backhoe": backhoe,
    "funny_car": funny_car, "monster_truck": monster_truck, "convertible": convertible,
    "glam_convertible": glam_convertible, "glam_suv": glam_suv, "glam_pickup": glam_pickup,
    "boxy_sedan": boxy_sedan, "wagon_modern": wagon_modern, "rear_engine": rear_engine, "spider": spider,
    "rat_rod": rat_rod, "motorhome": motorhome, "boxy_suv": boxy_suv, "kei_3wheel": kei_3wheel,
    "trike_bike": trike_bike, "city_mini": city_mini, "classic_luxury_suv": classic_luxury_suv,
    "gt_coupe": gt_coupe, "pickup_classic": pickup_classic, "pickup_crew": pickup_crew,
    "sedan": sedan, "taxi": taxi, "patrol": patrol, "wagon": wagon, "roadster": roadster,
    "wedge": wedge, "open_wheel": open_wheel, "dragster": dragster, "fire_truck": fire_truck,
    "rescue_van": rescue_van, "school_bus": school_bus, "delivery_van": delivery_van,
    "ice_cream_truck": ice_cream_truck, "tow_truck": tow_truck, "garbage_truck": garbage_truck,
    "camper": camper, "dune_buggy": dune_buggy, "mud_truck": mud_truck, "hot_rod": hot_rod,
    "bug": bug, "limo": limo, "trail_jeep": trail_jeep, "fuel_tanker": fuel_tanker,
    "muscle_coupe": muscle_coupe, "microbus": microbus, "hatch": hatch,
    "offroader": offroader, "pickup": pickup, "sports_car": sports_car,
    "military_truck": military_truck, "troop_transport": troop_transport,
    "recon": recon, "tank": tank, "armored_carrier": armored_carrier,
    "dump_truck": dump_truck, "excavator": excavator, "bulldozer": bulldozer,
    "cement_mixer": cement_mixer, "crane_truck": crane_truck,
    "front_loader": front_loader,
}


# ---------------------------------------------------------------- detail "trim" layer
# Per-silhouette anchors (400x260 canvas) used to add panel lines, handles, mirrors, lamps and to place
# the hotspot callouts in the storefront detail view.
TRIM = {
    "muscle_coupe": dict(front=364, rear=38, belt=134, sill=172, w=(110, 300, 178, 27), doors=[196], handles=[176], mirror=(262, 112), lamp_y=152),
    "sedan": dict(front=362, rear=40, belt=134, sill=172, w=(108, 300, 178, 27), doors=[126, 196, 276], handles=[160, 232], mirror=(276, 114), lamp_y=152),
    "taxi": dict(front=362, rear=40, belt=134, sill=172, w=(108, 300, 178, 27), doors=[126, 196, 276], handles=[160, 232], mirror=(276, 114), lamp_y=152),
    "patrol": dict(front=362, rear=40, belt=134, sill=172, w=(108, 300, 178, 27), doors=[126, 196, 276], handles=[160, 232], mirror=(276, 114), lamp_y=152),
    "boxy_sedan": dict(front=380, rear=28, belt=136, sill=172, w=(104, 312, 178, 27), doors=[186, 280], handles=[160, 250], mirror=(300, 122), lamp_y=150),
    "wagon": dict(front=358, rear=44, belt=136, sill=172, w=(112, 292, 178, 27), doors=[128, 190, 240], handles=[100, 160, 214], mirror=(296, 120), lamp_y=154),
    "wagon_modern": dict(front=364, rear=42, belt=134, sill=172, w=(112, 298, 178, 27), doors=[129, 199], handles=[160, 232], mirror=(312, 116), lamp_y=154),
    "hatch": dict(front=352, rear=58, belt=132, sill=172, w=(118, 290, 178, 27), doors=[196], handles=[174], mirror=(272, 108), lamp_y=154),
    "gt_coupe": dict(front=364, rear=36, belt=140, sill=172, w=(110, 300, 178, 27), doors=[210], handles=[196], mirror=(290, 130), lamp_y=152),
    "rear_engine": dict(front=364, rear=40, belt=134, sill=172, w=(108, 290, 178, 28), doors=[196], handles=[176], mirror=(264, 124), lamp_y=148),
    "bug": dict(front=354, rear=52, belt=134, sill=172, w=(108, 292, 178, 27), doors=[196], handles=[176], mirror=(272, 128), lamp_y=152),
    "city_mini": dict(front=318, rear=80, belt=134, sill=176, w=(112, 290, 180, 24), doors=[190], handles=[172], mirror=(250, 124), lamp_y=152),
    "microbus": dict(front=354, rear=48, belt=130, sill=172, w=(112, 296, 178, 27), doors=[130, 240, 306], handles=[108, 214, 292], mirror=(344, 112), lamp_y=152),
    "offroader": dict(front=348, rear=62, belt=132, sill=172, w=(116, 290, 176, 32), doors=[140, 196], handles=[120, 170], mirror=(252, 112), lamp_y=146),
    "trail_jeep": dict(front=356, rear=58, belt=140, sill=172, w=(116, 292, 176, 32), doors=[172], handles=[150], mirror=(190, 112), lamp_y=150),
    "boxy_suv": dict(front=352, rear=52, belt=130, sill=172, w=(118, 288, 178, 29), doors=[125, 190], handles=[100, 160, 230], mirror=(282, 114), lamp_y=136),
    "classic_luxury_suv": dict(front=356, rear=50, belt=130, sill=172, w=(112, 292, 178, 29), doors=[178], handles=[150, 210], mirror=(276, 112), lamp_y=136),
    "pickup": dict(front=362, rear=50, belt=128, sill=172, w=(112, 300, 178, 27), doors=[226], handles=[256], mirror=(300, 112), lamp_y=146),
    "pickup_classic": dict(front=358, rear=44, belt=124, sill=172, w=(100, 306, 178, 28), doors=[232], handles=[256], mirror=(278, 112), lamp_y=140),
    "pickup_crew": dict(front=368, rear=40, belt=124, sill=172, w=(112, 306, 178, 30), doors=[200, 248], handles=[222, 270], mirror=(312, 108), lamp_y=132),
    "convertible": dict(front=374, rear=26, belt=146, sill=174, w=(106, 304, 178, 27), doors=[180], handles=[160], mirror=None, lamp_y=150),
    "glam_convertible": dict(front=366, rear=38, belt=142, sill=174, w=(108, 300, 180, 25), doors=[151, 226], handles=[184], mirror=(139, 105), lamp_y=150),
    "glam_suv": dict(front=364, rear=42, belt=118, sill=174, w=(106, 302, 180, 28), doors=[58, 151, 207, 269], handles=[174, 226], mirror=(280, 109), lamp_y=140),
    "glam_pickup": dict(front=368, rear=38, belt=120, sill=174, w=(104, 304, 180, 29), doors=[181, 235, 298], handles=[202, 254], mirror=(308, 109), lamp_y=140),
    "roadster": dict(front=364, rear=36, belt=150, sill=176, w=(108, 296, 178, 26), doors=[], handles=[], mirror=None, lamp_y=156),
    "spider": dict(front=366, rear=40, belt=146, sill=176, w=(112, 290, 178, 26), doors=[], handles=[], mirror=None, lamp_y=152),
    "sports_car": dict(front=364, rear=36, belt=146, sill=178, w=(108, 296, 180, 25), doors=[200], handles=[188], mirror=(262, 124), lamp_y=154),
    "wedge": dict(front=368, rear=32, belt=150, sill=184, w=(100, 300, 182, 25), doors=[230], handles=[214], mirror=(272, 128), lamp_y=158),
}

# (what it is, [three feature bullets], wheel description)
META = {
    "muscle_coupe": ("Two-door muscle coupe", ["Long hood with scoop and racing stripe", "Chrome bumpers front and rear", "Rolling mag-style wheels"], "Rolling mag wheels"),
    "sedan": ("Four-door sedan", ["Three-box body with chrome beltline", "Etched door seams and handles", "Rolling wheels with chrome bumper"], "Rolling mag wheels"),
    "taxi": ("City taxi", ["Roof sign and checker stripe", "Four-door sedan casting", "Chrome bumpers"], "Rolling mag wheels"),
    "patrol": ("Patrol cruiser", ["Roof light bar", "Two-tone door panels", "Four-door sedan casting"], "Rolling mag wheels"),
    "boxy_sedan": ("Boxy full-size sedan", ["Vinyl-style roof with opera window", "Slatted chrome grille and big bumpers", "Whitewall hubcaps"], "Whitewall hubcap wheels"),
    "wagon": ("Woody station wagon", ["Wood-grain side panels", "Roof rack with luggage", "Chrome bumpers"], "Rolling wheels"),
    "wagon_modern": ("Modern family wagon", ["Long roof with rails and spoiler", "Three-window greenhouse", "Body-color bumpers"], "Rolling wheels"),
    "hatch": ("Compact hatchback", ["Rally-style stripe", "Chrome bumpers", "Sunroof-ready roofline"], "Rolling wheels"),
    "gt_coupe": ("Grand-touring fastback", ["Teardrop roofline with side vents", "Plexi-style headlamps", "Wire-style wheels"], "Wire-style wheels"),
    "rear_engine": ("Rear-engine fastback", ["Rounded body with duck-tail", "Round headlamps", "Five-spoke mag wheels"], "Five-spoke mag wheels"),
    "spider": ("Open two-seat spider", ["Open cockpit with two seats", "Shield-style grille", "Wire-style wheels"], "Wire-style wheels"),
    "bug": ("Rounded rear-engine bug", ["Separate fenders and running boards", "Round headlamps with chrome rims", "Chrome bumpers"], "Rolling wheels"),
    "city_mini": ("Micro city car", ["Tiny rounded body", "Rear engine grille", "Chrome bumpers"], "Disc-style wheels"),
    "glam_convertible": ("Modern four-seat convertible", ["Top-down cabin with four seats", "Raked windshield and two proper doors", "Polished five-spoke wheels"], "Polished five-spoke wheels"),
    "glam_suv": ("Modern five-door crossover", ["Five-door body with a full glass greenhouse", "Roof rails and protective lower trim", "Short overhangs and road wheels"], "Polished road wheels"),
    "glam_pickup": ("Modern crew-cab pickup", ["Four-door cab with a separate short bed", "Side step and realistic truck stance", "Polished all-terrain wheels"], "Polished all-terrain wheels"),
    "microbus": ("Split-window microbus", ["Two-tone paint with V-shaped nose stripe", "Panoramic window row", "Chrome bumpers"], "Rolling wheels"),
    "offroader": ("Classic 4x4", ["Roof rack with light bar", "Rear-mounted spare tire", "Lifted stance"], "Chunky off-road wheels"),
    "trail_jeep": ("Open-top trail runner", ["Soft top and windshield frame", "Slotted grille", "Rear spare tire"], "Chunky off-road wheels"),
    "boxy_suv": ("Boxy four-wheel-drive wagon", ["Roof rails and flared fenders", "Side steps", "Three-window greenhouse"], "Steel-style wheels"),
    "classic_luxury_suv": ("Two-tone luxury 4x4", ["Two-tone paint with chrome divider", "Mesh grille", "Roof rail"], "Steel-style wheels"),
    "pickup": ("Regular-cab pickup", ["Open bed with liner detail", "Chrome bumpers", "Painted stripe"], "Rolling wheels"),
    "pickup_classic": ("1950s step-side pickup", ["Wood bed floor and rails", "Bucket headlamps and running board", "Whitewall wheels"], "Whitewall steel wheels"),
    "pickup_crew": ("Crew-cab pickup", ["Four doors with tonneau-covered bed", "Roof lamps and side steps", "Fender flares and tow hitch"], "Five-spoke mag wheels"),
    "convertible": ("Big convertible", ["Top down with folded boot", "Tail fins and chrome spear", "Whitewall wheels"], "Whitewall steel wheels"),
    "roadster": ("Open roadster", ["Open cockpit with twin seats", "Racing number stripe", "Chrome bumpers"], "Rolling wheels"),
    "sports_car": ("Sports coupe", ["Rear spoiler", "Low roofline", "Side stripe"], "Rolling wheels"),
    "wedge": ("Wedge supercar", ["Cab-forward wedge shape with big wing", "Side air intake", "Slit headlamps"], "Low-profile wheels"),
    "hot_rod": ("Hot rod", ["Exposed supercharger and chrome grille", "Painted flames", "Big rear tires"], "Big-and-little wheels"),
    "rat_rod": ("Rat rod", ["Patina paint and primer patches", "Exposed engine with exhaust stacks", "Chopped cab"], "Steel wheels"),
    "motorhome": ("Class-A motorhome", ["Panoramic windshield", "Swoosh stripe graphics", "Roof air-conditioner"], "Disc wheels"),
    "camper": ("Camper van", ["Awning stripe", "Roof air-conditioner", "Side door"], "Rolling wheels"),
    "kei_3wheel": ("Three-wheel mini truck", ["Single front wheel", "Slatted cargo bed", "Open-sided cab"], "Small steel wheels"),
    "trike_bike": ("Touring trike", ["Twin rear wheels and trunk", "Chrome pipes and fork", "Tank with highlight"], "Wire-style wheels"),
    "monster_truck": ("Giant-wheel show truck", ["Oversize tires with shocks", "Flame decals and roof lamps", "Lifted body shell"], "Giant chunky wheels"),
    "dune_buggy": ("Fiberglass beach buggy", ["Curved fiberglass tub and fenders", "Exposed rear engine", "Roll bar and bug-eye lamps"], "Big-and-little wheels"),
    "mud_truck": ("Lifted mud truck", ["Lift kit with oversize tires", "Roof lamp bar", "Open bed"], "Chunky off-road wheels"),
    "limo": ("Stretch limousine", ["Extended body with three window panels", "Chrome trim", "Long wheelbase"], "Rolling wheels"),
    "funny_car": ("Drag-strip funny car", ["Long tilt-body shell with giant rear wing", "Header pipes with painted flames", "Huge slick rear tires"], "Slick rear tires"),
    "fire_truck": ("Fire engine", ["Ladder with rungs", "Roll-up compartment doors", "Roof light bar"], "Rolling wheels"),
    "rescue_van": ("Rescue van", ["Roof light bar", "Rear chevron stripes", "Side window"], "Rolling wheels"),
    "school_bus": ("School bus", ["Six side windows", "Black safety stripes", "Rear red lights"], "Rolling wheels"),
    "delivery_van": ("Box delivery truck", ["Large cargo box with stripe", "Cab with side window", "Chassis rails"], "Rolling wheels"),
    "ice_cream_truck": ("Ice-cream truck", ["Serving window with striped awning", "Giant roof cone", "Rounded body"], "Rolling wheels"),
    "tow_truck": ("Wrecker tow truck", ["Boom with hook and cable", "Amber roof beacon", "Tandem rear axle"], "Rolling wheels"),
    "garbage_truck": ("Refuse truck", ["Rear lifter arm", "Hopper opening", "Rib panel body"], "Rolling wheels"),
    "military_truck": ("Military utility vehicle", ["Flat roof with hatch and antenna", "Long flat hood and narrow windows", "Wide wheel openings and big tires"], "Big off-road wheels"),
    "troop_transport": ("Troop transport", ["Canvas cargo cover with ribs", "Three axles", "Cab with window"], "Rolling wheels"),
    "recon": ("Quarter-ton scout", ["Upright fold-style windshield and open seats", "Rear spare, jerry can and side shovel", "Whip antenna"], "Steel military wheels"),
    "tank": ("Battle tank", ["Rotating-style turret and long barrel", "Road wheels and tracks", "Camo patches"], "Tracked"),
    "armored_carrier": ("Armored carrier", ["Four axles", "Roof turret", "Slit windows"], "Rolling wheels"),
    "fuel_tanker": ("Fuel tanker", ["Tank barrel with bands", "Roof hatch", "Tandem rear axle"], "Rolling wheels"),
    "dump_truck": ("Dump truck", ["Tilted bed with ribs", "Hydraulic ram", "Tandem axle"], "Rolling wheels"),
    "excavator": ("Excavator", ["Boom, dipper and bucket", "Rotating-style cab", "Rubber-style tracks"], "Tracked"),
    "bulldozer": ("Bulldozer", ["Front blade with push arms", "Exhaust stack", "Tracks"], "Tracked"),
    "cement_mixer": ("Cement mixer", ["Striped mixing drum", "Rear chute", "Tandem axle"], "Rolling wheels"),
    "crane_truck": ("Crane truck", ["Lattice boom with hook", "Outrigger-style base", "Tandem axle"], "Rolling wheels"),
    "wedge_pickup": ("Angular stainless pickup", ["Flat stainless body planes", "Full-width light-bar nose", "Sail-panel covered bed"], "Aero disc wheels"),
    "bucket_truck": ("Utility bucket truck", ["Articulating boom with work bucket", "Service body with compartments", "Outrigger and amber beacon"], "Rolling wheels"),
    "sand_rail": ("Long-travel sand rail", ["Tube frame with roof light bar", "Exposed rear engine and coil-overs", "Whip flag"], "Paddle-style off-road wheels"),
    "flatbed": ("Flatbed truck", ["Steel deck with stake pockets", "Headache rack", "Strapped load of crates"], "Tandem rear axle"),
    "tractor": ("Farm tractor", ["Giant ribbed rear tires", "Roll-over cab and exhaust stack", "Long hood with grille"], "Big-and-little ag wheels"),
    "backhoe": ("Backhoe loader", ["Front loader bucket", "Rear digging arm", "Stabilizer legs"], "Big rear wheels"),
    "hot_dog": ("Hot-dog promo car", ["Giant sausage body with a mustard stripe", "Toasted-bun lower body with porthole windows", "Bubble windshield"], "Whitewall disc wheels"),
    "formula_racer": ("Modern formula car", ["Halo cockpit protection", "Multi-element front and rear wings", "Sidepods and shark-fin engine cover"], "Covered racing wheels"),
    "stock_car": ("Oval-track stock car", ["Big door number roundel", "Window net and two-tone livery", "Rear spoiler, decal strip and front splitter"], "Black steel racing wheels"),
    "police_suv": ("Police pursuit SUV", ["Split red and blue light bar", "Two-tone doors", "Push bumper and spotlight"], "Black steel wheels"),
    "fire_suv": ("Fire command SUV", ["All-red light bar", "Reflective side stripe", "Push bumper"], "Five-spoke mag wheels"),
    "steam_roller": ("Steam road roller", ["Front roller drum", "Boiler with brass bands and tall chimney", "Canopy and flywheel"], "Spoked rear wheels and steel drum"),
    "pinto_compact": ("1970s subcompact fastback", ["Sloping hatchback rear glass", "Big chrome bumpers", "Side tape stripe"], "Small hubcaps"),
    "gullwing": ("Stainless gullwing coupe", ["Gullwing door raised", "Louvered rear glass", "Brushed stainless panels"], "Five-spoke wheels"),
    "two_door_4x4": ("Two-door 4x4", ["Soft top with rounded rear bow", "Upright windshield and exposed hinges", "Flat fender flares and rear spare"], "Beadlock-style off-road wheels"),
    "four_door_4x4": ("Four-door 4x4", ["Upright windshield and removable-style hardtop", "Four doors with exposed hinges", "Flat fender flares, rock rails and rear spare"], "Beadlock-style off-road wheels"),
    "open_top_4x4": ("Open-top 4x4", ["Black soft top folded down", "Black roll bars over four seats", "Black interior, flares and rear spare"], "Beadlock-style off-road wheels"),
    "front_loader": ("Wheel loader", ["Lift arms and bucket", "Giant tires", "Articulated-style body"], "Giant wheels"),
    "open_wheel": ("Open-wheel racer", ["Front and rear wings", "Driver helmet", "Exposed wheels"], "Racing wheels"),
    "dragster": ("Drag racer", ["Supercharged engine", "Huge rear slicks", "Rear wing"], "Slick rear tires"),
}



# Callout anchors for silhouettes without a car-style TRIM entry: (label, text, x, y) on the 400x260 canvas.
ANCH = {
    "hot_rod": [("Headlamp", "Chrome-ringed lamp on a stalk", 318, 124), ("Engine", "Exposed supercharger with intake scoop", 287, 125), ("Rear tire", "Big rear tire with five-spoke wheel", 104, 170)],
    "rat_rod": [("Headlamp", "Bare lamp on a chrome bucket", 296, 146), ("Engine", "Exposed engine with exhaust stacks", 236, 138), ("Patina", "Rust and primer patches", 118, 142)],
    "fire_truck": [("Ladder", "Rail ladder with rungs", 150, 100), ("Compartments", "Roll-up compartment doors", 130, 140), ("Light bar", "Red and blue roof lights", 300, 88), ("Wheels", "Tandem rear axle", 168, 180)],
    "rescue_van": [("Light bar", "Red and blue roof lights", 198, 92), ("Chevrons", "Rear safety chevron stripes", 90, 124), ("Wheels", "Rolling wheels with rim highlights", 296, 178)],
    "school_bus": [("Windows", "Six side windows", 160, 112), ("Safety stripes", "Black safety stripes", 200, 135), ("Wheels", "Rolling wheels", 300, 178)],
    "delivery_van": [("Cargo box", "Large box with stripe and package icon", 140, 106), ("Cab", "Cab with side window", 300, 110), ("Wheels", "Rolling wheels", 300, 178)],
    "ice_cream_truck": [("Giant cone", "Cone with scoops and a cherry", 170, 60), ("Serving window", "Striped awning over the counter", 160, 126), ("Wheels", "Rolling wheels", 296, 178)],
    "tow_truck": [("Boom and hook", "Boom with cable and hook", 120, 114), ("Beacon", "Amber roof beacon", 282, 90), ("Wheels", "Tandem rear axle", 160, 180)],
    "garbage_truck": [("Lifter arm", "Rear lifter arm", 30, 146), ("Hopper", "Dark hopper opening", 70, 156), ("Cab", "Cab with side window", 300, 110)],
    "camper": [("Awning stripe", "Wavy side stripe", 150, 150), ("Door", "Side door with window", 215, 134), ("Roof A/C", "Roof air-conditioner", 130, 80)],
    "motorhome": [("Windshield", "Panoramic windshield", 342, 102), ("Swoosh stripes", "Three-color swoosh graphics", 180, 140), ("Roof A/C", "Roof air-conditioner", 146, 64)],
    "limo": [("Windows", "Three window panels", 170, 124), ("Chrome trim", "Chrome belt strip", 200, 150), ("Wheels", "Long wheelbase", 318, 178)],
    "dune_buggy": [("Roll bar", "Tubular roll bar", 180, 100), ("Engine", "Exposed rear engine with fins", 74, 146), ("Bug-eye lamps", "Chrome bug-eye lamps", 318, 120), ("Big tires", "Big rear tires", 118, 172)],
    "mud_truck": [("Lift kit", "Raised body on a lifted frame", 200, 152), ("Roof lamps", "Roof lamp bar", 258, 62), ("Tires", "Oversize chunky tires", 300, 166)],
    "monster_truck": [("Shocks", "Chrome shocks and springs", 116, 140), ("Flames", "Painted flame decals", 250, 98), ("Giant tires", "Oversize chunky tires", 304, 152)],
    "trike_bike": [("Trunk", "Rear trunk box", 115, 120), ("Pipes", "Chrome exhaust pipes", 140, 168), ("Headlamp", "Chrome headlamp and windscreen", 314, 124), ("Twin wheels", "Two rear wheels", 105, 174)],
    "kei_3wheel": [("Cargo bed", "Slatted bed", 140, 142), ("Open cab", "Open-sided cab with roof", 270, 112), ("Single front wheel", "One small front wheel", 306, 178)],
    "funny_car": [("Rear wing", "Giant rear wing", 70, 96), ("Header flames", "Header pipes with flames", 190, 176), ("Slicks", "Huge rear slicks", 100, 164)],
    "dragster": [("Rear wing", "Rear wing and supports", 80, 112), ("Blower", "Supercharger on top of the engine", 214, 128), ("Slicks", "Huge rear slicks", 96, 164)],
    "open_wheel": [("Rear wing", "Rear wing with end plates", 70, 122), ("Helmet", "Driver helmet and visor", 228, 132), ("Wheels", "Exposed racing wheels", 104, 170)],
    "military_truck": [("Antenna", "Whip antenna", 64, 40), ("Roof hatch", "Roof hatch", 147, 79), ("Hood", "Long flat hood", 300, 122), ("Tires", "Big off-road tires", 312, 175)],
    "troop_transport": [("Canvas cover", "Ribbed canvas cargo cover", 150, 100), ("Cab", "Cab with window", 300, 108), ("Axles", "Three axles", 125, 180)],
    "fuel_tanker": [("Tank", "Banded tank barrel", 150, 130), ("Hatch", "Roof hatch", 150, 94), ("Axles", "Tandem rear axle", 132, 180)],
    "recon": [("Windshield", "Upright fold-style windshield", 251, 104), ("Spare", "Rear-mounted spare", 86, 142), ("Jerry can", "Jerry can and side shovel", 105, 124), ("Seats", "Open seats", 206, 120)],
    "tank": [("Barrel", "Long gun barrel with muzzle", 330, 102), ("Turret", "Turret with hatch", 210, 100), ("Tracks", "Road wheels and tracks", 200, 172)],
    "armored_carrier": [("Turret", "Roof turret", 200, 98), ("Slit windows", "Armored slit windows", 110, 124), ("Wheels", "Four axles", 310, 180)],
    "dump_truck": [("Dump bed", "Tilted bed with ribs", 150, 110), ("Hydraulic ram", "Hydraulic lift ram", 212, 136), ("Wheels", "Tandem rear axle", 170, 180)],
    "excavator": [("Bucket", "Digging bucket", 352, 150), ("Boom", "Boom and dipper", 292, 80), ("Tracks", "Track links and rollers", 190, 186)],
    "bulldozer": [("Blade", "Front blade with push arms", 338, 150), ("Exhaust stack", "Exhaust stack", 266, 92), ("Tracks", "Track links and rollers", 190, 177)],
    "cement_mixer": [("Mixing drum", "Striped mixing drum", 150, 110), ("Chute", "Rear chute", 50, 160), ("Wheels", "Tandem rear axle", 160, 180)],
    "crane_truck": [("Boom", "Lattice boom", 210, 70), ("Hook", "Hook and cable", 292, 112), ("Wheels", "Tandem rear axle", 152, 180)],
    "wedge_pickup": [("Light bar", "Full-width light bar across the nose", 360, 130), ("Body planes", "Flat stainless panels, no curves", 214, 100), ("Sail panel", "Covered bed sloping off the roof", 90, 118), ("Wheels", "Aero disc wheel covers", 300, 178)],
    "bucket_truck": [("Work bucket", "Fiberglass bucket for the line crew", 111, 36), ("Boom", "Two-section articulating boom", 140, 76), ("Compartments", "Service-body tool compartments", 66, 142), ("Outrigger", "Stabilizer leg and pad", 58, 190)],
    "sand_rail": [("Whip flag", "Antenna flag for the dunes", 156, 29), ("Light bar", "Roof light bar", 204, 94), ("Engine", "Exposed rear engine with air filter", 102, 120), ("Paddle tires", "Paddle-style rear tires", 118, 168)],
    "flatbed": [("Crates", "Strapped load of wooden crates", 84, 126), ("Headache rack", "Protects the cab from the load", 238, 124), ("Deck", "Steel deck with stake pockets", 140, 156), ("Wheels", "Tandem rear axle", 128, 180)],
    "tractor": [("Rear tire", "Giant ribbed rear tire", 122, 140), ("Exhaust stack", "Vertical exhaust stack", 293, 80), ("Cab", "Roll-over cab with seat and wheel", 166, 92), ("Grille", "Front grille and hood", 341, 138)],
    "backhoe": [("Backhoe arm", "Rear digging arm with bucket", 40, 90), ("Loader bucket", "Front loader bucket", 364, 148), ("Cab", "Glass cab", 180, 98), ("Stabilizer", "Stabilizer leg and pad", 78, 186)],
    "hot_dog": [("Mustard", "Zig-zag mustard stripe down the top", 200, 84), ("Sausage", "Sausage body overhanging the bun", 30, 106), ("Bun windows", "Rounded windows in the bun", 167, 142), ("Windshield", "Bubble windshield", 340, 142), ("Whitewalls", "Whitewall disc wheels", 300, 182)],
    "formula_racer": [("Rear wing", "Two-element rear wing with end plate", 72, 96), ("Halo", "Titanium-style halo over the cockpit", 228, 110), ("Front wing", "Multi-element front wing", 362, 174), ("Wheels", "Covered racing wheels", 96, 177)],
    "stock_car": [("Door number", "Big number roundel", 236, 150), ("Window net", "Driver window net", 188, 116), ("Spoiler", "Rear deck spoiler", 50, 121), ("Splitter", "Front splitter", 358, 176)],
    "police_suv": [("Light bar", "Split red and blue light bar", 177, 99), ("Doors", "Two-tone doors with lettering", 205, 152), ("Push bumper", "Front push bumper", 366, 152), ("Wheels", "Black steel wheels", 300, 178)],
    "fire_suv": [("Light bar", "All-red light bar", 177, 99), ("Stripe", "Reflective side stripe", 120, 150), ("Push bumper", "Front push bumper", 366, 152), ("Wheels", "Five-spoke mag wheels", 300, 178)],
    "steam_roller": [("Chimney", "Tall chimney with brass cap", 295, 60), ("Roller drum", "Front roller drum", 320, 172), ("Flywheel", "Spoked flywheel", 214, 92), ("Canopy", "Canopy on posts", 126, 44)],
    "pinto_compact": [("Hatch glass", "Sloping fastback hatch", 150, 118), ("Bumpers", "Big chrome bumpers", 355, 170), ("Stripe", "Side tape stripe", 200, 147), ("Hubcaps", "Small hubcaps", 296, 180)],
    "gullwing": [("Gullwing door", "Door raised on its roof hinge", 230, 70), ("Louvers", "Louvered rear glass", 156, 116), ("Interior", "Seat visible through the open door", 221, 142), ("Wheels", "Five-spoke wheels", 306, 178)],
    "four_door_4x4": [("Hardtop", "Removable-style hardtop", 140, 85), ("Door hinges", "Exposed door hinges", 168, 140), ("Spare", "Tailgate-mounted spare", 38, 128), ("Flares", "Flat fender flares and off-road tires", 300, 148)],
    "two_door_4x4": [("Soft top", "Soft top with a rounded rear bow", 120, 82), ("Door hinges", "Exposed door hinges", 152, 140), ("Spare", "Tailgate-mounted spare", 58, 128), ("Flares", "Flat fender flares and off-road tires", 294, 148)],
    "open_top_4x4": [("Folded top", "Black soft top folded at the back", 108, 118), ("Roll bars", "Black roll bars", 186, 94), ("Interior", "Four black seats", 208, 118), ("Spare", "Rear spare", 86, 140)],
    "front_loader": [("Bucket", "Loader bucket", 360, 154), ("Lift arms", "Z-bar lift arms", 290, 124), ("Cab", "Tall glass cab", 192, 94), ("Giant tires", "Big loader tires", 282, 168)],
}

def _trim(key):
    p = TRIM.get(key)
    if not p:
        return ""
    f, rr, belt, sill = p["front"], p["rear"], p["belt"], p["sill"]
    x1, x2, wy, wr = p["w"]
    s = f'<path d="M{rr + 8} {belt} H{f - 14}" stroke="#fff" stroke-width="1.6" opacity=".5"/><path d="M{rr + 8} {belt + 2.2} H{f - 14}" stroke="#000" stroke-width="1.2" opacity=".16"/>'
    s += f'<rect x="{x1 + wr + 3}" y="{sill - 5}" width="{x2 - x1 - 2 * wr - 6}" height="5" rx="2" fill="{DARK}" opacity=".55"/>'
    for x in p["doors"]:
        s += f'<path d="M{x} {belt} V{sill - 6}" stroke="#000" stroke-width="1.4" opacity=".32"/><path d="M{x + 1.6} {belt} V{sill - 6}" stroke="#fff" stroke-width="1" opacity=".3"/>'
    for x in p["handles"]:
        s += f'<rect x="{x - 6}" y="{belt + 7}" width="12" height="3.6" rx="1.8" fill="#1d2027" opacity=".35" transform="translate(0 1)"/><rect x="{x - 6}" y="{belt + 7}" width="12" height="3.6" rx="1.8" fill="{CHROME}"/>'
    if p.get("mirror"):
        mx, my = p["mirror"]
        s += f'<path d="M{mx} {my + 3} L{mx - 5} {my + 8}" stroke="{DARK}" stroke-width="2"/><ellipse cx="{mx}" cy="{my}" rx="6" ry="4" fill="{DARK}"/><ellipse cx="{mx - 1}" cy="{my - 1}" rx="3" ry="1.6" fill="#fff" opacity=".4"/>'
    ly = p["lamp_y"]
    s += f'<circle cx="{f - 11}" cy="{ly}" r="9" fill="{CHROME}"/><circle cx="{f - 11}" cy="{ly}" r="6.4" fill="#ffefa8"/><circle cx="{f - 12.5}" cy="{ly - 1.8}" r="2.6" fill="#fff"/>'
    s += f'<rect x="{rr + 2}" y="{ly - 5}" width="8" height="13" rx="2.5" fill="#c92b2b"/><rect x="{rr + 3.4}" y="{ly - 3.6}" width="2.6" height="9" rx="1.3" fill="#ff9a9a" opacity=".8"/>'
    return s


def hotspots(key):
    """Callout anchors as percentages of the 400x260 canvas, for the storefront detail view."""
    p = TRIM.get(key)
    if not p:
        return [dict(label=a, text=t, x=round(x / 4.0, 1), y=round(y / 2.6, 1)) for a, t, x, y in ANCH.get(key, [])]
    x1, x2, wy, wr = p["w"]
    spots = [
        ("Headlamps", "Chrome-ringed lens with painted reflector detail", (p["front"] - 11) / 4.0, p["lamp_y"] / 2.6),
        ("Wheels", META.get(key, ("", [], "Rolling wheels"))[2] + " with sidewall rings and rim highlights", x2 / 4.0, wy / 2.6),
        ("Tail lamps", "Red lens with a molded highlight", (p["rear"] + 6) / 4.0, p["lamp_y"] / 2.6),
    ]
    if p["handles"]:
        spots.append(("Doors", "Etched door seams and chrome handles", p["handles"][0] / 4.0, (p["belt"] + 9) / 2.6))
    return [dict(label=a, text=b, x=round(c, 1), y=round(d, 1)) for a, b, c, d in spots]



# ---------------------------------------------------------------- softening (die-cast castings have no knife edges)
import re as _re

# Corner radius per silhouette. Cars and pickups get generous radii; working trucks and military less;
# the wedge concept car keeps its hard edges on purpose.
SOFT_DEFAULT = 14
SOFT = {"open_top_4x4": 6, "four_door_4x4": 7, "two_door_4x4": 7, "steam_roller": 6, "gullwing": 4, "formula_racer": 4, "wedge": 0, "wedge_pickup": 0, "bucket_truck": 6, "flatbed": 6, "tractor": 6, "backhoe": 5, "sand_rail": 4, "open_wheel": 4, "dragster": 4, "funny_car": 7,
        "tank": 4, "armored_carrier": 4, "military_truck": 5, "troop_transport": 5, "recon": 5, "fuel_tanker": 5,
        "dump_truck": 5, "excavator": 4, "bulldozer": 4, "cement_mixer": 5, "crane_truck": 5, "front_loader": 4,
        "fire_truck": 6, "garbage_truck": 6, "tow_truck": 6, "school_bus": 7, "delivery_van": 7, "motorhome": 8}
_TOK = _re.compile(r"[MLQZmlqz]|-?\d*\.?\d+")


def _round_path(d, R):
    """Round every corner of a closed M/L/Q path with radius up to R (clamped to 45% of each adjacent segment)."""
    toks = _TOK.findall(d)
    if not toks or any(t in "mlqz" for t in toks if t.isalpha()) or "Z" not in toks:
        return None
    segs, i, cur = [], 0, None   # segs: (kind, ctrl, end)
    start = None
    while i < len(toks):
        t = toks[i]
        if t == "M":
            if start is not None:
                return None  # multi-subpath: leave alone
            start = (float(toks[i + 1]), float(toks[i + 2])); cur = start; i += 3
        elif t == "L":
            p = (float(toks[i + 1]), float(toks[i + 2])); segs.append(("L", None, p)); cur = p; i += 3
        elif t == "Q":
            c = (float(toks[i + 1]), float(toks[i + 2])); p = (float(toks[i + 3]), float(toks[i + 4]))
            segs.append(("Q", c, p)); cur = p; i += 5
        elif t == "Z":
            i += 1
        else:  # implicit repeat of last command
            if not segs:
                return None
            k = segs[-1][0]
            if k == "L":
                p = (float(toks[i]), float(toks[i + 1])); segs.append(("L", None, p)); cur = p; i += 2
            else:
                return None
    if start is None or len(segs) < 2:
        return None
    if segs[-1][2] != start:
        segs.append(("L", None, start))
    n = len(segs)
    pts = [segs[k - 1][2] if k else start for k in range(n)]  # pts[k] = start point of seg k
    def dist(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])
    def toward(a, b, r):
        L = dist(a, b) or 1.0
        return (a[0] + (b[0] - a[0]) * r / L, a[1] + (b[1] - a[1]) * r / L)
    # corner k sits at pts[k], between seg k-1 (incoming) and seg k (outgoing); only round L-L corners,
    # and L-Q / Q-L corners on the straight side
    cut_in, cut_out = {}, {}
    for k in range(n):
        inc, out = segs[k - 1], segs[k]
        v = pts[k]
        a = inc[1] if inc[0] == "Q" else pts[k - 1]
        b = out[1] if out[0] == "Q" else out[2]
        la, lb = dist(v, a), dist(v, b)
        if la < 0.5 or lb < 0.5:
            continue
        ux, uy = (a[0] - v[0]) / la, (a[1] - v[1]) / la
        wx, wy = (b[0] - v[0]) / lb, (b[1] - v[1]) / lb
        if abs(ux * wy - uy * wx) < 0.08:  # nearly straight: nothing to round
            continue
        r = R
        if inc[0] == "L":
            r = min(r, la * 0.45)
        if out[0] == "L":
            r = min(r, lb * 0.45)
        if inc[0] == "Q" and out[0] == "Q":
            continue
        if r < 0.8:
            continue
        cut_in[k] = toward(v, a, r) if inc[0] == "L" else None
        cut_out[k] = toward(v, b, r) if out[0] == "L" else None
    f = lambda p: f"{p[0]:.1f} {p[1]:.1f}"
    area = sum(pts[k][0] * pts[(k + 1) % n][1] - pts[(k + 1) % n][0] * pts[k][1] for k in range(n))
    crown = min(1.0, R / 14.0)

    def line(a, b):
        """Straight edge -> slightly crowned edge (castings have convex panels), except surfaces facing down."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        if L < 14:
            return f"L{f(b)}"
        nx, ny = ((dy, -dx) if area > 0 else (-dy, dx))
        nx, ny = nx / L, ny / L
        if ny > 0.35:
            return f"L{f(b)}"
        bow = min(2.6, L * 0.03) * crown
        return f"Q{f(((a[0] + b[0]) / 2 + nx * bow, (a[1] + b[1]) / 2 + ny * bow))} {f(b)}"
    first = cut_out.get(0) or start
    out = [f"M{f(first)}"]
    pos = first
    for k in range(n):
        kind, c, e = segs[k]
        nxt = (k + 1) % n
        end_pt = cut_in.get(nxt) or e
        if kind == "L":
            out.append(line(pos, end_pt))
        else:
            out.append(f"Q{f(c)} {f(e)}")
        if nxt in cut_in or nxt in cut_out:
            v = pts[nxt]
            to = cut_out.get(nxt) or v
            if cut_in.get(nxt) is None:  # Q into corner: already at v
                out.append(f"L{f(to)}")
            else:
                out.append(f"Q{f(v)} {f(to)}")
            pos = to
        else:
            pos = end_pt if kind == "L" else e
    out.append("Z")
    return "".join(out)


_PATH = _re.compile(r'<path d="([^"]+)"( fill="(?!none)[^"]+")')
_RECT = _re.compile(r'<rect x="([\d.\-]+)" y="([\d.\-]+)" width="([\d.]+)" height="([\d.]+)"( fill="url\(#(?:body|accent)\)")')


def soften(art, R):
    if R <= 0:
        return art
    def p(m):
        d = _round_path(m.group(1), R * (0.45 if "glass" in m.group(2) else 1.0))
        return f'<path d="{d}"{m.group(2)}' if d else m.group(0)
    def r(m):
        w, h = float(m.group(3)), float(m.group(4))
        rx = min(R * 0.6, w / 2, h / 2)
        return f'<rect x="{m.group(1)}" y="{m.group(2)}" width="{m.group(3)}" height="{m.group(4)}" rx="{rx:.1f}"{m.group(5)}'
    return _RECT.sub(r, _PATH.sub(p, art))


# Literal colours used by the templates, mapped to realistic materials.
_MATERIALS = [
    ('fill="#ffe36b"', 'fill="url(#lamp)"'), ('fill="#ffe9a0"', 'fill="url(#lamp)"'), ('fill="#ffefa8"', 'fill="url(#lamp)"'),
    ('fill="#e03b3b"', 'fill="url(#tail)"'), ('fill="#c92b2b"', 'fill="url(#tail)"'),
    ('fill="#3d7be0"', 'fill="#2457b5"'), ('fill="#2a2d34"', 'fill="#17191d"'),
    ('fill="#9a6a3e"', 'fill="url(#wood)"'), ('fill="#4a4f58"', 'fill="#2e3238"'),
]
STUDIO = "#eceef0"


def _paint(gid, base, gloss=1.0):
    """Automotive paint: sky reflection on top, dark horizon line at the shoulder, ground bounce at the sill."""
    st = [(0, 0.50), (0.16, 0.22), (0.38, 0.04), (0.45, -0.5), (0.52, -0.08), (0.72, -0.2), (0.9, -0.38), (1, -0.2)]
    stops = "".join(f'<stop offset="{o}" stop-color="{shade(base, f * gloss)}"/>' for o, f in st)
    return f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">{stops}</linearGradient>'


def render(body_key, category, body, accent, sku, limited=False):
    tint = BG["Limited Edition" if limited else category][0]
    if limited:
        body, accent = "#c9a13b", "#6e1a1a"
    _WHEELS.clear()
    _ARCHES.clear()
    _STYLE.update(style="mag", hub=None)
    if category == "Military & Army" and not limited:
        _STYLE.update(style="steel", hub=shade(body, -0.25))
    elif category == "Construction":
        _STYLE.update(style="steel", hub="#d9a520")
    c = {"body": "url(#body)", "accent": "url(#accent)"}
    art, trim = TEMPLATES[body_key](c), _trim(body_key)
    art = soften(art, SOFT.get(body_key, SOFT_DEFAULT))
    for a, b in _MATERIALS:
        art, trim = art.replace(a, b), trim.replace(a, b)
    contact = "".join(
        f'<ellipse cx="{cx}" cy="{yb - 0.5:.1f}" rx="{rx:.1f}" ry="{max(2.2, min(r, 30) * 0.11):.1f}" fill="#000" opacity=".62" filter="url(#blur2)"/>'
        for cx, yb, rx, r in _WHEELS if yb >= 198)
    defs = (
        _paint("body", body) + _paint("accent", accent, 0.75)
        + '<linearGradient id="glassg" gradientUnits="userSpaceOnUse" x1="0" y1="70" x2="0" y2="160"><stop offset="0" stop-color="#9fb1c1"/><stop offset=".35" stop-color="#55687a"/><stop offset=".5" stop-color="#26313c"/><stop offset="1" stop-color="#121820"/></linearGradient>'
        '<pattern id="glass" patternUnits="userSpaceOnUse" width="400" height="260"><rect width="400" height="260" fill="url(#glassg)"/>'
        '<path d="M70 40 L118 40 L40 220 L-8 220 Z M134 40 L150 40 L72 220 L56 220 Z M250 40 L292 40 L214 220 L172 220 Z M306 40 L318 40 L240 220 L228 220 Z" fill="#fff" opacity=".13"/></pattern>'
        '<linearGradient id="chrome" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="9" spreadMethod="reflect"><stop offset="0" stop-color="#fbfcfd"/><stop offset=".3" stop-color="#c6ccd3"/><stop offset=".48" stop-color="#5a626d"/><stop offset=".58" stop-color="#262b31"/><stop offset=".82" stop-color="#a7afb9"/><stop offset="1" stop-color="#eef1f4"/></linearGradient>'
        '<radialGradient id="tire" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#26282c"/><stop offset=".6" stop-color="#1b1c1f"/><stop offset=".82" stop-color="#2d2f34"/><stop offset=".93" stop-color="#18191c"/><stop offset="1" stop-color="#0a0b0c"/></radialGradient>'
        '<radialGradient id="rim" cx=".36" cy=".3" r=".85"><stop offset="0" stop-color="#ffffff"/><stop offset=".3" stop-color="#d6dbe1"/><stop offset=".62" stop-color="#8d95a0"/><stop offset=".8" stop-color="#c3c9d0"/><stop offset="1" stop-color="#5c636d"/></radialGradient>'
        '<radialGradient id="dish" cx=".5" cy=".5" r=".5"><stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset=".85" stop-color="#000" stop-opacity=".28"/><stop offset="1" stop-color="#fff" stop-opacity=".25"/></radialGradient>'
        '<radialGradient id="rimwell" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#4a4f57"/><stop offset=".7" stop-color="#202328"/><stop offset="1" stop-color="#0d0e10"/></radialGradient>'
        '<linearGradient id="spoke" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f4f6f8"/><stop offset=".5" stop-color="#b3bac3"/><stop offset="1" stop-color="#7e8692"/></linearGradient>'
        '<radialGradient id="gunmetal" cx=".38" cy=".32" r=".8"><stop offset="0" stop-color="#8b9098"/><stop offset=".6" stop-color="#4c5158"/><stop offset="1" stop-color="#26292e"/></radialGradient>'
        '<linearGradient id="whitewall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f6f5ef"/><stop offset="1" stop-color="#c9c7bd"/></linearGradient>'
        '<linearGradient id="treadg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#0c0d0f"/><stop offset=".45" stroke-width="0" stop-color="#3a3d42"/><stop offset="1" stop-color="#16171a"/></linearGradient>'
        '<linearGradient id="rubber" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a3d42"/><stop offset=".2" stop-color="#222428"/><stop offset=".8" stop-color="#16171a"/><stop offset="1" stop-color="#2a2c30"/></linearGradient>'
        '<linearGradient id="well" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#050506"/><stop offset="1" stop-color="#1c1e22"/></linearGradient>'
        '<radialGradient id="lamp" cx=".4" cy=".38" r=".7"><stop offset="0" stop-color="#ffffff"/><stop offset=".35" stop-color="#f4f1e6"/><stop offset=".75" stop-color="#c9c3ae"/><stop offset="1" stop-color="#8e8873"/></radialGradient>'
        '<radialGradient id="tail" cx=".4" cy=".35" r=".75"><stop offset="0" stop-color="#ff8a7a"/><stop offset=".35" stop-color="#d0241b"/><stop offset="1" stop-color="#5a0806"/></radialGradient>'
        '<linearGradient id="wood" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a87447"/><stop offset=".5" stop-color="#7e5130"/><stop offset="1" stop-color="#5b371e"/></linearGradient>'
        # studio cyclorama: wall sweeping into the floor, soft key light, vignette
        f'<linearGradient id="cyc" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f7f8f9"/><stop offset=".62" stop-color="{STUDIO}"/><stop offset=".79" stop-color="#d9dcdf"/><stop offset=".84" stop-color="#e3e5e8"/><stop offset="1" stop-color="#f2f3f4"/></linearGradient>'
        '<radialGradient id="key" cx=".5" cy=".38" r=".6"><stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="vig" cx=".5" cy=".5" r=".75"><stop offset=".6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".16"/></radialGradient>'
        '<linearGradient id="sheen" gradientUnits="userSpaceOnUse" x1="0" y1="60" x2="400" y2="200">'
        '<stop offset=".18" stop-color="#fff" stop-opacity="0"/><stop offset=".27" stop-color="#fff" stop-opacity=".26"/><stop offset=".33" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset=".6" stop-color="#fff" stop-opacity="0"/><stop offset=".66" stop-color="#fff" stop-opacity=".1"/><stop offset=".7" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        '<linearGradient id="ao" gradientUnits="userSpaceOnUse" x1="0" y1="120" x2="0" y2="206"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset=".7" stop-color="#000" stop-opacity=".1"/><stop offset="1" stop-color="#000" stop-opacity=".35"/></linearGradient>'
        '<linearGradient id="fadeg" gradientUnits="userSpaceOnUse" x1="0" y1="206" x2="0" y2="246"><stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        '<mask id="fade" maskUnits="userSpaceOnUse" x="0" y="0" width="400" height="260"><rect x="0" y="206" width="400" height="54" fill="url(#fadeg)"/></mask>'
        '<filter id="white" x="0" y="0" width="1" height="1"><feColorMatrix type="matrix" values="0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 1 0"/></filter>'
        '<mask id="carm" maskUnits="userSpaceOnUse" x="0" y="0" width="400" height="260"><use href="#car" filter="url(#white)"/></mask>'
        '<filter id="blur2" x="-50%" y="-300%" width="200%" height="700%"><feGaussianBlur stdDeviation="1.8"/></filter>'
        '<filter id="blur6" x="-30%" y="-400%" width="160%" height="900%"><feGaussianBlur stdDeviation="7"/></filter>'
        # rounds every silhouette edge (moulded die-cast look): bevel from blurred alpha, soft diffuse + crisp specular
        '<filter id="studio" x="-4%" y="-8%" width="108%" height="116%" color-interpolation-filters="sRGB">'
        '<feGaussianBlur in="SourceAlpha" stdDeviation="2.4" result="b"/>'
        '<feDiffuseLighting in="b" surfaceScale="4" diffuseConstant="1.04" lighting-color="#fff" result="df"><feDistantLight azimuth="245" elevation="62"/></feDiffuseLighting>'
        '<feBlend in="SourceGraphic" in2="df" mode="multiply" result="lit"/>'
        '<feSpecularLighting in="b" surfaceScale="4" specularConstant=".7" specularExponent="26" lighting-color="#fff" result="sp"><feDistantLight azimuth="245" elevation="50"/></feSpecularLighting>'
        '<feComposite in="sp" in2="lit" operator="arithmetic" k1="0" k2=".55" k3="1" k4="0" result="all"/>'
        '<feComposite in="all" in2="SourceAlpha" operator="in"/></filter>'
    )
    badge = ""
    if limited:
        badge = ('<g transform="translate(340 40)"><circle r="22" fill="url(#accent)"/><circle r="22" fill="none" stroke="#e3c46a" stroke-width="2.2"/>'
                 '<circle r="17.5" fill="none" stroke="#e3c46a" stroke-width=".8" opacity=".8"/>'
                 '<path d="M0 -12 L3.6 -3.8 L12.4 -3.8 L5.4 1.8 L7.8 10.6 L0 5.6 L-7.8 10.6 L-5.4 1.8 L-12.4 -3.8 L-3.6 -3.8 Z" fill="#e3c46a"/></g>')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 400 260" width="400" height="260">'
        f'<defs>{defs}<g id="tpl">{art}</g><mask id="tplm" maskUnits="userSpaceOnUse" x="0" y="0" width="400" height="260"><use href="#tpl" filter="url(#white)"/></mask>'
        f'<g id="car"><use href="#tpl"/><g mask="url(#tplm)">{trim}</g></g></defs>'
        '<rect width="400" height="260" rx="18" fill="url(#cyc)"/>'
        f'<rect width="400" height="260" rx="18" fill="{tint}" opacity=".22"/>'
        '<rect width="400" height="260" rx="18" fill="url(#key)"/>'
        '<g mask="url(#fade)" opacity=".15"><use href="#car" transform="translate(0 412) scale(1 -1)"/></g>'
        '<ellipse cx="200" cy="206" rx="170" ry="11" fill="#000" opacity=".3" filter="url(#blur6)"/>'
        '<ellipse cx="200" cy="205" rx="140" ry="4" fill="#000" opacity=".35" filter="url(#blur2)"/>'
        f'{contact}'
        '<use href="#car" filter="url(#studio)"/>'
        '<g mask="url(#carm)"><rect width="400" height="260" fill="url(#ao)"/></g>'
        '<rect width="400" height="260" rx="18" fill="url(#vig)"/>'
        f'{badge}</svg>'
    )
