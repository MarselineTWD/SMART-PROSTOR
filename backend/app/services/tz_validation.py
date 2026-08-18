"""Детерминированная проверка ТЗ по ЕДТ и бизнес-правилам ревью."""
from __future__ import annotations

from backend.app.models.domain import TZDocument
from backend.app.schemas.tz import TZValidationIssue, TZValidationResult
from backend.app.services.tz_templates import tz_template_service


class TZValidationService:
    def validate(self, document: TZDocument) -> TZValidationResult:
        issues: list[TZValidationIssue] = []
        data = document.input_data
        stages = [str(v) for v in (document.requisites.get("stages") or [])]

        required = {
            "object_name": (document.object_name, "Объект работ"),
            "customer_name": (document.customer_name, "Заказчик"),
            "goal": (data.goal, "Цель работ"),
            "deadline": (data.deadline, "Плановый срок"),
        }
        for field, (value, label) in required.items():
            if not value or not str(value).strip():
                issues.append(TZValidationIssue(
                    code=f"missing_{field}", severity="high", field=field,
                    title=f"Не заполнено: {label}",
                    message=f"Поле «{label}» обязательно для проверенного ТЗ.",
                    recommendation=f"Заполните поле «{label}».",
                ))

        template = tz_template_service.get_or_default(document.template_key)
        dynamic_required: list[tuple[str, object, str]] = []
        base_keys = set(required)
        for field in template.fields:
            if not field.required or field.key in base_keys:
                continue
            value = document.requisites.get(field.key)
            dynamic_required.append((field.key, value, field.label))
            if value is None or (isinstance(value, str) and not value.strip()):
                issues.append(TZValidationIssue(
                    code=f"missing_template_field_{field.key}", severity="high", field=field.key,
                    title=f"Не заполнено для этого типа ТЗ: {field.label}",
                    message=f"Шаблон «{template.name}» требует поле «{field.label}».",
                    recommendation=f"Заполните поле «{field.label}» в параметрах выбранного типа ТЗ.",
                ))

        if not stages:
            issues.append(TZValidationIssue(
                code="missing_stages", severity="high", field="stages",
                title="Не выбраны этапы", message="Календарный план нельзя рассчитать без этапов.",
                recommendation="Добавьте этапы из пресета выбранного шаблона.",
            ))

        empty_sections = [s for s in document.sections if not s.content.strip()]
        for section in empty_sections:
            issues.append(TZValidationIssue(
                code=f"empty_section_{section.key}", severity="medium", section_key=section.key,
                title=f"Пустой раздел: {section.title}",
                message="Обязательный раздел шаблона не заполнен.",
                recommendation="Заполните вручную или используйте точечное заполнение ИИ.",
            ))

        if data.needs_3d_model and not data.source_data_ready:
            issues.append(TZValidationIssue(
                code="3d_missing_input_data", severity="high", field="source_data_ready",
                title="Нет исходных данных для 3D-модели",
                message="Запрошена 3D-модель, но готовность исходных данных не подтверждена.",
                recommendation="Подтвердите состав исходных данных или исключите 3D-модель.",
            ))
        if data.needs_3d_model and not any("подготов" in s.lower() and "дан" in s.lower() for s in stages):
            issues.append(TZValidationIssue(
                code="3d_without_preparation", severity="medium", field="stages",
                title="Нет этапа подготовки данных",
                message="Для 3D-модели в плане отсутствует подготовка данных.",
                recommendation="Добавьте этап подготовки и проверки исходных данных.",
            ))

        executor = (document.executor_name or "").lower()
        if data.requires_subcontractor:
            if data.subcontract_share_percent is None:
                issues.append(TZValidationIssue(
                    code="subcontract_share_missing", severity="medium", field="subcontract_share_percent",
                    title="Не указана доля субподряда", message="Нельзя проверить договорный лимит.",
                    recommendation="Укажите долю субподряда в процентах.",
                ))
            if any(v in executor for v in ("hnt", "хантос")) and (data.subcontract_share_percent or 0) > 70:
                issues.append(TZValidationIssue(
                    code="subcontract_limit", severity="high", field="subcontract_share_percent",
                    title="Превышен лимит субподряда 70%", message="Для Хантос/HNT доля превышает допустимый лимит.",
                    recommendation="Снизьте долю до 70% или выберите другого исполнителя.",
                ))
            if any(v in executor for v in ("mng", "мегион")):
                issues.append(TZValidationIssue(
                    code="subcontract_forbidden", severity="high", field="requires_subcontractor",
                    title="Субподряд запрещён", message="Для Мегионнефтегаз/MNG работы выполняются без субподряда.",
                    recommendation="Отключите субподряд или выберите другого исполнителя.",
                ))
            if any(v in executor for v in ("ang", "ангара")) and not data.separate_subcontract_estimate:
                issues.append(TZValidationIssue(
                    code="missing_subcontract_rs", severity="high", field="separate_subcontract_estimate",
                    title="Нужен отдельный РС субподряда", message="Для Ангары требуется отдельный расчёт стоимости.",
                    recommendation="Включите отдельный РС по субподрядным работам.",
                ))

        field_values = [value for value, _ in required.values()] + [value for _, value, _ in dynamic_required]
        field_ratio = sum(value is not None and (not isinstance(value, str) or bool(value.strip())) for value in field_values) / len(field_values)
        section_ratio = (len(document.sections) - len(empty_sections)) / len(document.sections) if document.sections else 0
        stage_ratio = 1 if stages else 0
        base_score = round((field_ratio * .40 + section_ratio * .45 + stage_ratio * .15) * 100)
        penalty = sum({"high": 8, "medium": 3, "low": 1}[i.severity] for i in issues)
        score = max(0, min(100, base_score - penalty))
        counts = {severity: sum(i.severity == severity for i in issues) for severity in ("high", "medium", "low")}
        return TZValidationResult(
            valid=counts["high"] == 0 and score >= 70,
            ready_score=score,
            filled_sections=len(document.sections) - len(empty_sections),
            total_sections=len(document.sections),
            issue_counts=counts,
            issues=issues,
        )


tz_validation_service = TZValidationService()
