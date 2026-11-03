"""Ask the configured LLM for the emoji that best looks like each noun in the sticker bank.

Run (needs an AI configured in .env):   python tools/map_emoji.py
Writes sticker_banks/emoji.json:  {"areas": {area: emoji}, "specifics": {area: {specific: emoji}}}
Offline stickers are drawn from these, so the sticker is shaped like the thing.
Replies are cached in sticker_banks/.cache so an interrupted run resumes.
"""
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import llm  # noqa: E402

OUT = ROOT / "sticker_banks"
CACHE = OUT / ".cache"
CACHE.mkdir(parents=True, exist_ok=True)
LETTERS = re.compile(r"[A-Za-z0-9 ,.\-_'\"()\[\]{}:;]")


def is_emoji(x):
    return isinstance(x, str) and 0 < len(x) <= 12 and not LETTERS.search(x) and any(ord(c) > 0x2000 for c in x)


PROMPT = ("For each group below, pick the SINGLE emoji that looks most like it, then one emoji for each of its members. "
          "The emoji will be shown huge as a sticker, so it should look like the thing itself. "
          "Choose the most specific emoji that exists (monarch butterfly -> a butterfly, yorkshire terrier -> a dog, stand mixer -> a cooking/kitchen emoji, "
          "cumulonimbus cloud -> a cloud, griffin -> an eagle or a lion if nothing closer, dragon -> a dragon). "
          "If nothing matches well, choose the closest visual stand-in, never a blank. Different members may share an emoji if they truly look alike, "
          "but use variety when the emoji set offers it. One emoji character each (a ZWJ sequence counts as one).\n")


def ask(groups):
    """groups: list of (area, [specifics]). Returns {area: (emoji, [emoji...])} for groups that parsed."""
    spec = [{"group": a, "members": s} for a, s in groups]
    prompt = (PROMPT + f"Groups: {json.dumps(spec, ensure_ascii=False)}\n"
              "Format: {\"results\": [{\"group\": \"<name>\", \"emoji\": \"<emoji>\", \"members\": [\"<emoji per member, same order>\"]}]}\n"
              "Reply with ONLY a JSON object, no commentary.")
    key = hashlib.md5(prompt.encode()).hexdigest()[:12]
    path = CACHE / f"emoji_{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    for attempt in range(3):
        try:
            data = llm.extract_json(llm.chat([{"role": "user", "content": prompt}], timeout=300))
            res = {}
            for item in data.get("results", []):
                g, e, m = item.get("group"), item.get("emoji"), item.get("members")
                src = dict(groups).get(g)
                if src is None or not is_emoji(e) or not isinstance(m, list):
                    continue
                m = [x if is_emoji(x) else None for x in m[:len(src)]] + [None] * max(0, len(src) - len(m))
                res[g] = [e, m]
            if len(res) >= len(groups) * 0.7:
                path.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
                return res
            raise ValueError(f"only {len(res)}/{len(groups)} groups usable")
        except Exception as exc:  # noqa: BLE001
            print(f"  retry ({attempt + 1}): {str(exc)[:100]}", flush=True)
    return {}


def solve(groups):
    res = ask(groups)
    missing = [g for g in groups if g[0] not in res]
    if missing and len(groups) > 1:
        half = len(missing) // 2 or 1
        res.update(solve(missing[:half]))
        if missing[half:]:
            res.update(solve(missing[half:]))
    return res


def main():
    bank = json.loads((OUT / "bank.json").read_text(encoding="utf-8"))
    areas = [(a["area"], a["specifics"]) for a in bank["areas"] if len(a.get("specifics", [])) >= 3]
    chunks = [areas[i:i + 6] for i in range(0, len(areas), 6)]
    print("areas:", len(areas), "calls:", len(chunks), flush=True)
    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(solve, chunks))
    out = {"areas": {}, "specifics": {}}
    n = 0
    for r in results:
        for g, (e, members) in r.items():
            out["areas"][g] = e
            sp = dict(areas)[g]
            out["specifics"][g] = {s: m for s, m in zip(sp, members) if m}
            n += len(out["specifics"][g])
    total = sum(len(s) for _, s in areas)
    print(f"areas mapped: {len(out['areas'])}/{len(areas)}   specifics mapped: {n}/{total}", flush=True)
    (OUT / "emoji.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print("done", flush=True)


if __name__ == "__main__":
    main()
