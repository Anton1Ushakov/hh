"""Collect canonical skill counts for all IT roles."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from hh_api import HHAPIClient, TokenManager  # noqa: E402
from skills_catalog import count_canonical_skills, extract_vacancy_skills, get_alias_index  # noqa: E402
from skills_map_data import export_skills_map_json  # noqa: E402
from it_roles_catalog import load_it_dictionary  # noqa: E402

PERIOD_DAYS = 14
VACANCIES_PER_ROLE = 100
DETAIL_LIMIT_PER_ROLE = 25
DEFAULT_OUTPUT = ROOT / "data" / "it_skills_counts.json"


def strip_html(value: str) -> str:
    text = unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", text).strip()


def snippet_text(item: dict) -> str:
    snippet = item.get("snippet") or {}
    parts = [snippet.get("requirement") or "", snippet.get("responsibility") or ""]
    return strip_html(" ".join(parts))


def collect_role_skills(
    client: HHAPIClient,
    role_id: str,
    *,
    period: int,
    alias_index,
) -> dict:
    result = client.search_vacancies_list(
        page=0,
        per_page=VACANCIES_PER_ROLE,
        professional_role=role_id,
        period=period,
        search_everywhere=False,
        search_in_name=True,
    )
    items = result.get("items") or []
    skill_sets: list[set[str]] = []

    for index, item in enumerate(items):
        key_skill_names: list[str] = []
        description_text = ""

        if index < DETAIL_LIMIT_PER_ROLE:
            try:
                detail = client.get_vacancy(str(item["id"]))
                key_skill_names = [
                    skill.get("name", "")
                    for skill in (detail.get("key_skills") or [])
                ]
                description_text = strip_html(detail.get("description") or "")
            except Exception:
                pass

        skills = extract_vacancy_skills(
            key_skill_names=key_skill_names,
            vacancy_name=item.get("name") or "",
            snippet_text=snippet_text(item),
            description_text=description_text,
            alias_index=alias_index,
        )
        if skills:
            skill_sets.append(skills)

    counter = count_canonical_skills(skill_sets)
    return {
        "role_id": role_id,
        "vacancies_scanned": len(items),
        "vacancies_with_skills": len(skill_sets),
        "skills": [
            {"name": name, "count": count}
            for name, count in counter.most_common()
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect IT skills by canonical map")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--period", type=int, default=PERIOD_DAYS)
    parser.add_argument("--role", action="append", dest="roles")
    args = parser.parse_args()

    export_skills_map_json()
    alias_index = get_alias_index()

    client = HHAPIClient(
        token_manager=TokenManager(
            access_token=os.getenv("HH_ACCESS_TOKEN"),
            refresh_token=os.getenv("HH_REFRESH_TOKEN"),
        )
    )

    dictionary = load_it_dictionary()
    role_names = {str(role["id"]): role["name"] for role in dictionary["it_roles"]}
    role_ids = args.roles or [str(role["id"]) for role in dictionary["it_roles"]]

    by_role: dict[str, dict] = {}
    global_counter: Counter[str] = Counter()

    for role_id in role_ids:
        role_name = role_names.get(role_id, role_id)
        print(f"[{role_id}] {role_name}", flush=True)
        role_stats = collect_role_skills(
            client,
            role_id,
            period=args.period,
            alias_index=alias_index,
        )
        role_stats["role_name"] = role_name
        by_role[role_id] = role_stats
        for row in role_stats["skills"]:
            global_counter[row["name"]] += row["count"]
        print(
            f"  scanned={role_stats['vacancies_scanned']} "
            f"with_skills={role_stats['vacancies_with_skills']} "
            f"unique={len(role_stats['skills'])}",
            flush=True,
        )

    payload = {
        "period_days": args.period,
        "skills_map_path": "data/skills_map.json",
        "by_role": by_role,
        "global": [
            {"name": name, "count": count}
            for name, count in global_counter.most_common()
        ],
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
