"""IT professional roles catalog: logical groups and dictionary loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from title_semantics import group_titles_by_seniority

DEFAULT_DICTIONARY_PATH = Path(__file__).resolve().parent / "data" / "it_vacancy_titles_all.json"
DEFAULT_SKILLS_COUNTS_PATH = Path(__file__).resolve().parent / "data" / "it_skills_counts.json"

IT_ROLE_GROUPS: list[dict[str, Any]] = [
    {
        "id": "development",
        "name": "Разработка и инженерия",
        "description": "Программирование, DevOps, тестирование, сети",
        "role_ids": ["96", "160", "112", "114", "124"],
    },
    {
        "id": "analytics",
        "name": "Аналитика и данные",
        "description": "Бизнес-, системная и продуктовая аналитика, BI, ML",
        "role_ids": ["10", "150", "156", "165", "164", "148", "157"],
    },
    {
        "id": "design",
        "name": "Дизайн и креатив",
        "description": "UI/UX, графика, геймдизайн, арт-дирекшн",
        "role_ids": ["34", "12", "25"],
    },
    {
        "id": "infrastructure",
        "name": "Инфраструктура и поддержка",
        "description": "Администрирование, техподдержка, ИБ",
        "role_ids": ["113", "121", "116"],
    },
    {
        "id": "management",
        "name": "Управление и продукт",
        "description": "Продукт, проекты, руководство, C-level",
        "role_ids": ["73", "36", "104", "107", "125", "155"],
    },
    {
        "id": "content",
        "name": "Документация",
        "description": "Техническое письмо и методология",
        "role_ids": ["126"],
    },
]


def load_it_dictionary(path: Path | None = None) -> dict[str, Any]:
    dictionary_path = path or DEFAULT_DICTIONARY_PATH
    if not dictionary_path.is_file():
        raise FileNotFoundError(f"Dictionary not found: {dictionary_path}")
    return json.loads(dictionary_path.read_text(encoding="utf-8"))


def load_skills_counts(path: Path | None = None) -> dict[str, Any]:
    counts_path = path or DEFAULT_SKILLS_COUNTS_PATH
    if not counts_path.is_file():
        return {}
    return json.loads(counts_path.read_text(encoding="utf-8"))


def _build_role_entry(
    role_id: str,
    meta: dict[str, Any],
    role_names: dict[str, str],
    skills_by_role: dict[str, Any] | None = None,
) -> dict[str, Any]:
    titles = meta.get("titles") or []
    role_name = role_names.get(role_id, meta.get("role_name", role_id))
    seniority_levels = group_titles_by_seniority(titles, role_name=role_name)
    entries_count = sum(level["entries_count"] for level in seniority_levels)
    role_skills = ((skills_by_role or {}).get(role_id) or {}).get("skills") or []
    return {
        "id": role_id,
        "name": role_name,
        "unique_vacancies": int(meta.get("unique_vacancies") or 0),
        "total_found_on_hh": int(meta.get("total_found_on_hh") or 0),
        "strategy": meta.get("strategy"),
        "coverage_note": meta.get("coverage_note"),
        "entries_count": entries_count,
        "seniority_levels": seniority_levels,
        "flat_entries": seniority_levels[0]["entries"] if (
            len(seniority_levels) == 1 and seniority_levels[0].get("inline")
        ) else [],
        "top_skills": role_skills[:15],
        "skills_sample_size": ((skills_by_role or {}).get(role_id) or {}).get(
            "vacancies_with_skills", 0
        ),
    }


def build_grouped_catalog(data: dict[str, Any]) -> dict[str, Any]:
    """Build UI-ready grouped structure from collected dictionary JSON."""
    role_meta_by_id = {
        str(item["role_id"]): item for item in data.get("role_collection", [])
    }
    role_names = {str(role["id"]): role["name"] for role in data.get("it_roles", [])}
    skills_data = load_skills_counts()
    skills_by_role = skills_data.get("by_role") or {}
    assigned: set[str] = set()
    groups: list[dict[str, Any]] = []

    for group in IT_ROLE_GROUPS:
        roles: list[dict[str, Any]] = []
        for role_id in group["role_ids"]:
            assigned.add(role_id)
            meta = role_meta_by_id.get(role_id, {})
            roles.append(_build_role_entry(role_id, meta, role_names, skills_by_role))

        groups.append(
            {
                "id": group["id"],
                "name": group["name"],
                "description": group.get("description", ""),
                "roles": roles,
                "roles_count": len(roles),
                "vacancies_count": sum(role["unique_vacancies"] for role in roles),
                "entries_count": sum(role["entries_count"] for role in roles),
            }
        )

    unassigned = [
        rid for rid in role_names if rid not in assigned
    ]
    if unassigned:
        roles = []
        for role_id in unassigned:
            meta = role_meta_by_id.get(role_id, {})
            roles.append(_build_role_entry(role_id, meta, role_names, skills_by_role))
        groups.append(
            {
                "id": "other",
                "name": "Прочие роли",
                "description": "",
                "roles": roles,
                "roles_count": len(roles),
                "vacancies_count": sum(role["unique_vacancies"] for role in roles),
                "entries_count": sum(role["entries_count"] for role in roles),
            }
        )

    stats = data.get("stats") or {}
    query = data.get("query") or {}
    return {
        "category": data.get("category") or {},
        "period_days": query.get("period_days"),
        "collected_at": data.get("collected_at"),
        "skills_collected_at": skills_data.get("collected_at"),
        "stats": {
            "roles_scanned": stats.get("roles_scanned", len(role_names)),
            "unique_vacancies": stats.get("unique_vacancies", 0),
            "unique_titles": stats.get("unique_titles", 0),
        },
        "groups": groups,
    }
