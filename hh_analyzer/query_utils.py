"""Query signature and daily aggregation helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from database import AggregatedStats


def build_query_signature(filters: Dict[str, Any]) -> str:
    """Stable hash of all non-empty filter values."""
    clean = {
        k: v
        for k, v in sorted(filters.items())
        if v is not None and v != "" and v is not False
    }
    payload = json.dumps(clean, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def collect_filter_snapshot(
    *,
    text: Optional[str] = None,
    area: Optional[str] = None,
    professional_role: Optional[str] = None,
    resume_text_logic: Optional[str] = None,
    resume_text_field: Optional[str] = None,
    resume_text_period: Optional[str] = None,
    vacancy_employment_form: Optional[str] = None,
    vacancy_work_schedule_by_days: Optional[str] = None,
    vacancy_work_format: Optional[str] = None,
    vacancy_working_hours: Optional[str] = None,
    vacancy_experience: Optional[str] = None,
    vacancy_education: Optional[str] = None,
    vacancy_salary: Optional[int] = None,
    vacancy_currency: Optional[str] = None,
    vacancy_salary_frequency: Optional[str] = None,
    vacancy_salary_mode: Optional[str] = None,
    vacancy_industry: Optional[str] = None,
    vacancy_label: Optional[str] = None,
    vacancy_type: Optional[str] = None,
    vacancy_period: Optional[int] = None,
    resume_education: Optional[str] = None,
    resume_relocation: Optional[str] = None,
    resume_gender: Optional[str] = None,
    resume_age_from: Optional[int] = None,
    resume_age_to: Optional[int] = None,
    resume_employment_form: Optional[str] = None,
    resume_work_format: Optional[str] = None,
    resume_experience: Optional[str] = None,
    resume_salary_from: Optional[int] = None,
    resume_salary_to: Optional[int] = None,
    resume_currency: Optional[str] = None,
    resume_language: Optional[str] = None,
    resume_language_level: Optional[str] = None,
    resume_skill: Optional[str] = None,
    resume_job_search_status: Optional[str] = None,
    resume_label: Optional[str] = None,
    resume_period: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "text": text,
        "area": area,
        "professional_role": professional_role,
        "resume_text_logic": resume_text_logic or "all",
        "resume_text_field": resume_text_field or "title",
        "resume_text_period": resume_text_period or "all_time",
        "vacancy_employment_form": vacancy_employment_form,
        "vacancy_work_schedule_by_days": vacancy_work_schedule_by_days,
        "vacancy_work_format": vacancy_work_format,
        "vacancy_working_hours": vacancy_working_hours,
        "vacancy_experience": vacancy_experience,
        "vacancy_education": vacancy_education,
        "vacancy_salary": vacancy_salary,
        "vacancy_currency": vacancy_currency,
        "vacancy_salary_frequency": vacancy_salary_frequency,
        "vacancy_salary_mode": vacancy_salary_mode,
        "vacancy_industry": vacancy_industry,
        "vacancy_label": vacancy_label,
        "vacancy_type": vacancy_type,
        "vacancy_period": vacancy_period,
        "resume_education": resume_education,
        "resume_relocation": resume_relocation,
        "resume_gender": resume_gender,
        "resume_age_from": resume_age_from,
        "resume_age_to": resume_age_to,
        "resume_employment_form": resume_employment_form,
        "resume_work_format": resume_work_format,
        "resume_experience": resume_experience,
        "resume_salary_from": resume_salary_from,
        "resume_salary_to": resume_salary_to,
        "resume_currency": resume_currency,
        "resume_language": resume_language,
        "resume_language_level": resume_language_level,
        "resume_skill": resume_skill,
        "resume_job_search_status": resume_job_search_status,
        "resume_label": resume_label,
        "resume_period": resume_period,
        "vacancy_search_in_name": True,
    }


def upsert_aggregated_stats(
    db: Session,
    query_signature: str,
    vacancies_count: int,
    resumes_count: int,
) -> None:
    """Update or insert daily averages for a filter combination."""
    today = date.today()
    row = (
        db.query(AggregatedStats)
        .filter(
            AggregatedStats.date == today,
            AggregatedStats.query_signature == query_signature,
        )
        .first()
    )
    if row:
        count = row.request_count or 1
        row.avg_vacancies = (row.avg_vacancies * count + vacancies_count) / (count + 1)
        row.avg_resumes = (row.avg_resumes * count + resumes_count) / (count + 1)
        row.request_count = count + 1
    else:
        db.add(
            AggregatedStats(
                date=today,
                query_signature=query_signature,
                avg_vacancies=float(vacancies_count),
                avg_resumes=float(resumes_count),
                request_count=1,
            )
        )
