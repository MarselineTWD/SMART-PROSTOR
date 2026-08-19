"""HTTP-тесты REST API через FastAPI TestClient.

Проверяют реальный слой роутинга/валидации/сериализации (запрос -> ответ),
а не только сервисы. LLM отключён (conftest + setUpModule), репозиторий ТЗ —
in-memory, поэтому тесты не требуют сети и PostgreSQL.

TestClient создаётся без контекстного менеджера — тогда FastAPI не запускает
lifespan (снапшот каталога из БД). Каталог обслуживается из встроенного
cold-start фолбэка, а procurement/estimate — из committed seed-файла.
Эндпоинт с pgvector (/search/query) изолируется dependency override + патчем.
"""
from __future__ import annotations

import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.core.db import get_session
from backend.app.main import app
from backend.app.models.domain import SearchContext
from backend.app.services.search import search_service
from backend.app.services.tz_generator import tz_generator
from backend.app.services.tz_templates import tz_template_service
import backend.app.services.tz_repository as tz_repo


def setUpModule() -> None:
    settings.llm_api_key = ""
    tz_repo._use_memory = True
    tz_repo._MEMORY.clear()


client = TestClient(app)


def _geology_document_payload() -> dict:
    template = tz_template_service.get_template("tz-geology-concept")
    document = tz_generator.new_document(
        template,
        title="ТЗ: Концепт геологии Северного участка",
        object_name="Северный участок",
        customer_name="Блок геологии",
    )
    document.input_data.goal = "Подготовить геологическую концепцию"
    document.input_data.deadline = "2026-12-20"
    document.requisites["stages"] = ["Проверка данных", "Интерпретация", "Отчёт"]
    return document.model_dump(mode="json")


class HealthApiTest(unittest.TestCase):
    def test_healthcheck_ok(self):
        resp = client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})


class TemplatesApiTest(unittest.TestCase):
    def test_list_templates(self):
        resp = client.get("/api/tz/templates")
        self.assertEqual(resp.status_code, 200)
        templates = resp.json()["templates"]
        self.assertGreaterEqual(len(templates), 1)
        for key in ("key", "name", "section_count"):
            self.assertIn(key, templates[0])

    def test_get_template_detail(self):
        key = client.get("/api/tz/templates").json()["templates"][0]["key"]
        resp = client.get(f"/api/tz/templates/{key}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["template"]["key"], key)

    def test_get_unknown_template_is_404(self):
        self.assertEqual(client.get("/api/tz/templates/does-not-exist").status_code, 404)


class TzPreviewApiTest(unittest.TestCase):
    def test_preview_builds_document_without_persisting(self):
        resp = client.post("/api/tz/preview", json={"template_key": "tz-geology-concept"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["document"]["template_key"], "tz-geology-concept")
        self.assertIn("ready_score", body["validation"])
        listed = client.get("/api/tz").json()["documents"]
        self.assertNotIn(body["document"]["id"], [d["id"] for d in listed])

    def test_preview_validate_reports_issues_for_empty_draft(self):
        resp = client.post("/api/tz/preview/validate", json={
            "template_key": "tz-geology-concept", "template_name": "x",
        })
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["valid"])
        self.assertLess(body["ready_score"], 100)

    def test_preview_requires_known_template(self):
        self.assertEqual(client.post("/api/tz/preview", json={"template_key": "nope"}).status_code, 404)


class TzCrudApiTest(unittest.TestCase):
    def _create(self) -> dict:
        resp = client.post("/api/tz", json={
            "template_key": "tz-geology-concept",
            "object_name": "Куст 12",
            "customer_name": "Блок геологии",
        })
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()["document"]

    def test_create_then_get_and_list(self):
        doc = self._create()
        got = client.get(f"/api/tz/{doc['id']}")
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.json()["document"]["object_name"], "Куст 12")
        listed = client.get("/api/tz").json()["documents"]
        self.assertIn(doc["id"], [d["id"] for d in listed])

    def test_update_document_fields(self):
        doc = self._create()
        resp = client.put(f"/api/tz/{doc['id']}", json={"object_name": "Куст 99"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["document"]["object_name"], "Куст 99")

    def test_delete_document(self):
        doc = self._create()
        self.assertEqual(client.delete(f"/api/tz/{doc['id']}").status_code, 200)
        self.assertEqual(client.get(f"/api/tz/{doc['id']}").status_code, 404)

    def test_get_missing_document_is_404(self):
        self.assertEqual(client.get("/api/tz/missing-id").status_code, 404)

    def test_delete_missing_document_is_404(self):
        self.assertEqual(client.delete("/api/tz/missing-id").status_code, 404)
