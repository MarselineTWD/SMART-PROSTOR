# PROSTOR MVP

Стартовый backend для MVP из задания в [Ревью_задания_ПРОСТОР_единое.md](C:\Users\Marse\OneDrive\Рабочий стол\ПРОСТОР\Ревью_задания_ПРОСТОР_единое.md).

## Что уже есть

- `FastAPI`-каркас
- `Search Engine` на эвристиках для демо-режима
- каноническая сущность `RequestDraft`
- `Rules Engine` для ready score и рисков
- простая аналитика на мок-данных

## Структура

- `backend/app/main.py` — точка входа
- `backend/app/data/catalog.py` — мок-справочники MVP
- `backend/app/services/search.py` — подбор продукта и исполнителя
- `backend/app/services/drafts.py` — предзаполнение черновика
- `backend/app/services/rules.py` — правила проверки и ready score
- `backend/app/services/documents.py` — генерация ZIP-пакета DOCX/XLSX

## Запуск

```bash
pip install -e .
uvicorn backend.app.main:app --reload
```

## Основные эндпоинты

- `GET /api/health`
- `POST /api/search/query`
- `POST /api/drafts/from-search`
- `POST /api/drafts/evaluate`
- `POST /api/drafts/export`
- `GET /api/analytics/overview`

## Документация MVP

- `docs/ЕДТ_ПРОСТОР_MVP.md` — единый документ требований к ИТ-решению
- `docs/Архитектура_ПРОСТОР_MVP.md` — архитектура и компоненты
- `docs/Демо_сценарий_ПРОСТОР.md` — сценарий презентационного показа на 5–7 минут
