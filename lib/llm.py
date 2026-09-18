"""Provider calls. Gemini primary, Groq secondary, degraded mode last."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

import httpx

from .prompt import RESPONSE_SCHEMA, SYSTEM, build_prompt

log = logging.getLogger("gridwise.llm")

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
OFFLINE = os.getenv("OFFLINE_FALLBACK", "0") == "1"
TIMEOUT = float(os.getenv("LLM_TIMEOUT_SECONDS", "12"))

_FENCE = re.compile(r"^```(?:json)?|```$", re.M)


def providers_available() -> list[str]:
    if OFFLINE:
        return []
    out = []
    if GEMINI_KEY:
        out.append("gemini")
    if GROQ_KEY:
        out.append("groq")
    return out


def _loads(text: str) -> dict[str, Any]:
    cleaned = _FENCE.sub("", text or "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


async def _gemini(client: httpx.AsyncClient, prompt: str) -> dict[str, Any]:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_MODEL}:generateContent")
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
    }
    r = await client.post(url, params={"key": GEMINI_KEY}, json=payload,
                          timeout=TIMEOUT)
    r.raise_for_status()
    body = r.json()
    text = body["candidates"][0]["content"]["parts"][0]["text"]
    return _loads(text)


async def _groq(client: httpx.AsyncClient, prompt: str) -> dict[str, Any]:
    payload = {
        "model": GROQ_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
    }
    r = await client.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_KEY}"},
        json=payload, timeout=TIMEOUT,
    )
    r.raise_for_status()
    return _loads(r.json()["choices"][0]["message"]["content"])


async def extract(notes: list[tuple[int, str]],
                  battery: dict) -> tuple[list[dict[str, Any]], str]:
    """Return (raw_entries, provider_used). Never raises."""
    order = providers_available()
    if not order or not notes:
        return [], "degraded"

    prompt = build_prompt(notes, battery)
    async with httpx.AsyncClient() as client:
        for name in order:
            for attempt in (1, 2, 3):
                try:
                    fn = _gemini if name == "gemini" else _groq
                    data = await fn(client, prompt)
                    items = data.get("interpretations")
                    if isinstance(items, list) and items:
                        return items, name
                    log.warning("provider %s returned no interpretations", name)
                except httpx.HTTPStatusError as exc:
                    log.warning("provider %s attempt %d failed: %s (status %s)",
                                name, attempt, type(exc).__name__, exc.response.status_code)
                    if exc.response.status_code in (429, 500, 502, 503, 504):
                        await asyncio.sleep(2.0 * attempt)
                except Exception as exc:  # noqa: BLE001 - never propagate
                    log.warning("provider %s attempt %d failed: %s",
                                name, attempt, type(exc).__name__)
    return [], "degraded"
