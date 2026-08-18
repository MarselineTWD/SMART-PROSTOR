"""Однократный ETL: docx-шаблоны ТЗ из `Файлы/Выгрузка/Шаблоны ТЗ/`
заливаются в MinIO-бакет `prostor-templates`.

Идемпотентно: если объект с тем же ключом уже есть — пропускаем. В
docker-compose путь `Файлы/...` можно смонтировать как volume, иначе
скрипт молча ничего не сделает (для dev-запуска без монтирования).
"""
from __future__ import annotations

import logging
from pathlib import Path

from backend.app.core.config import settings
from backend.app.services.storage import DOCX_MIME, get_storage_service


logger = logging.getLogger(__name__)


TEMPLATE_SOURCES: tuple[Path, ...] = (
    Path("/app/templates"),
    Path(__file__).resolve().parents[3] / "Файлы" / "Выгрузка из системы" / "Шаблоны ТЗ",
)


def _find_source_dir() -> Path | None:
    for candidate in TEMPLATE_SOURCES:
        if candidate.exists() and any(candidate.glob("*.docx")):
            return candidate
    return None


def sync_templates_to_minio() -> int:
    source = _find_source_dir()
    if source is None:
        logger.info("templates source dir not mounted — skipping MinIO upload")
        return 0

    storage = get_storage_service()
    try:
        storage.ensure_bucket(settings.s3_bucket_templates)
    except Exception as exc:
        logger.warning("cannot ensure bucket %s: %s", settings.s3_bucket_templates, exc)
        return 0

    uploaded = 0
    for path in sorted(source.glob("*.docx")):
        key = path.name
        if storage.object_exists(settings.s3_bucket_templates, key):
            continue
        try:
            storage.put_file(settings.s3_bucket_templates, key, path, DOCX_MIME)
            uploaded += 1
            logger.info("uploaded template: %s", key)
        except Exception as exc:
            logger.warning("failed to upload %s: %s", key, exc)
    return uploaded


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")
    n = sync_templates_to_minio()
    logger.info("templates uploaded: %d", n)
