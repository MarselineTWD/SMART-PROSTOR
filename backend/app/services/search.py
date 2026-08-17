import re

from backend.app.models.domain import IntentType, SearchContext, SearchResult
from backend.app.services.catalog import catalog_service


INTENT_KEYWORDS: dict[IntentType, set[str]] = {
    "service_search": {"найти", "нужно", "услуга", "сервис", "оценить", "подобрать"},
    "contractor_selection": {"исполнитель", "подрядчик", "компания", "кто", "кому"},
    "similar_cases": {"аналог", "пример", "похож", "кейс"},
    "draft_generation": {"тз", "техзадание", "сформировать", "заявка", "черновик"},
}


class SearchService:
    def detect_intent(self, query: str) -> IntentType:
        tokens = set(self._tokenize(query))
        scores = {
            intent: len(tokens & keywords)
            for intent, keywords in INTENT_KEYWORDS.items()
        }
        return max(scores, key=scores.get) if any(scores.values()) else "service_search"

    def search(self, query: str, limit: int = 3) -> SearchContext:
        tokens = set(self._tokenize(query))
        detected_intent = self.detect_intent(query)
        results: list[SearchResult] = []

        for product in catalog_service.list_products():
            score = 0.0
            reasons: list[str] = []
            product_terms = set(self._tokenize(" ".join([product.name, product.summary, *product.keywords, *product.synonyms])))
            overlap = tokens & product_terms
            if not overlap:
                continue

            if overlap:
                score += len(overlap) * 2.5
                reasons.append(f"Совпали ключевые термины: {', '.join(sorted(overlap))}.")

            if product.active_contract_ids:
                score += 1.5
                reasons.append("Есть активные договоры по продукту.")

            if product.has_operations:
                score += 1.0
                reasons.append("Продукт покрыт операциями для последующей детализации.")

            if product.has_price_rules:
                score += 1.0
                reasons.append("Есть расценки для расчёта стоимости.")

            similar_cases = catalog_service.list_historical_cases(product.id)
            if similar_cases:
                score += min(len(similar_cases), 2)
                reasons.append("Найдены аналогичные выполненные работы.")

            companies = catalog_service.list_product_companies(product.id)
            if companies:
                top_company = companies[0]
                score += top_company.rating / 5
                reasons.append(
                    f"Доступен сильный исполнитель: {top_company.name} с рейтингом {top_company.rating:.1f}."
                )

            if score == 0:
                continue

            results.append(
                SearchResult(
                    product=product,
                    score=round(score, 2),
                    reasons=reasons,
                    recommended_companies=companies[:3],
                    similar_cases=similar_cases[:2],
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        shortlisted = results[:limit]
        if not shortlisted:
            fallback_products = sorted(
                catalog_service.list_products(),
                key=lambda item: len(item.active_contract_ids),
                reverse=True,
            )[:limit]
            shortlisted = [
                SearchResult(
                    product=item,
                    score=1.0,
                    reasons=["Точного совпадения не найдено, показан наиболее востребованный продукт из MVP-периметра."],
                    recommended_companies=catalog_service.list_product_companies(item.id)[:3],
                    similar_cases=catalog_service.list_historical_cases(item.id)[:2],
                )
                for item in fallback_products
            ]

        recommendations = [
            "Сузьте объект и ожидаемый результат, чтобы точнее подобрать шаблон ТЗ.",
            "Выберите исполнителя до генерации черновика, чтобы сразу проверить правила субподряда.",
        ]
        if detected_intent == "draft_generation":
            recommendations.append("После выбора продукта можно сразу перейти к предзаполненному RequestDraft.")

        return SearchContext(
            query=query,
            detected_intent=detected_intent,
            products=shortlisted,
            recommendations=recommendations,
        )

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        normalized = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", " ", text.lower())
        return [token for token in normalized.split() if token]


search_service = SearchService()
