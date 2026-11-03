"""Sticker making: a procedural generator (offline) and a sanitiser for AI-drawn SVG."""

import hashlib
import math
import random
import re
import xml.etree.ElementTree as ET

NAMES_A = ["Wild", "Bright", "Quiet", "Curious", "Bold", "Little", "Electric", "Sleepy", "Cosmic", "Stubborn", "Gentle", "Sparky"]
NAMES_B = ["Spark", "Compass", "Seed", "Comet", "Lantern", "Kite", "Orbit", "Puzzle", "Ripple", "Sprout", "Beacon", "Ember"]


def _blob(rng, cx, cy, r):
    n = rng.choice([7, 8, 9, 10])
    pts = []
    for i in range(n):
        a = i * 2 * math.pi / n
        rr = r * rng.uniform(0.84, 1.0)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    mids = [((pts[i][0] + pts[(i + 1) % n][0]) / 2, (pts[i][1] + pts[(i + 1) % n][1]) / 2) for i in range(n)]
    d = f"M{mids[-1][0]:.1f},{mids[-1][1]:.1f}"
    for i in range(n):
        d += f" Q{pts[i][0]:.1f},{pts[i][1]:.1f} {mids[i][0]:.1f},{mids[i][1]:.1f}"
    return d + "Z"


def procedural(seed_text, colors):
    """Deterministic sticker from text. Returns (name, svg)."""
    seed = int(hashlib.sha256(seed_text.encode()).hexdigest()[:12], 16)
    rng = random.Random(seed)
    palette = list(colors) or ["#4f8cff", "#f0873c"]
    extras = ["#ffd166", "#ef476f", "#06d6a0", "#118ab2", "#9b5de5", "#fb8500"]
    rng.shuffle(extras)
    cols = (palette + extras)[:5]
    base, c2, c3, c4 = cols[0], cols[1], cols[2], cols[3]
    d = _blob(rng, 100, 100, 82)
    motifs = rng.sample(["rays", "rings", "dots", "waves", "stripes", "star"], 3)
    parts = []
    for k, m in enumerate(motifs):
        col = [c2, c3, c4][k]
        if m == "rays":
            n = rng.choice([8, 12, 16])
            for i in range(n):
                a = i * 2 * math.pi / n
                parts.append(f'<line x1="100" y1="100" x2="{100 + 120 * math.cos(a):.1f}" y2="{100 + 120 * math.sin(a):.1f}" stroke="{col}" stroke-width="5" opacity=".55"/>')
        elif m == "rings":
            for r in range(20, 100, rng.choice([16, 20, 24])):
                parts.append(f'<circle cx="100" cy="100" r="{r}" fill="none" stroke="{col}" stroke-width="5" opacity=".6"/>')
        elif m == "dots":
            for _ in range(rng.randint(10, 18)):
                parts.append(f'<circle cx="{rng.uniform(20, 180):.1f}" cy="{rng.uniform(20, 180):.1f}" r="{rng.uniform(3, 9):.1f}" fill="{col}" opacity=".8"/>')
        elif m == "waves":
            for y in range(40, 170, 28):
                amp = rng.uniform(6, 14)
                parts.append(f'<path d="M0,{y} Q50,{y - amp:.1f} 100,{y} T200,{y}" fill="none" stroke="{col}" stroke-width="6" opacity=".6"/>')
        elif m == "stripes":
            for x in range(-40, 240, 30):
                parts.append(f'<line x1="{x}" y1="0" x2="{x + 80}" y2="200" stroke="{col}" stroke-width="10" opacity=".45"/>')
        else:
            pts = []
            for i in range(10):
                rr = 44 if i % 2 == 0 else 20
                a = i * math.pi / 5 - math.pi / 2
                pts.append(f"{100 + rr * math.cos(a):.1f},{100 + rr * math.sin(a):.1f}")
            parts.append(f'<polygon points="{" ".join(pts)}" fill="{col}" opacity=".9"/>')
    letter = next((c for c in seed_text.upper() if c.isalpha()), "J")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">'
        f'<defs><clipPath id="c"><path d="{d}"/></clipPath></defs>'
        f'<path d="{d}" fill="#fff" stroke="#fff" stroke-width="16" stroke-linejoin="round"/>'
        f'<path d="{d}" fill="{base}"/>'
        f'<g clip-path="url(#c)">{"".join(parts)}</g>'
        f'<circle cx="100" cy="100" r="30" fill="#fff" opacity=".92"/>'
        f'<text x="100" y="113" text-anchor="middle" font-family="Georgia,serif" font-weight="700" font-size="38" fill="{base}">{letter}</text>'
        f'<path d="{d}" fill="none" stroke="rgba(0,0,0,.18)" stroke-width="2"/>'
        "</svg>")
    return f"{rng.choice(NAMES_A)} {rng.choice(NAMES_B)}", svg


_BAD = re.compile(r"<\s*(script|foreignObject|image|iframe|embed|object|audio|video|animate|set)\b|on\w+\s*=|javascript:|<!doctype|<!entity|@import|url\(\s*['\"]?\s*(https?:|//|data:)",
                  re.I)


def clean_svg(text):
    """Return a safe SVG string or None. Shown only through <img>, which also blocks scripts."""
    if not text:
        return None
    m = re.search(r"<svg\b.*</svg>", text, re.S | re.I)
    if not m:
        return None
    svg = m.group(0)
    if len(svg) > 30000 or _BAD.search(svg):
        return None
    if re.search(r"(href|src)\s*=\s*['\"]\s*(https?:|//|data:)", svg, re.I):
        return None
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return None
    if not root.tag.endswith("svg"):
        return None
    if "xmlns=" not in svg[:300]:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    if "viewBox" not in svg[:400]:
        svg = svg.replace("<svg", '<svg viewBox="0 0 200 200"', 1)
    return svg
