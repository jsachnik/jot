"""Plain clipart stickers for people with no AI: "Cat Sticker", "Blue Cat Sticker", drawn with bundled Noto Emoji artwork.

One picture, one name: every emoji is its own thing ("cat", "poodle", "heart on fire"), so no two stickers look alike
unless they are the same sticker. A colour word is sometimes added and recolours the picture ("Red Cat"). Rarity is how
unusual the picture is (judged from how many everyday things in the word bank it stands for), and puffy, holographic and
damage can still turn up. The collection is the set of distinct pictures, so new rolls lean toward ones you don't have yet.

Artwork: sticker_banks/emoji_art.json.gz (Noto Emoji, Apache-2.0, see NOTO_EMOJI_LICENSE.txt), built by tools/build_emoji_art.py.
"""

import collections
import gzip
import json
import math
import random

import config
import stickerbank
from stickerbank import _art_hex, _bits, _cum, _draw

_ART = {"data": None}
_PICS = {"v": None}
_CUTS = {"v": None}
RETRIES = 4          # re-rolls when the picture is already in your collection
COLOR_CHANCE = 0.3   # how often a colour word is added


def key(ch):
    """File key for an emoji string (code points in hex joined by '_', no variation selector). Matches tools/build_emoji_art.py."""
    return "_".join(f"{ord(c):x}" for c in ch if ord(c) != 0xFE0F)


def library():
    """{key: {"n": name, "s": svg}}"""
    if _ART["data"] is None:
        try:
            with gzip.open(config.APP_DIR / "sticker_banks" / "emoji_art.json.gz", "rt", encoding="utf-8") as f:
                _ART["data"] = json.load(f)
        except (OSError, ValueError):
            _ART["data"] = {}
    return _ART["data"]


def total():
    """How many different pictures can be collected."""
    return len(library())


def pictures():
    """Per picture: its weight (how common), the word-bank area it mostly belongs to, and the emoji character.
    The bank maps many nouns to each emoji; the number of everyday ones is a good measure of how common the picture is."""
    if _PICS["v"] is None:
        b, lib = stickerbank.load_bank(), library()
        em = b["emoji"]
        fw = {int(k): v for k, v in config.STICKER["familiarity_weight"].items()}
        weight, areas, chars = collections.Counter(), collections.defaultdict(collections.Counter), {}
        for ai, a in enumerate(b["areas"]):
            for s, f in zip(a["specifics"], a["_sf"]):
                ch = em["specifics"].get(a["area"], {}).get(s) or em["areas"].get(a["area"])
                if ch and key(ch) in lib:
                    weight[key(ch)] += fw[min(5, max(1, round(f)))]
                    areas[key(ch)][ai] += 1
                    chars[key(ch)] = ch
        keys = sorted(lib)
        for k in keys:                       # pictures no noun maps to still exist, just rare
            weight.setdefault(k, 1)
            chars.setdefault(k, "".join(chr(int(x, 16)) for x in k.split("_")))
        _PICS["v"] = {
            "keys": keys,
            "w": [math.sqrt(weight[k]) for k in keys],          # square root so a picture standing for 300 things isn't 300x as common
            "area": {k: (areas[k].most_common(1)[0][0] if areas[k] else None) for k in keys},
            "char": chars,
        }
        _PICS["v"]["cum"] = _cum(_PICS["v"]["w"])
    return _PICS["v"]


def _pick(rng, hint, b):
    """(picture key, bits). Chosen ideas can steer toward a picture near their words."""
    p = pictures()
    if hint and rng.random() < config.STICKER["idea_bias"]:
        hits = b["index"].query(hint, 8)
        if hits:
            area = b["areas"][rng.choice(hits)[0]]
            em = b["emoji"]
            cands = [key(em["specifics"].get(area["area"], {}).get(s) or em["areas"].get(area["area"]) or "") for s in area["specifics"]]
            cands = [k for k in cands if k in p["char"] and k in library()]
            if cands:
                k = rng.choice(cands)
                return k, _bits(p["cum"], p["keys"].index(k))
    i = _draw(rng, p["cum"])
    return p["keys"][i], _bits(p["cum"], i)


def _colour(rng, b):
    """(colour dict or None, bits)."""
    if rng.random() >= COLOR_CHANCE:
        return None, -math.log2(1 - COLOR_CHANCE)
    i = _draw(rng, b["pcum"]["color"])
    c = b["pools"]["color"][i]
    return {"name": c.get("name") or c["text"], "hex": c["hex"]}, -math.log2(COLOR_CHANCE) + _bits(b["pcum"]["color"], i)


def _cuts():
    """Bit totals separating the tiers, found once from a big sample (like stickerbank._cuts)."""
    if _CUTS["v"] is None:
        b = stickerbank.load_bank()
        rng = random.Random(20241016)
        sample = sorted(_pick(rng, "", b)[1] + _colour(rng, b)[1] for _ in range(20000))
        s = config.STICKER["tier_shares"]
        above = [s["uncommon"] + s["rare"] + s["legendary"] + s["mythical"], s["rare"] + s["legendary"] + s["mythical"],
                 s["legendary"] + s["mythical"], s["mythical"]]
        _CUTS["v"] = [sample[min(len(sample) - 1, int(len(sample) * (1 - x)))] for x in above]
    return _CUTS["v"]


def roll(hint_text="", rng=None, owned=()):
    """A plain clipart recipe (same fields as stickerbank.roll, minus most adjectives), or None if the word bank or artwork is missing.
    `owned` is a set of picture keys you already have; the roll tries a few times to land on a new one."""
    b = stickerbank.load_bank()
    if not b or not library():
        return None
    rng = rng or random.Random()
    P = config.STICKER
    for attempt in range(RETRIES):
        k, bits = _pick(rng, hint_text, b)
        if k not in owned or attempt == RETRIES - 1:
            break
    color, cbits = _colour(rng, b)
    bits += cbits
    q = {"puffy": rng.random() < P["puffy"], "holographic": rng.random() < P["holographic"], "damage": 0}
    x, acc = rng.random(), 0.0
    for tier_, name in enumerate(("scuffed", "ripped", "shredded"), 1):
        acc += P["damage"][name]
        if x < acc:
            q["damage"] = tier_
            break
    if rng.random() < P["torn_off"]:
        q.update(damage=4, puffy=False, holographic=False)
    tier = sum(bits >= c for c in _cuts())
    tier = min(4, tier + (1 if q["puffy"] or q["holographic"] else 0))
    if q["damage"] == 4:
        tier = max(tier, 3)
    p = pictures()
    ai = p["area"][k]
    area = b["areas"][ai] if ai is not None else None
    specific = library()[k]["n"]
    return {
        "area": area["area"] if area else specific, "theme": area["theme"] if area else "toys", "specific": specific,
        "adjectives": [{"type": "color", "text": color["name"], "hex": color["hex"]}] if color else [],
        "color": color, "modifier": None, "look": None, "painter": None, "verb": None,
        "quality": q, "bits": round(bits, 2), "seed": rng.randrange(1, 10 ** 9),
        "art_hex": color["hex"] if color else _art_hex(k), "emoji": p["char"][k], "tier": tier, "clipart": True,
    }


def name(recipe):
    """'RARE Puffy Red Cat Sticker'"""
    return stickerbank.full_name(recipe) + " Sticker"


_FILTER = ('<filter id="stk" ' + stickerbank._REGION + '><feGaussianBlur in="SourceAlpha" stdDeviation="4.5" result="b"/>'
           '<feComponentTransfer in="b" result="edge"><feFuncA type="linear" slope="14" intercept="-.7"/></feComponentTransfer>'
           '<feFlood flood-color="#fff" result="w"/><feComposite in="w" in2="edge" operator="in" result="white"/>'
           '<feGaussianBlur in="edge" stdDeviation="3" result="sb"/><feOffset in="sb" dy="3" result="so"/>'
           '<feFlood flood-color="#000" flood-opacity=".25"/><feComposite in2="so" operator="in" result="shadow"/>'
           '<feMerge><feMergeNode in="shadow"/><feMergeNode in="white"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')


def art(recipe):
    """The sticker artwork SVG (picture with a white die-cut border, recoloured if the recipe has a colour), or None if there is no picture."""
    entry = library().get(key(recipe.get("emoji") or ""))
    if not entry:
        return None
    inner, defs = entry["s"], _FILTER
    if recipe.get("color"):
        defs += ('<filter id="tint" ' + stickerbank._REGION + f'><feFlood flood-color="{recipe["color"]["hex"]}" result="t"/>'
                 '<feBlend in="t" in2="SourceGraphic" mode="color" result="m"/><feComposite in="m" in2="SourceAlpha" operator="in"/></filter>')
        inner = f'<g filter="url(#tint)">{inner}</g>'
    return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 200 200">'
            f'<defs>{defs}</defs><g filter="url(#stk)"><svg x="30" y="30" width="140" height="140" viewBox="0 0 128 128">{inner}</svg></g></svg>')


def owned_keys(recipes):
    """Picture keys in a list of stored recipes (dicts or None)."""
    lib = library()
    return {key(r["emoji"]) for r in recipes if r and r.get("emoji") and key(r["emoji"]) in lib}
