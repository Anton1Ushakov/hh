"""
Database module for HH.ru Analytics
Contains SQLAlchemy models and database connection setup
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hh_analyzer.db")

# Create engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


class UserQuery(Base):
    """Model for storing user search queries with all filters"""
    __tablename__ = "user_queries"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Common filters
    text = Column(String, nullable=True)
    area = Column(String, nullable=True)
    professional_role = Column(String, nullable=True)
    
    # Search fields for vacancies
    search_everywhere = Column(Boolean, nullable=True)
    search_in_name = Column(Boolean, nullable=True)
    search_in_company_name = Column(Boolean, nullable=True)
    search_in_description = Column(Boolean, nullable=True)
    
    # Search fields for resumes - text.* triad
    resume_text_logic = Column(String, nullable=True)  # all, any, phrase, except
    resume_text_field = Column(String, nullable=True)  # everywhere, title, education, skills, experience, etc
    resume_text_period = Column(String, nullable=True)  # all_time, last_year, last_three_years, last_six_years
    
    # Vacancy-specific filters (new API)
    vacancy_employment_form = Column(String, nullable=True)  # FULL, PART, PROJECT, FLY_IN_FLY_OUT, SIDE_JOB
    vacancy_work_schedule_by_days = Column(String, nullable=True)  # SIX_ON_ONE_OFF, FIVE_ON_TWO_OFF, etc
    vacancy_work_format = Column(String, nullable=True)  # ON_SITE, REMOTE, HYBRID, FIELD_WORK
    vacancy_working_hours = Column(String, nullable=True)  # HOURS_2, HOURS_4, FLEXIBLE, etc
    vacancy_experience = Column(String, nullable=True)  # noExperience, between1And3, between3And6, moreThan6
    vacancy_education = Column(String, nullable=True)  # not_required_or_not_specified, special_secondary, higher
    vacancy_salary = Column(Integer, nullable=True)  # Single salary value
    vacancy_currency = Column(String, nullable=True)  # RUR, USD, EUR, etc
    vacancy_salary_frequency = Column(String, nullable=True)  # DAILY, WEEKLY, TWICE_PER_MONTH, MONTHLY, PER_PROJECT
    vacancy_salary_mode = Column(String, nullable=True)  # MONTH, SHIFT, HOUR, FLY_IN_FLY_OUT, SERVICE
    vacancy_industry = Column(String, nullable=True)
    vacancy_label = Column(String, nullable=True)  # with_salary, accept_handicapped, accept_kids, etc
    vacancy_type = Column(String, nullable=True)  # open, closed, anonymous, direct
    vacancy_period = Column(Integer, nullable=True)  # days (1, 3, 7, 30)
    vacancy_metro = Column(String, nullable=True)
    
    # Resume-specific filters
    resume_education = Column(String, nullable=True)
    resume_relocation = Column(String, nullable=True)
    resume_gender = Column(String, nullable=True)
    resume_age_from = Column(Integer, nullable=True)
    resume_age_to = Column(Integer, nullable=True)
    resume_employment = Column(String, nullable=True)
    resume_schedule = Column(String, nullable=True)
    resume_experience = Column(String, nullable=True)
    resume_salary_from = Column(Integer, nullable=True)
    resume_salary_to = Column(Integer, nullable=True)
    resume_currency = Column(String, nullable=True)
    resume_language = Column(String, nullable=True)
    resume_language_level = Column(String, nullable=True)
    resume_skill = Column(String, nullable=True)
    resume_job_search_status = Column(String, nullable=True)  # active_search, looking_for_offers, etc
    resume_label = Column(String, nullable=True)
    resume_period = Column(Integer, nullable=True)
    query_signature = Column(String, nullable=True, index=True)
    
    # Results
    vacancies_count = Column(Integer, nullable=True)
    resumes_count = Column(Integer, nullable=True)


class AggregatedStats(Base):
    """Model for storing aggregated statistics by day"""
    __tablename__ = "aggregated_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date)
    query_signature = Column(String)  # Hash of filter combination
    avg_vacancies = Column(Float)
    avg_resumes = Column(Float)
    request_count = Column(Integer, default=1)


class CachedDictionary(Base):
    """Model for caching HH.ru dictionaries (areas, roles, etc.)"""
    __tablename__ = "cached_dictionaries"
    
    id = Column(Integer, primary_key=True, index=True)
    dict_type = Column(String, index=True)  # 'areas', 'professional_roles', etc.
    data = Column(String)  # JSON string
    updated_at = Column(DateTime, default=datetime.utcnow)


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_database_dir() -> None:
    """Create parent directory for SQLite file paths (e.g. /data on Render)."""
    if not DATABASE_URL.startswith("sqlite:///"):
        return
    db_path = DATABASE_URL.replace("sqlite:///", "", 1)
    if db_path in (":memory:", "") or db_path.startswith("?"):
        return
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _migrate_schema() -> None:
    """Lightweight SQLite migrations for existing databases."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if not inspector.has_table("user_queries"):
        return
    columns = {column["name"] for column in inspector.get_columns("user_queries")}
    if "query_signature" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE user_queries ADD COLUMN query_signature VARCHAR"))


def init_db():
    """Initialize database - create all tables"""
    ensure_database_dir()
    Base.metadata.create_all(bind=engine)
    _migrate_schema()
