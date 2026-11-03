"""Write sample stickers to an HTML page so you can see every rare quality.

    python tools/sticker_preview.py [out.html]
"""
import base64
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import stickerbank  # noqa: E402

out = Path(sys.argv[1] if len(sys.argv) > 1 else "sticker_preview.html")
cells = []
rng = random.Random(7)
base = stickerbank.roll(rng=rng)
cases = [("common", {"puffy": False, "holographic": False, "damage": 0}),
         ("puffy", {"puffy": True, "holographic": False, "damage": 0}),
         ("holographic", {"puffy": False, "holographic": True, "damage": 0}),
         ("scuffed", {"puffy": False, "holographic": False, "damage": 1}),
         ("ripped", {"puffy": False, "holographic": False, "damage": 2}),
         ("shredded", {"puffy": False, "holographic": False, "damage": 3}),
         ("torn off", {"puffy": False, "holographic": False, "damage": 4}),
         ("puffy + ripped", {"puffy": True, "holographic": False, "damage": 2})]
for label, q in cases:
    r = dict(base, quality=q)
    cells.append(f'<div style="text-align:center;font:13px sans-serif;background:#f3f3f8;padding:8px;border-radius:12px">'
                 f'<img width="220" src="data:image/svg+xml;base64,{base64.b64encode(stickerbank.render(r).encode()).decode()}"><b>{label}</b><br>{stickerbank.full_name(r)}</div>')
out.write_text('<body style="background:#dde;display:flex;flex-wrap:wrap;gap:12px;padding:12px">' + "".join(cells) + "</body>", encoding="utf-8")
print("wrote", out.resolve())
