"""AI image stickers ("Method 3"): three image-model steps, then a transparent SVG wrapper.

  1. draw the recipe's subject as a picture
  2. turn that picture into a die-cut sticker (art look, colour, painter, verb, white border) on flat magenta
  3. redraw that sticker as a glossy emoji, still with the white border, on flat magenta
Then the magenta is keyed out to real transparency and the raster is wrapped as <image href="data:..."> inside a
200x200 SVG that only this code writes. That SVG goes through stickerbank.render() like any other art, so puffy,
damage and the holographic mask keep working.

Needs a TAMU AI gateway (the only provider here that serves image models) and Pillow. If either is missing, or any
step fails, make() returns None and the app falls back to the older AI-SVG / emoji sticker.
Uses only the standard library plus Pillow. Set JOT_IMAGE_STICKERS=off in .env to disable, JOT_IMAGE_MODEL to change the model.
"""

import base64
import io
import json
import os
import re
import urllib.error
import urllib.request

import llm

DEFAULT_MODEL = "protected.gemini-3.1-flash-lite-image"
_IMG = re.compile(r"data:image/\w+;base64,([A-Za-z0-9+/=]+)")


def available():
    """True when image stickers can be attempted."""
    if (os.environ.get("JOT_IMAGE_STICKERS") or "").strip().lower() in ("off", "0", "no", "false"):
        return False
    try:
        import PIL  # noqa: F401
        _, _, _, provider = llm.settings()
    except Exception:  # noqa: BLE001
        return False
    return provider == "tamu"


def _model():
    return (os.environ.get("JOT_IMAGE_MODEL") or "").strip() or DEFAULT_MODEL


def _image_call(content, timeout=150):
    """One image-model call. The gateway answers (as an SSE stream, whatever `stream` says) with a message whose
    content is '![image](data:image/png;base64,...)'. Returns the image bytes."""
    base, _, key, _ = llm.settings()
    body = json.dumps({"model": _model(), "messages": [{"role": "user", "content": content}]}).encode()
    last = None
    for _attempt in range(2):
        req = urllib.request.Request(base + "/chat/completions", data=body, method="POST", headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {key}", "User-Agent": "jot/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", "replace")
            m = _IMG.search(raw)
            if m:
                return base64.b64decode(m.group(1))
            last = RuntimeError("the image model returned no image")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
    raise last


# ---- prompts, built from a stickerbank recipe ------------------------------------

def _subject(r):
    what = " ".join(x for x in [r.get("modifier"), r["color"]["name"] if r.get("color") else None, r["specific"]] if x)
    return "a " + what + (", " + r["verb"] if r.get("verb") else "")


def draw_prompt(r):
    style = r.get("look") or ""
    if r.get("painter"):
        style += (", " if style else "") + "in the style of " + r["painter"]
    return (f"Draw {_subject(r)}" + (f", {style}" if style else "") +
            ". One single subject, centered, whole body visible, on a plain light background. No text, no frame.")


def sticker_prompt(r):
    bits = [f"Subject: {_subject(r)}."]
    if r.get("look"):
        bits.append(f"Art look: {r['look']}.")
    if r.get("painter"):
        bits.append(f"Painter's style: {r['painter']}.")
    if r.get("color"):
        bits.append(f"Main colour: {r['color']['name']}.")
    if r.get("modifier"):
        bits.append(f"Character: {r['modifier']}.")
    return ("Turn the attached image into a die-cut vinyl sticker. Keep the same subject and drawing. " + " ".join(bits) +
            " Add a thick, even, clean WHITE die-cut sticker border that hugs the outline of the whole subject, with a soft drop shadow. "
            "Remove the original background completely and put the sticker on a FLAT SOLID PURE MAGENTA (#FF00FF) background, "
            "with no gradient, no texture and no scenery. Magenta must appear nowhere on the sticker itself. Square image, sticker centered.")


EMOJI_PROMPT = ("Turn the attached sticker into an emoji. Redraw the same subject as a modern flat-glossy emoji icon "
                "(like Apple or Google emoji): simplified shapes, bold clean smooth shading, big friendly details, no fine texture or brush strokes, "
                "same main colours. Keep the thick white die-cut sticker border around it. "
                "Put it on a FLAT SOLID PURE MAGENTA (#FF00FF) background, no gradient, no scenery, and no magenta on the emoji itself. "
                "Square image, centered, no text.")


# ---- magenta -> transparency -----------------------------------------------------

def _magenta(p):
    r, g, b = p
    return r > 50 and b > 50 and g < 0.8 * min(r, b) and abs(r - b) < 110


def key_out(image_bytes, work=384, out=320):
    """Flood the magenta background from the edges to alpha 0 (including the darker magenta drop shadow), soften the
    edge, crop to the sticker and return WebP bytes with alpha. Returns None if the result looks wrong."""
    from PIL import Image, ImageFilter
    im = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((work, work), Image.LANCZOS)
    w = h = work
    px = list(im.getdata())
    bg = bytearray(w * h)
    stack = [i for i in list(range(w)) + list(range((h - 1) * w, w * h)) + list(range(0, w * h, w)) + list(range(w - 1, w * h, w)) if _magenta(px[i])]
    for i in stack:
        bg[i] = 1
    while stack:
        i = stack.pop()
        x, y = i % w, i // w
        for j in ((i - 1) if x else -1, (i + 1) if x < w - 1 else -1, (i - w) if y else -1, (i + w) if y < h - 1 else -1):
            if j >= 0 and not bg[j] and _magenta(px[j]):
                bg[j] = 1
                stack.append(j)
    cleared = sum(bg) / (w * h)
    if cleared < 0.08 or cleared > 0.9:      # no background found, or it ate the sticker
        return None
    mask = Image.new("L", (w, h))
    mask.putdata([0 if v else 255 for v in bg])
    mask = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.0))
    im.putalpha(mask)
    box = mask.point(lambda v: 255 if v > 8 else 0).getbbox()
    if box:
        l, t, r, b = box
        side = max(r - l, b - t) + 12
        cx, cy = (l + r) // 2, (t + b) // 2
        im = im.crop((cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side))
    im = im.resize((out, out), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=88, method=4)
    return buf.getvalue()


def wrap_svg(webp):
    uri = "data:image/webp;base64," + base64.b64encode(webp).decode()
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">'
            f'<image x="6" y="6" width="188" height="188" href="{uri}"/></svg>')


def make(recipe):
    """The wrapped SVG for a recipe, or None on any failure (caller falls back)."""
    try:
        def data_uri(b):
            return "data:image/png;base64," + base64.b64encode(b).decode()

        def edit(prompt, picture):
            return _image_call([{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_uri(picture)}}])

        picture = _image_call(draw_prompt(recipe))
        sticker = edit(sticker_prompt(recipe), picture)
        emoji = edit(EMOJI_PROMPT, sticker)
        webp = key_out(emoji)
        return wrap_svg(webp) if webp else None
    except Exception:  # noqa: BLE001
        return None
