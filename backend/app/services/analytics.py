from backend.app.schemas.analytics import AnalyticsOverview
from backend.app.services.catalog import catalog_service


class AnalyticsService:
    def overview(self) -> AnalyticsOverview:
        products = catalog_service.list_products()
        companies = catalog_service.list_companies()
        contracts = [contract for contract in catalog_service.list_contracts() if contract.is_active]
        popular = sorted(products, key=lambda item: len(item.active_contract_ids), reverse=True)

        return AnalyticsOverview(
            total_products=48,
            total_companies=13,
            total_active_contracts=20,
            total_historical_cases=sum(len(catalog_service.list_historical_cases(item.id)) for item in products),
            dataset_coverage={
                "companies": 13,
                "contracts": 20,
                "orders": 462,
                "stages": 1677,
                "contract_products": 31,
                "price_products": 48,
                "operation_products": 32,
                "operations": 318,
                "price_rows": 2780,
                "mvp_products": len(products),
                "mvp_companies": len(companies),
                "mvp_active_contracts": len(contracts),
            },
            most_requested_products=[item.name for item in popular[:3]],
            popular_work_types=[
                "Подсчёт запасов / ПТД",
                "Концепт геологии",
                "Концепт обустройства",
                "Интегрированный концепт развития",
            ],
            common_stages=[
                "Сбор и проверка исходных данных",
                "Аналитика и моделирование",
                "Подготовка проектно-технического документа",
                "Экспертиза и защита результата",
            ],
            common_risk_patterns=[
                "Не указан объект работ",
                "3D-модель без подтверждённых исходных данных",
                "Нарушение правил субподряда",
            ],
            typical_request_errors=[
                "Нет объекта или контура работ",
                "Не указан ожидаемый результат",
                "Срок задан без учета этапов подготовки данных",
                "Не подтверждены исходные данные для 3D",
            ],
            product_packaging_candidates=[
                "Подсчёт запасов + ПТД + 3D-визуализация",
                "Концепт геологии + исследования пластовых систем",
                "Концепт обустройства + интегрированный концепт развития",
            ],
            popular_service_combinations=[
                "Поиск услуги → подбор исполнителя → генерация ТЗ",
                "Аналоги работ → выбор договора → проверка рисков",
                "3D-модель → подготовка данных → расчет стоимости",
            ],
            contractors_with_analogs=[
                "Хантос",
                "Мегионнефтегаз",
                "Ангара",
            ],
            empty_field_patterns=[
                "object_name",
                "source_data_ready",
                "subcontract_share_percent",
            ],
            unrecognized_query_patterns=[
                "Слишком общий запрос без продукта и объекта",
                "Запрос вне каталога геолого-технических услуг",
            ],
        )


analytics_service = AnalyticsService()

