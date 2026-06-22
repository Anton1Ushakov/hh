"""Semantic grouping of vacancy titles (synonyms, seniority, stack)."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TitleSignature:
    seniority: str
    role: str
    stack: str
    domain: str

    def label_parts(self) -> list[str]:
        parts: list[str] = []
        if self.seniority:
            parts.append(self.seniority)
        if self.stack:
            parts.append(self.stack)
        if self.domain:
            parts.append(self.domain)
        if self.role and self.role not in self.domain.lower():
            parts.append(self.role)
        return parts


SENIORITY_RULES: list[tuple[re.Pattern[str], str]] = [
  (re.compile(r"\b(intern|trainee|стаж[её]р|стажер)\b", re.I), "Intern"),
  (re.compile(r"\b(junior|jr\.?|младший|мл\.?)\b", re.I), "Junior"),
  (re.compile(r"\b(middle\+|middle|mid\.?|средний)\b", re.I), "Middle"),
  (re.compile(r"\b(senior|sr\.?|старший|ст\.?)\b", re.I), "Senior"),
  (
    re.compile(
      r"\b(lead|team\s*lead|тимлид|тим-лид|tech\s*lead|техлид|ведущий|главный|principal)\b",
      re.I,
    ),
    "Lead",
  ),
]

STACK_RULES: list[tuple[re.Pattern[str], str]] = [
  (re.compile(r"1[cс](?::|\b|[-/])", re.I), "1С"),
  (re.compile(r"\b1[cс]\b", re.I), "1С"),
  (re.compile(r"\bpython\b", re.I), "Python"),
  (re.compile(r"\bjava\b(?!script)", re.I), "Java"),
  (re.compile(r"\bjavascript\b|\bjs\b", re.I), "JavaScript"),
  (re.compile(r"\btypescript\b|\bts\b", re.I), "TypeScript"),
  (re.compile(r"\bgolang\b|\bgo\b(?=\s*(developer|разработ|engineer|програм))", re.I), "Go"),
  (re.compile(r"\bphp\b", re.I), "PHP"),
  (re.compile(r"\bc\+\+\b|\bcpp\b", re.I), "C++"),
  (re.compile(r"\bc#\b|\.net\b|\bdotnet\b", re.I), "C# / .NET"),
  (re.compile(r"\breact\b", re.I), "React"),
  (re.compile(r"\bangular\b", re.I), "Angular"),
  (re.compile(r"\bvue\b", re.I), "Vue"),
  (re.compile(r"\bnode\.?js\b", re.I), "Node.js"),
  (re.compile(r"\bfrontend\b|front-end|фронтенд|фронт-енд", re.I), "Frontend"),
  (re.compile(r"\bbackend\b|back-end|бэкенд|бекенд", re.I), "Backend"),
  (re.compile(r"\bfull\s*stack\b|fullstack|фулстек|фуллстек", re.I), "Fullstack"),
  (re.compile(r"\bandroid\b", re.I), "Android"),
  (re.compile(r"\bios\b", re.I), "iOS"),
  (re.compile(r"\bswift\b", re.I), "Swift"),
  (re.compile(r"\bkotlin\b", re.I), "Kotlin"),
  (re.compile(r"\bflutter\b", re.I), "Flutter"),
  (re.compile(r"\bdevops\b", re.I), "DevOps"),
  (re.compile(r"\bml\b|\bmachine learning\b|машинн", re.I), "ML"),
  (re.compile(r"\bai\b|artificial intelligence|искусствен", re.I), "AI"),
  (re.compile(r"\bdata engineer\b|data\s+engineer", re.I), "Data Engineering"),
  (re.compile(r"\bqa\b|\bтестиров", re.I), "QA"),
  (re.compile(r"\bsap\b", re.I), "SAP"),
  (re.compile(r"\bbitrix\b|битрикс", re.I), "Bitrix"),
  (re.compile(r"\bwordpress\b", re.I), "WordPress"),
  (re.compile(r"\berp\b", re.I), "ERP"),
  (re.compile(r"\bwms\b", re.I), "WMS"),
  (re.compile(r"\bsql\b", re.I), "SQL"),
  (re.compile(r"\bpostgres", re.I), "PostgreSQL"),
  (re.compile(r"\bmysql\b", re.I), "MySQL"),
  (re.compile(r"\bkubernetes\b|\bk8s\b", re.I), "Kubernetes"),
  (re.compile(r"\bdocker\b", re.I), "Docker"),
  (re.compile(r"\blinux\b", re.I), "Linux"),
  (re.compile(r"\b1с:erp\b|1c:erp", re.I), "1С ERP"),
]

ROLE_RULES: list[tuple[re.Pattern[str], str]] = [
  (re.compile(r"\b(программист|разработчик|developer|devops-инженер)\b", re.I), "разработчик"),
  (re.compile(r"\b(инженер|engineer)\b", re.I), "инженер"),
  (re.compile(r"\b(аналитик|analyst)\b", re.I), "аналитик"),
  (re.compile(r"\b(администратор|administrator|admin)\b", re.I), "администратор"),
  (re.compile(r"\b(тестировщик|tester|qa)\b", re.I), "тестировщик"),
  (re.compile(r"\b(дизайнер|designer)\b", re.I), "дизайнер"),
  (re.compile(r"\b(менеджер|manager)\b", re.I), "менеджер"),
  (re.compile(r"\b(архитектор|architect)\b", re.I), "архитектор"),
  (re.compile(r"\b(поддержк|support|helpdesk|хелпдеск)\b", re.I), "поддержка"),
  (re.compile(r"\b(консультант|consultant)\b", re.I), "консультант"),
  (re.compile(r"\b(писатель|writer|копирайтер)\b", re.I), "писатель"),
]

DOMAIN_RULES: list[tuple[re.Pattern[str], str]] = [
  (re.compile(r"системн", re.I), "системный"),
  (re.compile(r"бизнес", re.I), "бизнес"),
  (re.compile(r"продуктов", re.I), "продуктовый"),
  (re.compile(r"техническ", re.I), "технический"),
  (re.compile(r"информационн.{0,12}безопас", re.I), "ИБ"),
  (re.compile(r"сетев", re.I), "сетевой"),
  (re.compile(r"графическ", re.I), "графический"),
  (re.compile(r"ux/ui|ui/ux|\bux\b|\bui\b", re.I), "UX/UI"),
  (re.compile(r"мобильн", re.I), "мобильный"),
  (re.compile(r"веб", re.I), "веб"),
]

NOISE_RE = re.compile(
  r"[^\w\s+#./:+\-]|→|—|–",
  re.UNICODE,
)


def normalize_title(title: str) -> str:
  text = title.strip().lower().replace("ё", "е")
  text = text.replace("1c", "1с")
  text = NOISE_RE.sub(" ", text)
  text = re.sub(r"\s+", " ", text).strip()
  return text


def _first_match(rules: list[tuple[re.Pattern[str], str]], text: str) -> str:
  for pattern, label in rules:
    if pattern.search(text):
      return label
  return ""


def _strip_matches(text: str, rules: list[tuple[re.Pattern[str], str]]) -> str:
  for pattern, _ in rules:
    text = pattern.sub(" ", text)
  return re.sub(r"\s+", " ", text).strip()


def parse_title_signature(title: str) -> TitleSignature:
  normalized = normalize_title(title)
  seniority = _first_match(SENIORITY_RULES, normalized)
  stack = _first_match(STACK_RULES, normalized)
  role = _first_match(ROLE_RULES, normalized)
  domain = _first_match(DOMAIN_RULES, normalized)

  remainder = _strip_matches(normalized, SENIORITY_RULES + STACK_RULES)
  if not role:
    role = _first_match(ROLE_RULES, remainder)
  if not domain:
    domain = _first_match(DOMAIN_RULES, remainder)

  if stack == "1С ERP":
    stack = "1С"
    domain = domain or "ERP"

  return TitleSignature(
    seniority=seniority,
    role=role,
    stack=stack,
    domain=domain,
  )


def _fingerprint(title: str) -> tuple[str, ...]:
  sig = parse_title_signature(title)
  normalized = normalize_title(title)

  if sig.stack or sig.role:
    return (
      sig.seniority,
      sig.stack,
      sig.role,
      sig.domain,
    )

  words = [w for w in normalized.split() if len(w) > 2][:4]
  if words:
    return ("__text__", " ".join(words))

  return ("__raw__", normalized[:80])


def _cluster_label(variants: list[dict[str, Any]], signature: TitleSignature) -> str:
  parts = signature.label_parts()
  if parts:
    return " · ".join(parts)

  top = max(variants, key=lambda item: item["count"])
  name = top["name"]
  if len(name) <= 64:
    return name
  return name[:61] + "..."


SENIORITY_ORDER = ["Intern", "Junior", "Middle", "Senior", "Lead", ""]

SENIORITY_LABELS: dict[str, str] = {
    "Intern": "Стажёр",
    "Junior": "Junior",
    "Middle": "Middle",
    "Senior": "Senior",
    "Lead": "Lead / ведущий",
    "": "Без уровня",
}

SENIORITY_SEARCH_ALIASES: dict[str, str] = {
    "Intern": "intern стажер стажёр trainee",
    "Junior": "junior jr младший мл",
    "Middle": "middle mid средний",
    "Senior": "senior sr старший ст",
    "Lead": "lead teamlead тимлид ведущий главный principal techlead техлид",
    "": "без уровня не указан",
}


def cluster_label_without_seniority(
    variants: list[dict[str, Any]],
    signature: TitleSignature,
) -> str:
    """Cluster label for nesting inside a seniority level."""
    parts: list[str] = []
    if signature.stack:
        parts.append(signature.stack)
    if signature.domain:
        parts.append(signature.domain)
    if signature.role and signature.role not in signature.domain.lower():
        parts.append(signature.role)
    if parts:
        return " · ".join(parts)
    return _cluster_label(variants, signature)


def compact_label_for_role(label: str, role_name: str) -> str:
    """Drop words already implied by the parent HH role."""
    role_norm = normalize_title(role_name)
    stop_words = {
        role_norm,
        *[
            normalize_title(part)
            for part in re.split(r"[,/]", role_name)
        ],
    }
    for word in role_norm.split():
        if len(word) > 2:
            stop_words.add(word)

    stop_words.update(
        {
            "программист",
            "разработчик",
            "developer",
            "аналитик",
            "analyst",
            "инженер",
            "engineer",
            "дизайнер",
            "designer",
            "администратор",
            "administrator",
            "тестировщик",
            "менеджер",
            "manager",
        }
    )

    parts = [part.strip() for part in label.split("·") if part.strip()]
    kept = [part for part in parts if normalize_title(part) not in stop_words]
    if kept:
        return " · ".join(kept)
    if parts:
        return parts[0]
    return label


def _dedupe_variants(
    label: str,
    variants: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove variant rows that repeat the merged label."""
    label_norm = normalize_title(label)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()

    for variant in variants:
        name = variant["name"]
        name_norm = normalize_title(name)
        if name_norm in seen:
            continue
        if name_norm == label_norm:
            continue
        seen.add(name_norm)
        deduped.append(variant)

    return deduped


def _merge_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    for entry in entries:
        key = normalize_title(entry["name"])
        if key not in merged:
            merged[key] = {
                "name": entry["name"],
                "count": entry["count"],
                "variants": list(entry.get("variants") or []),
            }
            continue

        bucket = merged[key]
        bucket["count"] += entry["count"]
        bucket["variants"].extend(entry.get("variants") or [])

    result: list[dict[str, Any]] = []
    for bucket in merged.values():
        variants = _dedupe_variants(bucket["name"], bucket["variants"])
        result.append(
            {
                "name": bucket["name"],
                "count": bucket["count"],
                "variants": variants,
                "variants_count": len(variants),
            }
        )

    result.sort(key=lambda item: (-item["count"], item["name"].lower()))
    return result


def group_clusters_by_seniority(
    clusters: list[dict[str, Any]],
    *,
    role_name: str = "",
) -> list[dict[str, Any]]:
    """Nest semantic clusters under seniority levels."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for cluster in clusters:
        seniority = cluster.get("seniority") or ""
        signature = TitleSignature(
            seniority=seniority,
            role=cluster.get("role") or "",
            stack=cluster.get("stack") or "",
            domain=cluster.get("domain") or "",
        )
        label = compact_label_for_role(
            cluster_label_without_seniority(cluster["variants"], signature),
            role_name,
        )
        variants = _dedupe_variants(label, cluster["variants"])
        buckets[seniority].append(
            {
                "name": label,
                "count": cluster["total_count"],
                "variants": variants,
                "variants_count": len(variants),
            }
        )

    levels: list[dict[str, Any]] = []
    for seniority in SENIORITY_ORDER:
        items = buckets.get(seniority, [])
        if not items:
            continue
        entries = _merge_entries(items)
        levels.append(
            {
                "id": seniority.lower() if seniority else "unspecified",
                "seniority": seniority,
                "name": SENIORITY_LABELS[seniority],
                "search_aliases": SENIORITY_SEARCH_ALIASES[seniority],
                "total_count": sum(entry["count"] for entry in entries),
                "entries_count": len(entries),
                "entries": entries,
                "inline": False,
            }
        )

    if len(levels) == 1 and levels[0]["id"] == "unspecified":
        levels[0]["inline"] = True

    return levels


def group_titles_by_seniority(
    titles: list[dict[str, Any]],
    *,
    role_name: str = "",
) -> list[dict[str, Any]]:
    """Full pipeline: titles -> semantic clusters -> seniority levels."""
    return group_clusters_by_seniority(
        group_titles_semantically(titles),
        role_name=role_name,
    )


def group_titles_semantically(titles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group raw titles into semantic clusters sorted by total vacancy count."""
    buckets: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)

    for item in titles:
        name = (item.get("name") or "").strip()
        count = int(item.get("count") or 0)
        if not name or count <= 0:
            continue
        buckets[_fingerprint(name)].append({"name": name, "count": count})

    clusters: list[dict[str, Any]] = []
    for _key, variants in buckets.items():
        variants.sort(key=lambda v: (-v["count"], v["name"].lower()))
        total = sum(v["count"] for v in variants)
        signature = parse_title_signature(variants[0]["name"])
        clusters.append(
            {
                "label": _cluster_label(variants, signature),
                "total_count": total,
                "variants_count": len(variants),
                "seniority": signature.seniority,
                "stack": signature.stack,
                "role": signature.role,
                "domain": signature.domain,
                "variants": variants,
            }
        )

    clusters.sort(key=lambda c: (-c["total_count"], c["label"].lower()))
    return clusters
