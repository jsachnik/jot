"""Pack the Noto Emoji artwork the sticker bank uses into one small JSON file (sticker_banks/emoji_art.json.gz).

Noto Emoji (https://github.com/googlefonts/noto-emoji) artwork is Apache-2.0, so it can ship with Jot.
Only needed when rebuilding; the packed file is committed.

    git clone --depth 1 --filter=blob:none --sparse https://github.com/googlefonts/noto-emoji.git
    cd noto-emoji && git sparse-checkout set 2D/svg
    pip install emoji        (only to get the CLDR emoji names, e.g. "cat", "heart on fire")
    python tools/build_emoji_art.py path/to/noto-emoji/2D/svg
"""
import gzip
import json
import re
import sys
from pathlib import Path

import emoji as emoji_pkg

BANKS = Path(__file__).resolve().parent.parent / "sticker_banks"


def key(ch):
    """Noto file key for an emoji string: code points in hex joined by '_', without the variation selector."""
    return "_".join(f"{ord(c):x}" for c in ch if ord(c) != 0xFE0F)


def shrink(svg):
    svg = re.sub(r"<\?xml.*?\?>|<!--.*?-->|<!DOCTYPE.*?>", "", svg, flags=re.S)
    inner = re.search(r"<svg\b[^>]*>(.*)</svg>", svg, re.S).group(1)
    inner = re.sub(r"<(i:\w+)\b[^>]*/>|<(i:\w+)\b.*?</\2>|<foreignObject\b.*?</foreignObject>", "", inner, flags=re.S)   # Illustrator private data
    inner = re.sub(r"\s(?:i|a|x):[\w-]+=\"[^\"]*\"", "", inner)
    inner = re.sub(r"(\d+\.\d)\d+", r"\1", inner)            # 1 decimal is plenty at this size
    inner = re.sub(r"\s+", " ", inner)
    return re.sub(r">\s+<", "><", inner).strip()


def main(src):
    src = Path(src)
    emoji = json.loads((BANKS / "emoji.json").read_text(encoding="utf-8"))
    used = set(emoji["areas"].values())
    for d in emoji["specifics"].values():
        used |= set(d.values())
    art, missing = {}, []
    for ch in sorted(used):
        f = src / f"emoji_u{key(ch)}.svg"
        name = emoji_pkg.demojize(ch if ch.endswith("️") or len(ch) > 1 else ch + "️")
        if f.exists() and name.startswith(":") and name.endswith(":") and name.count(":") == 2:
            art[key(ch)] = {"n": name.strip(":").replace("_", " "), "s": shrink(f.read_text(encoding="utf-8"))}
        else:
            missing.append(ch)
    out = BANKS / "emoji_art.json.gz"
    out.write_bytes(gzip.compress(json.dumps(art, separators=(",", ":")).encode("utf-8"), 9))
    print(f"packed {len(art)} emoji, {out.stat().st_size / 1e6:.1f} MB gzipped; no artwork for {len(missing)}: {' '.join(missing)}")


if __name__ == "__main__":
    main(sys.argv[1])
