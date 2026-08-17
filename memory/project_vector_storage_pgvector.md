---
name: Векторное хранилище — pgvector
description: Решение использовать PostgreSQL + pgvector для эмбеддингов вместо in-memory numpy или Qdrant.
type: project
---

Для эмбеддингов используется **PostgreSQL + pgvector**, не in-memory numpy и не Qdrant/FAISS.

**Why:** объём данных в предоставленных Excel-выгрузках (13 компаний, 462 заказа, 31–48 продуктов) — это только сэмпл. В реальной системе ПРОСТОР данных на порядки больше (заявки, ТЗ, история, ставки, операции). In-memory решение не масштабируется и на защите АК его снимут первым же вопросом. Отдельный векторный движок (Qdrant/FAISS) добавляет ещё один компонент инфраструктуры без выгоды: у Газпром нефти уже есть Postgres Pro в корпоративном контуре, а pgvector даёт HNSW/IVFFlat и джойны с реляционными таблицами (продукты, договоры, компании) в одной транзакции.

**How to apply:**
- Backend работает через SQLAlchemy + asyncpg с реальным PostgreSQL, а не с моками из `backend/app/data/catalog.py`.
- Для локальной разработки — docker-compose с образом `pgvector/pgvector:pg16`.
- Схема: колонки `embedding vector(384)` (под multilingual-e5-small) на таблицах `products`, `historical_cases`, при необходимости `intents`.
- Индекс HNSW для cosine (`vector_cosine_ops`). IVFFlat — как fallback, если HNSW не подтянется.
- Ingestion-скрипт заполняет БД из Excel + считает эмбеддинги батчами.
- Поиск — SQL с оператором `<=>` (cosine distance), гибридный скор считается в SQL или на уровне сервиса поверх top-K из векторного запроса.
- Мок-каталог из `data/catalog.py` оставить только как seed для тестов и как fallback, если БД недоступна на демо.
