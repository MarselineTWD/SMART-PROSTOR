"""Генерация и дополнение технического задания.

Работает офлайн на эвристиках (детерминированно, без внешних сервисов),
поэтому демо не зависит от сети и ключей. Если в окружении задан ключ LLM
(``LLM_API_KEY``), для наполнения разделов используется реальная модель через
OpenAI-совместимый endpoint, а при любой ошибке — откат на эвристику.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.app.core.config import settings
from backend.app.models.domain import (
    DraftInputData,
    RequestDraft,
    TZDocument,
    TZDocumentSection,
    TZTemplate,
)
from backend.app.services.normative_acts import normative_act_service
from backend.app.services.tz_templates import tz_template_service
from backend.app.services.llm import llm_complete


ABBREVIATIONS = [
    "ГИС — геофизические исследования скважин",
    "ГКЗ — Государственная комиссия по запасам полезных ископаемых",
    "ГМ — геологическая модель",
    " КП — календарный план",
    "НГКМ — нефтегазоконденсатное месторождение",
    "ОПЗ — оперативный пересчёт запасов УВС",
    "ПО — программное обеспечение",
    "ПТД — проектно-технический документ",
    "ТЗ — техническое задание",
    "УВС — углеводородное сырьё",
]


class TZGenerator:
    # --- Создание документа из шаблона ---------------------------------------

    def new_document(
        self,
        template: TZTemplate,
        *,
        title: str | None = None,
        object_name: str | None = None,
        customer_name: str | None = None,
        executor_name: str | None = None,
        contract_name: str | None = None,
        product_id: str | None = None,
        input_data: DraftInputData | None = None,
        requisites: dict | None = None,
    ) -> TZDocument:
        input_data = input_data or DraftInputData()
        requisites = dict(requisites or {})
        requisites.setdefault("stages", list(template.stage_presets))
        sections = [
            TZDocumentSection(key=s.key, title=s.title, content="", source="template")
            for s in template.sections
        ]
        doc = TZDocument(
            id=f"tz-{uuid4().hex[:8]}",
            template_key=template.key,
            template_name=template.name,
            product_id=product_id or template.product_id,
            title=title or f"{template.name}: {object_name or 'без объекта'}",
            object_name=object_name,
            customer_name=customer_name,
            executor_name=executor_name,
            contract_name=contract_name,
            input_data=input_data,
            requisites=requisites,
            sections=sections,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        doc.ready_score = self.compute_ready_score(doc)
        return doc

    # --- Дополнение / полная генерация ---------------------------------------

    def generate(
        self,
        document: TZDocument,
        *,
        mode: str = "augment",
        instruction: str | None = None,
        section_keys: list[str] | None = None,
        template: TZTemplate | None = None,
    ) -> TZDocument:
        template = template or tz_template_service.get_or_default(document.template_key)
        ctx = self._context(document, template)
        targets = set(section_keys or [])

        for section in document.sections:
            if targets:
                # Явно выбранные разделы всегда перегенерируются (точечно).
                should = section.key in targets
            elif mode == "full":
                should = True
            else:  # augment — только пустые разделы, ручной текст не трогаем
                should = not section.content.strip()
            if not should:
                continue
            text = self._render_section(section.key, ctx, instruction)
            if text:
                section.content = text
                section.source = "ai"

        if targets:
            note = "ИИ обновил выбранные разделы ТЗ."
        elif mode == "full":
            note = "ИИ сгенерировал ТЗ полностью."
        else:
            note = "ИИ дополнил недостающие разделы ТЗ."
        document.notes = [*[n for n in document.notes if not n.startswith("ИИ ")], note]
        document.updated_at = datetime.now(timezone.utc)
        document.ready_score = self.compute_ready_score(document)
        return document

    def document_from_draft(self, draft: RequestDraft) -> TZDocument:
        """Собирает и наполняет ТЗ из канонического RequestDraft (для экспорта)."""
        template = tz_template_service.template_for_product(draft.product_id)
        requisites = {"stages": list(draft.stages or template.stage_presets)}
        doc = self.new_document(
            template,
            title=f"{template.name}: {draft.input_data.object_name or draft.product_name}",
            object_name=draft.input_data.object_name,
            customer_name=draft.input_data.customer_name,
            executor_name=draft.company_name,
            contract_name=draft.contract_name,
            product_id=draft.product_id,
            input_data=draft.input_data,
            requisites=requisites,
        )
        return self.generate(doc, mode="full", template=template)

    # --- Оценка готовности ----------------------------------------------------

    def compute_ready_score(self, document: TZDocument) -> int:
        sections = document.sections or []
        filled = sum(1 for s in sections if s.content.strip())
        section_ratio = (filled / len(sections)) if sections else 0.0

        data = document.input_data
        key_fields = [document.object_name, document.customer_name, data.goal, data.deadline]
        input_ratio = sum(1 for v in key_fields if v and str(v).strip()) / len(key_fields)

        score = round(0.65 * section_ratio * 100 + 0.35 * input_ratio * 100)
        return max(0, min(100, score))

    # --- Контекст и рендер разделов ------------------------------------------

    def _context(self, document: TZDocument, template: TZTemplate) -> dict:
        data = document.input_data
        stages = document.requisites.get("stages") or template.stage_presets
        domain_parameters = [
            f"{field.label}: {document.requisites[field.key]}"
            for field in template.fields
            if field.key in document.requisites
            and document.requisites[field.key] not in (None, "", False)
        ]
        return {
            "template_key": template.key,
            "object": document.object_name or "объект работ",
            "customer": document.customer_name or "Заказчик",
            "executor": document.executor_name or "Исполнитель",
            "goal": (data.goal or "").strip() or template.description or "выполнение работ по теме ТЗ",
            "deadline": (data.deadline or "").strip() or "[указать дату]",
            "city": str(document.requisites.get("city") or "").strip() or "по месту нахождения Исполнителя",
            "stages": list(stages),
            "domain_parameters": domain_parameters,
            "source_data_ready": bool(data.source_data_ready),
            "needs_3d": bool(data.needs_3d_model),
            "requires_subcontractor": bool(data.requires_subcontractor),
            "subcontract_share": data.subcontract_share_percent,
            "separate_estimate": bool(data.separate_subcontract_estimate),
        }

    def _render_section(self, key: str, ctx: dict, instruction: str | None) -> str:
        renderer = getattr(self, f"_sec_{key}", None)
        if renderer is None:
            text = self._sec_generic(key, ctx)
        else:
            text = renderer(ctx)
        # Сначала пробуем LLM, если он настроен; иначе — эвристика.
        llm = self._llm_section(key, ctx, instruction, text)
        if llm:
            return llm
        if instruction:
            text = f"{text}\nДополнительно (по запросу): {instruction.strip()}"
        return text

    def _numbered_stages(self, ctx: dict) -> str:
        return "\n".join(f"{i}. {stage}" for i, stage in enumerate(ctx["stages"], start=1))

    def _sec_goal(self, ctx: dict) -> str:
        tasks = "\n".join(f"{i}. {stage}." for i, stage in enumerate(ctx["stages"], start=1))
        return (
            f"Цель работ — {ctx['goal']} по объекту «{ctx['object']}».\n"
            f"Для достижения цели решаются задачи:\n{tasks}"
        )

    def _sec_abbreviations(self, ctx: dict) -> str:
        return "В настоящем ТЗ приняты следующие сокращения:\n" + "\n".join(ABBREVIATIONS)

    def _sec_scope(self, ctx: dict) -> str:
        text = (
            f"Периметр работ: {ctx['object']}. Заказчик: {ctx['customer']}.\n"
            f"Место выполнения работ: {ctx['city']}."
        )
        if ctx["domain_parameters"]:
            text += "\nПараметры выбранного типа ТЗ:\n- " + "\n- ".join(ctx["domain_parameters"])
        return text

    def _sec_schedule(self, ctx: dict) -> str:
        return (
            f"Общие сроки выполнения работ: с момента подписания Заказа до {ctx['deadline']}.\n"
            "Сроки выполнения по этапам и их продолжительность определяются календарным планом "
            "(Приложение № 2 к Заказу). Этапы работ:\n"
            f"{self._numbered_stages(ctx)}"
        )

    def _sec_content(self, ctx: dict) -> str:
        lines = ["Перечень работ по этапам с ожидаемыми результатами:"]
        for i, stage in enumerate(ctx["stages"], start=1):
            lines.append(
                f"{i}. {stage}. Ожидаемый результат: подтверждённые материалы этапа "
                "с приёмкой Заказчиком."
            )
        return "\n".join(lines)

    def _sec_conditions(self, ctx: dict) -> str:
        parts = [
            "Заказчик предоставляет Исполнителю до начала и в процессе работ исходные данные "
            "(геолого-геофизические материалы, данные скважин, результаты предыдущих исследований)."
        ]
        parts.append(
            "Исходные данные предоставлены и подтверждены Заказчиком."
            if ctx["source_data_ready"]
            else "Готовность и состав исходных данных подлежат подтверждению Заказчиком до начала работ."
        )
        if ctx["needs_3d"]:
            parts.append(
                "Для построения 3D-модели требуется полный комплект подтверждённых исходных данных."
            )
        parts.append(
            "Приёмка выполненной работы осуществляется Заказчиком по результатам проверки "
            "соответствия результатов требованиям ТЗ."
        )
        return "\n".join(parts)

    def _sec_documentation(self, ctx: dict) -> str:
        return (
            "По завершении работ Исполнитель передаёт Заказчику:\n"
            "1. Отчёт в формате MS Word и PDF.\n"
            "2. Презентационные материалы по результатам работ.\n"
            "3. Результаты моделирования (проекты/кубы) в согласованном формате.\n"
            "Графические приложения предоставляются в векторном формате (PDF). "
            "Порядок сдачи и приёмки — согласно календарному плану."
        )

    def _sec_work_requirements(self, ctx: dict) -> str:
        preamble = (
            "Работы выполняются в соответствии с действующими нормативными документами и "
            "методиками Заказчика с использованием лицензионного программного обеспечения. "
            "Исполнитель обеспечивает квалифицированный персонал и соблюдение требований "
            "промышленной безопасности, охраны труда и окружающей среды."
        )
        # Список НПА подгружается из БД для конкретного шаблона (справочник
        # наполнен из docx-шаблонов ТЗ; embedding позволяет в будущем
        # рекомендовать дополнительные акты по описанию работ).
        acts = normative_act_service.acts_for_template(ctx.get("template_key", ""))
        if not acts:
            return preamble
        listed = "\n".join(f"{i}. {a.title}." for i, a in enumerate(acts, start=1))
        return (
            f"{preamble}\n\n"
            "Материалы должны соответствовать требованиям следующих нормативных документов:\n"
            f"{listed}"
        )

    def _sec_quality(self, ctx: dict) -> str:
        return (
            "Приёмка работ осуществляется с оформлением акта сдачи-приёмки работ. "
            "Контроль качества выполняется поэтапно; возникающие вопросы эскалируются на "
            "геолого-технический / научно-технический совет Заказчика."
        )

    def _sec_subcontractors(self, ctx: dict) -> str:
        if not ctx["requires_subcontractor"]:
            return (
                "Привлечение субподрядчиков настоящим ТЗ не предусмотрено; "
                "работы выполняются силами Исполнителя."
            )
        share = ctx["subcontract_share"] if ctx["subcontract_share"] is not None else 70
        text = (
            "По согласованию с Заказчиком Исполнитель вправе привлекать субисполнителей. "
            f"Максимальная доля работ, передаваемых на субподряд, — не более {share}%. "
            "Исполнитель несёт ответственность за работы субисполнителей."
        )
        if ctx["separate_estimate"]:
            text += " По субподрядным работам оформляется отдельный расчёт стоимости (РС)."
        return text

    def _sec_other(self, ctx: dict) -> str:
        return (
            "Особые требования по координации и контролю выполняемых работ согласуются "
            "сторонами дополнительно. Иные условия по настоящему ТЗ отсутствуют."
        )

    def _sec_generic(self, key: str, ctx: dict) -> str:
        return (
            f"Раздел «{key}» по объекту «{ctx['object']}» (Заказчик: {ctx['customer']}). "
            "Содержание раздела уточняется по согласованию сторон."
        )

    # --- Необязательный вызов LLM --------------------------------------------

    def _llm_section(self, key: str, ctx: dict, instruction: str | None, draft_text: str) -> str | None:
        if not settings.llm_enabled:
            return None
        system = (
            "Ты — инженер-эксперт, составляющий разделы технического задания (ТЗ) "
            "для нефтегазовых проектов на русском языке. Пиши официально, по делу, "
            "без воды. Возвращай только текст раздела."
        )
        prompt = (
            f"Раздел ТЗ: {key}.\n"
            f"Объект: {ctx['object']}. Заказчик: {ctx['customer']}. Исполнитель: {ctx['executor']}.\n"
            f"Цель: {ctx['goal']}. Срок: {ctx['deadline']}. Этапы: {', '.join(ctx['stages'])}.\n"
            f"Параметры выбранного типа ТЗ: {', '.join(ctx['domain_parameters']) or 'не указаны'}.\n"
            f"Черновик раздела: {draft_text}\n"
        )
        if instruction:
            prompt += f"Указание пользователя: {instruction}\n"
        return self._llm_complete(system, prompt)

    def _llm_complete(self, system: str, prompt: str) -> str | None:
        return llm_complete(system, prompt, temperature=0.3)


tz_generator = TZGenerator()
