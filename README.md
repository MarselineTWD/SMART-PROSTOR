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

### Через Docker Compose

Рекомендуемый способ для запуска на другом устройстве:

```bash
git clone https://github.com/MarselineTWD/SMART-PROSTOR.git
cd SMART-PROSTOR
docker compose up --build
```

Если репозиторий уже скачан, достаточно выполнить из корня проекта:

```bash
docker compose up --build
```

После запуска:

- интерфейс: http://localhost:5173
- backend через frontend proxy: http://localhost:5173/api/health
- backend напрямую: http://localhost:8000/api/health

Остановка:

```bash
docker compose down
```

Сгенерированные пакеты документов сохраняются во внутреннем Docker volume `prostor_outputs`.

### Локально без Docker

Backend:

```bash
pip install -e .
uvicorn backend.app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Локальный frontend использует относительный путь `/api` и Vite proxy на `http://127.0.0.1:8000`.

## Основные эндпоинты

- `GET /api/health`
- `POST /api/search/query`
- `POST /api/drafts/from-search`
- `POST /api/drafts/evaluate`
- `POST /api/drafts/export`
- `GET /api/analytics/overview`
- `GET /api/tz/templates` — 11 структурированных шаблонов с привязкой к исходным DOCX
- `POST /api/tz/{id}/switch-template` — смена шаблона с сохранением совпадающих разделов
- `POST /api/tz/{id}/validate` — готовность, критичные замечания и рекомендации
- `GET /api/estimates/products/{id}` — сроки и индикативная стоимость по каждому подрядчику
- `GET /api/assistant/status` — состояние DeepSeek/офлайн-fallback

## DeepSeek

Создайте локальный файл `.env.secrets` (он исключён из Git):

```env
LLM_API_KEY=your-key
```

Чат и генератор ТЗ используют `deepseek-chat` через backend. При недоступности API
приложение автоматически переключается на детерминированные правила.

## Расчёт стоимости

Подрядчики, договоры, длительность, этапы и роли берутся из XLSX ПРОСТОР.
В каталожной выгрузке нет числовых договорных ставок, поэтому интерфейс показывает
индикативную оценку по базовой ставке 1 000 руб./рабочий день из примера
`Приложение 3. РС.xlsx`, с НДС 22%. Перед оформлением заказа ставка требует уточнения.

## Документация MVP

- `docs/ЕДТ_ПРОСТОР_MVP.md` — единый документ требований к ИТ-решению
- `docs/Архитектура_ПРОСТОР_MVP.md` — архитектура и компоненты
- `docs/Демо_сценарий_ПРОСТОР.md` — сценарий презентационного показа на 5–7 минут
