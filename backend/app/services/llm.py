"""Минимальный клиент OpenAI-совместимого API (DeepSeek) с безопасным fallback."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from backend.app.core.config import settings


logger = logging.getLogger(__name__)


def llm_complete(system: str, prompt: str, *, temperature: float = 0.2) -> str | None:
    if not settings.llm_enabled:
        return None
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "stream": False,
    }
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
