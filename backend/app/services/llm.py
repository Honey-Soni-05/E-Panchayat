"""Gemini client.

The key lives here, server-side, and nowhere else. The old frontend gated its
LLM calls on a VITE_ prefixed variable, which meant the feature only worked if
the key was compiled into the browser bundle — so the secure configuration and
the working configuration were mutually exclusive. The browser now asks the
server whether AI is available; it never holds a key.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)

BASE = "https://generativelanguage.googleapis.com/v1beta"


class LLMUnavailable(RuntimeError):
    """Raised when no key is configured or the upstream call fails."""


async def generate(
    prompt: str,
    system: str | None = None,
    *,
    json_schema: dict[str, Any] | None = None,
    temperature: float = 0.2,
    timeout: float = 45.0,
) -> str:
    if not settings.ai_enabled:
        raise LLMUnavailable("GEMINI_API_KEY is not configured on the server.")

    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_schema:
        body["generationConfig"]["responseMimeType"] = "application/json"
        body["generationConfig"]["responseSchema"] = json_schema

    url = f"{BASE}/models/{settings.GEMINI_MODEL}:generateContent"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url, params={"key": settings.GEMINI_API_KEY}, json=body
            )
    except httpx.HTTPError as exc:
        log.warning("Gemini request failed: %s", exc)
        raise LLMUnavailable("Could not reach the language model.") from exc

    if resp.status_code != 200:
        log.warning("Gemini returned %s: %s", resp.status_code, resp.text[:500])
        raise LLMUnavailable(f"Language model returned status {resp.status_code}.")

    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise LLMUnavailable("The language model returned no answer.")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise LLMUnavailable("The language model returned an empty answer.")
    return text


async def generate_json(
    prompt: str, schema: dict[str, Any], system: str | None = None
) -> Any:
    raw = await generate(prompt, system, json_schema=schema, temperature=0.1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("Gemini returned unparseable JSON: %s", raw[:500])
        raise LLMUnavailable("The language model returned malformed data.") from exc


async def embed(texts: list[str], timeout: float = 60.0) -> list[list[float]]:
    """Batch-embed for the retrieval index (Phase 3)."""
    if not settings.ai_enabled:
        raise LLMUnavailable("GEMINI_API_KEY is not configured on the server.")

    model = f"models/{settings.GEMINI_EMBED_MODEL}"
    url = f"{BASE}/{model}:batchEmbedContents"
    body = {
        "requests": [
            {"model": model, "content": {"parts": [{"text": t}]}} for t in texts
        ]
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, params={"key": settings.GEMINI_API_KEY}, json=body)

    if resp.status_code != 200:
        raise LLMUnavailable(f"Embedding request returned status {resp.status_code}.")
    return [e["values"] for e in resp.json().get("embeddings", [])]
