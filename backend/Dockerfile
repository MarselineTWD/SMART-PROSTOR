# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf-cache \
    SENTENCE_TRANSFORMERS_HOME=/opt/hf-cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only torch wheel keeps the image ~1.5GB smaller than the default CUDA build.
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.2.0,<3.0.0"

COPY pyproject.toml ./
RUN pip install \
    "fastapi>=0.116.0,<1.0.0" \
    "uvicorn[standard]>=0.35.0,<1.0.0" \
    "python-docx>=1.1.2,<2.0.0" \
    "openpyxl>=3.1.0,<4.0.0" \
    "pydantic-settings>=2.5.0,<3.0.0" \
    "sqlalchemy[asyncio]>=2.0.30,<3.0.0" \
    "asyncpg>=0.29.0,<1.0.0" \
    "pgvector>=0.3.0,<1.0.0" \
    "alembic>=1.13.0,<2.0.0" \
    "sentence-transformers>=3.0.0,<4.0.0" \
    "numpy>=1.26.0,<3.0.0"

# Pre-cache the embedding model so container start doesn't need network.
ARG EMBEDDING_MODEL_NAME=intfloat/multilingual-e5-small
ENV EMBEDDING_MODEL_NAME=${EMBEDDING_MODEL_NAME}
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL_NAME}')"

COPY backend ./backend
COPY alembic.ini ./alembic.ini
COPY backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
