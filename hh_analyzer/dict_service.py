"""Load HH.ru dictionaries into the local cache."""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from database import CachedDictionary
from hh_api import HHAPIClient


def cache_dict(db: Session, dict_type: str, data: list) -> None:
    cached = (
        db.query(CachedDictionary)
        .filter(CachedDictionary.dict_type == dict_type)
        .first()
    )
    if cached:
        cached.data = json.dumps(data, ensure_ascii=False)
        cached.updated_at = datetime.utcnow()
    else:
        db.add(
            CachedDictionary(
                dict_type=dict_type,
                data=json.dumps(data, ensure_ascii=False),
            )
        )
    db.commit()


def refresh_all_dictionaries(db: Session, client: HHAPIClient) -> None:
    areas = client.get_areas()
    cache_dict(db, "areas", areas)

    roles = client.get_professional_roles()
    cache_dict(db, "professional_roles", roles)

    dicts = client._make_request("/dictionaries")
    cache_dict(db, "employments", dicts.get("employment", []))
    cache_dict(db, "schedules", dicts.get("schedule", []))
    cache_dict(db, "experiences", dicts.get("experience", []))
    cache_dict(db, "educations", dicts.get("education_level", []))
    cache_dict(db, "resume_employment_forms", dicts.get("resume_employment_form", []))
    cache_dict(db, "resume_work_formats", dicts.get("resume_work_format", []))
    cache_dict(db, "job_search_statuses", dicts.get("job_search_statuses_employer", []))
    cache_dict(db, "language_levels", dicts.get("language_level", []))


def ensure_dictionaries(db: Session, client: HHAPIClient) -> None:
    cached = (
        db.query(CachedDictionary)
        .filter(CachedDictionary.dict_type == "areas")
        .first()
    )
    if cached:
        return
    print("Dictionary cache empty — fetching from API...")
    refresh_all_dictionaries(db, client)
    print("Dictionaries cached.")
