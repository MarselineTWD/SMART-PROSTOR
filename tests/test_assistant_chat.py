"""Тесты структурированного чата: очистка, белый список, маршрутизация правок."""
import unittest

from backend.app.models.domain import TZFieldUpdate
from backend.app.schemas.assistant import AllowedField, AssistantChatRequest, AssistantReply
from backend.app.services.assistant import assistant_service, sanitize_text
from backend.app.services.llm import _loads_relaxed
from backend.app.services.tz_chat import tz_chat_service
from backend.app.services.tz_generator import tz_generator
from backend.app.services.tz_templates import tz_template_service


def _new_doc():
    template = tz_template_service.list_templates()[0]
    document = tz_generator.new_document(template, object_name="", customer_name="")
    return document, template


class SanitizeTest(unittest.TestCase):
    def test_strips_markdown_and_bullets(self):
        raw = "**Заголовок**\n- пункт один\n\n\n1. пункт два   лишние   пробелы"
        out = sanitize_text(raw)
        self.assertNotIn("*", out)
        self.assertNotIn("- ", out)
        self.assertNotIn("1. ", out)
        self.assertNotIn("   ", out)

    def test_strips_backticks_and_headers(self):
        noise = "#" + " Заголовок " + chr(96) + "code" + chr(96)
        out = sanitize_text(noise)
        self.assertNotIn(chr(96), out)
        self.assertNotIn("#", out)

    def test_length_cap(self):
        self.assertLessEqual(len(sanitize_text("a" * 5000, limit=100)), 100)


class LoadsRelaxedTest(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(_loads_relaxed('{"a": 1}'), {"a": 1})

    def test_fenced_json(self):
        fence = chr(96) * 3
        text = fence + "json\n" + '{"a": 2}' + "\n" + fence
        self.assertEqual(_loads_relaxed(text), {"a": 2})

    def test_garbage_returns_none(self):
        self.assertIsNone(_loads_relaxed("это не json"))


class WhitelistTest(unittest.TestCase):
    def test_drops_unknown_and_keeps_known(self):
        allowed = [
            AllowedField(target="document", key="object_name", label="Объект работ"),
            AllowedField(target="input_data", key="deadline", label="Плановый срок", type="date"),
        ]
        reply = AssistantReply(
            reply="ok",
            field_updates=[
                TZFieldUpdate(target="document", key="object_name", value="Куст 12", confidence=2.0),
                TZFieldUpdate(target="requisites", key="secret", value="x"),  # не в списке
                TZFieldUpdate(target="input_data", key="deadline", value="  "),  # пустое
            ],
        )
        result = assistant_service._postprocess(reply, allowed)
        keys = [(u.target, u.key) for u in result.field_updates]
        self.assertIn(("document", "object_name"), keys)
        self.assertNotIn(("requisites", "secret"), keys)
        self.assertNotIn(("input_data", "deadline"), keys)
        self.assertLessEqual(result.field_updates[0].confidence, 1.0)
        self.assertEqual(result.field_updates[0].label, "Объект работ")


class RoutingApplyTest(unittest.TestCase):
    def test_apply_routes_values_to_correct_places(self):
        document, template = _new_doc()
        section_key = template.sections[0].key
        updates = [
            TZFieldUpdate(target="document", key="object_name", value="Приобское м/р"),
            TZFieldUpdate(target="input_data", key="deadline", value="2026-12-31"),
            TZFieldUpdate(target="input_data", key="needs_3d_model", value="да"),
            TZFieldUpdate(target="input_data", key="subcontract_share_percent", value="до 60%"),
            TZFieldUpdate(target="section", key=section_key, value="Текст раздела от ИИ"),
        ]
        applied, skipped = tz_chat_service.apply(document, template, updates)
        self.assertEqual(document.object_name, "Приобское м/р")
        self.assertEqual(document.input_data.deadline, "2026-12-31")
        self.assertIs(document.input_data.needs_3d_model, True)
        self.assertEqual(document.input_data.subcontract_share_percent, 60)
        section = next(s for s in document.sections if s.key == section_key)
        self.assertEqual(section.content, "Текст раздела от ИИ")
        self.assertEqual(section.source, "ai")
        self.assertEqual(len(applied), 5)
        self.assertTrue(all(u.applied for u in applied))
        self.assertEqual(skipped, [])

    def test_apply_skips_unknown_target(self):
        document, template = _new_doc()
        updates = [TZFieldUpdate(target="requisites", key="__nope__", value="x")]
        applied, skipped = tz_chat_service.apply(document, template, updates)
        self.assertEqual(applied, [])
        self.assertEqual(len(skipped), 1)

    def test_allowed_fields_cover_targets(self):
        document, template = _new_doc()
        allowed = tz_chat_service.allowed_fields(document, template)
        targets = {a.target for a in allowed}
        self.assertEqual(targets, {"document", "input_data", "requisites", "section"})


class FallbackTest(unittest.TestCase):
    """Детерминированный слой без обращения к сети/LLM."""

    def test_fallback_is_structured_and_clean(self):
        reply = assistant_service._fallback(
            "Проверь готовность ТЗ", {"tz": {"ready_score": 42}}
        )
        self.assertIsInstance(reply, AssistantReply)
        self.assertIn("42", reply.reply)
        self.assertNotIn("*", reply.reply)
        self.assertTrue(reply.suggestions)

    def test_stateless_drops_field_updates(self):
        # Без белого списка (stateless) правки полей не проходят.
        reply = AssistantReply(
            reply="ok",
            field_updates=[TZFieldUpdate(target="document", key="object_name", value="X")],
        )
        result = assistant_service._postprocess(reply, None)
        self.assertEqual(result.field_updates, [])


if __name__ == "__main__":
    unittest.main()


class ChatEndpointTest(unittest.TestCase):
    """Сквозной сценарий эндпоинтов чата с мок-ответом LLM (без сети)."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from backend.app.main import app
        # In-memory режим репозитория: детерминированно и без asyncpg
        # (у TestClient на Windows пул asyncpg рушится между event loop'ами).
        import backend.app.services.tz_repository as repo_mod
        repo_mod._use_memory = True
        repo_mod._MEMORY.clear()
        self.client = TestClient(app)

    def _create_doc(self):
        template = tz_template_service.list_templates()[0]
        resp = self.client.post("/api/tz", json={"template_key": template.key})
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()["document"]["id"]

    def test_chat_send_history_and_apply(self):
        from unittest import mock

        doc_id = self._create_doc()
        canned = (
            AssistantReply(
                reply="Заполню объект и срок из вашего сообщения.",
                suggestions=["Сгенерировать всё"],
                field_updates=[
                    TZFieldUpdate(target="document", key="object_name", value="Куст 12", confidence=0.9),
                    TZFieldUpdate(target="input_data", key="deadline", value="2026-12-31", confidence=0.8),
                ],
                warnings=["Не указана цель работ"],
            ),
            "deepseek",
            False,
        )
        with mock.patch.object(assistant_service, "generate", return_value=canned):
            send = self.client.post(
                f"/api/tz/{doc_id}/chat",
                json={"message": "Объект Куст 12, срок до 31.12.2026"},
            )
        self.assertEqual(send.status_code, 200, send.text)
        body = send.json()
        self.assertEqual(body["provider"], "deepseek")
        self.assertEqual(len(body["message"]["field_updates"]), 2)
        self.assertNotIn("*", body["message"]["text"])

        history = self.client.get(f"/api/tz/{doc_id}/chat").json()
        self.assertEqual(len(history["messages"]), 2)  # user + assistant
        self.assertTrue(history["allowed_fields"])

        updates = body["message"]["field_updates"]
        applied = self.client.post(f"/api/tz/{doc_id}/chat/apply", json={"updates": updates})
        self.assertEqual(applied.status_code, 200, applied.text)
        result = applied.json()
        self.assertEqual(result["document"]["object_name"], "Куст 12")
        self.assertEqual(result["document"]["input_data"]["deadline"], "2026-12-31")
        self.assertEqual(len(result["applied"]), 2)
        self.assertTrue(all(u["applied"] for u in result["applied"]))
        self.assertIn("ready_score", result["validation"])
