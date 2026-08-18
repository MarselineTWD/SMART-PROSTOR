"""Справочные данные ПРОСТОР (из xlsx -> БД) и расчёт сроков/роадмапа.

Данные читаются из committed-файла ``backend/app/data/procurement_seed.json``
(тот же, которым засеивается БД миграцией 0003), поэтому расчёт работает и без
БД. По заполненному ТЗ модуль определяет продукт и по расчётам стоимости (РС)
строит для каждого подрядчика оценку срока и роадмап этапов.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "procurement_seed.json"

# Числовая ставка присутствует только в эталонном «Приложении 3. РС.xlsx»:
# 1 000 руб./рабочий день. В каталожной выгрузке перечислены роли и единицы,
# но сами договорные ставки намеренно отсутствуют. Поэтому денежная оценка
# показывается как индикативная и не подменяет согласованный РС.
BASE_DAY_RATE_RUB = 1_000.0
VAT_RATE = 0.22
FTE_PER_ROLE = 0.9
COST_DISCLAIMER = (
    "Индикативная оценка: подрядчик, длительность и роли взяты из XLSX ПРОСТОР; "
    "базовая ставка 1 000 руб./раб. день — из примера Приложения 3. РС. "
    "В выгрузке договорные суммы отсутствуют, перед заказом ставку нужно уточнить."
)

_TOKEN_RE = re.compile(r"[а-яёa-z0-9]+")
# Помогает связать шаблоны ТЗ (демо) с реальными продуктами выгрузки.
_ALIASES = {
    "птд": "проектно технический документ",
    "запас": "проектно технический документ подсчет запасов",
    "опз": "проектно технический документ оперативная",
    "геолог": "концепт геологии",
    "обустройств": "концепт обустройства",
    "развит": "интегрированный концепт развития",
    "заканчиван": "интегрированный концепт заканчивания",
    "сопровожден": "сопровождение инженерных работ",
}


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _pdate(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


# --- Сезонные ограничения выполнения работ -----------------------------------
# Часть нефтесервисных работ можно проводить только в определённые месяцы:
# полевые/сейсморазведочные — по зимникам и промёрзшему грунту, завоз грузов —
# только в навигацию. Планировщик роадмапа сдвигает старт таких этапов к
# ближайшему допустимому месяцу и показывает ожидание сезона на диаграмме Ганта.
# Правила data-driven: ключевые слова матчатся по названию этапа; пользователь
# может переопределить сезон явно через requisites.stage_constraints.
_WINTER_MONTHS = [11, 12, 1, 2, 3]        # ноябрь–март
_NAVIGATION_MONTHS = [6, 7, 8, 9, 10]     # июнь–октябрь

SEASONAL_RULES: list[dict] = [
    {
        "id": "winter-field",
        "season": "winter",
        "allowed_months": _WINTER_MONTHS,
        "label": "Зимний период (зимник), ноя–мар",
        "reason": (
            "Полевые, сейсморазведочные и геологоразведочные работы в "
            "заболоченных районах доступны только по зимникам и промёрзшему "
            "грунту (ноябрь–март)."
        ),
        "keywords": [
            "полев", "сейсморазвед", "сейсмосъ", "сейсмическ съ", "грр",
            "геологоразвед", "изыскан", "рекогносц", "отбор керна", "керноотбор",
            "снегосъ", "аэросъ",
        ],
    },
    {
        "id": "summer-navigation",
        "season": "summer",
        "allowed_months": _NAVIGATION_MONTHS,
        "label": "Летняя навигация, июн–окт",
        "reason": (
            "Доставка грузов и крупногабаритного оборудования водным "
            "транспортом возможна только в период навигации (июнь–октябрь)."
        ),
        "keywords": [
            "навигац", "завоз", "водн транспорт", "баржа", "паром",
            "речн перевоз", "морск перевоз", "доставк оборуд",
        ],
    },
]
_RULES_BY_SEASON = {rule["season"]: rule for rule in SEASONAL_RULES}
_RULES_BY_ID = {rule["id"]: rule for rule in SEASONAL_RULES}
_NO_CONSTRAINT = {"", "none", "нет", "любой", "круглогодично", "year", "any"}


def _resolve_constraint(name: str, override: object | None = None) -> dict | None:
    """Определяет сезонное окно этапа: сначала явный override, затем по названию."""
    if override is not None:
        season = override.get("season") if isinstance(override, dict) else override
        season = str(season or "").strip().lower()
        if season in _NO_CONSTRAINT:
            return None
        rule = _RULES_BY_SEASON.get(season) or _RULES_BY_ID.get(season)
        if rule:
            return rule
    text = (name or "").lower()
    for rule in SEASONAL_RULES:
        if any(keyword in text for keyword in rule["keywords"]):
            return rule
    return None


def _next_allowed_start(current: date, allowed_months: list[int]) -> date:
    """Ближайшая дата ≥ current, попадающая в разрешённые месяцы.

    Если текущий месяц запрещён — переносим старт на 1-е число ближайшего
    допустимого месяца (это и есть простой в ожидании сезона).
    """
    if not allowed_months or current.month in allowed_months:
        return current
    year, month = current.year, current.month
    for _ in range(24):
        month += 1
        if month > 12:
            month, year = 1, year + 1
        if month in allowed_months:
            return date(year, month, 1)
    return current



class ProcurementService:
    def __init__(self) -> None:
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        self.companies = {c["id"]: c for c in seed["companies"]}
        self.contracts = {c["id"]: c for c in seed["contracts"]}
        self.products = {p["id"]: p for p in seed["products"]}
        self.operations_by_product: dict[str, list[str]] = defaultdict(list)
        for o in seed["operations"]:
            self.operations_by_product[o["product_id"]].append(o["operation_name"])
        self.roles_by_product: dict[str, set[str]] = defaultdict(set)
        for p in seed["prices"]:
            if p["price_name"]:
                self.roles_by_product[p["product_id"]].add(p["price_name"])
        self.calcs_by_product: dict[str, list[dict]] = defaultdict(list)
        for c in seed["calcs"]:
            self.calcs_by_product[c["product_id"]].append(c)
        self.stages_by_calc: dict[str, list[dict]] = defaultdict(list)
        for s in seed["stages"]:
            self.stages_by_calc[s["calc_id"]].append(s)
        self._loaded = True

    # --- Вспомогательные расчёты ---------------------------------------------

    def _span_days(self, calc: dict) -> int:
        start, end = _pdate(calc.get("start_date")), _pdate(calc.get("end_date"))
        if start and end:
            return max((end - start).days, 1)
        return max(len(self.stages_by_calc.get(calc["calc_id"], [])) * 30, 30)

    def _build_roadmap(self, calc: dict) -> tuple[int, list[dict]]:
        total = self._span_days(calc)
        stages = sorted(
            self.stages_by_calc.get(calc["calc_id"], []),
            key=lambda s: (s.get("order_num") or 0, s.get("start_date") or ""),
        )
        if not stages:
            return total, []
        weights = []
        for s in stages:
            a, b = _pdate(s.get("start_date")), _pdate(s.get("end_date"))
            days = (b - a).days if a and b else 0
            weights.append(days if days > 0 else 0)
        if sum(weights) == 0:
            weights = [1] * len(stages)
        total_w = sum(weights)
        start = _pdate(calc.get("start_date"))
        out, offset, used = [], 0, 0
        for i, (s, w) in enumerate(zip(stages, weights)):
            days = total - used if i == len(stages) - 1 else max(round(total * w / total_w), 1)
            used += days
            item = {
                "order": i + 1,
                "name": s["name"],
                "days": days,
                "weeks": round(days / 7, 1),
                "offset_days": offset,
                "percent": round(days * 100 / total, 1) if total else 0.0,
                "documentation": s.get("documentation") or "",
            }
            if start:
                item["start_date"] = (start + timedelta(days=offset)).isoformat()
                item["end_date"] = (start + timedelta(days=offset + days)).isoformat()
            out.append(item)
            offset += days
        return total, out

    def _build_tz_roadmap(
        self,
        calc: dict,
        stage_names: list[str],
        plan_start: str | None = None,
        constraints: dict | None = None,
    ) -> tuple[int, list[dict]]:
        """Распределяет срок подрядчика по этапам ТЗ с учётом сезонных окон.

        XLSX используется для оценки общей длительности подрядчика. Названия и
        количество этапов берутся из сохранённого ТЗ, а не из исторического РС.
        Если число исторических и пользовательских этапов совпадает, сохраняем
        исторические пропорции; иначе делим срок поровну и явно не выдумываем
        отсутствующую в исходных данных детализацию.

        Дополнительно: если у этапа есть сезонное ограничение (полевые работы —
        только зимой, завоз — только в навигацию), его старт переносится к
        ближайшему допустимому месяцу. Возникающий простой фиксируется в
        ``gap_days`` — это делает календарный план реалистичным.
        """
        names = [str(name).strip() for name in stage_names if str(name).strip()]
        if not names:
            return self._span_days(calc), []

        constraints = constraints or {}
        total = max(self._span_days(calc), len(names))
        historical = sorted(
            self.stages_by_calc.get(calc["calc_id"], []),
            key=lambda item: (item.get("order_num") or 0, item.get("start_date") or ""),
        )
        weights: list[int] = []
        if len(historical) == len(names):
            for item in historical:
                start, end = _pdate(item.get("start_date")), _pdate(item.get("end_date"))
                weights.append(max((end - start).days, 1) if start and end else 1)
        else:
            weights = [1] * len(names)

        weight_sum = sum(weights)
        start = _pdate(plan_start) or date.today()
        out: list[dict] = []
        remaining = total
        cursor = start
        for index, (name, weight) in enumerate(zip(names, weights)):
            stages_left = len(names) - index - 1
            days = remaining if stages_left == 0 else max(1, round(total * weight / weight_sum))
            days = min(days, remaining - stages_left)

            override = (
                constraints.get(name)
                or constraints.get(str(index))
                or constraints.get(index)
            )
            rule = _resolve_constraint(name, override)
            allowed = list(rule["allowed_months"]) if rule else []
            stage_start = _next_allowed_start(cursor, allowed)
            gap_days = (stage_start - cursor).days
            stage_end = stage_start + timedelta(days=days)

            historical_item = historical[index] if len(historical) == len(names) else {}
            out.append({
                "order": index + 1,
                "name": name,
                "days": days,
                "weeks": round(days / 7, 1),
                "offset_days": (stage_start - start).days,
                "percent": round(days * 100 / total, 1),
                "documentation": historical_item.get("documentation") or "",
                "start_date": stage_start.isoformat(),
                "end_date": stage_end.isoformat(),
                "allowed_months": allowed,
                "constraint_season": rule["season"] if rule else "",
                "constraint_label": rule["label"] if rule else "",
                "constraint_reason": rule["reason"] if rule else "",
                "gap_days": gap_days,
            })
            cursor = stage_end
            remaining -= days
        return total, out


    def _cost_for_calc(self, product_id: str, calc: dict) -> dict:
        total = self._span_days(calc)
        workdays = max(round(total * 5 / 7), 1)
        role_count = max(len(self.roles_by_product.get(product_id, [])), 1)
        average_fte = round(max(role_count * FTE_PER_ROLE, 1.0), 2)
        cost_without_vat = round(workdays * average_fte * BASE_DAY_RATE_RUB, 2)
        return {
            "estimated_days": total,
            "workdays": workdays,
            "role_count": role_count,
            "average_fte": average_fte,
            "cost_without_vat": cost_without_vat,
        }

    def _additional_services(self, product_id: str, company_ids: set[str]) -> list[dict]:
        options: list[dict] = []
        for other_id, calcs in self.calcs_by_product.items():
            if other_id == product_id:
                continue
            name = self.products.get(other_id, {}).get("name") or calcs[0].get("product_name") or other_id
            if name.upper().startswith("НЕАКТУАЛЬНО"):
                continue
            common = sorted(company_ids & {calc["company_id"] for calc in calcs})
            if not common:
                continue
            costs = [
                self._cost_for_calc(other_id, calc)["cost_without_vat"]
                for calc in calcs if calc["company_id"] in common
            ]
            options.append({
                "product_id": other_id,
                "name": name,
                "common_company_count": len(common),
                "role_count": max(len(self.roles_by_product.get(other_id, [])), 1),
                "operation_count": len(self.operations_by_product.get(other_id, [])),
                "min_cost_without_vat": min(costs),
            })
        options.sort(key=lambda item: (-item["common_company_count"], item["min_cost_without_vat"], item["name"]))
        return options[:12]

    # --- Публичное API --------------------------------------------------------

    def list_products(self) -> list[dict]:
        """Продукты, для которых есть расчёты стоимости (можно оценить сроки)."""
        self._load()
        out = []
        for pid, calcs in self.calcs_by_product.items():
            spans = [self._span_days(c) for c in calcs]
            companies = {c["company_id"] for c in calcs}
            out.append({
                "product_id": pid,
                "name": self.products.get(pid, {}).get("name") or calcs[0].get("product_name") or pid,
                "company_count": len(companies),
                "calc_count": len(calcs),
                "operation_count": len(self.operations_by_product.get(pid, [])),
                "min_days": min(spans),
                "max_days": max(spans),
            })
        out.sort(key=lambda r: (-r["company_count"], r["name"]))
        return out

    def estimate_product(
        self,
        product_id: str,
        additional_product_ids: list[str] | None = None,
        *,
        roadmap_stages: list[str] | None = None,
        plan_start: str | None = None,
        roadmap_constraints: dict | None = None,
    ) -> dict | None:
        """Для продукта — срок, роадмап и индикативная стоимость подрядчиков."""
        self._load()
        calcs = self.calcs_by_product.get(product_id)
        if not calcs:
            return None
        by_company: dict[str, list[dict]] = defaultdict(list)
        for c in calcs:
            by_company[c["company_id"]].append(c)

        company_ids = set(by_company)
        available_additional_services = self._additional_services(product_id, company_ids)
        allowed_additional_ids = {item["product_id"] for item in available_additional_services}
        selected_additional_ids = [
            item for item in dict.fromkeys(additional_product_ids or []) if item in allowed_additional_ids
        ]

        companies = []
        product_roles = sorted(self.roles_by_product.get(product_id, []))
        role_count = max(len(product_roles), 1)
        for cid, comp_calcs in by_company.items():
            rep = max(comp_calcs, key=lambda c: (len(self.stages_by_calc.get(c["calc_id"], [])), self._span_days(c)))
            spans = [self._span_days(c) for c in comp_calcs]
            total, roadmap = (
                self._build_tz_roadmap(rep, roadmap_stages, plan_start, roadmap_constraints)
                if roadmap_stages
                else self._build_roadmap(rep)
            )
            info = self.companies.get(cid, {})
            contract = self.contracts.get(rep.get("contract_id") or "", {})
            workdays = max(round(total * 5 / 7), 1)
            average_fte = round(max(role_count * FTE_PER_ROLE, 1.0), 2)
            cost_without_vat = round(workdays * average_fte * BASE_DAY_RATE_RUB, 2)
            base_cost_without_vat = cost_without_vat
            selected_services = []
            for additional_id in selected_additional_ids:
                candidate_calcs = [
                    calc for calc in self.calcs_by_product.get(additional_id, [])
                    if calc["company_id"] == cid
                ]
                if not candidate_calcs:
                    continue
                additional_calc = min(candidate_calcs, key=self._span_days)
                additional_cost = self._cost_for_calc(additional_id, additional_calc)
                additional_name = self.products.get(additional_id, {}).get("name") or additional_calc.get("product_name") or additional_id
                selected_services.append({
                    "product_id": additional_id,
                    "name": additional_name,
                    "estimated_days": additional_cost["estimated_days"],
                    "cost_without_vat": additional_cost["cost_without_vat"],
                })
            additional_cost_without_vat = round(sum(item["cost_without_vat"] for item in selected_services), 2)
            cost_without_vat = round(base_cost_without_vat + additional_cost_without_vat, 2)
            vat_amount = round(cost_without_vat * VAT_RATE, 2)
            for stage in roadmap:
                stage["estimated_cost_without_vat"] = round(
                    base_cost_without_vat * stage["percent"] / 100, 2
                )
            dated_stages = [s for s in roadmap if s.get("start_date") and s.get("end_date")]
            if dated_stages:
                first = dated_stages[0]
                # Истинное начало плана — с учётом простоя перед первым этапом
                # (если старт сдвинут в сезон, ведущее ожидание попадает в план).
                plan_start_dt = _pdate(first["start_date"]) - timedelta(days=int(first.get("gap_days", 0)))
                plan_start_iso = plan_start_dt.isoformat()
                plan_end_iso = max(s["end_date"] for s in dated_stages)
                calendar_days = max((_pdate(plan_end_iso) - plan_start_dt).days, total)
            else:
                plan_start_iso = None
                plan_end_iso = None
                calendar_days = total
            season_wait_days = sum(int(s.get("gap_days", 0)) for s in roadmap)
            companies.append({
                "company_id": cid,
                "company_name": info.get("name", cid),
                "rating": info.get("rating"),
                "info": info.get("info", ""),
                "services": info.get("services", ""),
                "contract_number": contract.get("number", ""),
                "calc_id": rep["calc_id"],
                "calc_name": rep.get("name", ""),
                "estimated_days": total,
                "estimated_weeks": round(total / 7, 1),
                "estimated_months": round(total / 30, 1),
                "min_days": min(spans),
                "max_days": max(spans),
                "variants": len(comp_calcs),
                "stage_count": len(roadmap),
                "stages": roadmap,
                "plan_start": plan_start_iso,
                "plan_end": plan_end_iso,
                "calendar_days": calendar_days,
                "season_wait_days": season_wait_days,
                "workdays": workdays,
                "role_count": role_count,
                "average_fte": average_fte,
                "base_day_rate_rub": BASE_DAY_RATE_RUB,
                "cost_without_vat": cost_without_vat,
                "vat_rate": VAT_RATE,
                "vat_amount": vat_amount,
                "cost_with_vat": round(cost_without_vat + vat_amount, 2),
                "cost_basis": COST_DISCLAIMER,
                "cost_confidence": "indicative",
                "base_cost_without_vat": base_cost_without_vat,
                "additional_cost_without_vat": additional_cost_without_vat,
                "additional_services": selected_services,
            })
        companies.sort(key=lambda r: (r["cost_without_vat"], r["estimated_days"], -(r["rating"] or 0)))

        days = [c["estimated_days"] for c in companies]
        costs = [c["cost_without_vat"] for c in companies]
        summary = {
            "company_count": len(companies),
            "fastest_days": min(days),
            "slowest_days": max(days),
            "average_days": round(sum(days) / len(days)),
            "fastest_company": min(companies, key=lambda c: c["estimated_days"])["company_name"],
            "lowest_cost_without_vat": min(costs),
            "highest_cost_without_vat": max(costs),
            "average_cost_without_vat": round(sum(costs) / len(costs), 2),
            "lowest_cost_company": min(companies, key=lambda c: c["cost_without_vat"])["company_name"],
            "vat_rate": VAT_RATE,
            "cost_disclaimer": COST_DISCLAIMER,
        }
        return {
            "product_id": product_id,
            "product_name": self.products.get(product_id, {}).get("name") or calcs[0].get("product_name") or product_id,
            "operations": self.operations_by_product.get(product_id, []),
            "roles": sorted(self.roles_by_product.get(product_id, [])),
            "companies": companies,
            "summary": summary,
            "available_additional_services": available_additional_services,
            "selected_additional_product_ids": selected_additional_ids,
        }

    def match_products(self, query: str, limit: int = 5) -> list[dict]:
        """Подбор продукта (с расчётами) по свободному запросу/названию ТЗ."""
        self._load()
        q = set(_tokens(query))
        for key, expansion in _ALIASES.items():
            if key in (query or "").lower():
                q |= set(_tokens(expansion))
        scored = []
        for pid in self.calcs_by_product:
            name = self.products.get(pid, {}).get("name", "")
            name_tokens = set(_tokens(name))
            if not name_tokens or not q:
                continue
            overlap = len(q & name_tokens)
            if overlap:
                score = overlap / len(q | name_tokens)
                scored.append({"product_id": pid, "name": name, "score": round(score, 3), "overlap": overlap})
        scored.sort(key=lambda r: (-r["overlap"], -r["score"]))
        return scored[:limit]

    def estimate_for_tz(self, tz, additional_product_ids: list[str] | None = None) -> dict:
        """Строит оценку по этапам ТЗ; каталог нужен только для подбора подрядчиков."""
        user_stages = [
            str(stage).strip()
            for stage in (getattr(tz, "requisites", {}) or {}).get("stages", [])
            if str(stage).strip()
        ]
        query = " ".join(filter(None, [
            getattr(tz, "template_name", "") or "",
            getattr(tz, "title", "") or "",
            (getattr(tz, "object_name", "") or ""),
            (getattr(getattr(tz, "input_data", None), "goal", "") or ""),
        ]))
        matches = self.match_products(query, limit=5)
        estimate = None
        if matches and user_stages:
            requisites = getattr(tz, "requisites", {}) or {}
            stage_constraints = requisites.get("stage_constraints") or {}
            estimate = self.estimate_product(
                matches[0]["product_id"],
                additional_product_ids,
                roadmap_stages=user_stages,
                plan_start=requisites.get("start_date"),
                roadmap_constraints=stage_constraints if isinstance(stage_constraints, dict) else {},
            )
            if estimate:
                estimate["roadmap_source"] = "tz"
                estimate["tz_id"] = getattr(tz, "id", None)
                estimate["tz_title"] = getattr(tz, "title", "") or getattr(tz, "template_name", "")
        return {"query": query, "matched": matches[0] if matches else None,
                "alternatives": matches[1:], "estimate": estimate}


procurement_service = ProcurementService()
