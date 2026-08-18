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

    def estimate_product(self, product_id: str) -> dict | None:
        """Для продукта — оценка срока и роадмап по каждому подрядчику."""
        self._load()
        calcs = self.calcs_by_product.get(product_id)
        if not calcs:
            return None
        by_company: dict[str, list[dict]] = defaultdict(list)
        for c in calcs:
            by_company[c["company_id"]].append(c)

        companies = []
        for cid, comp_calcs in by_company.items():
            rep = max(comp_calcs, key=lambda c: (len(self.stages_by_calc.get(c["calc_id"], [])), self._span_days(c)))
            spans = [self._span_days(c) for c in comp_calcs]
            total, roadmap = self._build_roadmap(rep)
            info = self.companies.get(cid, {})
            contract = self.contracts.get(rep.get("contract_id") or "", {})
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
            })
        companies.sort(key=lambda r: (r["estimated_days"], -(r["rating"] or 0)))

        days = [c["estimated_days"] for c in companies]
        summary = {
            "company_count": len(companies),
            "fastest_days": min(days),
            "slowest_days": max(days),
            "average_days": round(sum(days) / len(days)),
            "fastest_company": companies[0]["company_name"],
        }
        return {
            "product_id": product_id,
            "product_name": self.products.get(product_id, {}).get("name") or calcs[0].get("product_name") or product_id,
            "operations": self.operations_by_product.get(product_id, []),
            "roles": sorted(self.roles_by_product.get(product_id, [])),
            "companies": companies,
            "summary": summary,
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

    def estimate_for_tz(self, tz) -> dict:
        """По ТЗ подобрать продукт и вернуть оценку + альтернативы."""
        query = " ".join(filter(None, [
            getattr(tz, "template_name", "") or "",
            getattr(tz, "title", "") or "",
            (getattr(tz, "object_name", "") or ""),
        ]))
        matches = self.match_products(query, limit=5)
        estimate = self.estimate_product(matches[0]["product_id"]) if matches else None
        return {"query": query, "matched": matches[0] if matches else None,
                "alternatives": matches[1:], "estimate": estimate}


procurement_service = ProcurementService()
