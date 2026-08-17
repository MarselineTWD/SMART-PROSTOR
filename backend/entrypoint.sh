#!/bin/sh
set -e

echo "[entrypoint] waiting for postgres..."
python - <<'PY'
import os
import socket
import time
from urllib.parse import urlparse

url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://prostor:prostor@postgres:5432/prostor")
parsed = urlparse(url.replace("+asyncpg", ""))
host = parsed.hostname or "postgres"
port = parsed.port or 5432
deadline = time.time() + 60
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"[entrypoint] postgres reachable at {host}:{port}")
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit(f"[entrypoint] postgres at {host}:{port} not reachable after 60s")
PY

echo "[entrypoint] running migrations..."
alembic upgrade head

echo "[entrypoint] backfilling embeddings..."
python -m backend.app.scripts.embed_seeds

echo "[entrypoint] starting: $*"
exec "$@"
