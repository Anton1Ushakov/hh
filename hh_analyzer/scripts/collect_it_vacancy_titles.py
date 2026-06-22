"""
Сбор уникальных названий вакансий по всем ИТ-ролям HH (категория 11).

Алгоритм:
  1. 25 professional_role из «Информационные технологии»
  2. Фильтр period=14 (вакансии за последние 14 дней)
  3. Если вакансий <= 2000 — один запрос по роли
  4. Если > 2000 — дробим только по крупным городам (миллионники), дедуп по id
  5. Считаем уникальные названия

  py -3 scripts/collect_it_vacancy_titles.py
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from hh_api import HHAPIClient, TokenManager  # noqa: E402

IT_CATEGORY_ID = "11"
PERIOD_DAYS = 14
API_PAGE_LIMIT = 2000
MAX_PAGES = 20
PER_PAGE = 100
DEFAULT_JSON = ROOT / "data" / "it_vacancy_titles_all.json"
DEFAULT_CSV = ROOT / "data" / "it_vacancy_titles_all.csv"

# HH area id -> город-миллионник (листовой регион в справочнике areas)
MAJOR_CITY_AREAS: list[tuple[str, str]] = [
    ("1", "Москва"),
    ("2", "Санкт-Петербург"),
    ("4", "Новосибирск"),
    ("3", "Екатеринбург"),
    ("88", "Казань"),
    ("66", "Нижний Новгород"),
    ("104", "Челябинск"),
    ("78", "Самара"),
    ("68", "Омск"),
    ("76", "Ростов-на-Дону"),
    ("99", "Уфа"),
    ("54", "Красноярск"),
    ("26", "Воронеж"),
    ("72", "Пермь"),
    ("24", "Волгоград"),
    ("53", "Краснодар"),
]


def build_client() -> HHAPIClient:
    return HHAPIClient(
        token_manager=TokenManager(
            access_token=os.getenv("HH_ACCESS_TOKEN"),
            refresh_token=os.getenv("HH_REFRESH_TOKEN"),
        )
    )


def get_it_roles(client: HHAPIClient) -> list[dict]:
    return client.get_category_professional_roles(IT_CATEGORY_ID)["roles"]


def ingest_items(
    seen_ids: dict[str, str],
    items,
) -> int:
    """Add vacancy items; return number of newly seen ids."""
    added = 0
    for item in items:
        vid = item["id"]
        if vid in seen_ids:
            continue
        seen_ids[vid] = item["name"]
        added += 1
    return added


def fetch_slice(
    client: HHAPIClient,
    seen_ids: dict[str, str],
    *,
    professional_role: str,
    area: str | None = None,
    period: int = PERIOD_DAYS,
) -> int:
    added = ingest_items(
        seen_ids,
        client.iter_vacancy_items(
            professional_role=professional_role,
            area=area,
            period=period,
            per_page=PER_PAGE,
            max_pages=MAX_PAGES,
        ),
    )
    label = f"role={professional_role} period={period}"
    if area:
        label += f" area={area}"
    if added:
        print(f"    +{added} ({label})", flush=True)
    return added


def fetch_role_vacancies(
    client: HHAPIClient,
    role_id: str,
    role_name: str,
    *,
    period: int = PERIOD_DAYS,
) -> tuple[dict[str, str], dict]:
    """
    Fetch vacancies for one IT role.
    Returns id->name map and metadata.
    """
    seen_ids: dict[str, str] = {}
    meta: dict = {
        "role_id": role_id,
        "role_name": role_name,
        "period": period,
        "strategy": "direct",
        "slices": [],
    }

    total_found = client.get_vacancy_found(
        professional_role=role_id,
        period=period,
    )
    meta["total_found_on_hh"] = total_found

    if total_found <= API_PAGE_LIMIT:
        fetch_slice(client, seen_ids, professional_role=role_id, period=period)
        meta["unique_vacancies"] = len(seen_ids)
        return seen_ids, meta

    meta["strategy"] = "major_cities"
    print(
        f"  >2000 ({total_found}), дробим по {len(MAJOR_CITY_AREAS)} крупным городам...",
        flush=True,
    )

    for area_id, city_name in MAJOR_CITY_AREAS:
        city_found = client.get_vacancy_found(
            professional_role=role_id,
            area=area_id,
            period=period,
        )
        if city_found == 0:
            continue

        slice_info = {
            "area_id": area_id,
            "area_name": city_name,
            "found": city_found,
        }
        if city_found > API_PAGE_LIMIT:
            print(
                f"    ! {city_name} ({area_id}): {city_found} — "
                f"берём первые {API_PAGE_LIMIT}",
                flush=True,
            )
            slice_info["truncated"] = True

        fetch_slice(
            client,
            seen_ids,
            professional_role=role_id,
            area=area_id,
            period=period,
        )
        meta["slices"].append(slice_info)

    meta["unique_vacancies"] = len(seen_ids)
    meta["coverage_note"] = (
        "Роль >2000: собраны только вакансии из крупных городов за period дней"
    )
    return seen_ids, meta


def fetch_all_it_vacancy_titles(
    client: HHAPIClient,
    *,
    role_ids: list[str] | None = None,
    period: int = PERIOD_DAYS,
) -> tuple[Counter[str], list[dict], list[dict], int]:
    roles = get_it_roles(client)
    if role_ids:
        allow = {str(x) for x in role_ids}
        roles = [r for r in roles if str(r["id"]) in allow]

    title_counter: Counter[str] = Counter()
    role_meta: list[dict] = []
    total_unique_ids = 0

    for role in roles:
        rid = str(role["id"])
        rname = role["name"]
        print(f"[{rid}] {rname}", flush=True)

        try:
            seen_ids, meta = fetch_role_vacancies(
                client, rid, rname, period=period
            )
        except Exception as e:
            print(f"  ошибка: {e}", flush=True)
            meta = {"role_id": rid, "role_name": rname, "error": str(e)}
            seen_ids = {}

        for name in seen_ids.values():
            title_counter[name] += 1

        title_counts = Counter(seen_ids.values())
        meta["titles"] = [
            {"name": name, "count": count}
            for name, count in title_counts.most_common()
        ]
        meta["titles_count"] = len(meta["titles"])

        total_unique_ids += len(seen_ids)
        role_meta.append(meta)
        print(
            f"  уник. вакансий: {len(seen_ids)}, "
            f"уник. названий в роли: {len(set(seen_ids.values()))}",
            flush=True,
        )

    return title_counter, roles, role_meta, total_unique_ids


def build_report(
    counter: Counter[str],
    roles: list[dict],
    role_meta: list[dict],
    total_unique_ids: int,
    *,
    period: int = PERIOD_DAYS,
) -> dict:
    titles = [{"name": name, "count": count} for name, count in counter.most_common()]
    return {
        "category": {"id": IT_CATEGORY_ID, "name": "Информационные технологии"},
        "query": {
            "endpoint": "https://api.hh.ru/vacancies",
            "period_days": period,
            "filters": (
                f"professional_role + period={period}; "
                "при >2000 — area по крупным городам"
            ),
            "dedupe_by": "vacancy_id",
            "api_page_limit": API_PAGE_LIMIT,
            "major_city_areas": [
                {"id": aid, "name": name} for aid, name in MAJOR_CITY_AREAS
            ],
        },
        "it_roles": roles,
        "role_collection": role_meta,
        "stats": {
            "roles_scanned": len(roles),
            "unique_vacancies": total_unique_ids,
            "unique_titles": len(counter),
        },
        "titles": titles,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON: {path}")


def save_csv(path: Path, titles: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Название вакансии", "Количество"])
        for row in titles:
            writer.writerow([row["name"], row["count"]])
    print(f"CSV:  {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ИТ-вакансии HH -> уникальные названия (period=14, split по городам)"
    )
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument(
        "--period",
        type=int,
        default=PERIOD_DAYS,
        help=f"Дней с публикации (по умолчанию {PERIOD_DAYS})",
    )
    parser.add_argument(
        "--role",
        action="append",
        dest="roles",
        help="Только указанные professional_role id (можно повторять)",
    )
    parser.add_argument(
        "--from-json",
        type=Path,
        help="Пересобрать CSV из JSON без запросов к API",
    )
    args = parser.parse_args()

    if args.from_json:
        data = json.loads(args.from_json.read_text(encoding="utf-8"))
        save_csv(args.csv, data["titles"])
        print(f"Строк: {len(data['titles'])}")
        return

    client = build_client()
    counter, roles, role_meta, total_unique = fetch_all_it_vacancy_titles(
        client,
        role_ids=args.roles,
        period=args.period,
    )
    data = build_report(
        counter, roles, role_meta, total_unique, period=args.period
    )
    save_json(args.json, data)
    save_csv(args.csv, data["titles"])

    print(
        f"Готово: {data['stats']['unique_vacancies']} уникальных вакансий -> "
        f"{data['stats']['unique_titles']} уникальных названий"
    )


if __name__ == "__main__":
    main()
