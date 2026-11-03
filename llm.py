"""Optional LLM access for Jot. Jot works fully without it.

Any OpenAI-compatible chat endpoint works (TAMU AI, OpenAI, OpenRouter,
Ollama, ...). Uses only the standard library. Configure in `.env`
(see .env.example). With no configuration Jot simply runs in offline mode.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import config

PROVIDERS = {
    "tamu": ("https://chat-api.tamu.ai/openai", "protected.Claude Sonnet 4.6", "TAMU_AI_API_KEY"),
    "openai": ("https://api.openai.com/v1", "gpt-5.4-mini", "OPENAI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", None, "OPENROUTER_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None, None),
    "custom": ("", None, "JOT_API_KEY"),
}


class LLMUnavailable(RuntimeError):
    pass


def _load_env():
    path = config.APP_DIR / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name, value = name.strip(), value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


def settings():
    """Return (base_url, model, key, provider) or raise LLMUnavailable."""
    _load_env()
    name = (os.environ.get("JOT_PROVIDER") or "").strip().lower()
    if not name or name in ("none", "off", "offline"):
        raise LLMUnavailable("No AI provider configured (offline mode).")
    if name not in PROVIDERS:
        raise LLMUnavailable(f"JOT_PROVIDER '{name}' is not one of: {', '.join(PROVIDERS)}.")
    base, default_model, key_env = PROVIDERS[name]
    base = (os.environ.get("JOT_BASE_URL") or base).rstrip("/")
    model = os.environ.get("JOT_MODEL") or default_model
    if not base:
        raise LLMUnavailable("Set JOT_BASE_URL in .env for the custom provider.")
    if not model:
        raise LLMUnavailable(f"Set JOT_MODEL in .env for provider '{name}'.")
    key = ""
    if key_env:
        key = (os.environ.get(key_env) or "").strip()
        if not key and name == "tamu":
            f = Path.home() / ".config" / "tamu-ai" / "api-key"
            if f.exists():
                key = f.read_text(encoding="utf-8").strip()
        if not key:
            raise LLMUnavailable(f"No API key: set {key_env} in .env.")
    return base, model, key or "not-needed", name


def describe():
    try:
        _, model, _, provider = settings()
        return {"configured": True, "label": f"{provider} / {model}"}
    except LLMUnavailable as exc:
        return {"configured": False, "label": "", "reason": str(exc)}


_THINK = re.compile(r"\A\s*<(think|thinking|reasoning)>.*?</\1>\s*", re.S | re.I)


def chat(messages, timeout=120):
    """One completion. Sends NO sampling params and NO response_format:
    TAMU's Claude models reject the former and silently break on the latter."""
    base, model, key, _ = settings()
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]
    # stream must be sent explicitly or the TAMU gateway streams anyway.
    body = json.dumps({"model": model, "messages": messages, "stream": False}).encode()
    last = None
    for attempt in range(3):
        req = urllib.request.Request(
            base + "/chat/completions", data=body, method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}",
                     "User-Agent": "jot/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            last = LLMUnavailable(f"HTTP {exc.code}: {detail}")
            if exc.code not in (429, 500, 502, 503, 504):
                raise last
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = LLMUnavailable(f"Could not reach the AI service: {exc}")
        else:
            # The gateway can answer HTTP 200 with an error body.
            if data.get("error"):
                raise LLMUnavailable(f"AI service error: {str(data['error'])[:300]}")
            choices = data.get("choices") or []
            if not choices:
                raise LLMUnavailable("The AI service returned no completion.")
            text = (choices[0].get("message") or {}).get("content") or ""
            prev = None
            while text != prev:
                prev, text = text, _THINK.sub("", text, count=1).strip()
            if not text.strip():
                raise LLMUnavailable("The AI service returned an empty reply.")
            return text.strip()
        time.sleep(2 ** attempt)
    raise last


def extract_json(text):
    """Pull a JSON object out of a reply that may be fenced or chatty."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = esc = False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise ValueError("No JSON object found in the reply.")


def chat_json(messages, timeout=120):
    return extract_json(chat(messages, timeout=timeout))
