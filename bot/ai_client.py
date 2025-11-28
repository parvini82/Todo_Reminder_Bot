"""Client for parsing natural language tasks via OpenRouter."""
from __future__ import annotations

import json
from typing import Any, Dict

import requests

from .config import OPENROUTER_API_KEY, OPENROUTER_MODEL

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_SYSTEM_PROMPT = (
    "You are a task parsing assistant. You MUST return valid JSON only with the"
    " keys title, due_datetime (ISO8601 or null), and priority ('normal' or 'high')."
    " Never include extra keys or text."
)


class OpenRouterError(Exception):
    """Raised when the OpenRouter API cannot return a valid response."""


def _default_payload(text: str) -> Dict[str, Any]:
    return {
        "title": text.strip() or "Task",
        "due_datetime": None,
        "priority": "normal",
    }


def parse_task(text: str) -> Dict[str, Any]:
    """Parse a task description using OpenRouter and return structured data."""
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Respond with JSON only. Parse the following task: " + text.strip()
                ),
            },
        ],
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        title = parsed.get("title") or text.strip()
        due_datetime = parsed.get("due_datetime")
        priority = parsed.get("priority", "normal")
        if priority not in {"normal", "high"}:
            priority = "normal"
        return {
            "title": title,
            "due_datetime": due_datetime,
            "priority": priority,
        }
    except Exception as exc:  # pragma: no cover - network failure fallback
        raise OpenRouterError("Failed to parse task") from exc


def safe_parse_task(text: str) -> Dict[str, Any]:
    """Parse task data with graceful fallback."""
    try:
        return parse_task(text)
    except OpenRouterError:
        return _default_payload(text)
