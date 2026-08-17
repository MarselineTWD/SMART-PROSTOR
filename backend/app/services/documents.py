from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document
from docx.shared import Pt
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from backend.app.models.domain import RequestDraft
from backend.app.services.rules import rules_service


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = PROJECT_ROOT / "outputs"


class DocumentExportService:
    """Builds a demonstrable PROSTOR document package from a canonical RequestDraft."""

    def export_zip(self, draft: RequestDraft) -> Path:
        evaluated = rules_service.evaluate(draft)
        package_dir = OUTPUT_ROOT / evaluated.id
        package_dir.mkdir(parents=True, exist_ok=True)

        tz_path = package_dir / "Приложение 1. ТЗ.docx"
        kp_path = package_dir / "Приложение 2. КП.xlsx"
        rs_path = package_dir / "Приложение 3. РС.xlsx"

        self._build_tz(evaluated, tz_path)
        self._build_calendar_plan(evaluated, kp_path)
        self._build_cost_estimate(evaluated, rs_path)

        zip_path = package_dir / f"prostor-{evaluated.id}-package.zip"
        with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
            for path in (tz_path, kp_path, rs_path):
                archive.write(path, arcname=path.name)
        return zip_path

    def _build_tz(self, draft: RequestDraft, path: Path) -> None:
        doc = Document()
        normal_style = doc.styles["Normal"]
        normal_style.font.name = "Arial"
        normal_style.font.size = Pt(10)

        doc.add_heading("Техническое задание", 0)
        doc.add_paragraph(f"Сформировано в PROSTOR MVP: {datetime.now():%d.%m.%Y %H:%M}")

        self._add_key_value_table(
            doc,
            [
                ("ID черновика", draft.id),
                ("Тип / продукт", draft.product_name),
                ("Заказчик", draft.input_data.customer_name or "Не заполнено"),
                ("Исполнитель", draft.company_name or "Не выбран"),
                ("Договор", draft.contract_name or "Не выбран"),
                ("Готовность", f"{draft.ready_score}%"),
            ],
        )

        doc.add_heading("1. Цели и ожидаемый результат", level=1)
        doc.add_paragraph(draft.input_data.goal or "Цель работ требует уточнения.")

        doc.add_heading("2. Объект и исходные данные", level=1)
        self._add_key_value_table(
            doc,
            [
                ("Объект", draft.input_data.object_name or "Не заполнено"),
                ("Плановый срок", draft.input_data.deadline or "Не заполнено"),
                ("Исходные данные", "Подтверждены" if draft.input_data.source_data_ready else "Требуют уточнения"),
                ("3D-модель", "Требуется" if draft.input_data.needs_3d_model else "Не требуется"),
                ("Субподряд", "Предусмотрен" if draft.input_data.requires_subcontractor else "Не предусмотрен"),
            ],
        )

        doc.add_heading("3. Этапы выполнения", level=1)
        for index, stage in enumerate(draft.stages, start=1):
            doc.add_paragraph(f"{index}. {stage}", style="List Number")

        doc.add_heading("4. Проверка рисков и рекомендации", level=1)
        if draft.risks:
            for risk in draft.risks:
                doc.add_paragraph(
                    f"{risk.severity.upper()}: {risk.message} Рекомендация: {risk.recommendation}",
                    style="List Bullet",
                )
        else:
            doc.add_paragraph("Критичных рисков не выявлено.")

        doc.add_heading("5. Состав пакета документов", level=1)
        for document in draft.documents:
            doc.add_paragraph(f"{document.kind}: {document.status}", style="List Bullet")

        doc.add_heading("6. Примечания системы", level=1)
        for note in dict.fromkeys(draft.notes):
            doc.add_paragraph(note, style="List Bullet")

        doc.save(path)

    def _build_calendar_plan(self, draft: RequestDraft, path: Path) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Календарный план"
        sheet.append(["№", "Этап", "Результат", "Статус"])
        for index, stage in enumerate(draft.stages, start=1):
            sheet.append([index, stage, f"Результат этапа «{stage}»", "План"])
        self._style_sheet(sheet)
        workbook.save(path)

    def _build_cost_estimate(self, draft: RequestDraft, path: Path) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Расчет стоимости"
        sheet.append(["№", "Работа", "Ед. изм.", "Кол-во", "Ставка, руб.", "Стоимость, руб."])
        for index, stage in enumerate(draft.stages, start=1):
            sheet.append([index, stage, "этап", 1, 100000, f"=D{index + 1}*E{index + 1}"])

        next_row = len(draft.stages) + 2
        if draft.input_data.requires_subcontractor:
            sheet.append([
                len(draft.stages) + 1,
                "Субподрядные работы",
                "комплект",
                1,
                70000,
                f"=D{next_row}*E{next_row}",
            ])
            next_row += 1

        sheet.append(["", "", "", "", "Итого", f"=SUM(F2:F{next_row - 1})"])
        self._style_sheet(sheet)
        workbook.save(path)

    @staticmethod
    def _add_key_value_table(doc: Document, rows: list[tuple[str, str]]) -> None:
        table = doc.add_table(rows=0, cols=2)
        table.style = "Table Grid"
        for key, value in rows:
            cells = table.add_row().cells
            cells[0].text = key
            cells[1].text = value

    @staticmethod
    def _style_sheet(sheet) -> None:
        header_fill = PatternFill("solid", fgColor="1F4E78")
        header_font = Font(color="FFFFFF", bold=True)
        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
        for column_cells in sheet.columns:
            width = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells) + 2
            sheet.column_dimensions[get_column_letter(column_cells[0].column)].width = min(width, 60)


document_export_service = DocumentExportService()
