"""Extract the "Требования к работе" section from ТЗ docx templates and
build a normalized normative-acts fixture.

Runs once during development. Output:
    backend/app/data/normative_acts_seed.json

Format:
{
  "acts": [
    {
      "id": "<slug>",
      "document_type": "ФЗ|Приказ|Постановление|ГОСТ|СТО|СК|МД|Методические рекомендации|Правила|Прочее",
      "authority": "<издатель, best-effort>",
      "number": "<номер, best-effort>",
      "date_issued": "YYYY-MM-DD | null",
      "title": "<полный текст акта, как в docx>",
      "short_title": "<первые 120 символов для UI>",
      "url": null
    },
    ...
  ],
  "template_links": [
    {"template_key": "tz-ptd-reserves", "act_id": "...", "sort_order": 1},
    ...
  ]
}
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from docx import Document


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = PROJECT_ROOT / "Файлы" / "Выгрузка из системы" / "Шаблоны ТЗ"
OUT_PATH = PROJECT_ROOT / "backend" / "app" / "data" / "normative_acts_seed.json"

# Filename -> template_key in backend/app/data/tz_templates.py
FILE_TO_TEMPLATE_KEY: dict[str, str] = {
    "Прил 1_ТЗ_ПТД.docx": "tz-ptd-reserves",
    "Приложение 1. ТЗ (ПЗ Нового м-я).docx": "tz-ptd-new-field",
    "Приложение 1. ТЗ (шаблон ПТД ДО)_2026.docx": "tz-ptd-do",
    "Приложение 1. ТЗ (шаблон ПТД ННГ)_2026.docx": "tz-ptd-nng",
    "Приложение 3. ТЗ ПТД_ОПЗ УВС Песц НГКМ.docx": "tz-ptd-opz",
    "ТЗ Интегрированный концепт заканчивания.docx": "tz-integrated-completion",
    "ТЗ Интегрированный концепт развития.docx": "tz-integrated-development",
    "ТЗ Концепт геологии.docx": "tz-geology-concept",
    "ТЗ Концепт обустройства.docx": "tz-arrangement-concept",
    "ТЗ Сопровождение инженерных работ и высокорисковых операций.docx": "tz-engineering-support",
}

# Markers signalling start of the normative section (comparison is done on
# text stripped of leading numbering and lowercased). Different template
# authors use different section wording, so we cover the common variants.
START_MARKERS = (
    "требования к работе",
    "должны отвечать требованиям",
    "в соответствии со следующими документами",
    "в соответствии со следующими нормативными",
    "нормативные документы",
    "перечень нормативных",
)
# Markers that end it.
END_MARKERS = (
    "требования к документации",
    "требования к распечатанной",
    "контроль качества",
    "условия привлечения субподряд",
    "условия привлечения субисполнителей",
    "иные условия",
    "порядок привлечения субподряд",
    "порядок сдачи",
    "подписи сторон",
)

# Heuristic — a paragraph is a normative act if it contains any of these tokens.
ACT_TOKENS = [
    "закон рф",
    "закон ",
    "постановление правительства",
    "постановление ",
    "приказ ",
    "распоряжение ",
    "гост ",
    "снип ",
    "санпин",
    "рд ",
    "стандарт компании",
    "методические рекомендации",
    "методические указания",
    "правила ",
    "требования к",
    "классификация запасов",
    "инструкция",
    "положение о",
    "мд м-",
    "мд р",
    "сто ",
    "ост ",
    "пнст ",
    "нмд ",
    "фед. закон",
]

DATE_RE = re.compile(r"(\d{1,2})[.\-\s](\d{1,2})[.\-\s](\d{4})")
NUMBER_RE = re.compile(r"№\s*([A-ZА-Я0-9\-./ ]+?)(?=[«\"\s,;])", re.IGNORECASE)
GOST_RE = re.compile(r"(ГОСТ(?:\s+Р)?)\s+([0-9]+[-–][0-9]+)")
SK_RE = re.compile(r"(?:СК|CТО|СТО|МД)[\s-]?([A-ZА-Я0-9\-.]+)", re.IGNORECASE)


def _classify(text: str) -> tuple[str, str | None]:
    """Return (document_type, authority) from the leading words of the act."""
    low = text.lower().strip()
    if low.startswith("гост"):
        return "ГОСТ", "Росстандарт"
    if low.startswith("снип"):
        return "СНиП", None
    if low.startswith("санпин"):
        return "СанПиН", "Роспотребнадзор"
    if low.startswith("постановление правительства"):
        return "Постановление", "Правительство РФ"
    if low.startswith("постановление"):
        return "Постановление", None
    if low.startswith("приказ мпр") or low.startswith("приказ министерства природ"):
        return "Приказ", "Минприроды РФ"
    if low.startswith("приказ"):
        return "Приказ", None
    if low.startswith("распоряжение"):
        return "Распоряжение", None
    if low.startswith("закон рф") or low.startswith("федеральный закон") or low.startswith("фед. закон"):
        return "ФЗ", None
    if "стандарт компании" in low and "газпром" in low:
        return "СК", "ПАО «Газпром нефть»"
    if low.startswith("сто"):
        return "СТО", None
    if low.startswith("мд м-") or low.startswith("мд р-") or low.startswith("мд "):
        return "МД", "ПАО «Газпром нефть»"
    if "методические рекомендации" in low:
        return "Методические рекомендации", None
    if "методические указания" in low:
        return "Методические указания", None
    if low.startswith("классификация запасов"):
        return "Методические рекомендации", "ЕСОЭН"
    if low.startswith("правил"):
        return "Правила", None
    if low.startswith("требования к"):
        return "Требования", None
    if low.startswith("инструкция"):
        return "Инструкция", None
    if low.startswith("положение"):
        return "Положение", None
    return "Прочее", None


def _extract_date(text: str) -> str | None:
    m = DATE_RE.search(text)
    if not m:
        return None
    d, mo, y = map(int, m.groups())
    if not (1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2100):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


def _extract_number(text: str, doc_type: str) -> str | None:
    if doc_type == "ГОСТ":
        m = GOST_RE.search(text)
        if m:
            return m.group(2)
    m = NUMBER_RE.search(text)
    if m:
        return m.group(1).strip()
    # СК / МД / СТО style numbers like "СК-01.01.04.01.03"
    for prefix in ("СК-", "МД М-", "МД Р-", "СТО-", "МД "):
        idx = text.find(prefix)
        if idx >= 0:
            tail = text[idx + len(prefix):]
            end = re.search(r"[\s«\"\.,]", tail)
            return (tail[:end.start()] if end else tail).strip(" .,;:") or None
    return None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).strip(" .,;:—-")


def _slug(text: str) -> str:
    normalized = _clean(text).lower()
    h = hashlib.blake2s(normalized.encode("utf-8"), digest_size=8).hexdigest()
    return f"act-{h}"


def _looks_like_act(text: str) -> bool:
    low = text.lower()
    if len(low) < 15 or len(low) > 700:
        return False
    if any(tok in low for tok in ACT_TOKENS):
        return True
    # Fallback: has «...» and either "от" or "№" or 4-digit year
    if ("«" in text or "\"" in text) and re.search(r"(№|\bот\b|\b(19|20)\d{2}\b)", text):
        return True
    return False


def _in_normative_section(text: str) -> tuple[bool, bool]:
    """Return (is_start_marker, is_end_marker)."""
    low = text.lower().strip(" .:0123456789")
    # Start marker can appear either as a bare heading or as an intro clause
    # inside a longer sentence ("Материалы должны отвечать требованиям...").
    start = any(m in low for m in START_MARKERS)
    end = any(low.startswith(m) for m in END_MARKERS)
    return start, end


def _parse_docx(path: Path) -> list[str]:
    doc = Document(path)
    acts_raw: list[str] = []
    in_section = False
    for para in doc.paragraphs:
        text = _clean(para.text)
        if not text:
            continue
        is_start, is_end = _in_normative_section(text)
        if is_end and in_section:
            break
        if is_start:
            in_section = True
            continue
        if in_section and _looks_like_act(text):
            acts_raw.append(text)
    return acts_raw


def _structured(text: str) -> dict[str, Any]:
    doc_type, authority = _classify(text)
    return {
        "document_type": doc_type,
        "authority": authority,
        "number": _extract_number(text, doc_type),
        "date_issued": _extract_date(text),
        "title": text,
        "short_title": (text[:117] + "…") if len(text) > 120 else text,
        "url": None,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(message)s")

    acts_by_id: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []

    for filename, template_key in FILE_TO_TEMPLATE_KEY.items():
        path = TEMPLATE_DIR / filename
        if not path.exists():
            logger.warning("skip: %s (файл не найден)", filename)
            continue

        raw_acts = _parse_docx(path)
        logger.info("%s -> %d актов (шаблон %s)", filename, len(raw_acts), template_key)

        seen_in_template: set[str] = set()
        for sort_order, raw in enumerate(raw_acts, start=1):
            act_id = _slug(raw)
            if act_id not in acts_by_id:
                acts_by_id[act_id] = {"id": act_id, **_structured(raw)}
            if act_id in seen_in_template:
                continue  # тот же акт продублирован в одном шаблоне — пропускаем
            seen_in_template.add(act_id)
            links.append({
                "template_key": template_key,
                "act_id": act_id,
                "sort_order": sort_order,
            })

    result = {
        "acts": sorted(acts_by_id.values(), key=lambda a: a["title"]),
        "template_links": links,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    logger.info(
        "готово: %d уникальных актов, %d связей шаблон↔акт → %s",
        len(result["acts"]),
        len(result["template_links"]),
        OUT_PATH.relative_to(PROJECT_ROOT),
    )


if __name__ == "__main__":
    main()
