"""Ask the configured LLM how familiar/ordinary each noun in the sticker bank is.

Run (needs an AI configured in .env):   python tools/rate_banks.py
Writes sticker_banks/ratings.json:  {"areas": {area: 1-5}, "specifics": {area: {specific: 1-5}}}
5 = everyone knows it (dog, apple), 1 = obscure, weird or outlandish.
Replies are cached in sticker_banks/.cache so an interrupted run resumes.
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

SCALE = ("Rate each item from 1 to 5 for how familiar and ordinary it is to a typical child or ordinary person: "
         "5 = everyone knows it and it is everyday (dog, apple, spoon, rainbow), 4 = very well known, 3 = known to most but less ordinary, "
         "2 = specialised, unusual or only known to enthusiasts, 1 = obscure, strange or outlandish (rare breeds, deep-lore myth figures, exotic oddities). "
         "Judge each item on its own; do not give everything the same score.")


def ask_ratings(prompt, n):
    for attempt in range(4):
        key = hashlib.md5(prompt.encode()).hexdigest()[:12]
        path = CACHE / f"rate_{key}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        try:
            text = llm.chat([{"role": "user", "content": prompt + "\nReply with ONLY a JSON object, no commentary."}], timeout=300)
            data = llm.extract_json(text)
            r = data.get("ratings")
            if isinstance(r, list) and len(r) == n and all(isinstance(x, (int, float)) and 1 <= x <= 5 for x in r):
                path.write_text(json.dumps(r), encoding="utf-8")
                return r
            raise ValueError(f"expected {n} ratings, got {str(r)[:60]}")
        except Exception as exc:  # noqa: BLE001
            print(f"  retry ({attempt + 1}): {str(exc)[:100]}", flush=True)
    return None


def rate_list(items, context=""):
    """Rate items in order; on failure split in half; give up on a single item (None = unknown)."""
    if not items:
        return []
    prompt = (f"{SCALE}\n{context}Items (rate in this exact order): {json.dumps(items)}\n"
              f"Format: {{\"ratings\": [<one integer 1-5 per item, same order, exactly {len(items)} numbers>]}}")
    r = ask_ratings(prompt, len(items))
    if r is not None:
        return r
    if len(items) == 1:
        return [None]
    mid = len(items) // 2
    return rate_list(items[:mid], context) + rate_list(items[mid:], context)


def main():
    bank = json.loads((OUT / "bank.json").read_text(encoding="utf-8"))
    areas = [a for a in bank["areas"] if len(a.get("specifics", [])) >= 3]
    print("areas:", len(areas), flush=True)

    # 1) how familiar is each area (as a category)
    names = [a["area"] for a in areas]
    chunks = [names[i:i + 40] for i in range(0, len(names), 40)]
    ctx = "These are categories (groups of things), such as 'kitchen appliance', 'songbird' or 'norse giant'. Rate the category itself.\n"
    with ThreadPoolExecutor(6) as pool:
        res = list(pool.map(lambda c: rate_list(c, ctx), chunks))
    area_rate = {}
    for c, r in zip(chunks, res):
        for n, x in zip(c, r):
            area_rate[n] = x
    print("areas rated:", sum(v is not None for v in area_rate.values()), flush=True)

    # 2) how familiar is each specific item, rated within its area so the scale stays comparable
    def one(a):
        sp = a["specifics"]
        return a["area"], sp, rate_list(sp, f"These are all kinds of '{a['area']}'. Rate each kind.\n")
    spec_rate = {}
    with ThreadPoolExecutor(6) as pool:
        for area, sp, r in pool.map(one, areas):
            spec_rate[area] = {s: x for s, x in zip(sp, r)}
    n_ok = sum(v is not None for d in spec_rate.values() for v in d.values())
    print("specifics rated:", n_ok, flush=True)
    (OUT / "ratings.json").write_text(json.dumps({"areas": area_rate, "specifics": spec_rate}, ensure_ascii=False), encoding="utf-8")
    print("done", flush=True)


if __name__ == "__main__":
    main()
