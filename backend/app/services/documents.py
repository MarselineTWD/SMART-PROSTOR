"""Экспорт технического задания в DOCX.

Формируется единый документ .docx на основе сохранённого ТЗ (``TZDocument``).
Ранее пакет включал XLSX (КП/РС) — от них отказались: результат один
самодостаточный файл ТЗ.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.shared import Pt

from backend.app.models.domain import RequestDraft, TZDocument
from backend.app.services.tz_generator import tz_generator


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = PROJECT_ROOT / "outputs"


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-zА-Яа-яЁё _.-]+", "", name).strip()
    return (cleaned or "ТЗ")[:80]


class DocumentExportService:
    """Строит DOCX-файл технического задания."""

    def export_docx(self, document: TZDocument) -> Path:
        package_dir = OUTPUT_ROOT / document.id
        package_dir.mkdir(parents=True, exist_ok=True)
        path = package_dir / f"{_safe_filename(document.title or 'Техническое задание')}.docx"
        self._build_tz(document, path)
        return path

    def export_from_draft(self, draft: RequestDraft) -> Path:
        """Совместимость: собирает ТЗ из RequestDraft и выгружает DOCX."""
        document = tz_generator.document_from_draft(draft)
        return self.export_docx(document)

    def _build_tz(self, document: TZDocument, path: Path) -> None:
        doc = Document()
        normal = doc.styles["Normal"]
        normal.font.name = "Arial"
        normal.font.size = Pt(11)

        doc.add_heading("Техническое задание", 0)
        if document.template_name:
            doc.add_paragraph(document.template_name)
        doc.add_paragraph(f"Сформировано в PROSTOR: {datetime.now():%d.%m.%Y %H:%M}")

        self._add_key_value_table(
            doc,
            [
                ("Договор", self._contract_line(document)),
                ("Объект", document.object_name or "Не заполнено"),
                ("Заказчик", document.customer_name or "Не заполнено"),
                ("Исполнитель", document.executor_name or "Не выбран"),
                ("Место выполнения", str(document.requisites.get("city") or "Не заполнено")),
                ("Готовность", f"{document.ready_score}%"),
            ],
        )

        for index, section in enumerate(document.sections, start=1):
            doc.add_heading(f"{index}. {section.title}", level=1)
            content = section.content.strip() or "Раздел требует заполнения."
            for line in content.split("\n"):
                line = line.strip()
                if line:
                    doc.add_paragraph(line)

        doc.add_heading("Подписи сторон", level=1)
        self._add_key_value_table(
            doc,
            [
                ("ЗАКАЗЧИК", str(document.requisites.get("signatory_customer") or "____________ / ____________")),
                ("ИСПОЛНИТЕЛЬ", str(document.requisites.get("signatory_executor") or "____________ / ____________")),
            ],
        )

        doc.save(path)

    @staticmethod
    def _contract_line(document: TZDocument) -> str:
        number = document.requisites.get("contract_number")
        date = document.requisites.get("contract_date")
        if number or date:
            return f"№ {number or '—'} от {date or '—'}"
        return document.contract_name or "Не выбран"

    @staticmethod
    def _add_key_value_table(doc: Document, rows: list[tuple[str, str]]) -> None:
        table = doc.add_table(rows=0, cols=2)
        table.style = "Table Grid"
        for key, value in rows:
            cells = table.add_row().cells
            cells[0].text = key
            cells[1].text = value


document_export_service = DocumentExportService()
