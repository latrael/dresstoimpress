"""Thin wrappers around Claude (vision + text) and Gemini (image gen).

MOCK_AI=1 (or a missing key) returns deterministic fake output so the app
and frontend can be built without spending credits or waiting on models.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")


def mock_mode(key_env: str) -> bool:
    return os.getenv("MOCK_AI") == "1" or not os.getenv(key_env)


class BadModelOutput(Exception):
    pass


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


def claude_json(prompt: str, image_url: str | None = None, max_tokens: int = 1500) -> Any:
    """Call Claude and return parsed JSON. Retries once on unparseable output."""
    from anthropic import Anthropic

    client = Anthropic()
    content: list[dict] = []
    if image_url:
        content.append({"type": "image", "source": {"type": "url", "url": image_url}})
    content.append({"type": "text", "text": prompt})

    last_err: Exception | None = None
    for _ in range(2):
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        try:
            return extract_json(text)
        except BadModelOutput as e:
            last_err = e
    raise BadModelOutput(str(last_err))


def fetch_image(url: str) -> tuple[bytes, str]:
    r = httpx.get(url, timeout=20, follow_redirects=True)
    r.raise_for_status()
    mime = r.headers.get("content-type", "image/jpeg").split(";")[0]
    return r.content, mime


def gemini_image(prompt: str, image_urls: list[str]) -> bytes:
    """Generate one image from a prompt + reference images. Returns PNG/JPEG bytes."""
    from google import genai
    from google.genai import types

    client = genai.Client()
    parts: list[Any] = []
    for url in image_urls:
        data, mime = fetch_image(url)
        parts.append(types.Part.from_bytes(data=data, mime_type=mime))
    parts.append(prompt)

    resp = client.models.generate_content(model=GEMINI_IMAGE_MODEL, contents=parts)
    for cand in resp.candidates or []:
        for part in cand.content.parts or []:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                return part.inline_data.data
    raise BadModelOutput("Gemini returned no image")
