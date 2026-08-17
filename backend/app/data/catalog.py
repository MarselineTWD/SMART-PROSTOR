from backend.app.models.domain import (
    Company,
    Contract,
    HistoricalCase,
    Product,
    Template,
    TemplateField,
    TemplateSection,
)


COMPANIES: list[Company] = [
    Company(
        id="company-hantos",
        name="Хантос",
        description="Сильный подрядчик по геологии и оценке запасов.",
        rating=4.8,
        product_ids=["product-reserves", "product-geology"],
        subcontract_policy="limit_70",
    ),
    Company(
        id="company-megion",
        name="Мегионнефтегаз",
        description="Исполнитель со строгими правилами по субподряду.",
        rating=4.4,
        product_ids=["product-reserves", "product-concept"],
        subcontract_policy="forbidden",
    ),
    Company(
        id="company-angara",
        name="Ангара",
        description="Исполнитель по концептам развития и обустройства.",
        rating=4.2,
        product_ids=["product-development", "product-concept"],
        subcontract_policy="separate_rs_required",
    ),
]


CONTRACTS: list[Contract] = [
    Contract(
        id="contract-001",
        company_id="company-hantos",
        name="Договор на геологические исследования",
        product_ids=["product-reserves", "product-geology"],
    ),
    Contract(
        id="contract-002",
        company_id="company-megion",
        name="Договор на оценку запасов",
        product_ids=["product-reserves"],
    ),
    Contract(
        id="contract-003",
        company_id="company-angara",
        name="Договор на стратегические концепты",
        product_ids=["product-concept", "product-development"],
    ),
]


PRODUCTS: list[Product] = [
    Product(
        id="product-reserves",
        name="Подсчёт запасов / ПТД",
        summary="Оценка запасов по объекту с подготовкой ТЗ, этапов и пакета расчётов.",
        keywords=["запасы", "птд", "геология", "оценка", "подсчёт"],
        operations=["сбор исходных данных", "геологический анализ", "расчёт запасов", "подготовка отчёта"],
        active_contract_ids=["contract-001", "contract-002"],
        template_id="template-reserves",
        synonyms=["оценить запасы", "подсчет запасов", "reserves"],
    ),
    Product(
        id="product-geology",
        name="Концепт геологии",
        summary="Подготовка геологической концепции для новых и действующих объектов.",
        keywords=["геология", "геологический концепт", "модель", "скважина"],
        operations=["сбор геоданных", "интерпретация", "подготовка концепции"],
        active_contract_ids=["contract-001"],
        template_id="template-geology",
        synonyms=["геологический концепт", "концепция геологии"],
    ),
    Product(
        id="product-concept",
        name="Концепт обустройства",
        summary="Разработка концепта обустройства объекта с вариантной проработкой.",
        keywords=["обустройство", "объект", "3d", "инфраструктура", "варианты"],
        operations=["сбор требований", "вариантное проектирование", "3D-модель", "календарный план"],
        active_contract_ids=["contract-002", "contract-003"],
        template_id="template-concept",
        synonyms=["обустройство", "концепт объекта"],
    ),
    Product(
        id="product-development",
        name="Интегрированный концепт развития",
        summary="Комплексная проработка развития актива с несколькими сценариями.",
        keywords=["развитие", "сценарий", "актив", "интегрированный концепт"],
        operations=["стратегическая сессия", "проектирование сценариев", "оценка эффектов"],
        active_contract_ids=["contract-003"],
        template_id="template-development",
        synonyms=["концепт развития", "стратегия развития"],
    ),
]


TEMPLATES: list[Template] = [
    Template(
        id="template-reserves",
        product_id="product-reserves",
        name="Шаблон ТЗ: Подсчёт запасов / ПТД",
        stage_presets=["Подготовка данных", "Геологический анализ", "Подсчёт запасов", "Отчётность"],
        sections=[
            TemplateSection(
                key="requisites",
                title="Реквизиты заказа",
                required_fields=[
                    TemplateField(key="object_name", label="Объект"),
                    TemplateField(key="customer_name", label="Заказчик"),
                ],
            ),
            TemplateSection(
                key="goal",
                title="Цели и ожидаемый результат",
                required_fields=[
                    TemplateField(key="goal", label="Цель работ"),
                ],
            ),
            TemplateSection(
                key="schedule",
                title="Сроки",
                required_fields=[
                    TemplateField(key="deadline", label="Плановый срок"),
                ],
            ),
        ],
    ),
    Template(
        id="template-geology",
        product_id="product-geology",
        name="Шаблон ТЗ: Концепт геологии",
        stage_presets=["Подготовка данных", "Интерпретация", "Концепция", "Согласование"],
        sections=[
            TemplateSection(
                key="requisites",
                title="Реквизиты заказа",
                required_fields=[
                    TemplateField(key="object_name", label="Объект"),
                    TemplateField(key="customer_name", label="Заказчик"),
                ],
            ),
            TemplateSection(
                key="goal",
                title="Цели",
                required_fields=[TemplateField(key="goal", label="Цель работ")],
            ),
        ],
    ),
    Template(
        id="template-concept",
        product_id="product-concept",
        name="Шаблон ТЗ: Концепт обустройства",
        stage_presets=["Сбор требований", "Вариантная проработка", "3D-модель", "Календарный план"],
        sections=[
            TemplateSection(
                key="requisites",
                title="Реквизиты заказа",
                required_fields=[
                    TemplateField(key="object_name", label="Объект"),
                    TemplateField(key="customer_name", label="Заказчик"),
                ],
            ),
            TemplateSection(
                key="requirements",
                title="Требования к работам",
                required_fields=[
                    TemplateField(key="goal", label="Цель работ"),
                    TemplateField(key="deadline", label="Плановый срок"),
                ],
            ),
        ],
    ),
    Template(
        id="template-development",
        product_id="product-development",
        name="Шаблон ТЗ: Интегрированный концепт развития",
        stage_presets=["Диагностика", "Сценарии", "Экономика", "Рекомендации"],
        sections=[
            TemplateSection(
                key="requisites",
                title="Реквизиты заказа",
                required_fields=[
                    TemplateField(key="object_name", label="Объект"),
                    TemplateField(key="customer_name", label="Заказчик"),
                ],
            ),
            TemplateSection(
                key="strategy",
                title="Стратегические цели",
                required_fields=[TemplateField(key="goal", label="Цель работ")],
            ),
        ],
    ),
]


HISTORICAL_CASES: list[HistoricalCase] = [
    HistoricalCase(
        id="case-001",
        product_id="product-reserves",
        title="Подсчёт запасов по Северному блоку",
        summary="Выполнена оценка запасов с полным циклом подготовки отчёта.",
        company_id="company-hantos",
        object_name="Северный блок",
    ),
    HistoricalCase(
        id="case-002",
        product_id="product-concept",
        title="Концепт обустройства для месторождения Вега",
        summary="Подготовлено 3 варианта инфраструктурного обустройства.",
        company_id="company-angara",
        object_name="Месторождение Вега",
    ),
    HistoricalCase(
        id="case-003",
        product_id="product-development",
        title="Интегрированный концепт развития актива Восток",
        summary="Собраны сценарии развития и сравнительная экономика.",
        company_id="company-angara",
        object_name="Актив Восток",
    ),
]

