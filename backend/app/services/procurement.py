"""Справочные данные ПРОСТОР (из xlsx -> БД) и расчёт сроков/стоимости.

Данные читаются из committed-файла ``backend/app/data/procurement_seed.json``
(тот же, которым засеивается БД миграцией 0003), поэтому расчёт работает и без
БД. По заполненному ТЗ модуль определяет продукт, для каждого подрядчика
восстанавливает исторический РС и считает индикативную стоимость и календарь
этапов.

Расчёт стоимости — по «командам» ролей. В выгрузке ставки идут по L2–L5
(грейд специалиста). Мы держим таблицу ставок руб/час по грейдам и синтезируем
команду для продукта: по одному человеку на каждый уникальный грейд.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "procurement_seed.json"


# ---- Ставки по грейду ------------------------------------------------------
# Синтетические, но правдоподобные для нефтесервисного контракта. Данные
# приведены в рублях/час без НДС. Реальные договорные ставки в выгрузке
# ПРОСТОР отсутствуют, поэтому цифры служат ориентиром — не заменяют
# согласованный РС.
GRADE_RATES_RUB_PER_HOUR: dict[str, int] = {
    "L2": 2_500,   # младший специалист
    "L3": 4_500,   # ведущий / старший специалист
    "L4": 7_500,   # эксперт / главный специалист
    "L5": 12_000,  # руководитель проекта / партнёр
}
DEFAULT_GRADE = "L3"
# Полная занятость каждого специалиста на проекте. Меньше 1.0 — реалистично:
# в нефтесервисной проектной работе один эксперт распределяется на несколько
# заказов одновременно.
GRADE_ALLOCATION = {"L2": 0.7, "L3": 0.6, "L4": 0.4, "L5": 0.3}
HOURS_PER_WORKDAY = 8
VAT_RATE = 0.20
WORKDAYS_PER_CALENDAR = 5 / 7

COST_DISCLAIMER = (
    "Индикативная оценка: длительность и состав ролей — из XLSX ПРОСТОР; "
    "ставки руб/час подобраны по грейду специалиста (L2 — 2 500, L3 — 4 500, "
    "L4 — 7 500, L5 — 12 000). Договорные суммы в исходных данных отсутствуют, "
    "перед заказом ставки должны быть подтверждены в РС."
)


_TOKEN_RE = re.compile(r"[а-яёa-z0-9]+")
_GRADE_RE = re.compile(r"\bL([2-5])\b", re.IGNORECASE)

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


def _grade_of(role_name: str) -> str:
    """Классифицирует роль по грейду L2/L3/L4/L5 по имени."""
    if not role_name:
        return DEFAULT_GRADE
    match = _GRADE_RE.search(role_name)
    if match:
        return f"L{match.group(1)}"
    low = role_name.lower()
    if any(k in low for k in ("директор", "партнер", "партнёр", "руководител")):
        return "L5"
    if any(k in low for k in ("эксперт", "главный")):
        return "L4"
    if any(k in low for k in ("старш", "ведущ", "консультант")):
        return "L3"
    return DEFAULT_GRADE


def _rate_for(role_name: str) -> int:
    return GRADE_RATES_RUB_PER_HOUR[_grade_of(role_name)]


def _short_role_label(role_name: str) -> str:
    """Убирает суффикс L2/L3/L4/L5 и возвращает читабельную область работ."""
    if not role_name:
        return "Специалист"
    return _GRADE_RE.sub("", role_name).strip(" -–—") or role_name


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

    # --- Команда и стоимость ------------------------------------------------

    def _team_composition(self, product_id: str) -> list[dict]:
        """Собирает представительную команду продукта: по одному человеку
        на каждый уникальный грейд из имеющихся расценок.
        """
        roles = self.roles_by_product.get(product_id) or set()
        by_grade: dict[str, str] = {}
        # Сохраняем первую встреченную роль для каждого грейда — обычно
        # это осмысленное направление ("Геология и разработка L3" > просто L3).
        for role in sorted(roles):
            grade = _grade_of(role)
            by_grade.setdefault(grade, role)
        if not by_grade:
            # Продукт без расценок — минимальная команда L3.
            by_grade = {DEFAULT_GRADE: "Специалист"}
        # Гарантируем, что в команде есть хотя бы L3 (эксперт по умолчанию).
        by_grade.setdefault(DEFAULT_GRADE, "Специалист")
        team: list[dict] = []
        for grade in ("L2", "L3", "L4", "L5"):
            if grade in by_grade:
                team.append({
                    "grade": grade,
                    "role": _short_role_label(by_grade[grade]),
                    "rate_rub_per_hour": GRADE_RATES_RUB_PER_HOUR[grade],
                    "allocation": GRADE_ALLOCATION[grade],
                })
        return team

    def _cost_breakdown(self, product_id: str, workdays: int) -> dict:
        team = self._team_composition(product_id)
        rows: list[dict] = []
        total_hours = 0
        total_cost = 0.0
        for member in team:
            hours = int(round(workdays * HOURS_PER_WORKDAY * member["allocation"]))
            cost = hours * member["rate_rub_per_hour"]
            total_hours += hours
            total_cost += cost
            rows.append({
                "grade": member["grade"],
                "role": member["role"],
                "rate_rub_per_hour": member["rate_rub_per_hour"],
                "allocation": member["allocation"],
                "hours": hours,
                "cost_rub": round(cost, 2),
            })
        cost_without_vat = round(total_cost, 2)
        vat = round(cost_without_vat * VAT_RATE, 2)
        return {
            "team": rows,
            "total_hours": total_hours,
            "workdays": workdays,
            "cost_without_vat": cost_without_vat,
            "vat_rate": VAT_RATE,
            "vat_amount": vat,
            "cost_with_vat": round(cost_without_vat + vat, 2),
        }

    # --- Длительность и календарь -------------------------------------------

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
    ) -> tuple[int, list[dict]]:
        """Распределяет срок подрядчика по этапам пользовательского ТЗ."""
        names = [str(name).strip() for name in stage_names if str(name).strip()]
        if not names:
            return self._span_days(calc), []

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
        offset = 0
        remaining = total
        for index, (name, weight) in enumerate(zip(names, weights)):
            stages_left = len(names) - index - 1
            days = remaining if stages_left == 0 else max(1, round(total * weight / weight_sum))
            days = min(days, remaining - stages_left)
            historical_item = historical[index] if len(historical) == len(names) else {}
            out.append({
                "order": index + 1,
                "name": name,
                "days": days,
                "weeks": round(days / 7, 1),
                "offset_days": offset,
                "percent": round(days * 100 / total, 1),
                "documentation": historical_item.get("documentation") or "",
                "start_date": (start + timedelta(days=offset)).isoformat(),
                "end_date": (start + timedelta(days=offset + days)).isoformat(),
            })
            offset += days
            remaining -= days
        return total, out

    def _cost_for_calc(self, product_id: str, calc: dict) -> dict:
        total = self._span_days(calc)
        workdays = max(round(total * WORKDAYS_PER_CALENDAR), 1)
        breakdown = self._cost_breakdown(product_id, workdays)
        return {
            "estimated_days": total,
            "workdays": workdays,
            "cost_without_vat": breakdown["cost_without_vat"],
            "vat_amount": breakdown["vat_amount"],
            "cost_with_vat": breakdown["cost_with_vat"],
            "team": breakdown["team"],
            "total_hours": breakdown["total_hours"],
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
        """Продукты, для которых есть расчёты стоимости."""
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
        for cid, comp_calcs in by_company.items():
            rep = max(
                comp_calcs,
                key=lambda c: (len(self.stages_by_calc.get(c["calc_id"], [])), self._span_days(c)),
            )
            spans = [self._span_days(c) for c in comp_calcs]
            total, roadmap = (
                self._build_tz_roadmap(rep, roadmap_stages, plan_start)
                if roadmap_stages
                else self._build_roadmap(rep)
            )
            info = self.companies.get(cid, {})
            contract = self.contracts.get(rep.get("contract_id") or "", {})
            workdays = max(round(total * WORKDAYS_PER_CALENDAR), 1)
            base_breakdown = self._cost_breakdown(product_id, workdays)
            base_cost_without_vat = base_breakdown["cost_without_vat"]
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
                additional_name = (
                    self.products.get(additional_id, {}).get("name")
                    or additional_calc.get("product_name")
                    or additional_id
                )
                selected_services.append({
                    "product_id": additional_id,
                    "name": additional_name,
                    "estimated_days": additional_cost["estimated_days"],
                    "cost_without_vat": additional_cost["cost_without_vat"],
                    "team": additional_cost["team"],
                })
            additional_cost_without_vat = round(sum(item["cost_without_vat"] for item in selected_services), 2)
            cost_without_vat = round(base_cost_without_vat + additional_cost_without_vat, 2)
            vat_amount = round(cost_without_vat * VAT_RATE, 2)
            for stage in roadmap:
                stage["estimated_cost_without_vat"] = round(
                    base_cost_without_vat * stage["percent"] / 100, 2
                )
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
                "workdays": workdays,
                "team": base_breakdown["team"],
                "total_hours": base_breakdown["total_hours"],
                # Совместимость со старой схемой ContractorEstimate:
                "role_count": len(base_breakdown["team"]),
                "average_fte": round(
                    sum(member["allocation"] for member in base_breakdown["team"]), 2
                ),
                "base_day_rate_rub": (
                    round(base_cost_without_vat / (workdays * HOURS_PER_WORKDAY), 2)
                    if workdays else 0
                ),
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
            estimate = self.estimate_product(
                matches[0]["product_id"],
                additional_product_ids,
                roadmap_stages=user_stages,
                plan_start=(getattr(tz, "requisites", {}) or {}).get("start_date"),
            )
            if estimate:
                estimate["roadmap_source"] = "tz"
                estimate["tz_id"] = getattr(tz, "id", None)
                estimate["tz_title"] = getattr(tz, "title", "") or getattr(tz, "template_name", "")
        return {"query": query, "matched": matches[0] if matches else None,
                "alternatives": matches[1:], "estimate": estimate}

    def top_contractors_for_tz(self, tz, top: int = 3) -> dict:
        """Топ-N подрядчиков под ТЗ с готовыми данными для диаграммы Ганта.

        Возвращает не сравнительную выборку по цене, а «шорт-лист под тендер»:
        первый — самый быстрый, второй — оптимум цена/срок, третий — самый
        рейтинговый (для сложных объектов). У каждого — календарь этапов,
        разложенный от `plan_start`, и полная стоимость с НДС.
        """
        analysis = self.estimate_for_tz(tz)
        estimate = analysis.get("estimate") or {}
        companies: list[dict] = list(estimate.get("companies") or [])
        if not companies:
            return {
                "tz_id": getattr(tz, "id", None),
                "matched_product": analysis.get("matched"),
                "contractors": [],
                "plan_start": None,
                "cost_disclaimer": COST_DISCLAIMER,
            }

        # Три оси: быстрее всех / дешевле всех / рейтинг.
        by_speed = min(companies, key=lambda c: c["estimated_days"])
        by_price = min(companies, key=lambda c: c["cost_without_vat"])
        by_rating = max(companies, key=lambda c: (c.get("rating") or 0, -c["cost_without_vat"]))

        picks: list[dict] = []
        seen: set[str] = set()
        for label, candidate in (
            ("fastest", by_speed),
            ("cheapest", by_price),
            ("top_rated", by_rating),
        ):
            if candidate["company_id"] in seen:
                continue
            seen.add(candidate["company_id"])
            picks.append({**candidate, "recommendation_reason": label})
            if len(picks) >= top:
                break

        # Добор до `top` — по возрастанию стоимости.
        if len(picks) < top:
            for candidate in sorted(companies, key=lambda c: c["cost_without_vat"]):
                if candidate["company_id"] in seen:
                    continue
                seen.add(candidate["company_id"])
                picks.append({**candidate, "recommendation_reason": "value"})
                if len(picks) >= top:
                    break

        plan_start = (getattr(tz, "requisites", {}) or {}).get("start_date")
        return {
            "tz_id": getattr(tz, "id", None),
            "tz_title": getattr(tz, "title", "") or getattr(tz, "template_name", ""),
            "matched_product": {
                "id": estimate.get("product_id"),
                "name": estimate.get("product_name"),
            },
            "plan_start": plan_start,
            "cost_disclaimer": COST_DISCLAIMER,
            "vat_rate": VAT_RATE,
            "contractors": picks,
        }


procurement_service = ProcurementService()
