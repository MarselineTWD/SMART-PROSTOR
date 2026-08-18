"""Каталог шаблонов технического задания (ТЗ).

Единый источник правды по шаблонам ТЗ. Реализованы все формы из папки
Файлы/Выгрузка из системы/Шаблоны ТЗ — пользователь может переключаться
между ними. Каждый шаблон описывает:

* key           — стабильный идентификатор шаблона;
* name          — человекочитаемое название;
* product_id    — связанный продукт каталога (может быть None);
* description   — краткое пояснение, когда применять;
* stage_presets — типовые этапы работ;
* fields        — реквизиты формы (шапка/подписи);
* sections      — упорядоченные разделы тела ТЗ.

Структура разделов основана на канонической «Форме технического задания»
(Приложение № 2.1) и повторяющейся структуре реальных ТЗ ПТД/концептов.
"""
from __future__ import annotations

from copy import deepcopy


# --- Канонические разделы ТЗ (ключ -> заголовок + подсказка) -----------------

CANONICAL_SECTIONS: dict[str, dict[str, str]] = {
    "goal": {
        "title": "Цели и задачи работ",
        "hint": "Что должно быть достигнуто и какие задачи решаются.",
    },
    "abbreviations": {
        "title": "Принятые сокращения",
        "hint": "Перечень сокращений и терминов, используемых в ТЗ.",
    },
    "scope": {
        "title": "Периметр работ",
        "hint": "Для кого и где выполняются работы, объект и место выполнения.",
    },
    "schedule": {
        "title": "Сроки выполнения работ",
        "hint": "Общие сроки и ссылка на календарный план по этапам.",
    },
    "content": {
        "title": "Содержание работ, особенности их выполнения и результаты",
        "hint": "Перечень работ по этапам с ожидаемыми результатами.",
    },
    "conditions": {
        "title": "Условие выполнения работы",
        "hint": "Исходные данные Заказчика, условия приёмки и отказа.",
    },
    "documentation": {
        "title": "Требования к документации",
        "hint": "Состав, формат и порядок сдачи отчётных материалов.",
    },
    "work_requirements": {
        "title": "Требования к работе",
        "hint": "Стандарты, методики и требования к качеству выполнения.",
    },
    "quality": {
        "title": "Контроль качества",
        "hint": "Методы управления качеством и механизм эскалации.",
    },
    "subcontractors": {
        "title": "Условия привлечения субподрядчиков",
        "hint": "Возможность и лимиты привлечения субисполнителей.",
    },
    "other": {
        "title": "Иные условия выполнения работ",
        "hint": "Особые требования по координации и контролю работ.",
    },
}


# --- Реквизиты формы (общие поля шапки/подписей) -----------------------------

def _field(
    key: str,
    label: str,
    placeholder: str = "",
    required: bool = False,
    *,
    input_type: str = "text",
    options: list[str] | None = None,
    group: str = "Основные данные",
) -> dict:
    return {
        "key": key, "label": label, "placeholder": placeholder, "required": required,
        "input_type": input_type, "options": options or [], "group": group,
    }


COMMON_FIELDS: list[dict] = [
    _field("contract_number", "Номер договора", "{Номер-Договора}", group="Договор"),
    _field("contract_date", "Дата договора", input_type="date", group="Договор"),
    _field("object_name", "Объект / месторождение", "Название месторождения", required=True, group="Объект и стороны"),
    _field("customer_name", "Заказчик (полное наименование)", "АО «...»", required=True, group="Объект и стороны"),
    _field("executor_name", "Исполнитель", "ООО «...»", group="Объект и стороны"),
    _field("city", "Место выполнения работ", "г. Тюмень", group="Объект и стороны"),
    _field("start_date", "Начало работ", input_type="date", group="Сроки договора"),
    _field("end_date", "Окончание работ", input_type="date", group="Сроки договора"),
    _field("signatory_customer", "Подписант Заказчика", "Должность, ФИО", group="Подписание"),
    _field("signatory_executor", "Подписант Исполнителя", "Должность, ФИО", group="Подписание"),
]


def _section(key: str, *, title: str | None = None, hint: str | None = None) -> dict:
    base = CANONICAL_SECTIONS.get(key, {})
    return {
        "key": key,
        "title": title or base.get("title", key),
        "hint": hint or base.get("hint", ""),
        "ai_fillable": True,
    }


# Базовый порядок разделов канонической формы ТЗ.
_BASE_ORDER = [
    "goal",
    "scope",
    "schedule",
    "content",
    "conditions",
    "documentation",
    "quality",
    "subcontractors",
    "other",
]


def _sections(keys: list[str], overrides: dict[str, dict] | None = None) -> list[dict]:
    overrides = overrides or {}
    out: list[dict] = []
    for key in keys:
        ov = overrides.get(key, {})
        out.append(_section(key, title=ov.get("title"), hint=ov.get("hint")))
    return out


# --- Определение шаблонов -----------------------------------------------------

TZ_TEMPLATES: list[dict] = [
    {
        "key": "tz-ptd-reserves",
        "name": "ТЗ: Подсчёт запасов / ПТД",
        "product_id": "product-reserves",
        "description": "Базовый проектно-технический документ по подсчёту запасов объекта.",
        "stage_presets": [
            "Сбор и проверка исходных данных",
            "Геологический анализ",
            "Подсчёт запасов",
            "Подготовка и защита отчёта",
        ],
        "fields": deepcopy(COMMON_FIELDS),
        "sections": _sections(_BASE_ORDER),
    },
    {
        "key": "tz-ptd-new-field",
        "name": "ТЗ ПТД: Пересчёт запасов нового месторождения",
        "product_id": "product-reserves",
        "description": "ПТД для нового месторождения: актуализация моделей и прирост запасов.",
        "stage_presets": [
            "Актуализация геологических моделей",
            "Пересчёт запасов УВС",
            "Сопровождение экспертизы ФБУ «ГКЗ»",
            "Актуализация программы восполнения РБ",
        ],
        "fields": deepcopy(COMMON_FIELDS),
        "sections": _sections(
            ["goal", "abbreviations", *_BASE_ORDER],
            {"content": {"title": "Содержание работ по этапам и ожидаемые результаты"}},
        ),
    },
    {
        "key": "tz-ptd-do",
        "name": "ТЗ ПТД (ДО) 2026",
        "product_id": "product-reserves",
        "description": "Шаблон ПТД для дочерних обществ (ДО), редакция 2026 года.",
        "stage_presets": [
            "Подготовка исходных данных",
            "Геолого-гидродинамическое моделирование",
            "Подсчёт запасов",
            "Отчётность и защита",
        ],
        "fields": deepcopy(COMMON_FIELDS),
        "sections": _sections(_BASE_ORDER),
    },
    {
        "key": "tz-ptd-nng",
        "name": "ТЗ ПТД (ННГ) 2026",
        "product_id": "product-reserves",
        "description": "Шаблон ПТД для периметра ННГ, редакция 2026 года.",
        "stage_presets": [
            "Подготовка исходных данных",
            "Геологическое моделирование",
            "Подсчёт запасов",
            "Отчётность и защита",
        ],
        "fields": deepcopy(COMMON_FIELDS),
        "sections": _sections(_BASE_ORDER),
    },
    {
        "key": "tz-ptd-opz",
        "name": "ТЗ ПТД: Оперативный пересчёт запасов УВС (ОПЗ)",
        "product_id": "product-reserves",
        "description": "Оперативный пересчёт запасов углеводородного сырья по объекту.",
        "stage_presets": [
            "Сбор исходных данных",
            "Оперативный пересчёт запасов",
            "Подготовка ОПЗ",
            "Согласование и защита",
        ],
        "fields": deepcopy(COMMON_FIELDS),
        "sections": _sections(
            ["goal", "scope", "schedule", "content", "conditions",
             "documentation", "work_requirements", "quality", "subcontractors", "other"],
        ),
    },
    {
        "key": "tz-geology-concept",
        "name": "ТЗ: Концепт геологии",
        "product_id": "product-geology",
        "description": "Переобработка и комплексная интерпретация материалов, геологическая концепция.",
        "stage_presets": [
            "Препроцессинг сейсмических данных",
            "Сигнальная обработка",
            "Миграция и построение изображений",
            "Структурная и динамическая интерпретация",
        ],
        "fields": deepcopy(COMMON_FIELDS),
        "sections": _sections(
            _BASE_ORDER,
            {"goal": {"title": "Цели и задачи работ",
                      "hint": "Уточнение строения объекта, коллекторских свойств, прогноз трещиноватости."}},
        ),
    },
    {
        "key": "tz-arrangement-concept",
        "name": "ТЗ: Концепт обустройства",
        "product_id": "product-concept",
        "description": "Разработка концепта обустройства объекта с вариантной проработкой.",
        "stage_presets": [
            "Сбор требований",
            "Вариантная проработка",
            "3D-модель обустройства",
            "Календарный план и оценка",
        ],
        "fields": deepcopy(COMMON_FIELDS),
        "sections": _sections(_BASE_ORDER),
    },
    {
        "key": "tz-integrated-development",
        "name": "ТЗ: Интегрированный концепт развития",
        "product_id": "product-development",
        "description": "Комплексная проработка развития актива с несколькими сценариями.",
        "stage_presets": [
            "Диагностика актива",
            "Проработка сценариев развития",
            "Экономическая оценка",
            "Рекомендации и дорожная карта",
        ],
        "fields": deepcopy(COMMON_FIELDS),
        "sections": _sections(_BASE_ORDER),
    },
    {
        "key": "tz-integrated-completion",
        "name": "ТЗ: Интегрированный концепт заканчивания",
        "product_id": "product-development",
        "description": "Интегрированный концепт заканчивания скважин месторождения.",
        "stage_presets": [
            "Анализ исходных данных",
            "Проработка вариантов заканчивания",
            "Технико-экономическое сравнение",
            "Формирование концепта",
        ],
        "fields": deepcopy(COMMON_FIELDS),
        "sections": _sections(_BASE_ORDER),
    },
    {
        "key": "tz-engineering-support",
        "name": "ТЗ: Сопровождение инженерных работ и высокорисковых операций",
        "product_id": "product-concept",
        "description": "Сопровождение инженерных работ и управление содержанием высокорисковых операций.",
        "stage_presets": [
            "Анализ рисков операций",
            "Разработка форматов и подходов",
            "Сопровождение работ",
            "Отчётность по результатам",
        ],
        "fields": deepcopy(COMMON_FIELDS),
        "sections": _sections(
            ["goal", "scope", "schedule", "content", "conditions",
             "documentation", "work_requirements", "quality", "subcontractors", "other"],
        ),
    },
    {
        "key": "tz-universal",
        "name": "Универсальная форма ТЗ (Приложение № 2.1)",
        "product_id": None,
        "description": "Эталонная форма ТЗ. Подходит для любого продукта, когда нет отдельного шаблона.",
        "stage_presets": [
            "Сбор и проверка исходных данных",
            "Аналитика и моделирование",
            "Подготовка результата",
            "Экспертиза и защита",
        ],
        "fields": deepcopy(COMMON_FIELDS),
        "sections": _sections(
            ["goal", "abbreviations", "scope", "schedule", "content",
             "conditions", "documentation", "quality", "subcontractors", "other"],
        ),
    },
]


DEFAULT_TEMPLATE_KEY = "tz-universal"


_TEMPLATE_SOURCE_FILES = {
    "tz-ptd-reserves": ["Прил 1_ТЗ_ПТД.docx"],
    "tz-ptd-new-field": ["Приложение 1. ТЗ (ПЗ Нового м-я).docx"],
    "tz-ptd-do": ["Приложение 1. ТЗ (шаблон ПТД ДО)_2026.docx"],
    "tz-ptd-nng": ["Приложение 1. ТЗ (шаблон ПТД ННГ)_2026.docx"],
    "tz-ptd-opz": ["Приложение 3. ТЗ ПТД_ОПЗ УВС Песц НГКМ.docx"],
    "tz-geology-concept": ["ТЗ Концепт геологии.docx"],
    "tz-arrangement-concept": ["ТЗ Концепт обустройства.docx"],
    "tz-integrated-development": ["ТЗ Интегрированный концепт развития.docx"],
    "tz-integrated-completion": ["ТЗ Интегрированный концепт заканчивания.docx"],
    "tz-engineering-support": ["ТЗ Сопровождение инженерных работ и высокорисковых операций.docx"],
    "tz-universal": ["Приложение № 2.1 Форма Технического задания.docx", "Приложение 1. ТЗ.docx"],
}

for _template in TZ_TEMPLATES:
    _template["source_files"] = _TEMPLATE_SOURCE_FILES.get(_template["key"], [])


_TEMPLATE_EXTRA_FIELDS = {
    "tz-ptd-reserves": [
        _field("reserve_standard", "Стандарт оценки запасов", required=True, input_type="select", options=["ГКЗ РФ", "SEC", "PRMS"], group="Параметры ПТД"),
        _field("license_area", "Лицензионный участок", "Наименование участка", group="Параметры ПТД"),
        _field("model_dimension", "Тип модели", input_type="select", options=["2D", "3D"], group="Параметры ПТД"),
    ],
    "tz-ptd-new-field": [
        _field("field_maturity", "Стадия изученности месторождения", input_type="select", options=["Поисковая", "Разведочная", "Опытно-промышленная"], group="Новое месторождение"),
        _field("reserve_standard", "Стандарт оценки запасов", required=True, input_type="select", options=["ГКЗ РФ", "SEC", "PRMS"], group="Новое месторождение"),
    ],
    "tz-ptd-do": [
        _field("subsidiary_name", "Дочернее общество", required=True, group="Периметр ДО"),
        _field("corporate_standard", "Корпоративный стандарт", "Шифр НМД", group="Периметр ДО"),
    ],
    "tz-ptd-nng": [
        _field("asset_code", "Код актива ННГ", required=True, group="Периметр ННГ"),
        _field("reserve_standard", "Стандарт оценки запасов", input_type="select", options=["ГКЗ РФ", "SEC", "PRMS"], group="Периметр ННГ"),
    ],
    "tz-ptd-opz": [
        _field("recalculation_reason", "Основание оперативного пересчёта", required=True, input_type="textarea", group="Параметры ОПЗ"),
        _field("regulator_deadline", "Срок подачи регулятору", input_type="date", group="Параметры ОПЗ"),
    ],
    "tz-geology-concept": [
        _field("study_area_km2", "Площадь исследований, км²", input_type="number", group="Геологические параметры"),
        _field("target_horizons", "Целевые горизонты", "Пласты и интервалы", required=True, group="Геологические параметры"),
        _field("interpretation_depth", "Глубина интерпретации, м", input_type="number", group="Геологические параметры"),
    ],
    "tz-arrangement-concept": [
        _field("concept_variants", "Количество вариантов концепта", input_type="number", required=True, group="Вариантная проработка"),
        _field("infrastructure_scope", "Объекты инфраструктуры", input_type="textarea", group="Вариантная проработка"),
    ],
    "tz-integrated-development": [
        _field("scenario_count", "Количество сценариев развития", input_type="number", required=True, group="Сценарный анализ"),
        _field("economic_horizon", "Горизонт оценки, лет", input_type="number", group="Сценарный анализ"),
    ],
    "tz-integrated-completion": [
        _field("well_count", "Количество скважин", input_type="number", required=True, group="Заканчивание"),
        _field("completion_type", "Тип заканчивания", input_type="select", options=["Открытый ствол", "Обсаженный ствол", "Многостадийный ГРП", "Комбинированный"], group="Заканчивание"),
    ],
    "tz-engineering-support": [
        _field("risk_level", "Уровень риска операций", required=True, input_type="select", options=["Средний", "Высокий", "Критический"], group="Риск-профиль"),
        _field("supervision_mode", "Формат сопровождения", input_type="select", options=["Очный", "Удалённый", "Гибридный"], group="Риск-профиль"),
        _field("operation_window", "Окно проведения операции", input_type="date", group="Риск-профиль"),
    ],
    "tz-universal": [
        _field("work_basis", "Основание выполнения работ", input_type="textarea", group="Дополнительные реквизиты"),
        _field("result_format", "Формат итогового результата", input_type="select", options=["Отчёт", "Модель", "Заключение", "Комплект документов"], group="Дополнительные реквизиты"),
    ],
}

_TEMPLATE_EXAMPLES = {
    key: {
        "title": template["name"].replace("ТЗ: ", ""),
        "object_name": "Месторождение Северное",
        "customer_name": "Блок геологии и разработки",
        "goal": template["description"],
        "deadline": "2026-12-20",
        "stages": template["stage_presets"],
        "result": f"Заполненное ТЗ по форме «{template['name']}» с проверенными реквизитами, этапами и ожидаемыми результатами.",
    }
    for key, template in ((item["key"], item) for item in TZ_TEMPLATES)
}

for _template in TZ_TEMPLATES:
    _template["fields"].extend(deepcopy(_TEMPLATE_EXTRA_FIELDS.get(_template["key"], [])))
    _template["example"] = deepcopy(_TEMPLATE_EXAMPLES[_template["key"]])


def get_template(key: str) -> dict | None:
    for tpl in TZ_TEMPLATES:
        if tpl["key"] == key:
            return deepcopy(tpl)
    return None


def template_for_product(product_id: str | None) -> dict:
    if product_id:
        for tpl in TZ_TEMPLATES:
            if tpl["product_id"] == product_id:
                return deepcopy(tpl)
    return get_template(DEFAULT_TEMPLATE_KEY)  # type: ignore[return-value]
