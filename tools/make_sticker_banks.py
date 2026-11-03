"""Ask the configured LLM to build the word banks for Jot's sticker generator.

Run (needs an AI configured in .env):   python tools/make_sticker_banks.py
Writes JSON to sticker_banks/. Replies are cached in sticker_banks/.cache so an
interrupted run resumes instead of starting over. Edit THEMES / prompts to taste.

Structure
  area      broad group           "kitchen appliance", "greek mythological creature", "terrier"
  specific  a member of the area  "refrigerator", "centaur", "yorkshire terrier"
  verbs     things an area member could be doing, sensibly
  modifiers life-stage / size words ("baby", "giant")
  styles    looks, and painters who died in 1959 or earlier
  colors    named colors with hex codes
"""
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import llm  # noqa: E402

OUT = ROOT / "sticker_banks"
CACHE = OUT / ".cache"
CACHE.mkdir(parents=True, exist_ok=True)
KID = ("Everything must be wholesome and kindergarten-appropriate: cute, friendly, imaginative. "
       "No gore, horror, weapons used to hurt, drugs, or anything scary-looking.")
NO_IP = ("Do not use trademarked or copyrighted names (no Dungeons & Dragons monsters or characters, no Pokemon, no Disney, etc). "
         "Use real-world things, public-domain myth and folklore, and generic fantasy kinds.")
LAST_DEATH_YEAR = 1959
# Names that belong to someone's trademark or copyrighted work. Matched as whole words and dropped from the banks.
import re  # noqa: E402
BANNED = re.compile(r"\b(gandalf|hobbit|hobbits|halfling|halflings|tolkien|fili|kili|thorin|beholder|mind flayer|illithid|owlbear|"
                    r"displacer beast|drow|umber hulk|pokemon|pikachu|disney|mickey|elsa|yoda|jedi|mario|zelda)\b", re.I)

# (theme key, what groups to list, target count)
THEMES = [
    # objects and things
    ("kitchen", "things found in or used in a kitchen: appliances, cookware, utensils, tableware", 28),
    ("furniture", "furniture, home furnishings and household fixtures", 24),
    ("tools", "hand tools, garden tools, workshop and building tools and equipment", 26),
    ("clothing", "clothing, hats, shoes, bags and accessories", 26),
    ("school", "school, office, art and craft supplies", 22),
    ("music", "musical instrument families and music-making things", 18),
    ("sports", "sports, games and playground equipment", 24),
    ("toys", "toys, games and playthings (non-electronic and electronic)", 26),
    ("vehicles", "vehicles and ways to travel, on land, water, air and rails", 28),
    ("buildings", "buildings, structures and places in towns and countryside", 26),
    ("foods", "kinds of foods and treats: baked goods, fruits, vegetables, sweets, dishes, drinks, snacks", 46),
    # nature
    ("trees", "kinds of trees (by genus or common group)", 30),
    ("flowers", "flowers, garden plants, herbs, crops and vines", 30),
    ("small_plants", "mushrooms and fungi, mosses, ferns, cacti, succulents, seaweeds and grasses", 26),
    ("landforms", "landforms and landscapes of land, mountains, deserts, caves, coasts and forests", 26),
    ("weather", "clouds, weather and sky phenomena", 24),
    ("water", "bodies and features of water: oceans, rivers, lakes, waves, ice", 20),
    ("rocks", "rocks, gemstones, minerals, crystals and fossils", 22),
    # animals
    ("dogs_cats", "groups of domestic dog breeds and groups of domestic cat breeds", 22),
    ("farm", "farm and domesticated animals", 20),
    ("wild_mammals", "wild mammal groups of forests, grasslands, mountains and jungles (cute and charismatic)", 36),
    ("small_mammals", "rodents, rabbits, bats, small and burrowing mammals", 18),
    ("marine_mammals", "mammals that live in the ocean (kinds of whales, dolphins, seals, sea lions, manatees, otters)", 10),
    ("birds", "groups of birds: songbirds, raptors, waterfowl, seabirds, parrots, flightless birds, etc", 44),
    ("fish", "freshwater and saltwater fish groups", 26),
    ("sea_life", "sea invertebrates and shore life: crabs, shells, jellyfish, corals, starfish and so on", 22),
    ("reptiles", "reptile groups: lizards, turtles, snakes, crocodilians", 20),
    ("amphibians", "frogs, toads, salamanders and other amphibians", 12),
    ("insects", "insect groups: beetles, butterflies, bees, flies, dragonflies, ants, grasshoppers and more", 48),
    ("spiders_crawlers", "spiders, scorpions, snails, slugs, worms and other small crawling creatures", 16),
    ("prehistoric", "dinosaurs and other prehistoric animals and plants", 22),
    # myth and fantasy
    ("greek_creatures", "creatures and beings from Greek mythology (as groups, like nymph, satyr)", 20),
    ("greek_gods", "gods, titans, heroes, muses and other figures of Greek mythology, and their sacred symbols and places", 22),
    ("world_myth", "mythological and folklore beings of Norse, Egyptian, Celtic, Slavic, Japanese, Chinese, Indian, African, Middle Eastern and Indigenous American traditions", 40),
    ("fairy_tale", "fairy-tale and folklore characters (fairy, elf, gnome, witch, troll...)", 24),
    ("dragons", "dragon-like and serpent-like creatures of myth, folklore and fantasy, as groups", 14),
    ("fantasy_roles", "fantasy adventurer roles, professions and characters in generic terms (wizard, knight, bard, alchemist...)", 20),
    ("fantasy_gear", "fantasy adventuring gear, potions, scrolls, magic items and tools in generic terms (lantern, grappling hook, spellbook, potion...)", 28),
    ("fantasy_places", "fantasy places and structures: castles, dungeons, towers, enchanted forests, ruins", 16),
    # space
    ("space", "planets, moons, stars, constellations, spacecraft and space things", 28),
]


def cached(name, fn):
    path = CACHE / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    for attempt in range(4):
        try:
            data = fn()
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        except Exception as exc:  # noqa: BLE001
            print(f"  retry {name} ({attempt + 1}): {str(exc)[:120]}", flush=True)
    raise RuntimeError(f"gave up on {name}")


def ask(prompt):
    text = llm.chat([{"role": "user", "content": prompt + "\nReply with ONLY a JSON object, no commentary."}], timeout=300)
    bare = text.strip().strip("`").removeprefix("json").strip()
    if bare.startswith("["):                      # a bare array, not an object
        try:
            return {"items": json.loads(bare)}
        except json.JSONDecodeError:
            pass
    try:
        return llm.extract_json(text)
    except ValueError:
        a, b = text.find("["), text.rfind("]")      # a bare array is fine too
        if a != -1 and b > a:
            return {"items": json.loads(text[a:b + 1])}
        print("  unparseable reply, first 200 chars:", text[:200].replace("\n", " "), flush=True)
        raise


def norm(s):
    return " ".join(str(s).strip().lower().split())


# ---- areas ----------------------------------------------------------------

def theme_areas(key, what, target):
    have, batch = [], 0
    while len(have) < target and batch < 6:
        want = min(40, target - len(have) + 4)
        avoid = f"\nDo NOT repeat any of these already chosen: {', '.join(have)}." if have else ""
        data = None
        for size in (want, 14):          # empty replies happen on big asks: retry smaller
            try:
                data = cached(f"areas_{key}_{batch}" + ("" if size == want else "_small"), lambda: ask(
                    f"List {size} different GROUP names (categories) of: {what}.\n"
                    "Each must be a group broad enough to contain at least 10 distinct specific members, "
                    "but NOT an individual thing. Good: 'kitchen appliance', 'greek mythological creature', 'terrier', 'cumulus-type cloud', "
                    "'oak tree', 'beetle', 'woodwind instrument', 'wading bird'. Bad (too specific): 'refrigerator', 'centaur', 'yorkshire terrier'. "
                    "Singular, lowercase, 1-4 words. Wide variety across the whole subject. "
                    f"{KID} {NO_IP}{avoid}\nFormat: {{\"items\": [\"...\", ...]}}"))
                break
            except RuntimeError:
                continue
        if data is None:
            print(f"  SKIPPED a batch of {key}", flush=True)
            break
        for x in data.get("items", []):
            x = norm(x)
            if x and x not in have:
                have.append(x)
        batch += 1
    print(f"areas {key}: {len(have)}", flush=True)
    return have


# ---- specifics and verbs ----------------------------------------------------

def request_details(areas):
    data = ask(
        "For each GROUP below give:\n"
        " - \"specifics\": 12 different specific members of that group (e.g. 'kitchen appliance' -> refrigerator, toaster, blender, stand mixer; "
        "'greek mythological creature' -> centaur, satyr, harpy, cyclops; 'terrier' -> yorkshire terrier, jack russell terrier; "
        "'oak tree' -> post oak, live oak, white oak). Use real species, breeds or varieties for real things, and classic named "
        "myth/folklore beings for myth. Lowercase, singular, 1-4 words, no adjectives like 'happy' or 'flying'. "
        "Each must be easy to draw as a single sticker.\n"
        " - \"verbs\": 6 fun things a member of this group could be doing, as short '-ing' phrases that make sense for it "
        "(rabbit-like animals: 'hopping through clover'; appliances: 'wearing a scarf'; clouds: 'drifting over a hill'). Cute, wholesome, varied.\n"
        f"{KID} {NO_IP}\nGroups: {json.dumps(areas)}\n"
        "Format: {\"results\": {\"<group exactly as given>\": {\"specifics\": [...12], \"verbs\": [...6]}, ...}}")
    res = data.get("results")
    if not isinstance(res, dict):
        raise ValueError("no results object")
    norm_keys = {norm(k): v for k, v in res.items()}
    covered = {a: norm_keys[a] for a in areas if a in norm_keys and len(norm_keys[a].get("specifics", [])) >= 6}
    if len(covered) < len(areas) * 0.8:
        raise ValueError("reply did not cover the groups")
    return {"results": covered}


def solve(areas):
    """Details for a list of areas. On repeated failure, retry in smaller groups, then one at a time; drop what never works."""
    key = hashlib.md5(json.dumps(areas).encode()).hexdigest()[:10]   # content-keyed: adding areas never invalidates the rest
    try:
        return cached(f"details_{key}", lambda: request_details(areas)).get("results", {})
    except RuntimeError:
        if len(areas) == 1:
            print(f"  DROPPED area with no details: {areas[0]}", flush=True)
            return {}
        step = 5 if len(areas) > 5 else 1
        merged = {}
        for j in range(0, len(areas), step):
            merged.update(solve(areas[j:j + step]))
        return merged


def details(chunk_id, areas):
    return solve(areas)


# ---- styles, modifiers, colors ---------------------------------------------

LOOKS = [
    ("looks_a", "art mediums, drawing styles and visual looks for a sticker (like realistic, cartoony, watercolor, crayon drawing, pixel art, paper cutout, claymation, "
                "woodblock print, stained glass, chalk pastel, neon sign, blueprint, storybook illustration, vaporwave, art nouveau, ukiyo-e, low-poly, retro 1980s)"),
    ("looks_b", "handmade craft and material looks (like origami, cross-stitch embroidery, knitted wool, LEGO bricks, salt dough, mosaic tiles, sand art, "
                "cardboard craft, gingerbread, balloon art, felt, paper quilling)"),
]


def style_list(key, what, n):
    items = []
    for batch in range(3):
        if len(items) >= n:
            break
        avoid = f" Do NOT repeat: {', '.join(items)}." if items else ""
        try:
            data = cached(f"styles_{key}_{batch}", lambda: ask(
                f"List {min(70, n - len(items) + 8)} different {what}. Lowercase except proper names. {KID}{avoid}\n"
                "Format: {\"items\": [\"first\", \"second\", ...]}"))
        except RuntimeError:
            continue
        for x in data.get("items", []):
            x = " ".join(str(x).split())
            if x and x.lower() not in [i.lower() for i in items]:
                items.append(x)
    print(f"styles {key}: {len(items)}", flush=True)
    return items


def painters():
    out = {}
    regions = ["Europe, 1400s to 1800s (old masters, romantic and realist painters)",
               "Europe and Russia, late 1800s to 1950s (impressionists, post-impressionists, modernists, art nouveau)",
               "Japan, China, Korea, India, Persia and the Middle East",
               "Africa, the Americas and Oceania, including folk and naive artists",
               "illustrators of children's books, fairy tales, posters and comics"]
    for batch, region in enumerate(regions):
        data = None
        for size in (40, 20):             # empty replies happen on big asks: retry smaller
            try:
                data = cached(f"painters2_{batch}" + ("" if size == 40 else "_small"), lambda: ask(
                    f"List {size} famous painters and illustrators from {region} who DIED IN {LAST_DEATH_YEAR} OR EARLIER, "
                    "with the year each died (be accurate; skip anyone you are unsure about). Wholesome work only. "
                    "Reply with ONLY JSON: {\"items\": [{\"name\": \"Vincent van Gogh\", \"died\": 1890}]}"))
                break
            except RuntimeError:
                continue
        if data is None:
            continue
        for a in data.get("items", []):
            try:
                name, died = " ".join(str(a["name"]).split()), int(a["died"])
            except (KeyError, ValueError, TypeError):
                continue
            if died <= LAST_DEATH_YEAR and name.lower() not in {k.lower() for k in out}:
                out[name] = died
    print(f"painters (died <= {LAST_DEATH_YEAR}): {len(out)}", flush=True)
    return out


def modifiers():
    data = cached("modifiers", lambda: ask(
        "List 60 single-word or two-word modifiers describing life stage, age or size that could be put in front of almost any creature or object "
        "to make it cuter or funnier (like baby, tiny, giant, elder, toddler, miniature, fluffy-sized, oversized, juvenile, wee, jumbo). "
        f"Wholesome. Lowercase.\nFormat: {{\"items\": [\"...\"]}}"))
    seen = []
    for x in data["items"]:
        x = norm(x)
        if x and x not in seen:
            seen.append(x)
    print(f"modifiers: {len(seen)}", flush=True)
    return seen


def colors():
    old = OUT / "colors.json"
    if old.exists():
        return json.loads(old.read_text(encoding="utf-8"))
    out = []
    for batch, family in enumerate(["reds, oranges, yellows and pinks", "greens, blues, teals and purples",
                                    "neutrals, browns, metallics, pastels and unusual or whimsical colors"]):
        data = cached(f"colors_{batch}", lambda: ask(
            f"List 70 distinct, evocative color names from {family}, each with a hex code (like 'sunset coral' #FF7F6E). "
            "Fun, cute, varied. Format: {\"items\": [{\"name\": \"...\", \"hex\": \"#RRGGBB\"}, ...]}"))
        for c in data.get("items", []):
            hexv, name = str(c.get("hex", "")).strip(), norm(c.get("name", ""))
            if name and len(hexv) == 7 and hexv.startswith("#") and not any(o["name"] == name for o in out):
                out.append({"name": name, "hex": hexv.upper()})
    return out


def main():
    print("AI:", llm.describe(), flush=True)
    with ThreadPoolExecutor(6) as pool:
        af = {k: pool.submit(theme_areas, k, w, t) for k, w, t in THEMES}
        lf = {k: pool.submit(style_list, k, w, 80) for k, w in LOOKS}
        pf, mf, cf = pool.submit(painters), pool.submit(modifiers), pool.submit(colors)
        by_theme = {k: f.result() for k, f in af.items()}
        looks_raw = [x for f in lf.values() for x in f.result()]
        painter_bank, modifier_bank, color_bank = pf.result(), mf.result(), cf.result()

    looks, seen_l = [], set()
    for x in looks_raw:
        if x.lower() not in seen_l:
            seen_l.add(x.lower()); looks.append(x)
    areas, seen = [], set()
    for k in [t for t in by_theme if t != "marine_mammals"] + ["marine_mammals"]:   # last, so earlier cached chunks stay valid
        for n in by_theme[k]:
            if n not in seen and not BANNED.search(n):
                seen.add(n); areas.append({"area": n, "theme": k})
    print("total areas:", len(areas), flush=True)

    chunks = [[a["area"] for a in areas[i:i + 15]] for i in range(0, len(areas), 15)]
    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(lambda ic: details(ic[0], ic[1]), enumerate(chunks)))
    detail = {}
    for r in results:
        for k, v in r.items():
            sp, seen_s = [], set()
            for s in v.get("specifics", []):
                s = norm(s)
                if s and s not in seen_s and not BANNED.search(s):
                    seen_s.add(s); sp.append(s)
            detail[norm(k)] = {"specifics": sp, "verbs": [" ".join(str(s).split()).lower() for s in v.get("verbs", [])]}
    for a in areas:
        a.update(detail.get(a["area"], {"specifics": [], "verbs": []}))
    thin = [a["area"] for a in areas if len(a["specifics"]) < 6 or len(a["verbs"]) < 3]
    print("areas with thin details:", len(thin), thin[:10], flush=True)
    total_sp = sum(len(a["specifics"]) for a in areas)

    bank = {"areas": areas, "modifiers": modifier_bank, "looks": looks,
            "painters": [{"name": n, "died": y} for n, y in sorted(painter_bank.items(), key=lambda kv: kv[1])], "colors": color_bank}
    (OUT / "bank.json").write_text(json.dumps(bank, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "colors.json").write_text(json.dumps(color_bank, indent=1, ensure_ascii=False), encoding="utf-8")

    lines = ["# Sticker banks: review copy\n",
             f"{len(areas)} areas · {total_sp} specifics · {len(modifier_bank)} modifiers · {len(looks)} looks · "
             f"{len(painter_bank)} painters · {len(color_bank)} colors\n"]
    for k, _, _ in THEMES:
        lines.append(f"\n## {k}  ({len(by_theme[k])})\n")
        for a in areas:
            if a["theme"] == k:
                lines.append(f"- **{a['area']}**: {', '.join(a['specifics'])}  |  verbs: {'; '.join(a['verbs'])}")
    lines.append(f"\n## modifiers ({len(modifier_bank)})\n" + "; ".join(modifier_bank))
    lines.append(f"\n## looks ({len(looks)})\n" + "; ".join(looks))
    lines.append(f"\n## painters, died {LAST_DEATH_YEAR} or earlier ({len(painter_bank)})\n" + "; ".join(f"{n} ({y})" for n, y in painter_bank.items()))
    lines.append(f"\n## colors ({len(color_bank)})\n" + "; ".join(f"{c['name']} {c['hex']}" for c in color_bank))
    (OUT / "REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    print("done", flush=True)


if __name__ == "__main__":
    main()
