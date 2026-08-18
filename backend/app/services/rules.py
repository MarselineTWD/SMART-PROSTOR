from backend.app.models.domain import DraftDocument, DraftRisk, RequestDraft
from backend.app.services.catalog import catalog_service


class RulesService:
    def evaluate(self, draft: RequestDraft) -> RequestDraft:
        template = catalog_service.get_template_by_product(draft.product_id)
        risks: list[DraftRisk] = []
        filled_required = 0
        total_required = 0

        for section in template.sections:
            for field in section.required_fields:
                total_required += 1
                value = getattr(draft.input_data, field.key, None)
                if self._is_filled(value):
                    filled_required += 1

        if not draft.input_data.object_name:
            risks.append(
                DraftRisk(
                    code="missing_object",
                    severity="high",
                    message="Не указан объект работ.",
                    recommendation="Заполните объект, чтобы корректно сформировать ТЗ и аналоги.",
                )
            )

        if draft.input_data.needs_3d_model and "Подготовка данных" not in draft.stages:
            risks.append(
                DraftRisk(
                    code="3d_without_preparation",
                    severity="medium",
                    message="Запрошена 3D-модель без этапа подготовки данных.",
                    recommendation="Добавьте этап подготовки данных или подтвердите готовность исходных материалов.",
                )
            )

        if draft.input_data.needs_3d_model and not draft.input_data.source_data_ready:
            risks.append(
                DraftRisk(
                    code="3d_missing_input_data",
                    severity="medium",
                    message="Для 3D-модели не подтверждена готовность исходных данных.",
                    recommendation="Уточните состав и готовность исходных данных.",
                )
            )

        if draft.company_id:
            company = catalog_service.get_company(draft.company_id)
            if draft.input_data.requires_subcontractor:
                if company.subcontract_policy == "forbidden":
                    risks.append(
                        DraftRisk(
                            code="subcontract_forbidden",
                            severity="high",
                            message=f"У исполнителя {company.name} субподряд запрещён.",
                            recommendation="Снимите признак субподряда или выберите другого исполнителя.",
                        )
                    )

                if (
                    company.subcontract_policy == "limit_70"
                    and draft.input_data.subcontract_share_percent is None
                ):
                    risks.append(
                        DraftRisk(
                            code="subcontract_share_missing",
                            severity="medium",
                            message="Для проверки лимита субподряда не указана его доля.",
                            recommendation="Заполните процент субподряда, чтобы система проверила лимит 70%.",
                        )
                    )

                if (
                    company.subcontract_policy == "limit_70"
                    and draft.input_data.subcontract_share_percent is not None
                    and draft.input_data.subcontract_share_percent > 70
                ):
                    risks.append(
                        DraftRisk(
                            code="subcontract_limit",
                            severity="high",
                            message="Доля субподряда превышает допустимый лимит 70%.",
                            recommendation="Снизьте долю субподряда или перераспределите объём работ.",
                        )
                    )

                if (
                    company.subcontract_policy == "separate_rs_required"
                    and not draft.input_data.separate_subcontract_estimate
                ):
                    risks.append(
                        DraftRisk(
                            code="missing_subcontract_rs",
                            severity="medium",
                            message="Для субподряда нужен отдельный расчёт стоимости.",
                            recommendation="Добавьте отдельный РС по субподряду в пакет документов.",
                        )
                    )

        completeness_ratio = (filled_required / total_required) if total_required else 0
        penalty = min(len(risks) * 8, 35)
        ready_score = max(int(round(completeness_ratio * 100)) - penalty, 0)

        documents = [
            DraftDocument(kind="tz", status="ready" if ready_score >= 70 else "planned"),
        ]

        draft.risks = risks
        draft.ready_score = ready_score
        draft.documents = documents
        system_note_prefixes = (
            "Заполнено обязательных полей:",
            "Оценка построена эвристически",
        )
        draft.notes = [
            *[
                note
                for note in draft.notes
                if not note.startswith(system_note_prefixes)
            ],
            f"Заполнено обязательных полей: {filled_required} из {total_required}.",
            "Оценка построена эвристически без LLM, что подходит для демо-резерва.",
        ]
        return draft

    @staticmethod
    def _is_filled(value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return bool(value)


rules_service = RulesService()
