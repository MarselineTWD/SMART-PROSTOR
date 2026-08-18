import shutil
import unittest
from pathlib import Path

from docx import Document as DocxDocument

from backend.app.models.domain import DraftInputData
from backend.app.schemas.draft import DraftFromSearchRequest
from backend.app.services.documents import document_export_service
from backend.app.services.drafts import draft_service
from backend.app.services.procurement import procurement_service
from backend.app.services.search import search_service
from backend.app.services.tz_generator import tz_generator
from backend.app.services.tz_templates import tz_template_service


class ProstorMvpTest(unittest.TestCase):
    def test_reserves_query_returns_reserves_product(self):
        result = search_service.search(
            "Нужно оценить запасы по объекту и подготовить проектно-технический документ",
            limit=3,
        )

        self.assertGreaterEqual(len(result.products), 1)
        self.assertEqual(result.products[0].product.id, "product-reserves")
        self.assertGreater(len(result.products[0].recommended_companies), 0)
        self.assertGreater(len(result.products[0].similar_cases), 0)

    def test_3d_without_input_data_creates_risks(self):
        draft = draft_service.create_from_search(
            DraftFromSearchRequest(
                product_id="product-reserves",
                input_data=DraftInputData(
                    customer_name="Блок геологии и разработки",
                    goal="Оценить запасы и подготовить ПТД",
                    deadline="2026-09-30",
                    needs_3d_model=True,
                    source_data_ready=False,
                ),
            )
        )

        risk_codes = {risk.code for risk in draft.risks}
        self.assertIn("missing_object", risk_codes)
        self.assertIn("3d_missing_input_data", risk_codes)
        self.assertLess(draft.ready_score, 100)

    def test_export_produces_single_docx_without_xlsx(self):
        draft = draft_service.create_from_search(
            DraftFromSearchRequest(
                product_id="product-reserves",
                input_data=DraftInputData(
                    object_name="Северный блок",
                    customer_name="Блок геологии и разработки",
                    goal="Оценить запасы и подготовить ПТД",
                    deadline="2026-09-30",
                ),
            )
        )

        docx_path = document_export_service.export_from_draft(draft)
        try:
            self.assertTrue(docx_path.exists())
            self.assertEqual(docx_path.suffix, ".docx")
            # Никаких xlsx рядом с результатом.
            self.assertEqual(list(docx_path.parent.glob("*.xlsx")), [])
            # Файл открывается как валидный docx.
            self.assertGreater(len(DocxDocument(str(docx_path)).paragraphs), 5)
        finally:
            shutil.rmtree(Path(docx_path).parent, ignore_errors=True)


class TZTemplatesTest(unittest.TestCase):
    def test_catalog_has_all_templates(self):
        templates = tz_template_service.list_templates()
        self.assertEqual(len(templates), 11)
        for tpl in templates:
            self.assertTrue(tpl.sections, f"{tpl.key} без разделов")
        self.assertIsNotNone(tz_template_service.get_template("tz-ptd-opz"))
        self.assertIsNone(tz_template_service.get_template("does-not-exist"))

    def test_template_for_product_falls_back_to_universal(self):
        self.assertEqual(
            tz_template_service.template_for_product("product-geology").key,
            "tz-geology-concept",
        )
        self.assertEqual(
            tz_template_service.template_for_product("unknown-product").key,
            "tz-universal",
        )


class TZGeneratorTest(unittest.TestCase):
    def _doc(self):
        tpl = tz_template_service.get_template("tz-ptd-reserves")
        return tpl, tz_generator.new_document(
            tpl,
            object_name="Приразломное месторождение",
            customer_name="АО «Заказчик»",
            input_data=DraftInputData(goal="подсчёт запасов", deadline="25.12.2026"),
        )

    def test_full_generation_fills_all_sections(self):
        tpl, doc = self._doc()
        tz_generator.generate(doc, mode="full", template=tpl)
        self.assertTrue(all(s.content.strip() for s in doc.sections))
        self.assertTrue(all(s.source == "ai" for s in doc.sections))
        self.assertGreaterEqual(doc.ready_score, 60)

    def test_augment_keeps_manual_sections(self):
        tpl, doc = self._doc()
        doc.sections[0].content = "Ручной текст цели"
        doc.sections[0].source = "manual"
        tz_generator.generate(doc, mode="augment", template=tpl)
        self.assertEqual(doc.sections[0].content, "Ручной текст цели")
        self.assertEqual(doc.sections[0].source, "manual")
        self.assertTrue(doc.sections[1].content.strip())

    def test_section_keys_regenerate_only_selected(self):
        tpl, doc = self._doc()
        tz_generator.generate(doc, mode="full", template=tpl)
        snapshot = {s.key: s.content for s in doc.sections}
        tz_generator.generate(
            doc,
            mode="augment",
            section_keys=["goal"],
            instruction="учесть сжатые сроки",
            template=tpl,
        )
        for section in doc.sections:
            if section.key == "goal":
                self.assertNotEqual(section.content, snapshot["goal"])
                self.assertIn("сжатые сроки", section.content)
            else:
                self.assertEqual(section.content, snapshot[section.key])


class ProcurementEstimateTest(unittest.TestCase):
    def test_products_loaded_from_seed(self):
        products = procurement_service.list_products()
        self.assertGreaterEqual(len(products), 20)
        sample = products[0]
        for key in ("product_id", "name", "company_count", "min_days", "max_days"):
            self.assertIn(key, sample)
        self.assertGreater(sample["company_count"], 0)

    def test_match_products_by_name(self):
        matches = procurement_service.match_products("ТЗ: Концепт геологии", limit=3)
        self.assertTrue(matches)
        self.assertEqual(matches[0]["name"], "Концепт геологии")

    def test_estimate_sorted_and_roadmap_consistent(self):
        product_id = procurement_service.list_products()[0]["product_id"]
        estimate = procurement_service.estimate_product(product_id)
        self.assertIsNotNone(estimate)
        companies = estimate["companies"]
        self.assertGreater(len(companies), 0)
        days = [c["estimated_days"] for c in companies]
        self.assertEqual(days, sorted(days))  # быстрейший подрядчик — первым
        for company in companies:
            stages = company["stages"]
            if not stages:
                continue
            self.assertEqual(sum(s["days"] for s in stages), company["estimated_days"])
            offset = 0
            for stage in stages:
                self.assertEqual(stage["offset_days"], offset)
                offset += stage["days"]

    def test_estimate_missing_product_returns_none(self):
        self.assertIsNone(procurement_service.estimate_product("no-such-product"))


if __name__ == "__main__":
    unittest.main()
