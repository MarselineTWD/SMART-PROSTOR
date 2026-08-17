import shutil
import unittest
from pathlib import Path
from zipfile import ZipFile

from backend.app.models.domain import DraftInputData
from backend.app.schemas.draft import DraftFromSearchRequest
from backend.app.services.documents import document_export_service
from backend.app.services.drafts import draft_service
from backend.app.services.search import search_service


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

    def test_export_package_contains_docx_and_xlsx(self):
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

        archive_path = document_export_service.export_zip(draft)
        self.assertTrue(archive_path.exists())
        with ZipFile(archive_path) as archive:
            names = set(archive.namelist())
        self.assertIn("Приложение 1. ТЗ.docx", names)
        self.assertIn("Приложение 2. КП.xlsx", names)
        self.assertIn("Приложение 3. РС.xlsx", names)

        shutil.rmtree(Path(archive_path).parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
