from backend.app.data.tz_templates import (
    DEFAULT_TEMPLATE_KEY,
    TZ_TEMPLATES,
    get_template,
    template_for_product,
)
from backend.app.models.domain import TZTemplate


class TZTemplateService:
    """Отдаёт каталог шаблонов ТЗ в доменных моделях."""

    def list_templates(self) -> list[TZTemplate]:
        return [TZTemplate(**tpl) for tpl in TZ_TEMPLATES]

    def get_template(self, key: str) -> TZTemplate | None:
        data = get_template(key)
        return TZTemplate(**data) if data else None

    def get_or_default(self, key: str | None) -> TZTemplate:
        if key:
            found = self.get_template(key)
            if found:
                return found
        return self.get_template(DEFAULT_TEMPLATE_KEY)  # type: ignore[return-value]

    def template_for_product(self, product_id: str | None) -> TZTemplate:
        return TZTemplate(**template_for_product(product_id))


tz_template_service = TZTemplateService()
