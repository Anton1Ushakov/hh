"""
Main FastAPI application for HH.ru Analytics
"""

from fastapi import FastAPI, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Any, Dict
import json
from urllib.parse import quote

import os
from dotenv import load_dotenv

from database import init_db, get_db, UserQuery, AggregatedStats, CachedDictionary, SessionLocal
from hh_api import HHAPIClient, TokenManager, get_auth_url, exchange_code_for_token
from query_utils import build_query_signature, collect_filter_snapshot, upsert_aggregated_stats
from dict_service import ensure_dictionaries, refresh_all_dictionaries, cache_dict

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="HH.ru Analytics", description="Labor market calculator")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Global token manager and API client
token_manager = TokenManager(
    access_token=os.getenv("HH_ACCESS_TOKEN"),
    refresh_token=os.getenv("HH_REFRESH_TOKEN"),
)
hh_client = HHAPIClient(token_manager=token_manager)


@app.on_event("startup")
async def startup_event():
    """Initialize database, dictionaries, and refresh token if needed."""
    init_db()
    db = SessionLocal()
    try:
        ensure_dictionaries(db, hh_client)
        _load_tokens_from_cache(db)
    finally:
        db.close()

    if token_manager.can_refresh() and token_manager.is_expired():
        try:
            token_manager.ensure_access_token()
            db = SessionLocal()
            try:
                _save_tokens_to_cache(db, token_manager.to_token_dict())
            finally:
                db.close()
            print("Access token refreshed on startup")
        except Exception as e:
            print(f"Startup token refresh failed: {e}")


@app.get("/health")
async def health():
    """Health check for load balancers and Render."""
    return {
        "status": "ok",
        "has_access_token": bool(token_manager.access_token),
        "can_refresh": token_manager.can_refresh(),
    }


# ==================== PAGES ====================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    """Main page with search form"""
    areas = get_cached_dict(db, "areas") or []
    roles = get_cached_dict(db, "professional_roles") or []
    experiences = get_cached_dict(db, "experiences") or []
    educations = get_cached_dict(db, "educations") or []
    resume_employment_forms = get_cached_dict(db, "resume_employment_forms") or []
    resume_work_formats = get_cached_dict(db, "resume_work_formats") or []
    job_search_statuses = get_cached_dict(db, "job_search_statuses") or []
    language_levels = get_cached_dict(db, "language_levels") or []
    currencies = [{"id": "RUR", "name": "Рубли (RUR)"}, {"id": "USD", "name": "Доллары (USD)"}, {"id": "EUR", "name": "Евро (EUR)"}]
    genders = [{"id": "male", "name": "Мужской"}, {"id": "female", "name": "Женский"}]
    auth_message = request.query_params.get("auth")
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "areas": areas,
        "roles": roles,
        "experiences": experiences,
        "educations": educations,
        "resume_employment_forms": resume_employment_forms,
        "resume_work_formats": resume_work_formats,
        "job_search_statuses": job_search_statuses,
        "language_levels": language_levels,
        "currencies": currencies,
        "genders": genders,
        "auth_message": auth_message,
        "prefill": dict(request.query_params),
    })


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request, db: Session = Depends(get_db)):
    """Statistics page with top queries"""
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    top_queries = db.query(UserQuery).filter(
        UserQuery.timestamp >= week_ago
    ).order_by(UserQuery.timestamp.desc()).limit(10).all()
    
    return templates.TemplateResponse("stats.html", {
        "request": request,
        "queries": [
            {
                "record": q,
                "signature": q.query_signature or signature_for_user_query(q),
            }
            for q in top_queries
        ],
    })


@app.get("/trends", response_class=HTMLResponse)
async def trends_page(
    request: Request,
    signature: str = Query(..., description="Query signature hash"),
    query: str = Query("", description="Display label"),
    db: Session = Depends(get_db)
):
    """Trends page for a specific filter combination."""
    month_ago = datetime.utcnow() - timedelta(days=30)
    
    trends = db.query(AggregatedStats).filter(
        AggregatedStats.date >= month_ago.date(),
        AggregatedStats.query_signature == signature
    ).order_by(AggregatedStats.date).all()
    
    return templates.TemplateResponse("trends.html", {
        "request": request,
        "query": query or "запрос",
        "signature": signature,
        "trends": trends
    })


# ==================== API ENDPOINTS ====================

@app.post("/api/calculate")
async def calculate(
    # Common filters
    text: Optional[str] = Form(None),
    area: Optional[str] = Form(None),
    professional_role: Optional[str] = Form(None),
    
    # Search fields for resumes - text.* triad
    resume_text_logic: Optional[str] = Form(None),  # all, any, phrase, except
    resume_text_field: Optional[str] = Form(None),  # everywhere, title, education, skills, experience, experience_company, experience_position, experience_description
    resume_text_period: Optional[str] = Form(None),  # all_time, last_year, last_three_years, last_six_years
    
    # Vacancy-specific filters (new API)
    vacancy_employment_form: Optional[str] = Form(None),  # FULL, PART, PROJECT, FLY_IN_FLY_OUT, SIDE_JOB
    vacancy_work_schedule_by_days: Optional[str] = Form(None),  # SIX_ON_ONE_OFF, FIVE_ON_TWO_OFF, etc
    vacancy_work_format: Optional[str] = Form(None),  # ON_SITE, REMOTE, HYBRID, FIELD_WORK
    vacancy_working_hours: Optional[str] = Form(None),  # HOURS_2, HOURS_4, FLEXIBLE, etc
    vacancy_experience: Optional[str] = Form(None),  # noExperience, between1And3, between3And6, moreThan6
    vacancy_education: Optional[str] = Form(None),  # not_required_or_not_specified, special_secondary, higher
    vacancy_salary: Optional[int] = Form(None),  # Single salary value
    vacancy_currency: Optional[str] = Form(None),  # RUR, USD, EUR, etc
    vacancy_salary_frequency: Optional[str] = Form(None),  # DAILY, WEEKLY, TWICE_PER_MONTH, MONTHLY, PER_PROJECT
    vacancy_salary_mode: Optional[str] = Form(None),  # MONTH, SHIFT, HOUR, FLY_IN_FLY_OUT, SERVICE
    vacancy_industry: Optional[str] = Form(None),
    vacancy_label: Optional[str] = Form(None),  # with_salary, accept_handicapped, accept_kids, etc
    vacancy_type: Optional[str] = Form(None),  # open, closed, anonymous, direct
    vacancy_period: Optional[int] = Form(None),  # days (1, 3, 7, 30)
    
    # Resume-specific filters
    resume_education: Optional[str] = Form(None),
    resume_relocation: Optional[str] = Form(None),
    resume_gender: Optional[str] = Form(None),
    resume_age_from: Optional[int] = Form(None),
    resume_age_to: Optional[int] = Form(None),
    resume_employment_form: Optional[str] = Form(None),
    resume_work_format: Optional[str] = Form(None),
    resume_experience: Optional[str] = Form(None),
    resume_salary_from: Optional[int] = Form(None),
    resume_salary_to: Optional[int] = Form(None),
    resume_currency: Optional[str] = Form(None),
    resume_language: Optional[str] = Form(None),
    resume_language_level: Optional[str] = Form(None),
    resume_skill: Optional[str] = Form(None),
    resume_job_search_status: Optional[str] = Form(None),
    resume_label: Optional[str] = Form(None),
    resume_period: Optional[str] = Form(None),
    
    db: Session = Depends(get_db)
):
    """
    Calculate vacancies/resumes ratio with separate filters
    """
    try:
        search_in_name_bool = True
        search_in_company_name_bool = False
        search_in_description_bool = False
        resume_period_int = int(resume_period) if resume_period else None

        filter_snapshot = collect_filter_snapshot(
            text=text,
            area=area,
            professional_role=professional_role,
            resume_text_logic=resume_text_logic,
            resume_text_field=resume_text_field,
            resume_text_period=resume_text_period,
            vacancy_employment_form=vacancy_employment_form,
            vacancy_work_schedule_by_days=vacancy_work_schedule_by_days,
            vacancy_work_format=vacancy_work_format,
            vacancy_working_hours=vacancy_working_hours,
            vacancy_experience=vacancy_experience,
            vacancy_education=vacancy_education,
            vacancy_salary=vacancy_salary,
            vacancy_currency=vacancy_currency,
            vacancy_salary_frequency=vacancy_salary_frequency,
            vacancy_salary_mode=vacancy_salary_mode,
            vacancy_industry=vacancy_industry,
            vacancy_label=vacancy_label,
            vacancy_type=vacancy_type,
            vacancy_period=vacancy_period,
            resume_education=resume_education,
            resume_relocation=resume_relocation,
            resume_gender=resume_gender,
            resume_age_from=resume_age_from,
            resume_age_to=resume_age_to,
            resume_employment_form=resume_employment_form,
            resume_work_format=resume_work_format,
            resume_experience=resume_experience,
            resume_salary_from=resume_salary_from,
            resume_salary_to=resume_salary_to,
            resume_currency=resume_currency,
            resume_language=resume_language,
            resume_language_level=resume_language_level,
            resume_skill=resume_skill,
            resume_job_search_status=resume_job_search_status,
            resume_label=resume_label,
            resume_period=resume_period_int,
        )
        query_signature = build_query_signature(filter_snapshot)

        vacancy_result = hh_client.search_vacancies_detail(
            text=text,
            area=area,
            professional_role=professional_role,
            search_everywhere=False,
            search_in_name=search_in_name_bool,
            search_in_company_name=search_in_company_name_bool,
            search_in_description=search_in_description_bool,
            employment_form=vacancy_employment_form,
            work_schedule_by_days=vacancy_work_schedule_by_days,
            work_format=vacancy_work_format,
            working_hours=vacancy_working_hours,
            experience=vacancy_experience,
            education=vacancy_education,
            salary=vacancy_salary,
            currency=vacancy_currency,
            salary_frequency=vacancy_salary_frequency,
            salary_mode=vacancy_salary_mode,
            industry=vacancy_industry,
            label=vacancy_label,
            type_=vacancy_type,
            period=vacancy_period,
        )

        resume_result = hh_client.search_resumes_detail(
            text=text,
            area=area,
            professional_role=professional_role,
            text_logic=resume_text_logic,
            text_field=resume_text_field,
            text_period=resume_text_period,
            education_levels=resume_education,
            relocation=resume_relocation,
            gender=resume_gender,
            age_from=resume_age_from,
            age_to=resume_age_to,
            employment_form=resume_employment_form,
            work_format=resume_work_format,
            experience=resume_experience,
            salary_from=resume_salary_from,
            salary_to=resume_salary_to,
            currency=resume_currency,
            language=resume_language,
            language_level=resume_language_level,
            skill=resume_skill,
            job_search_status=resume_job_search_status,
            label=resume_label,
            period=resume_period_int,
        )

        vacancies_count = vacancy_result["found"]
        resumes_count = resume_result["found"]
        resume_field = resume_result["params"].get("text.field", "title")
        resume_period_label = (
            f"обновлялись за {resume_period_int} дн."
            if resume_period_int
            else "за всё время"
        )
        
        query_record = UserQuery(
            text=text,
            area=area,
            professional_role=professional_role,
            # Search fields for vacancies
            search_everywhere=False,
            search_in_name=search_in_name_bool,
            search_in_company_name=search_in_company_name_bool,
            search_in_description=search_in_description_bool,
            # Search fields for resumes - text.* triad
            resume_text_logic=resume_text_logic,
            resume_text_field=resume_text_field,
            resume_text_period=resume_text_period,
            # Vacancy filters (new API)
            vacancy_employment_form=vacancy_employment_form,
            vacancy_work_schedule_by_days=vacancy_work_schedule_by_days,
            vacancy_work_format=vacancy_work_format,
            vacancy_working_hours=vacancy_working_hours,
            vacancy_experience=vacancy_experience,
            vacancy_education=vacancy_education,
            vacancy_salary=vacancy_salary,
            vacancy_currency=vacancy_currency,
            vacancy_salary_frequency=vacancy_salary_frequency,
            vacancy_salary_mode=vacancy_salary_mode,
            vacancy_industry=vacancy_industry,
            vacancy_label=vacancy_label,
            vacancy_type=vacancy_type,
            vacancy_period=vacancy_period,
            resume_education=resume_education,
            resume_relocation=resume_relocation,
            resume_gender=resume_gender,
            resume_age_from=resume_age_from,
            resume_age_to=resume_age_to,
            resume_employment=resume_employment_form,
            resume_schedule=resume_work_format,
            resume_experience=resume_experience,
            resume_salary_from=resume_salary_from,
            resume_salary_to=resume_salary_to,
            resume_currency=resume_currency,
            resume_language=resume_language,
            resume_language_level=resume_language_level,
            resume_skill=resume_skill,
            resume_job_search_status=resume_job_search_status,
            resume_label=resume_label,
            resume_period=resume_period_int,
            query_signature=query_signature,
            vacancies_count=vacancies_count,
            resumes_count=resumes_count
        )
        db.add(query_record)
        upsert_aggregated_stats(db, query_signature, vacancies_count, resumes_count)
        db.commit()
        
        return JSONResponse({
            "success": True,
            "vacancies_count": vacancies_count,
            "resumes_count": resumes_count,
            "ratio": round(vacancies_count / max(resumes_count, 1), 2),
            "difference": vacancies_count - resumes_count,
            "timestamp": datetime.utcnow().isoformat(),
            "query_signature": query_signature,
            "debug": {
                "vacancies": {
                    "url": vacancy_result["url"],
                    "params": vacancy_result["params"],
                    "note": "Поиск только в названии вакансии (search_field=name)",
                },
                "resumes": {
                    "url": resume_result["url"],
                    "params": resume_result["params"],
                    "note": f"Поиск в поле text.field={resume_field}, активность: {resume_period_label}",
                },
            },
        })
        
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/top-queries")
async def top_queries(db: Session = Depends(get_db)):
    """Get top 10 popular queries from last 7 days"""
    week_ago = datetime.utcnow() - timedelta(days=7)
    
    queries = db.query(UserQuery).filter(
        UserQuery.timestamp >= week_ago
    ).order_by(UserQuery.timestamp.desc()).limit(10).all()
    
    return [
        {
            "id": q.id,
            "timestamp": q.timestamp.isoformat(),
            "text": q.text,
            "area": q.area,
            "vacancies_count": q.vacancies_count,
            "resumes_count": q.resumes_count
        }
        for q in queries
    ]


@app.get("/api/suggest/keywords")
async def suggest_keywords(q: str = Query("", max_length=3000)):
    """Vacancy keyword and professional role suggestions from HH API"""
    query = q.strip()
    if len(query) < 2:
        return {"keywords": [], "roles": []}

    keywords = []
    roles = []
    try:
        keywords = hh_client.get_vacancy_keyword_suggests(query)
    except Exception as e:
        print(f"Keyword suggest error: {e}")
    try:
        roles = hh_client.get_professional_role_suggests(query)
    except Exception as e:
        print(f"Role suggest error: {e}")

    return {
        "keywords": [{"text": text} for text in keywords],
        "roles": [
            {"id": role.get("id"), "text": role.get("text")}
            for role in roles
            if role.get("id") and role.get("text")
        ],
    }


@app.get("/api/trends-data")
async def trends_data(
    signature: str = Query(...),
    db: Session = Depends(get_db)
):
    """Get trend data for chart"""
    month_ago = datetime.utcnow() - timedelta(days=30)
    
    trends = db.query(AggregatedStats).filter(
        AggregatedStats.date >= month_ago.date(),
        AggregatedStats.query_signature == signature
    ).order_by(AggregatedStats.date).all()
    
    return {
        "labels": [t.date.isoformat() for t in trends],
        "vacancies": [t.avg_vacancies for t in trends],
        "resumes": [t.avg_resumes for t in trends]
    }


@app.post("/api/refresh-dictionaries")
async def refresh_dictionaries(db: Session = Depends(get_db)):
    """Refresh cached dictionaries from HH API"""
    try:
        refresh_all_dictionaries(db, hh_client)
        return {"success": True, "message": "Dictionaries refreshed"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== AUTH ====================

@app.get("/auth/login")
async def auth_login():
    """Redirect to HH OAuth"""
    return RedirectResponse(get_auth_url())


@app.get("/auth/callback")
async def auth_callback(code: str, db: Session = Depends(get_db)):
    """Handle OAuth callback"""
    try:
        token_data = exchange_code_for_token(code)
        token_manager.apply_token_response(token_data)
        _save_tokens_to_cache(db, token_data)
        global hh_client
        hh_client = HHAPIClient(token_manager=token_manager)
        return RedirectResponse(url="/?auth=ok", status_code=302)
    except Exception as e:
        return RedirectResponse(
            url=f"/?auth=error&message={quote(str(e))}",
            status_code=302,
        )


# ==================== HELPERS ====================

def get_cached_dict(db: Session, dict_type: str):
    """Get cached dictionary from database"""
    cached = db.query(CachedDictionary).filter(
        CachedDictionary.dict_type == dict_type
    ).first()
    
    if cached:
        return json.loads(cached.data)
    return None


def cache_dict(db: Session, dict_type: str, data: list):
    """Cache dictionary in database"""
    cached = db.query(CachedDictionary).filter(
        CachedDictionary.dict_type == dict_type
    ).first()
    
    if cached:
        cached.data = json.dumps(data, ensure_ascii=False)
        cached.updated_at = datetime.utcnow()
    else:
        cached = CachedDictionary(
            dict_type=dict_type,
            data=json.dumps(data, ensure_ascii=False)
        )
        db.add(cached)
    
    db.commit()


def signature_for_user_query(query: UserQuery) -> str:
    return build_query_signature(
        collect_filter_snapshot(
            text=query.text,
            area=query.area,
            professional_role=query.professional_role,
            resume_text_logic=query.resume_text_logic,
            resume_text_field=query.resume_text_field,
            resume_text_period=query.resume_text_period,
            vacancy_employment_form=query.vacancy_employment_form,
            vacancy_work_schedule_by_days=query.vacancy_work_schedule_by_days,
            vacancy_work_format=query.vacancy_work_format,
            vacancy_working_hours=query.vacancy_working_hours,
            vacancy_experience=query.vacancy_experience,
            vacancy_education=query.vacancy_education,
            vacancy_salary=query.vacancy_salary,
            vacancy_currency=query.vacancy_currency,
            vacancy_salary_frequency=query.vacancy_salary_frequency,
            vacancy_salary_mode=query.vacancy_salary_mode,
            vacancy_industry=query.vacancy_industry,
            vacancy_label=query.vacancy_label,
            vacancy_type=query.vacancy_type,
            vacancy_period=query.vacancy_period,
            resume_education=query.resume_education,
            resume_relocation=query.resume_relocation,
            resume_gender=query.resume_gender,
            resume_age_from=query.resume_age_from,
            resume_age_to=query.resume_age_to,
            resume_employment_form=query.resume_employment,
            resume_work_format=query.resume_schedule,
            resume_experience=query.resume_experience,
            resume_salary_from=query.resume_salary_from,
            resume_salary_to=query.resume_salary_to,
            resume_currency=query.resume_currency,
            resume_language=query.resume_language,
            resume_language_level=query.resume_language_level,
            resume_skill=query.resume_skill,
            resume_job_search_status=query.resume_job_search_status,
            resume_label=query.resume_label,
            resume_period=query.resume_period,
        )
    )


def _save_tokens_to_cache(db: Session, token_data: Dict[str, Any]) -> None:
    cache_dict(db, "oauth_tokens", [token_data])


def _load_tokens_from_cache(db: Session) -> None:
    if token_manager.access_token and token_manager.refresh_token:
        return
    cached = get_cached_dict(db, "oauth_tokens")
    if not cached:
        return
    token_data = cached[0]
    token_manager.apply_token_response(token_data)
    print("OAuth tokens loaded from database cache")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
