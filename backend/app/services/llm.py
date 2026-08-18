"""Минимальный клиент OpenAI-совместимого API (DeepSeek) с безопасным fallback."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from backend.app.core.config import settings


logger = logging.getLogger(__name__)


def llm_complete(
    system: str,
    prompt: str,
    *,
    temperature: float = 0.2,
    json_mode: bool = False,
    max_tokens: int = 900,
) -> str | None:
    if not settings.llm_enabled:
        return None
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if json_mode:
        # OpenAI-совместимый строгий JSON-режим (поддерживается DeepSeek).
        payload["response_format"] = {"type": "json_object"}
    request = urllib.request.Request(
        f"{settings.llm_base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {settings.llm_api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.llm_timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return str(content).strip() or None
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError, OSError) as exc:
        logger.warning("LLM request failed (%s); deterministic fallback is used", type(exc).__name__)
        return None


def llm_complete_json(
    system: str,
    prompt: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 900,
) -> dict | None:
    """Запрашивает у модели строгий JSON-объект и возвращает его как dict.

    Возвращает ``None``, если LLM отключён, недоступен или ответ не является
    JSON-объектом — вызывающий код в этом случае использует детерминированный
    fallback.
    """
    raw = llm_complete(
        system, prompt, temperature=temperature, json_mode=True, max_tokens=max_tokens
    )
    if not raw:
        return None
    parsed = _loads_relaxed(raw)
    if not isinstance(parsed, dict):
        logger.warning("LLM returned non-object JSON; deterministic fallback is used")
        return None
    return parsed


def _loads_relaxed(raw: str) -> object | None:
    """Разбирает JSON устойчиво к обёрткам ```json ... ``` и постороннему тексту."""
    try:
        return json.loads(raw)
    except ValueError:
        pass
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(text[start : end + 1])
        except ValueError:
            return None
    return None
