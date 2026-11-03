"""The sticker roll.

A sticker is a chain of weighted rolls:

    1. noun category        (e.g. "kitchen appliance")        common ones are likelier
    2. the specific noun    (e.g. "refrigerator")             everyday ones are likelier
    3. how many adjectives  (1 almost always, 2 rare, 3 near impossible)
    4. for each adjective: its type (color 40% / modifier 35% / look 15% / "in the style of" 10%),
       then which one (plain "red" is common, "neon flamingo" is not)
    5. maybe a verb that suits the noun
    6. maybe puffy, holographic or damaged; and a 0.001% chance it has been torn right off

Every roll's "surprise" (-log2 of its probability) is added up. The total decides the rarity tier:
common, uncommon, rare, legendary, mythical. Tier cut-offs are set so each tier gets the share of
stickers listed in config.STICKER["tier_shares"].

Words: sticker_banks/bank.json (nouns), ratings.json (how everyday each noun is), traits.json (adjectives).
All odds: config.py.
"""

import bisect
import colorsys
import hashlib
import json
import math
import random
import string

import config
import sticker_effects
import textsim
from stickers import _blob

_BANK = {"tried": False, "data": None}

THEME_EMOJI = {
    "kitchen": "\U0001F373", "furniture": "\U0001FA91", "tools": "\U0001F527", "clothing": "\U0001F9E2", "school": "✏️",
    "music": "\U0001F3B5", "sports": "⚽", "toys": "\U0001F9F8", "vehicles": "\U0001F697", "buildings": "\U0001F3E0",
    "foods": "\U0001F9C1", "trees": "\U0001F333", "flowers": "\U0001F33B", "small_plants": "\U0001F344", "landforms": "⛰️",
    "weather": "☁️", "water": "\U0001F30A", "rocks": "\U0001F48E", "dogs_cats": "\U0001F415", "farm": "\U0001F404",
    "wild_mammals": "\U0001F98A", "small_mammals": "\U0001F430", "marine_mammals": "\U0001F40B", "birds": "\U0001F426", "fish": "\U0001F41F",
    "sea_life": "\U0001F980", "reptiles": "\U0001F98E", "amphibians": "\U0001F438", "insects": "\U0001F41E", "spiders_crawlers": "\U0001F40C",
    "prehistoric": "\U0001F995", "greek_creatures": "\U0001F40E", "greek_gods": "⚡", "world_myth": "\U0001F409", "fairy_tale": "\U0001F9DA",
    "dragons": "\U0001F432", "fantasy_roles": "\U0001F9D9", "fantasy_gear": "\U0001F9EA", "fantasy_places": "\U0001F3F0", "space": "\U0001FA90",
}


# ---- loading -------------------------------------------------------------------

def _cum(weights):
    out, t = [], 0.0
    for w in weights:
        t += w
        out.append(t)
    return out


def _draw(rng, cum):
    return min(bisect.bisect(cum, rng.random() * cum[-1]), len(cum) - 1)


def _bits(cum, i):
    w = cum[i] - (cum[i - 1] if i else 0.0)
    return -math.log2(w / cum[-1])


def _p_bits(p):
    return -math.log2(max(p, 1e-12))


def load_bank():
    if _BANK["tried"]:
        return _BANK["data"]
    _BANK["tried"] = True
    d = config.APP_DIR / "sticker_banks"
    try:
        bank = json.loads((d / "bank.json").read_text(encoding="utf-8"))
        traits = json.loads((d / "traits.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        rate = json.loads((d / "ratings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rate = {"areas": {}, "specifics": {}}
    try:
        emoji = json.loads((d / "emoji.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        emoji = {"areas": {}, "specifics": {}}
    fw = {int(k): v for k, v in config.STICKER["familiarity_weight"].items()}
    areas = [a for a in bank["areas"] if len(a.get("specifics", [])) >= 3]
    for a in areas:
        a["_f"] = rate["areas"].get(a["area"]) or 3
        sr = rate["specifics"].get(a["area"], {})
        a["_sf"] = [sr.get(s) or 3 for s in a["specifics"]]
        a["_scum"] = _cum(fw[min(5, max(1, round(f)))] for f in a["_sf"])
    index = textsim.Index({i: a["area"] + " " + " ".join(a["specifics"]) for i, a in enumerate(areas)})
    pools = {
        "color": traits["colors"], "modifier": traits["modifiers"], "look": traits["looks"], "style_of": traits["painters"],
    }
    _BANK["data"] = {
        "areas": areas, "index": index, "emoji": emoji,
        "acum": _cum(fw[min(5, max(1, round(a["_f"])))] for a in areas),
        "pools": pools, "pcum": {k: _cum(x["weight"] for x in v) for k, v in pools.items()},
    }
    return _BANK["data"]


# ---- the roll ------------------------------------------------------------------

def _art_hex(seed_text):
    h = int(hashlib.md5(seed_text.encode()).hexdigest()[:8], 16)
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, 0.55, 0.6)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def roll(hint_text="", rng=None):
    """Roll a sticker recipe. Returns None if the word banks are missing."""
    b = load_bank()
    if not b:
        return None
    rng = rng or random.Random()
    P = config.STICKER
    bits = 0.0

    # 1 + 2: the noun
    ai = None
    if hint_text and rng.random() < P["idea_bias"]:
        hits = b["index"].query(hint_text, 8)
        if hits:
            ai = rng.choice(hits)[0]
    if ai is None:
        ai = _draw(rng, b["acum"])
    area = b["areas"][ai]
    bits += _bits(b["acum"], ai)
    si = _draw(rng, area["_scum"])
    bits += _bits(area["_scum"], si)
    specific = area["specifics"][si]

    # 3: how many adjectives
    counts = P["adjective_counts"]
    n = 1 + _draw(rng, _cum(counts))
    bits += _p_bits(counts[n - 1] / sum(counts))

    # 4: each adjective's type, then which one
    remaining = dict(P["adjective_types"])
    adjectives = []
    for _ in range(n):
        total = sum(remaining.values())
        kind = rng.choices(list(remaining), weights=list(remaining.values()))[0]
        bits += _p_bits(remaining.pop(kind) / total)
        i = _draw(rng, b["pcum"][kind])
        bits += _bits(b["pcum"][kind], i)
        item = b["pools"][kind][i]
        adjectives.append({"type": kind, "text": item.get("name") or item["text"], "hex": item.get("hex")})
    by = {a["type"]: a for a in adjectives}

    # 5: a verb
    verb = None
    if area["verbs"] and rng.random() < P["verb"]:
        verb = rng.choice(area["verbs"])
        bits += _p_bits(P["verb"]) + math.log2(len(area["verbs"]))
    else:
        bits += _p_bits(1 - P["verb"])

    # 6: rare qualities
    q = {"puffy": rng.random() < P["puffy"], "holographic": rng.random() < P["holographic"], "damage": 0}
    bits += _p_bits(P["puffy"] if q["puffy"] else 1 - P["puffy"]) + _p_bits(P["holographic"] if q["holographic"] else 1 - P["holographic"])
    dmg = P["damage"]
    x, acc = rng.random(), 0.0
    for tier, name in enumerate(("scuffed", "ripped", "shredded"), 1):
        acc += dmg[name]
        if x < acc:
            q["damage"] = tier
            bits += _p_bits(dmg[name])
            break
    else:
        bits += _p_bits(1 - sum(dmg.values()))
    if rng.random() < P["torn_off"]:
        q.update(damage=4, puffy=False, holographic=False)
        bits += _p_bits(P["torn_off"])

    color = by.get("color")
    recipe = {
        "area": area["area"], "theme": area["theme"], "specific": specific,
        "adjectives": adjectives,
        "color": {"name": color["text"], "hex": color["hex"]} if color else None,
        "modifier": by["modifier"]["text"] if "modifier" in by else None,
        "look": by["look"]["text"] if "look" in by else None,
        "painter": by["style_of"]["text"] if "style_of" in by else None,
        "verb": verb, "quality": q, "bits": round(bits, 2), "seed": rng.randrange(1, 10 ** 9),
    }
    recipe["art_hex"] = color["hex"] if color else _art_hex(area["area"] + specific)
    em = b["emoji"]
    recipe["emoji"] = (em["specifics"].get(area["area"], {}).get(specific) or em["areas"].get(area["area"])
                       or THEME_EMOJI.get(area["theme"], "⭐"))
    recipe["tier"] = tier_for(bits)
    return recipe


_TIERS = {"cuts": None}


def _cuts():
    """Bit totals that separate the tiers, found once by rolling a lot of stickers."""
    if _TIERS["cuts"] is None:
        _TIERS["cuts"] = [float("inf")] * 4          # placeholder while the sample is rolled
        rng = random.Random(20241015)
        sample = sorted(roll(rng=rng)["bits"] for _ in range(30000))
        s = config.STICKER["tier_shares"]
        above = [s["uncommon"] + s["rare"] + s["legendary"] + s["mythical"],
                 s["rare"] + s["legendary"] + s["mythical"],
                 s["legendary"] + s["mythical"],
                 s["mythical"]]
        _TIERS["cuts"] = [sample[min(len(sample) - 1, int(len(sample) * (1 - x)))] for x in above]
    return _TIERS["cuts"]


def tier_for(bits):
    return sum(bits >= c for c in _cuts())


def rarity_label(recipe):
    return config.TIERS[recipe.get("tier", 0)]


# ---- naming --------------------------------------------------------------------

_SMALL = {"and", "of", "the", "in", "on", "a", "an", "to", "with"}


def _cap(s):
    words = string.capwords(s.replace("-", "- ")).replace("- ", "-").split(" ")
    return " ".join(w.lower() if i and w.lower() in _SMALL else w for i, w in enumerate(words))


def full_name(r):
    """e.g. 'RARE Holographic Cartoony Baby Mint Green Unicorn hopping through clover'"""
    q = r["quality"]
    parts = []
    if r.get("tier"):
        parts.append(rarity_label(r))
    if q.get("damage"):
        parts.append(config.DAMAGE_NAMES[q["damage"] - 1])
    if q.get("puffy"):
        parts.append("Puffy")
    if q.get("holographic"):
        parts.append("Holographic")
    for key in ("look", "modifier"):
        if r.get(key):
            parts.append(r[key] if key == "look" and r[key].isupper() else _cap(r[key]))
    if r.get("color"):
        parts.append(_cap(r["color"]["name"]))
    parts.append(_cap(r["specific"]))
    name = " ".join(parts)
    tail = []
    if r.get("verb"):
        tail.append(r["verb"])
    if r.get("painter"):
        tail.append("in the style of " + r["painter"])
    return name + (" " + ", ".join(tail) if tail else "")


def art_prompt(r):
    """What to tell an AI that draws the sticker."""
    what = " ".join(x for x in [r.get("modifier"), r["color"]["name"] if r.get("color") else None, r["specific"]] if x)
    out = what
    if r.get("verb"):
        out += f", {r['verb']}"
    if r.get("look"):
        out += f" ({r['look']} style)"
    if r.get("painter"):
        out += f" (in the style of {r['painter']})"
    if r.get("color"):
        out += f", mainly {r['color']['name']}"
    out += ". Just the thing itself, cut out along its own outline: no background shape, circle, disc, frame, ground or scenery."
    return out


# ---- the offline picture: the thing itself, as a sticker -----------------------

_SIZE_SMALL = {"tiny", "little", "teeny", "miniature", "wee", "baby", "newborn", "toddler", "pocket-sized", "lilliputian", "young"}
_SIZE_BIG = {"giant", "jumbo", "enormous", "colossal", "titanic", "big"}
_REGION = 'filterUnits="userSpaceOnUse" x="-30" y="-30" width="260" height="260" color-interpolation-filters="sRGB"'

# Light-touch versions of a few looks, done with SVG filters (the rest only show in the name offline).
_LOOKS = {
    "pencil sketch": '<feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncR type="linear" slope="1.5" intercept="-.2"/><feFuncG type="linear" slope="1.5" intercept="-.2"/><feFuncB type="linear" slope="1.5" intercept="-.2"/></feComponentTransfer>',
    "watercolor": '<feTurbulence type="fractalNoise" baseFrequency=".04" numOctaves="2" seed="3" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="7"/><feGaussianBlur stdDeviation=".7"/><feColorMatrix type="saturate" values=".8"/><feComponentTransfer><feFuncA type="linear" slope="1"/><feFuncR type="linear" slope=".85" intercept=".15"/><feFuncG type="linear" slope=".85" intercept=".15"/><feFuncB type="linear" slope=".85" intercept=".15"/></feComponentTransfer>',
    "crayon drawing": '<feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="5" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="6"/><feColorMatrix type="saturate" values="1.3"/>',
    "neon sign": '<feGaussianBlur stdDeviation="4" result="g"/><feColorMatrix in="SourceGraphic" type="saturate" values="2.2" result="s"/><feMerge><feMergeNode in="g"/><feMergeNode in="g"/><feMergeNode in="s"/></feMerge>',
    "vaporwave": '<feColorMatrix type="hueRotate" values="285"/><feColorMatrix type="saturate" values="1.5"/>',
    "cartoony": '<feColorMatrix type="saturate" values="1.45"/>',
    "claymation": '<feGaussianBlur stdDeviation=".8"/><feColorMatrix type="saturate" values="1.15"/>',
}


def badge(r):
    """Offline sticker art: the emoji for the thing, huge, with a white sticker border.
    A colour adjective recolours it; size words make it smaller or bigger; a few looks apply a filter."""
    emoji = r.get("emoji") or THEME_EMOJI.get(r["theme"], "⭐")
    mod = (r.get("modifier") or "").lower()
    size = 108 if mod in _SIZE_SMALL else 160 if mod in _SIZE_BIG else 134
    y = 100 + size * 0.33
    layers = ['<filter id="stk" ' + _REGION + '><feGaussianBlur in="SourceAlpha" stdDeviation="4.5" result="b"/>'
              '<feComponentTransfer in="b" result="edge"><feFuncA type="linear" slope="14" intercept="-.7"/></feComponentTransfer>'
              '<feFlood flood-color="#fff" result="w"/><feComposite in="w" in2="edge" operator="in" result="white"/>'
              '<feGaussianBlur in="edge" stdDeviation="3" result="sb"/><feOffset in="sb" dy="3" result="so"/>'
              '<feFlood flood-color="#000" flood-opacity=".25"/><feComposite in2="so" operator="in" result="shadow"/>'
              '<feMerge><feMergeNode in="shadow"/><feMergeNode in="white"/><feMergeNode in="SourceGraphic"/></feMerge></filter>']
    inner = f'<text x="100" y="{y:.0f}" text-anchor="middle" font-size="{size}" font-family="Segoe UI Emoji,Apple Color Emoji,Noto Color Emoji,sans-serif">{emoji}</text>'
    if r.get("color"):
        layers.append('<filter id="tint" ' + _REGION + f'><feFlood flood-color="{r["color"]["hex"]}" result="t"/>'
                      '<feBlend in="t" in2="SourceGraphic" mode="color" result="m"/><feComposite in="m" in2="SourceAlpha" operator="in"/></filter>')
        inner = f'<g filter="url(#tint)">{inner}</g>'
    look = _LOOKS.get((r.get("look") or "").lower())
    if look:
        layers.append('<filter id="look" ' + _REGION + f'>{look}</filter>')
        inner = f'<g filter="url(#look)">{inner}</g>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200"><defs>{"".join(layers)}</defs><g filter="url(#stk)">{inner}</g></svg>'


def render(recipe, art_svg=None):
    """Final SVG for a recipe: the artwork (AI-drawn if given, else the badge) with rare effects on top."""
    art = art_svg or badge(recipe)
    return sticker_effects.apply(art, recipe["quality"], recipe["seed"], recipe["art_hex"])
