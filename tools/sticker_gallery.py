"""Make a gallery page of fresh stickers: random offline ones, one of each rare effect, and a few AI drawings.

    python tools/sticker_gallery.py [out.html] [--seed N] [--ai 4]
"""
import argparse
import base64
import html
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import llm  # noqa: E402
import prompts  # noqa: E402
import stickerbank  # noqa: E402
import stickers  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("out", nargs="?", default="sticker_gallery.html")
ap.add_argument("--seed", type=int, default=int(time.time()) % 100000)
ap.add_argument("--random", type=int, default=24)
ap.add_argument("--ai", type=int, default=4)
args = ap.parse_args()
rng = random.Random(args.seed)


def data_uri(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def card(r, svg, note=""):
    q = r["quality"]
    tier = config.TIERS[r.get("tier", 0)]
    holo = f'<div class="holo" style="--m:url({data_uri(svg)})"></div>' if q.get("holographic") else ""
    badge = f'<span class="b t{r["tier"]}">{tier}</span>' if r.get("tier") else ""
    return (f'<div class="c t{r["tier"]}"><div class="stk{" ho" if holo else ""}"><img src="{data_uri(svg)}">{holo}</div>{badge}'
            f'<div class="n">{html.escape(stickerbank.full_name(r))}</div>'
            f'<div class="s">{html.escape(note)}score {r["bits"]}</div></div>')


sections = []

# 1) random offline stickers, exactly as the app would roll them
cells = []
for _ in range(args.random):
    r = stickerbank.roll(rng=rng)
    cells.append(card(r, stickerbank.render(r)))
sections.append(("Random rolls (offline emoji stickers)", cells))

# 2) one of each rare effect on a fresh sticker
cells = []
cases = [("puffy", dict(puffy=True, holographic=False, damage=0)), ("holographic", dict(puffy=False, holographic=True, damage=0)),
         ("puffy + holographic", dict(puffy=True, holographic=True, damage=0)), ("scuffed", dict(puffy=False, holographic=False, damage=1)),
         ("ripped", dict(puffy=False, holographic=False, damage=2)), ("shredded", dict(puffy=False, holographic=False, damage=3)),
         ("torn off (1 in 100,000)", dict(puffy=False, holographic=False, damage=4))]
for label, q in cases:
    r = stickerbank.roll(rng=rng)
    r["quality"] = q
    r["tier"] = max(r["tier"], 3 if label.startswith("torn") else 2)
    cells.append(card(r, stickerbank.render(r), label + " · "))
sections.append(("Rare effects", cells))


# 3) AI drawings (needs an AI in .env)
def draw(r):
    for _ in range(2):
        try:
            d = llm.chat_json([{"role": "system", "content": prompts.STICKER_SYSTEM},
                               {"role": "user", "content": stickerbank.art_prompt(r)}], timeout=150)
            art = stickers.clean_svg(str(d.get("svg") or ""))
            if art:
                return art
        except Exception:  # noqa: BLE001
            pass
    return None


if args.ai and llm.describe()["configured"]:
    recipes = [stickerbank.roll(rng=rng) for _ in range(args.ai)]
    with ThreadPoolExecutor(4) as pool:
        arts = list(pool.map(draw, recipes))
    cells = [card(r, stickerbank.render(r, a), "AI drawing · " if a else "AI failed, emoji fallback · ") for r, a in zip(recipes, arts)]
    sections.append(("Drawn by the AI", cells))

CSS = """body{font:14px system-ui,sans-serif;background:#eef0f8;margin:0;padding:18px 22px;color:#222}h1{margin:0 0 4px}h2{margin:26px 0 10px}
.g{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:14px}.c{background:#fff;border:1px solid #d6d9e8;border-radius:14px;padding:10px;text-align:center}
.c.t1{border-color:#3fb26b}.c.t2{border-color:#1e88ff;box-shadow:0 0 0 1px #1e88ff}.c.t3{border-color:#e0a526;box-shadow:0 0 12px #e0a52666}.c.t4{border-color:#c04cff;box-shadow:0 0 16px #c04cff88}
.stk{position:relative;aspect-ratio:1;--mx:50%;--my:50%;isolation:isolate}.stk img{width:100%;height:100%;display:block;filter:drop-shadow(0 3px 4px #0004)}
.holo{position:absolute;inset:0;pointer-events:none;mix-blend-mode:color;opacity:.8;-webkit-mask-image:var(--m);mask-image:var(--m);-webkit-mask-size:contain;mask-size:contain;-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;-webkit-mask-position:center;mask-position:center;
background:linear-gradient(115deg,#ff5fa2 0%,#ffb347 16%,#fff36b 32%,#5cf29b 48%,#4cd6ff 64%,#8c7bff 80%,#ff5fa2 100%);background-size:260% 260%;background-position:var(--mx) var(--my);animation:hs 5s ease-in-out infinite alternate}
.stk.tilting .holo{animation:none}@keyframes hs{from{background-position:0% 30%}to{background-position:100% 70%}}
.b{display:inline-block;font-size:10px;font-weight:800;letter-spacing:.06em;padding:1px 8px;border-radius:99px;color:#fff;margin-top:4px;background:#3fb26b}.b.t2{background:#1e88ff}.b.t3{background:#d89a1e}.b.t4{background:linear-gradient(90deg,#c04cff,#ff4c9a)}
.n{font-size:12px;margin-top:6px}.s{font-size:11px;color:#777;margin-top:2px}"""
JS = ("document.querySelectorAll('.stk.ho').forEach(f=>{f.addEventListener('pointermove',e=>{const r=f.getBoundingClientRect();f.classList.add('tilting');"
      "f.style.setProperty('--mx',((e.clientX-r.left)/r.width*100)+'%');f.style.setProperty('--my',((e.clientY-r.top)/r.height*100)+'%')});"
      "f.addEventListener('pointerleave',()=>f.classList.remove('tilting'))})")
body = "".join(f"<h2>{html.escape(t)}</h2><div class='g'>{''.join(c)}</div>" for t, c in sections)
Path(args.out).write_text(f"<!doctype html><meta charset=utf-8><title>Jot sticker gallery</title><style>{CSS}</style>"
                          f"<h1>Jot sticker gallery</h1><div style='color:#666'>seed {args.seed}. Hover a holographic one.</div>{body}<script>{JS}</script>", encoding="utf-8")
print("wrote", Path(args.out).resolve(), "seed", args.seed)
