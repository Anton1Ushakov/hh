"""Salary range and top skills from a sample of HH vacancies."""

from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any, Optional

from hh_api import HHAPIClient
from skills_catalog import (
    count_canonical_skills,
    extract_vacancy_skills,
    get_alias_index,
    top_skills_payload,
)

SALARY_SAMPLE_PAGES = 1
SALARY_PER_PAGE = 100
SKILL_DETAIL_LIMIT = 12
TOP_SKILLS_LIMIT = 20
MIN_SALARY = 10_000
MAX_SALARY = 10_000_000


def _salary_bounds(salary: Optional[dict[str, Any]]) -> tuple[Optional[int], Optional[int], Optional[str]]:
    if not salary:
        return None, None, None
    currency = salary.get("currency") or "RUR"
    low = salary.get("from")
    high = salary.get("to")
    if low is None and high is None:
        return None, None, currency
    if low is None:
        low = high
    if high is None:
        high = low
    return int(low), int(high), currency


def _filter_salary_values(values: list[int]) -> list[int]:
    return [value for value in values if MIN_SALARY <= value <= MAX_SALARY]


def _percentile(values: list[int], share: float) -> Optional[int]:
    if not values:
        return None
    ordered = sorted(values)
    index = int((len(ordered) - 1) * share)
    return ordered[index]


def _format_money(value: int, currency: str) -> str:
    formatted = f"{value:,}".replace(",", " ")
    symbols = {"RUR": "₽", "USD": "$", "EUR": "€"}
    suffix = symbols.get(currency, currency)
    if suffix in {"$", "€"}:
        return f"{suffix}{formatted}"
    return f"{formatted} {suffix}"


def _format_range(low: int, high: int, currency: str) -> str:
    if low == high:
        return _format_money(low, currency)
    return f"{_format_money(low, currency)} – {_format_money(high, currency)}"


EXPERIENCE_SALARY_BUCKETS: list[dict[str, Any]] = [
    {
        "id": "up_to_1",
        "name": "До 1 года",
        "hh_levels": ["noExperience"],
    },
    {
        "id": "1_to_3",
        "name": "1–3 года",
        "hh_levels": ["between1And3"],
    },
    {
        "id": "3_plus",
        "name": "3–5 лет и более",
        "hh_levels": ["between3And6", "moreThan6"],
    },
]


def _collect_salary_from_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    lows: list[int] = []
    highs: list[int] = []
    currencies: Counter[str] = Counter()
    scanned = len(items)
    with_salary = 0

    for item in items:
        salary = item.get("salary") or item.get("salary_range")
        low, high, currency = _salary_bounds(salary)
        if low is not None and high is not None and currency:
            with_salary += 1
            lows.append(low)
            highs.append(high)
            currencies[currency] += 1

    currency = currencies.most_common(1)[0][0] if currencies else "RUR"
    payload: dict[str, Any] = {
        "currency": currency,
        "sample_size": scanned,
        "with_salary": with_salary,
        "with_salary_percent": round(100 * with_salary / scanned, 1) if scanned else 0,
        "range_from": None,
        "range_to": None,
        "median_from": None,
        "median_to": None,
        "display": None,
        "median_display": None,
    }

    if not lows or not highs:
        return payload

    filtered_lows = _filter_salary_values(lows) or lows
    filtered_highs = _filter_salary_values(highs) or highs
    range_from = _percentile(filtered_lows, 0.1) or min(filtered_lows)
    range_to = _percentile(filtered_highs, 0.9) or max(filtered_highs)
    median_from = int(median(filtered_lows))
    median_to = int(median(filtered_highs))
    payload.update(
        {
            "range_from": range_from,
            "range_to": range_to,
            "median_from": median_from,
            "median_to": median_to,
            "display": _format_range(range_from, range_to, currency),
            "median_display": _format_range(
                min(median_from, median_to),
                max(median_from, median_to),
                currency,
            ),
        }
    )
    return payload


def _fetch_vacancy_items(
    client: HHAPIClient,
    clean_filters: dict[str, Any],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for page in range(SALARY_SAMPLE_PAGES):
        result = client.search_vacancies_list(
            page=page,
            per_page=SALARY_PER_PAGE,
            **clean_filters,
        )
        page_items = result.get("items") or []
        if not page_items:
            break
        items.extend(page_items)
        pages_total = result.get("pages") or 0
        if page + 1 >= pages_total:
            break
    return items


def collect_salary_by_experience(
    client: HHAPIClient,
    clean_filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """Salary ranges per experience bucket."""
    if clean_filters.get("experience"):
        return []

    rows: list[dict[str, Any]] = []
    for bucket in EXPERIENCE_SALARY_BUCKETS:
        merged_items: list[dict[str, Any]] = []
        for hh_level in bucket["hh_levels"]:
            level_filters = {**clean_filters, "experience": hh_level}
            merged_items.extend(_fetch_vacancy_items(client, level_filters))

        stats = _collect_salary_from_items(merged_items)
        rows.append(
            {
                "id": bucket["id"],
                "name": bucket["name"],
                **stats,
            }
        )
    return rows


def collect_vacancy_insights(client: HHAPIClient, **vacancy_filters: Any) -> dict[str, Any]:
    """
    Analyze vacancy list sample for salary spread and top key skills.
    Uses the same filters as the calculator vacancy search.
    """
    clean_filters = {
        key: value
        for key, value in vacancy_filters.items()
        if value is not None and value != ""
    }

    lows: list[int] = []
    highs: list[int] = []
    currencies: Counter[str] = Counter()
    scanned = 0
    with_salary = 0
    detail_ids: list[str] = []
    list_items_by_id: dict[str, dict] = {}
    alias_index = get_alias_index()

    items = _fetch_vacancy_items(client, clean_filters)
    scanned = len(items)
    for item in items:
        salary = item.get("salary") or item.get("salary_range")
        low, high, currency = _salary_bounds(salary)
        if low is not None and high is not None and currency:
            with_salary += 1
            lows.append(low)
            highs.append(high)
            currencies[currency] += 1

        if len(detail_ids) < SKILL_DETAIL_LIMIT:
            vacancy_id = item.get("id")
            if vacancy_id:
                vid = str(vacancy_id)
                detail_ids.append(vid)
                list_items_by_id[vid] = item

    salary_by_experience = collect_salary_by_experience(client, clean_filters)

    skill_sets: list[set[str]] = []
    for vacancy_id in detail_ids:
        item = list_items_by_id.get(vacancy_id, {})
        snippet = item.get("snippet") or {}
        snippet_text = " ".join(
            filter(
                None,
                [
                    (snippet.get("requirement") or ""),
                    (snippet.get("responsibility") or ""),
                ],
            )
        )
        key_skill_names: list[str] = []
        description_text = ""
        try:
            detail = client.get_vacancy(vacancy_id)
            key_skill_names = [
                skill.get("name", "") for skill in (detail.get("key_skills") or [])
            ]
            description_text = detail.get("description") or ""
        except Exception:
            pass

        skills = extract_vacancy_skills(
            key_skill_names=key_skill_names,
            vacancy_name=item.get("name") or "",
            snippet_text=snippet_text,
            description_text=description_text,
            alias_index=alias_index,
        )
        if skills:
            skill_sets.append(skills)

    skill_counter = count_canonical_skills(skill_sets)
    skills_sample = len(skill_sets)

    currency = currencies.most_common(1)[0][0] if currencies else "RUR"
    salary_payload: dict[str, Any] = {
        "currency": currency,
        "sample_size": scanned,
        "with_salary": with_salary,
        "with_salary_percent": round(100 * with_salary / scanned, 1) if scanned else 0,
        "range_from": None,
        "range_to": None,
        "median_from": None,
        "median_to": None,
        "display": None,
    }

    if lows and highs:
        filtered_lows = _filter_salary_values(lows)
        filtered_highs = _filter_salary_values(highs)
        if not filtered_lows:
            filtered_lows = lows
        if not filtered_highs:
            filtered_highs = highs

        range_from = _percentile(filtered_lows, 0.1) or min(filtered_lows)
        range_to = _percentile(filtered_highs, 0.9) or max(filtered_highs)
        median_from = int(median(filtered_lows))
        median_to = int(median(filtered_highs))
        salary_payload.update(
            {
                "range_from": range_from,
                "range_to": range_to,
                "median_from": median_from,
                "median_to": median_to,
                "display": _format_range(range_from, range_to, currency),
                "median_display": _format_range(
                    min(median_from, median_to),
                    max(median_from, median_to),
                    currency,
                ),
            }
        )

    top_skills = top_skills_payload(skill_counter, sample_size=skills_sample, limit=TOP_SKILLS_LIMIT)

    return {
        "sample_size": scanned,
        "skills_sample_size": skills_sample,
        "salary": salary_payload,
        "salary_by_experience": salary_by_experience,
        "top_skills": top_skills,
    }
