"""Thin wrappers around Claude / Gemini (vision + text) and Gemini (image gen).

Text tasks (tagging, pairing) go through `ai_json`:
  - Claude Haiku when ANTHROPIC_API_KEY is set (the Anthropic-track path),
  - else Gemini Flash text when GEMINI_API_KEY is set (free tier works),
  - else mock output. Force one with AI_TEXT_PROVIDER=claude|gemini|mock.
MOCK_AI=1 forces mock everywhere so the app can be built without spending anything.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

# Haiku by default: ~20x cheaper than Sonnet and plenty for tagging/pairing.
# Override per task if quality needs it (e.g. CLAUDE_PAIR_MODEL=claude-sonnet-5-5).
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")
CLAUDE_TAG_MODEL = os.getenv("CLAUDE_TAG_MODEL", CLAUDE_MODEL)
CLAUDE_PAIR_MODEL = os.getenv("CLAUDE_PAIR_MODEL", CLAUDE_MODEL)
# Cheapest image model; switch to gemini-3.1-flash-image if faces/bodies drift in try-on.
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-lite-image")
# gemini-2.5-flash is closed to new Google projects; Google points new users to 3.8 Flash.
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.8-flash")


def text_provider() -> str:
    if os.getenv("MOCK_AI") == "1":
        return "mock"
    forced = os.getenv("AI_TEXT_PROVIDER")
    if forced in {"claude", "gemini", "mock"}:
        return forced
    if os.getenv("ANTHROPIC_API_KEY"):
        return "claude"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    return "mock"


def text_mock() -> bool:
    return text_provider() == "mock"

# USD per million tokens (input, output), from platform.claude.com/docs pricing, Oct 2026.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}
# Hard stop: once estimated Claude spend passes this, calls fail fast and every
# endpoint uses its non-AI fallback instead. Set 0 to disable.
AI_BUDGET_USD = float(os.getenv("AI_BUDGET_USD", "5"))
# Gemini try-ons are the expensive part; cap how many fresh ones we generate.
MAX_TRYONS = int(os.getenv("MAX_TRYONS", "400"))  # see docs/tryon-budget.md


class BudgetExceeded(Exception):
    pass


def usage() -> dict:
    from ..store import store

    return store.get("ai_usage", "total") or {
        "claude_calls": 0, "input_tokens": 0, "output_tokens": 0, "est_usd": 0.0,
        "gemini_images": 0, "by_model": {}}


def _record_claude(model: str, in_tok: int, out_tok: int) -> None:
    from ..store import store

    u = usage()
    pin, pout = PRICES.get(model, PRICES["claude-sonnet-5-5"])  # unknown model: assume pricier
    cost = in_tok / 1e6 * pin + out_tok / 1e6 * pout
    u["claude_calls"] += 1
    u["input_tokens"] += in_tok
    u["output_tokens"] += out_tok
    u["est_usd"] = round(u["est_usd"] + cost, 6)
    m = u["by_model"].setdefault(model, {"calls": 0, "est_usd": 0.0})
    m["calls"] += 1
    m["est_usd"] = round(m["est_usd"] + cost, 6)
    store.put("ai_usage", "total", u)


def _record_gemini_text(in_tok: int, out_tok: int) -> None:
    from ..store import store

    u = usage()
    m = u["by_model"].setdefault(GEMINI_TEXT_MODEL, {"calls": 0, "est_usd": 0.0,
                                                     "input_tokens": 0, "output_tokens": 0})
    m["calls"] += 1
    m["input_tokens"] = m.get("input_tokens", 0) + in_tok
    m["output_tokens"] = m.get("output_tokens", 0) + out_tok
    store.put("ai_usage", "total", u)


def record_gemini_image() -> None:
    from ..store import store

    u = usage()
    u["gemini_images"] += 1
    store.put("ai_usage", "total", u)


def check_budget(kind: str = "claude") -> None:
    u = usage()
    if kind == "claude" and AI_BUDGET_USD and u["est_usd"] >= AI_BUDGET_USD:
        raise BudgetExceeded(f"Claude budget ${AI_BUDGET_USD} reached")
    if kind == "gemini" and MAX_TRYONS and u["gemini_images"] >= MAX_TRYONS:
        raise BudgetExceeded(f"try-on cap {MAX_TRYONS} reached")


def mock_mode(key_env: str) -> bool:
    return os.getenv("MOCK_AI") == "1" or not os.getenv(key_env)


class BadModelOutput(Exception):
    pass


# Determinism: every text call runs at temperature 0 and (where the SDK takes one) a fixed seed, so the same
# prompt + image gives the same JSON. Override with AI_TEMPERATURE / AI_SEED for experiments only.
TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0"))
SEED = int(os.getenv("AI_SEED", "7"))

_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def validate_schema(obj: Any, schema: dict | None, path: str = "$") -> None:
    """Tiny JSON-schema check (type, required, properties, items, enum, anyOf, min/maxItems).
    Raises BadModelOutput naming the first violation; no-op when schema is None."""
    if not schema:
        return
    if "anyOf" in schema:
        errs = []
        for sub in schema["anyOf"]:
            try:
                validate_schema(obj, sub, path)
                return
            except BadModelOutput as e:
                errs.append(str(e))
        raise BadModelOutput(f"{path}: matches no alternative ({'; '.join(errs)})")
    types = schema.get("type")
    if types:
        allowed = [types] if isinstance(types, str) else list(types)
        ok = False
        for t in allowed:
            if t == "number":
                ok = ok or (isinstance(obj, (int, float)) and not isinstance(obj, bool))
            elif t == "integer":
                ok = ok or (isinstance(obj, int) and not isinstance(obj, bool)) or (isinstance(obj, float) and obj.is_integer())
            else:
                ok = ok or isinstance(obj, _TYPES[t])
        if not ok:
            raise BadModelOutput(f"{path}: expected {types}, got {type(obj).__name__}")
    if "enum" in schema and obj not in schema["enum"]:
        raise BadModelOutput(f"{path}: {obj!r} not in {schema['enum']}")
    if isinstance(obj, dict):
        for key in schema.get("required", []):
            if key not in obj:
                raise BadModelOutput(f"{path}: missing {key!r}")
        for key, sub in schema.get("properties", {}).items():
            if key in obj and obj[key] is not None or (key in obj and "null" in (sub.get("type") or [])):
                validate_schema(obj[key], sub, f"{path}.{key}")
    if isinstance(obj, list):
        if "maxItems" in schema and len(obj) > schema["maxItems"]:
            raise BadModelOutput(f"{path}: {len(obj)} items > {schema['maxItems']}")
        if "minItems" in schema and len(obj) < schema["minItems"]:
            raise BadModelOutput(f"{path}: {len(obj)} items < {schema['minItems']}")
        if "items" in schema:
            for i, el in enumerate(obj):
                validate_schema(el, schema["items"], f"{path}[{i}]")


def _checked(obj: Any, prompt: str, schema: dict | None) -> Any:
    """Validate a parsed reply against the prompt's schema (explicit, else looked up by prompt)."""
    from . import prompts

    validate_schema(obj, schema if schema is not None else prompts.schema_for(prompt))
    return obj


def extract_json(text: str) -> Any:
    """Pull the first JSON object/array out of a model reply (handles ```json fences)."""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start = min((i for i in (text.find("{"), text.find("[")) if i != -1), default=-1)
    if start == -1:
        raise BadModelOutput(f"no JSON in reply: {text[:200]}")
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as e:
        raise BadModelOutput(str(e)) from e
    return obj


def claude_json(prompt: str, image_url: str | None = None, max_tokens: int = 1500,
                model: str | None = None, schema: dict | None = None) -> Any:
    """Call Claude and return parsed JSON. Retries once on unparseable output.
    Raises BadModelOutput (incl. when over budget) so callers fall back."""
    from anthropic import Anthropic

    model = model or CLAUDE_MODEL
    try:
        check_budget("claude")
    except BudgetExceeded as e:
        raise BadModelOutput(str(e)) from e
    client = Anthropic()
    content: list[dict] = []
    if image_url:
        content.append({"type": "image", "source": image_source(image_url)})
    content.append({"type": "text", "text": prompt})

    last_err: Exception | None = None
    for _ in range(2):
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": content}],
            # Haiku 5.5 thinks by default; that burned the whole token budget on pairing and cut the
            # JSON off. These are short structured tasks: no thinking = faster, cheaper, complete.
            # temperature is not allowed alongside thinking, so it only goes with thinking off.
            **({} if os.getenv("CLAUDE_THINKING") == "on"
               else {"thinking": {"type": "disabled"}, "temperature": TEMPERATURE}),
        )
        try:
            _record_claude(model, msg.usage.input_tokens, msg.usage.output_tokens)
        except Exception:  # noqa: BLE001 — never let accounting break a request
            pass
        text = "".join(b.text for b in msg.content if b.type == "text")
        try:
            return _checked(extract_json(text), prompt, schema)
        except BadModelOutput as e:
            last_err = e
    raise BadModelOutput(str(last_err))


def gemini_json(prompt: str, image_url: str | None = None, max_tokens: int = 1500,
                schema: dict | None = None) -> Any:
    """Same contract as claude_json, on Gemini Flash text. Retries once on bad JSON."""
    from google import genai
    from google.genai import types

    client = genai.Client()
    parts: list[Any] = []
    if image_url:
        data, mime = fetch_image(image_url)
        parts.append(types.Part.from_bytes(data=data, mime_type=mime))
    parts.append(prompt)
    det = {"temperature": TEMPERATURE, "seed": SEED, "response_mime_type": "application/json"}
    cfg = types.GenerateContentConfig(
        max_output_tokens=max_tokens,
        thinking_config=types.ThinkingConfig(thinking_budget=0),  # no thinking: cheaper, faster, no empty replies
        **det,
    )
    last_err: Exception | None = None
    for _ in range(2):
        try:
            resp = client.models.generate_content(model=GEMINI_TEXT_MODEL, contents=parts, config=cfg)
        except Exception as e:  # noqa: BLE001
            if "thinking" not in str(e).lower():
                raise
            # newer models may not accept thinking_budget=0; retry with defaults
            cfg = types.GenerateContentConfig(max_output_tokens=max_tokens * 4, **det)
            resp = client.models.generate_content(model=GEMINI_TEXT_MODEL, contents=parts, config=cfg)
        try:
            meta = resp.usage_metadata
            _record_gemini_text(meta.prompt_token_count or 0, meta.candidates_token_count or 0)
        except Exception:  # noqa: BLE001
            pass
        try:
            return _checked(extract_json(resp.text or ""), prompt, schema)
        except BadModelOutput as e:
            last_err = e
    raise BadModelOutput(str(last_err))


def ai_json(prompt: str, image_url: str | None = None, max_tokens: int = 1500,
            model: str | None = None, schema: dict | None = None) -> Any:
    """Route a JSON-returning text task to Claude or Gemini (see module doc).
    The reply is validated against `schema` (default: the one `prompts.schema_for(prompt)` finds);
    a reply that doesn't match counts as bad output, so the provider retries once, then callers fall back."""
    if text_provider() == "gemini":
        try:
            return gemini_json(prompt, image_url=image_url, max_tokens=max_tokens, schema=schema)
        except BadModelOutput:
            raise
        except Exception as e:  # noqa: BLE001 — network/quota errors become fallbacks
            raise BadModelOutput(f"gemini: {e}") from e
    try:
        return claude_json(prompt, image_url=image_url, max_tokens=max_tokens, model=model, schema=schema)
    except Exception as e:  # noqa: BLE001 — no credits, auth, network, budget, bad JSON
        claude_err = e
    # Claude failed: try Gemini before giving up, so the app keeps working
    # (e.g. Anthropic account out of credits mid-demo). Logged for /ai/usage.
    _note_fallback(str(claude_err))
    if os.getenv("GEMINI_API_KEY") and os.getenv("AI_TEXT_PROVIDER") != "claude":
        try:
            return gemini_json(prompt, image_url=image_url, max_tokens=max_tokens, schema=schema)
        except Exception as e:  # noqa: BLE001
            raise BadModelOutput(f"claude: {claude_err}; gemini: {e}") from e
    raise BadModelOutput(f"claude: {claude_err}") from claude_err


def _note_fallback(err: str) -> None:
    from ..store import store

    try:
        u = usage()
        u["claude_fallbacks"] = u.get("claude_fallbacks", 0) + 1
        u["last_claude_error"] = err[:200]
        store.put("ai_usage", "total", u)
    except Exception:  # noqa: BLE001
        pass


CLAUDE_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
                     "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"}


def fetch_image(url: str) -> tuple[bytes, str]:
    """Download an image. Local /static URLs are read from disk (works without ngrok)."""
    from ..store import DATA_DIR

    marker = "/static/"
    def safe(rel: str):
        root = DATA_DIR.resolve()
        p = (root / rel).resolve()
        if root not in p.parents:
            raise ValueError("path outside data dir")
        return p

    if url.startswith("file://"):
        if os.getenv("ALLOW_FILE_URLS") != "1":  # set only by local scripts (eval_tagger)
            raise ValueError("file:// URLs not allowed")
        from pathlib import Path
        from urllib.parse import unquote, urlparse

        path = Path(unquote(urlparse(url).path))
        return path.read_bytes(), _guess_mime(path.name)
    if url.startswith(marker):
        path = safe(url[len(marker):])
        return path.read_bytes(), _guess_mime(path.name)
    from ..static_urls import local_static_path

    # our own uploads / try-ons, whatever host the URL names (old tunnel, localhost, current tunnel)
    path = local_static_path(url, DATA_DIR)
    if path is not None:
        return path.read_bytes(), _guess_mime(path.name)

    r = httpx.get(url, timeout=20, follow_redirects=True, headers=_UA)
    r.raise_for_status()
    mime = r.headers.get("content-type", "").split(";")[0] or _guess_mime(url)
    return r.content, mime


def _guess_mime(name: str) -> str:
    n = name.lower().split("?")[0]
    if n.endswith(".png"):
        return "image/png"
    if n.endswith(".webp"):
        return "image/webp"
    if n.endswith(".gif"):
        return "image/gif"
    return "image/jpeg"


def image_source(url: str) -> dict:
    """Send images to Claude as base64: retailer CDNs often block Claude's own fetcher,
    and localhost URLs aren't reachable from the API at all."""
    import base64

    try:
        data, mime = fetch_image(url)
    except Exception:
        return {"type": "url", "url": url}  # last resort: let Claude try
    if mime not in CLAUDE_IMAGE_TYPES:
        mime = "image/jpeg"
    return {"type": "base64", "media_type": mime, "data": base64.b64encode(data).decode()}


def gemini_image(prompt: str, image_urls: list[str]) -> bytes:
    """Generate one image from a prompt + reference images. Returns PNG/JPEG bytes."""
    from google import genai
    from google.genai import types

    try:
        check_budget("gemini")
    except BudgetExceeded as e:
        raise BadModelOutput(str(e)) from e
    client = genai.Client()
    parts: list[Any] = []
    for url in image_urls:
        data, mime = fetch_image(url)
        parts.append(types.Part.from_bytes(data=data, mime_type=mime))
    parts.append(prompt)

    try:
        resp = client.models.generate_content(model=GEMINI_IMAGE_MODEL, contents=parts)
    except Exception as e:  # noqa: BLE001 — quota (429), network, etc.
        raise BadModelOutput(f"gemini image: {str(e)[:200]}") from e
    for cand in resp.candidates or []:
        for part in cand.content.parts or []:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                record_gemini_image()
                return part.inline_data.data
    raise BadModelOutput("Gemini returned no image")
