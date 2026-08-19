"""Общая тестовая конфигурация pytest для backend.

Делает набор тестов ГЕРМЕТИЧНЫМ и детерминированным:

* Отключает внешний LLM (DeepSeek). Ассистент и генератор ТЗ переходят на
  встроенный детерминированный fallback — без сети, быстро и воспроизводимо.
  Без этого часть тестов, проверяющих точный текст, «плавает» из-за живого
  ответа модели, а прогон занимает минуты вместо секунд.
* Переключает репозиторий ТЗ в режим in-memory, чтобы API-тесты не зависели
  от PostgreSQL/asyncpg.

Оба переключения выполняются на уровне модуля (до сбора тестов), поэтому
работают одинаково и под ``pytest``, и под ``python -m unittest`` при наличии
conftest в пути импорта.
"""
from __future__ import annotations

import pytest

from backend.app.core.config import settings
import backend.app.services.tz_repository as tz_repo


def _disable_llm() -> None:
    # llm_enabled == bool(llm_api_key.strip()); пустой ключ -> офлайн-режим.
    settings.llm_api_key = ""


def _use_memory_repo() -> None:
    tz_repo._use_memory = True


# Раннее (импорт-тайм) отключение: срабатывает до создания TestClient и до
# первого обращения к сервисам, независимо от порядка тестов.
_disable_llm()
_use_memory_repo()


@pytest.fixture(autouse=True)
def _hermetic_env():
    """Страховка на случай, если отдельный тест поменял глобальное состояние."""
    _disable_llm()
    _use_memory_repo()
    yield
