"""Rare-quality effects for stickers: puffy, and four tiers of damage.

(Holographic is drawn in the browser, because it has to react to how you tilt it:
see the .holo rules in static/style.css.)

`apply(svg, quality, seed)` takes any finished 200x200-ish sticker SVG and returns a new SVG
with the effects wrapped around it. It never looks inside the artwork, so it works the same on
an AI drawing and on the offline badge.
"""

import math
import random
import re

PUFF = """
<filter id="jot-puff" x="-15%" y="-15%" width="130%" height="130%" color-interpolation-filters="sRGB">
  <feGaussianBlur in="SourceAlpha" stdDeviation="4.5" result="blur"/>
  <feSpecularLighting in="blur" surfaceScale="7" specularConstant="1.05" specularExponent="22" lighting-color="#ffffff" result="spec">
    <fePointLight x="40" y="-30" z="150"/>
  </feSpecularLighting>
  <feComposite in="spec" in2="SourceAlpha" operator="in" result="specIn"/>
  <feGaussianBlur in="SourceAlpha" stdDeviation="6" result="shadowBlur"/>
  <feOffset in="shadowBlur" dx="0" dy="4" result="shadowOff"/>
  <feFlood flood-color="#000" flood-opacity=".28"/>
  <feComposite in2="shadowOff" operator="in" result="shadow"/>
  <feComposite in="SourceGraphic" in2="specIn" operator="arithmetic" k1="0" k2="1" k3="0.85" k4="0" result="lit"/>
  <feMerge><feMergeNode in="shadow"/><feMergeNode in="lit"/></feMerge>
</filter>"""

WHITE = """<filter id="jot-white" x="-5%" y="-5%" width="110%" height="110%">
  <feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 1 0"/></filter>"""


def _glue_filter(seed, freq=0.045):
    # Patchy translucent glue: noise, thresholded, used to cut the shape out of a flat tan fill.
    return f"""<filter id="jot-glue" x="-5%" y="-5%" width="110%" height="110%">
  <feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="3" seed="{seed % 997}" result="n"/>
  <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  9 0 0 0 -4.5" result="blobs"/>
  <feComposite in="SourceGraphic" in2="blobs" operator="in"/></filter>"""


def _jagged(rng, cx, cy, r, n=16):
    pts = []
    for i in range(n):
        a = i * 2 * math.pi / n + rng.uniform(-0.12, 0.12)
        rr = r * (rng.uniform(0.62, 1.1) if i % 2 else rng.uniform(0.9, 1.2))
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def _poly(pts):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def _edge_point(rng, side=None):
    side = side if side is not None else rng.randrange(4)
    t = rng.uniform(40, 160)
    return [(t, 0), (200, t), (t, 200), (0, t)][side]


def _split(svg):
    m = re.search(r"<svg\b([^>]*)>(.*)</svg>", svg, re.S | re.I)
    if not m:
        return "0 0 200 200", svg
    vb = re.search(r'viewBox\s*=\s*"([^"]+)"', m.group(1))
    return (vb.group(1) if vb else "0 0 200 200"), m.group(2)


def apply(svg, quality, seed=0, shard_color="#7aa7ff"):
    """quality: {"puffy": bool, "damage": 0..4}. Returns an SVG string (unchanged when nothing applies)."""
    puffy, damage = bool(quality.get("puffy")), int(quality.get("damage") or 0)
    if not puffy and not damage:
        return svg
    rng = random.Random(seed * 7919 + 13)
    vb, inner = _split(svg)
    body = f'<svg x="0" y="0" width="200" height="200" viewBox="{vb}" overflow="visible">{inner}</svg>'
    defs = [WHITE]
    cut_polys, over = [], []

    on_mask = f'<mask id="jot-on" maskUnits="userSpaceOnUse" x="-20" y="-20" width="240" height="240"><g filter="url(#jot-white)">{body}</g></mask>'
    defs.append(on_mask)

    if damage == 4:   # torn off: only what the sticker left behind
        defs.append(_glue_filter(seed, 0.05))
        shards = []
        for _ in range(rng.randint(5, 8)):
            cx, cy = rng.uniform(30, 170), rng.uniform(30, 170)
            shards.append(f'<polygon points="{_poly(_jagged(rng, cx, cy, rng.uniform(4, 10), 7))}" fill="{rng.choice([shard_color, "#ffffff", "#f4ecd8"])}" opacity=".8"/>')
        residue = (f'<g mask="url(#jot-on)"><g filter="url(#jot-glue)"><rect width="200" height="200" fill="#d9c58f" opacity=".85"/></g>'
                   f'<rect width="200" height="200" fill="#fffdf4" opacity=".16"/>{"".join(shards)}</g>')
        return _wrap(defs, residue)

    if damage >= 2:
        n_bites = 1 if damage == 2 else rng.choice([2, 3])
        radius = (rng.uniform(34, 48) if damage == 2 else rng.uniform(44, 62))
        start = rng.uniform(0, 6.283)
        for k in range(n_bites):
            a = start + k * (6.283 / n_bites) + rng.uniform(-0.5, 0.5)
            cut_polys.append(_jagged(rng, 100 + 80 * math.cos(a), 100 + 80 * math.sin(a), radius, 18))
    if cut_polys:
        holes = "".join(f'<polygon points="{_poly(p)}" fill="#000"/>' for p in cut_polys)
        defs.append(f'<mask id="jot-cut" maskUnits="userSpaceOnUse" x="-20" y="-20" width="240" height="240"><rect x="-20" y="-20" width="240" height="240" fill="#fff"/>{holes}</mask>')
        defs.append(_glue_filter(seed))
        for p in cut_polys:
            pts = _poly(p)
            over.append(f'<g mask="url(#jot-on)"><polygon points="{pts}" fill="#e7d9a8" opacity=".9" filter="url(#jot-glue)"/>'
                        f'<polygon points="{pts}" fill="none" stroke="#fffdf4" stroke-width="3.5" stroke-linejoin="round" opacity=".95"/>'
                        f'<polygon points="{pts}" fill="none" stroke="#c9b98a" stroke-width="1" stroke-dasharray="3 2"/></g>')
            # a few paper scraps clinging near the tear
            for _ in range(rng.randint(2, 4)):
                a = rng.uniform(0, 6.283)
                cx = sum(x for x, _ in p) / len(p) + math.cos(a) * radius * 1.0
                cy = sum(y for _, y in p) / len(p) + math.sin(a) * radius * 1.0
                over.append(f'<g mask="url(#jot-on)"><polygon points="{_poly(_jagged(rng, cx, cy, rng.uniform(3, 7), 7))}" fill="#fffdf4" opacity=".9"/></g>')
    if damage >= 1:   # scratches and a curled corner
        scratch = []
        for _ in range(rng.randint(3, 5) + damage * 2):
            x, y = rng.uniform(15, 185), rng.uniform(15, 185)
            a = rng.uniform(0, 3.14)
            ln = rng.uniform(14, 34)
            scratch.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x + ln * math.cos(a):.1f}" y2="{y + ln * math.sin(a):.1f}" stroke="#fff" stroke-width="{rng.uniform(.8, 1.8):.1f}" stroke-linecap="round" opacity="{rng.uniform(.45, .8):.2f}"/>')
        cx, cy = rng.choice([(200, 0), (0, 0), (200, 200), (0, 200)])
        sx = -1 if cx else 1
        sy = 1 if cy == 0 else -1
        s = 30 + damage * 6
        curl = (f'<polygon points="{cx},{cy} {cx + sx * s},{cy} {cx},{cy + sy * s}" fill="#fffdf4" opacity=".9"/>'
                f'<polygon points="{cx + sx * s},{cy} {cx},{cy + sy * s} {cx + sx * s * .55},{cy + sy * s * .55}" fill="#000" opacity=".12"/>')
        over.append(f'<g mask="url(#jot-on)">{"".join(scratch)}{curl}</g>')

    art = f'<g mask="url(#jot-cut)">{body}</g>' if cut_polys else body
    if damage >= 1:
        defs.append(f'<filter id="jot-fade"><feColorMatrix type="saturate" values="{1 - 0.12 * damage:.2f}"/></filter>')
        art = f'<g filter="url(#jot-fade)">{art}</g>'
    if puffy:
        defs.append(PUFF)
        art = f'<g filter="url(#jot-puff)">{art}</g>'
    return _wrap(defs, art + "".join(over))


def _wrap(defs, content):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-10 -10 220 230"><defs>{"".join(defs)}</defs>{content}</svg>'
