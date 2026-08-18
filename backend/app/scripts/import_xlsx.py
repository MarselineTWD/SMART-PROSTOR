"""Однократный ETL: xlsx-выгрузки ПРОСТОР -> procurement_seed.json.

Использование (из корня репозитория):
    python -m backend.app.scripts.import_xlsx ["папка с xlsx"]

По умолчанию читает «Файлы/Выгрузка из системы». Результат пишется в
backend/app/data/procurement_seed.json и используется миграцией 0003 для
наполнения БД. Требует пакет openpyxl (только для dev-этапа, не в рантайме).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FILES = {
    "companies": "0. Компании.xlsx",
    "contracts": "1. Договоры.xlsx",
    "rs": "2. Договор + РС.xlsx",
    "contract_products": "3. Договор + продукты.xlsx",
    "prices": "4. Продукты + расценки.xlsx",
    "operations": "5. Продукты + Операции.xlsx",
}
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "procurement_seed.json"


def _clean(value):
    if value is None:
        return None
    s = str(value).strip()
    return None if s in ("", "NULL") else s


def _date(value):
    """Извлекает YYYY-MM-DD, устойчиво к кавычкам/мусору в ячейке."""
    v = _clean(value)
    if not v:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}", v.strip("\"'"))
    return match.group(0) if match else None


def _rows(path: Path):
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    header = [str(h) if h is not None else "" for h in rows[0]]
    return [dict(zip(header, r)) for r in rows[1:] if any(v is not None for v in r)]


def build(src: Path) -> dict:
    c0, c1, c2 = _rows(src / FILES["companies"]), _rows(src / FILES["contracts"]), _rows(src / FILES["rs"])
    c3, c4, c5 = _rows(src / FILES["contract_products"]), _rows(src / FILES["prices"]), _rows(src / FILES["operations"])

    products: dict[str, str] = {}
    for source in (c2, c3, c4, c5):
        for r in source:
            pid, name = _clean(r.get("product_id")), _clean(r.get("product_name"))
            if pid and (pid not in products or (name and not products[pid])):
                products[pid] = name or products.get(pid, "")

    calcs: dict[str, dict] = {}
    stages: list[dict] = []
    for r in c2:
        cid = _clean(r.get("calc_id"))
        calcs.setdefault(cid, {
            "calc_id": cid, "company_id": _clean(r.get("company_id")),
            "contract_id": _clean(r.get("contract_id")), "product_id": _clean(r.get("product_id")),
            "product_name": _clean(r.get("product_name")) or "", "name": _clean(r.get("calc_name")) or "",
            "start_date": _date(r.get("calc_start_date")), "end_date": _date(r.get("calc_end_date")),
        })
        stages.append({
            "stage_id": _clean(r.get("stage_id")), "calc_id": cid,
            "parent_stage_id": _clean(r.get("parent_stage_id")), "name": _clean(r.get("stage_name")) or "",
            "start_date": _date(r.get("stage_start_date")), "end_date": _date(r.get("stage_end_date")),
            "order_num": int(r.get("stage_order_num")) if r.get("stage_order_num") is not None else 0,
            "documentation": _clean(r.get("stage_documentation_list")) or "",
        })

    return {
        "companies": [{"id": _clean(r.get("company_id")), "name": _clean(r.get("name")),
                       "info": _clean(r.get("info")) or "", "services": _clean(r.get("services")) or "",
                       "rating": float(r.get("rating")) if r.get("rating") is not None else 0.0} for r in c0],
        "contracts": [{"id": _clean(r.get("contract_id")), "number": _clean(r.get("contract_number")) or "",
                       "company_id": _clean(r.get("company_id"))} for r in c1],
        "products": [{"id": pid, "name": name} for pid, name in sorted(products.items(), key=lambda x: x[1] or "")],
        "contract_products": [{"company_id": _clean(r.get("company_id")), "contract_id": _clean(r.get("contract_id")),
                               "product_id": _clean(r.get("product_id"))} for r in c3],
        "prices": [{"price_id": _clean(r.get("price_id")), "product_id": _clean(r.get("product_id")),
                    "price_name": _clean(r.get("price_name")) or "", "measurement_name": _clean(r.get("measurement_name")) or "",
                    "measurement_type": _clean(r.get("measurement_type")) or ""} for r in c4],
        "operations": [{"operation_id": _clean(r.get("operation_id")), "product_id": _clean(r.get("product_id")),
                        "operation_name": _clean(r.get("operation_name")) or ""} for r in c5],
        "calcs": list(calcs.values()),
        "stages": stages,
    }


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Файлы") / "Выгрузка из системы"
    seed = build(src)
    OUT_PATH.write_text(json.dumps(seed, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")
    for key, value in seed.items():
        print(f"  {key}: {len(value)}")


if __name__ == "__main__":
    main()
