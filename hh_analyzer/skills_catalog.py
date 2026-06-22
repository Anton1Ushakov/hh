"""Match vacancy text and HH key_skills to canonical skills map."""

from __future__ import annotations

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

from skills_map_data import DEFAULT_SKILLS_MAP_PATH, SKILLS_MAP, export_skills_map_json

WORD_ALIAS_MIN_LEN = 3
SHORT_EXACT_ALIASES = {"go", "r", "js", "ts", "ml", "ai", "qa", "ui", "ux", "db", "erp", "wms", "tms", "elk", "dwh", "etl", "llm", "nlp", "cv", "dl", "sql", "php", "c#", "c++"}


def normalize_text(value: str) -> str:
    text = value.lower().replace("ё", "е").replace("1c", "1с")
    text = re.sub(r"[^\w\s+#./:+\-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return f" {text} "


@lru_cache(maxsize=4)
def load_skills_map(path: str | None = None) -> dict[str, list[str]]:
    map_path = Path(path) if path else DEFAULT_SKILLS_MAP_PATH
    if map_path.is_file():
        data = json.loads(map_path.read_text(encoding="utf-8"))
        return {str(key): list(value) for key, value in data.items()}
    export_skills_map_json(map_path)
    return dict(SKILLS_MAP)


def build_alias_index(skills_map: dict[str, list[str]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for canonical, aliases in skills_map.items():
        unique_aliases = {normalize_text(canonical).strip()}
        for alias in aliases:
            unique_aliases.add(normalize_text(alias).strip())
        for alias in sorted(unique_aliases, key=len, reverse=True):
            if alias:
                pairs.append((alias, canonical))
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return pairs


@lru_cache(maxsize=4)
def get_alias_index(path: str | None = None) -> list[tuple[str, str]]:
    return build_alias_index(load_skills_map(path))


def match_exact(value: str, alias_index: list[tuple[str, str]]) -> Optional[str]:
    normalized = normalize_text(value).strip()
    for alias, canonical in alias_index:
        if normalized == alias:
            return canonical
    return None


def find_in_text(text: str, alias_index: list[tuple[str, str]]) -> set[str]:
    if not text:
        return set()

    normalized = normalize_text(text)
    found: set[str] = set()

    for alias, canonical in alias_index:
        if not alias:
            continue
        if alias in SHORT_EXACT_ALIASES:
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized):
                found.add(canonical)
            continue
        if len(alias) < WORD_ALIAS_MIN_LEN:
            continue
        if alias in normalized:
            found.add(canonical)

    return found


def extract_vacancy_skills(
    *,
    key_skill_names: Iterable[str] | None = None,
    vacancy_name: str = "",
    snippet_text: str = "",
    description_text: str = "",
    alias_index: list[tuple[str, str]] | None = None,
) -> set[str]:
    index = alias_index or get_alias_index()
    found: set[str] = set()

    for raw_name in key_skill_names or []:
        name = (raw_name or "").strip()
        if not name:
            continue
        exact = match_exact(name, index)
        if exact:
            found.add(exact)
            continue
        found.update(find_in_text(name, index))

    combined_text = " ".join(
        part for part in [vacancy_name, snippet_text, description_text] if part
    )
    found.update(find_in_text(combined_text, index))
    return found


def count_canonical_skills(skill_sets: Iterable[set[str]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for skills in skill_sets:
        for skill in skills:
            counter[skill] += 1
    return counter


def top_skills_payload(
    counter: Counter[str],
    *,
    sample_size: int,
    limit: int = 10,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, count in counter.most_common(limit):
        rows.append(
            {
                "name": name,
                "count": count,
                "percent": round(100 * count / sample_size, 1) if sample_size else 0,
            }
        )
    return rows
