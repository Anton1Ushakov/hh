"""
Main FastAPI application for HH.ru Analytics
"""

from fastapi import FastAPI, Request, Depends, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import json
import hashlib

import os
from dotenv import load_dotenv

from database import init_db, get_db, UserQuery, AggregatedStats, CachedDictionary
from hh_api import HHAPIClient, get_auth_url, exchange_code_for_token, refresh_access_token

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="HH.ru Analytics", description="Labor market calculator")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Global API client (initialized with tokens from environment)
access_token = os.getenv("HH_ACCESS_TOKEN")
refresh_token = os.getenv("HH_REFRESH_TOKEN")
hh_client = HHAPIClient(access_token=access_token, refresh_token=refresh_token)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()


# ==================== PAGES ====================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    """Main page with search form"""
    # Get cached dictionaries
    areas = get_cached_dict(db, "areas") or []
    roles = get_cached_dict(db, "professional_roles") or []
    employments = get_cached_dict(db, "employments") or []
    schedules = get_cached_dict(db, "schedules") or []
    experiences = get_cached_dict(db, "experiences") or []
    educations = get_cached_dict(db, "educations") or []
    currencies = [{"id": "RUR", "name": "Рубли (RUR)"}, {"id": "USD", "name": "Доллары (USD)"}, {"id": "EUR", "name": "Евро (EUR)"}]
    genders = [{"id": "male", "name": "Мужской"}, {"id": "female", "name": "Женский"}]
    language_levels = [
        {"id": "basic", "name": "Базовый"},
        {"id": "intermediate", "name": "Средний"},
        {"id": "advanced", "name": "Продвинутый"},
        {"id": "fluent", "name": "Свободно"}
    ]
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "areas": areas,
        "roles": roles,
        "employments": employments,
        "schedules": schedules,
        "experiences": experiences,
        "educations": educations,
        "currencies": currencies,
        "genders": genders,
        "language_levels": language_levels
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
        "queries": top_queries
    })


@app.get("/trends", response_class=HTMLResponse)
async def trends_page(
    request: Request,
    query: str = Query(..., description="Search query"),
    db: Session = Depends(get_db)
):
    """Trends page for specific query"""
    month_ago = datetime.utcnow() - timedelta(days=30)
    
    trends = db.query(AggregatedStats).filter(
        AggregatedStats.date >= month_ago.date(),
        AggregatedStats.query_signature == hashlib.md5(query.encode()).hexdigest()
    ).order_by(AggregatedStats.date).all()
    
    return templates.TemplateResponse("trends.html", {
        "request": request,
        "query": query,
        "trends": trends
    })


# ==================== API ENDPOINTS ====================

@app.post("/api/calculate")
async def calculate(
    # Common filters
    text: Optional[str] = Form(None),
    area: Optional[str] = Form(None),
    professional_role: Optional[str] = Form(None),
    
    # Search fields for vacancies (received as str from checkboxes)
    search_in_name: str = Form("true"),
    search_in_company_name: str = Form("true"),
    search_in_description: str = Form("true"),
    
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
    resume_employment: Optional[str] = Form(None),
    resume_schedule: Optional[str] = Form(None),
    resume_experience: Optional[str] = Form(None),
    resume_salary_from: Optional[int] = Form(None),
    resume_salary_to: Optional[int] = Form(None),
    resume_currency: Optional[str] = Form(None),
    resume_language: Optional[str] = Form(None),
    resume_language_level: Optional[str] = Form(None),
    resume_skill: Optional[str] = Form(None),
    resume_job_search_status: Optional[str] = Form(None),  # active_search, looking_for_offers, not_looking_for_job, has_job_offer, accepted_job_offer
    resume_label: Optional[str] = Form(None),
    resume_period: Optional[int] = Form(None),
    
    db: Session = Depends(get_db)
):
    """
    Calculate vacancies/resumes ratio with separate filters
    """
    try:
        # Convert string 'true'/'false' to boolean for vacancy search fields
        search_in_name_bool = search_in_name.lower() == "true"
        search_in_company_name_bool = search_in_company_name.lower() == "true"
        search_in_description_bool = search_in_description.lower() == "true"
        
        # Search vacancies with vacancy-specific filters (new API)
        # For vacancies, always search in all 3 fields (no "everywhere" option)
        vacancies_count = hh_client.search_vacancies(
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
            period=vacancy_period
        )
        
        # Search resumes with resume-specific filters
        resumes_count = hh_client.search_resumes(
            text=text,
            area=area,
            professional_role=professional_role,
            text_logic=resume_text_logic,
            text_field=resume_text_field,
            text_period=resume_text_period,
            education=resume_education,
            relocation=resume_relocation,
            gender=resume_gender,
            age_from=resume_age_from,
            age_to=resume_age_to,
            employment=resume_employment,
            schedule=resume_schedule,
            experience=resume_experience,
            salary_from=resume_salary_from,
            salary_to=resume_salary_to,
            currency=resume_currency,
            language=resume_language,
            language_level=resume_language_level,
            skill=resume_skill,
            job_search_status=resume_job_search_status,
            label=resume_label,
            period=resume_period
        )
        
        # Save query to database with all filters
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
            resume_employment=resume_employment,
            resume_schedule=resume_schedule,
            resume_experience=resume_experience,
            resume_salary_from=resume_salary_from,
            resume_salary_to=resume_salary_to,
            resume_currency=resume_currency,
            resume_language=resume_language,
            resume_language_level=resume_language_level,
            resume_skill=resume_skill,
            resume_job_search_status=resume_job_search_status,
            resume_label=resume_label,
            resume_period=resume_period,
            vacancies_count=vacancies_count,
            resumes_count=resumes_count
        )
        db.add(query_record)
        db.commit()
        
        return JSONResponse({
            "success": True,
            "vacancies_count": vacancies_count,
            "resumes_count": resumes_count,
            "ratio": round(vacancies_count / max(resumes_count, 1), 2),
            "difference": vacancies_count - resumes_count,
            "timestamp": datetime.utcnow().isoformat()
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


@app.get("/api/trends-data")
async def trends_data(
    query: str = Query(...),
    db: Session = Depends(get_db)
):
    """Get trend data for chart"""
    month_ago = datetime.utcnow() - timedelta(days=30)
    
    trends = db.query(AggregatedStats).filter(
        AggregatedStats.date >= month_ago.date(),
        AggregatedStats.query_signature == hashlib.md5(query.encode()).hexdigest()
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
        areas = hh_client.get_areas()
        cache_dict(db, "areas", areas)
        
        roles = hh_client.get_professional_roles()
        cache_dict(db, "professional_roles", roles)
        
        dicts = hh_client._make_request("/dictionaries")
        cache_dict(db, "employments", dicts.get("employment", []))
        cache_dict(db, "schedules", dicts.get("schedule", []))
        cache_dict(db, "experiences", dicts.get("experience", []))
        cache_dict(db, "educations", dicts.get("education_level", []))
        
        return {"success": True, "message": "Dictionaries refreshed"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== AUTH ====================

@app.get("/auth/login")
async def auth_login():
    """Redirect to HH OAuth"""
    return RedirectResponse(get_auth_url())


@app.get("/auth/callback")
async def auth_callback(code: str):
    """Handle OAuth callback"""
    try:
        token_data = exchange_code_for_token(code)
        global hh_client
        hh_client = HHAPIClient(access_token=token_data.get("access_token"))
        return {"success": True, "message": "Authorized successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
        cached.data = json.dumps(data)
        cached.updated_at = datetime.utcnow()
    else:
        cached = CachedDictionary(
            dict_type=dict_type,
            data=json.dumps(data)
        )
        db.add(cached)
    
    db.commit()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
