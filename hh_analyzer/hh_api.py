"""
HH.ru API client module
Handles all interactions with HH.ru API
"""

import requests
import time
import os
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

# API Configuration
HH_API_BASE = "https://api.hh.ru"
HH_TOKEN_URL = "https://api.hh.ru/token"
RATE_LIMIT_DELAY = 0.2  # seconds between requests (max 10 req/sec)


class TokenManager:
    """In-memory OAuth token storage with proactive refresh."""

    def __init__(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        expires_at: Optional[float] = None,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at

    def apply_token_response(self, data: Dict[str, Any]) -> None:
        """Store token pair and expiry from HH OAuth response."""
        if data.get("access_token"):
            self.access_token = data["access_token"]
        if data.get("refresh_token"):
            self.refresh_token = data["refresh_token"]
        expires_in = data.get("expires_in")
        if expires_in is not None:
            self.expires_at = time.time() + float(expires_in)
        self._sync_env()

    def to_token_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": "bearer",
        }
        if self.expires_at is not None:
            payload["expires_in"] = max(int(self.expires_at - time.time()), 0)
        return payload

    def _sync_env(self) -> None:
        if self.access_token:
            os.environ["HH_ACCESS_TOKEN"] = self.access_token
        if self.refresh_token:
            os.environ["HH_REFRESH_TOKEN"] = self.refresh_token

    def is_expired(self, buffer_seconds: int = 300) -> bool:
        """True if access token is missing or expires within buffer_seconds."""
        if not self.access_token:
            return True
        if self.expires_at is None:
            return False
        return time.time() >= (self.expires_at - buffer_seconds)

    def can_refresh(self) -> bool:
        return bool(self.refresh_token)

    def ensure_access_token(self, force: bool = False) -> None:
        """Refresh access token if expired or force=True."""
        if not force and not self.is_expired():
            return
        if not self.refresh_token:
            if not self.access_token:
                raise Exception("No access token and no refresh token available.")
            return
        new_tokens = refresh_access_token(self.refresh_token)
        self.apply_token_response(new_tokens)

    def force_refresh(self) -> None:
        """Force refresh — used as fallback on 401."""
        if not self.refresh_token:
            raise Exception("No refresh token available.")
        new_tokens = refresh_access_token(self.refresh_token)
        self.apply_token_response(new_tokens)


class HHAPIClient:
    """Client for HH.ru API with automatic token refresh"""
    
    def __init__(
        self,
        token_manager: Optional[TokenManager] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ):
        if token_manager is not None:
            self.token_manager = token_manager
        else:
            self.token_manager = TokenManager(
                access_token=access_token,
                refresh_token=refresh_token,
            )
        self.last_request_time = 0
        self.user_agent = os.getenv("HH_USER_AGENT", "Market-Analytics/1.0")
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None, retry_with_refresh: bool = True) -> Dict[str, Any]:
        """
        Make rate-limited request to HH API
        
        Args:
            endpoint: API endpoint (e.g., '/vacancies')
            params: Query parameters
            retry_with_refresh: Whether to retry with refreshed token on 401
            
        Returns:
            JSON response as dictionary
        """
        if self.token_manager:
            try:
                self.token_manager.ensure_access_token()
            except Exception as e:
                print(f"Proactive token refresh failed: {e}")

        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        
        # Prepare headers
        headers = {
            "User-Agent": self.user_agent
        }
        access_token = self.token_manager.access_token if self.token_manager else None
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        
        # Make request
        url = f"{HH_API_BASE}{endpoint}"
        response = requests.get(url, headers=headers, params=params or {})
        self.last_request_time = time.time()
        
        # Handle 401 - try to refresh token
        if (
            response.status_code == 401
            and retry_with_refresh
            and self.token_manager
            and self.token_manager.can_refresh()
        ):
            print("Token expired, refreshing...")
            try:
                self.token_manager.force_refresh()
                print("Token refreshed successfully!")
                return self._make_request(endpoint, params, retry_with_refresh=False)
            except Exception as e:
                print(f"Failed to refresh token: {e}")
                raise Exception("Access token expired and refresh failed. Please re-authorize.")
        
        # Handle other errors
        if response.status_code == 403:
            raise Exception("Access denied. Check your access token for resume search.")
        elif response.status_code == 429:
            raise Exception("Rate limit exceeded. Please wait a moment.")
        elif response.status_code != 200:
            raise Exception(f"API error: {response.status_code} - {response.text}")
        
        return response.json()

    @staticmethod
    def build_full_url(endpoint: str, params: Dict[str, Any]) -> str:
        return f"{HH_API_BASE}{endpoint}?{requests.compat.urlencode(params, doseq=True)}"

    def _build_vacancy_params(
        self,
        *,
        text: Optional[str] = None,
        area: Optional[str] = None,
        professional_role: Optional[str] = None,
        search_everywhere: bool = True,
        search_in_name: bool = False,
        search_in_company_name: bool = False,
        search_in_description: bool = False,
        employment_form: Optional[str] = None,
        work_schedule_by_days: Optional[str] = None,
        work_format: Optional[str] = None,
        working_hours: Optional[str] = None,
        experience: Optional[str] = None,
        education: Optional[str] = None,
        salary: Optional[int] = None,
        currency: Optional[str] = None,
        salary_frequency: Optional[str] = None,
        salary_mode: Optional[str] = None,
        industry: Optional[str] = None,
        employer_id: Optional[str] = None,
        label: Optional[str] = None,
        type_: Optional[str] = None,
        period: Optional[int] = None,
        order_by: Optional[str] = None,
        metro: Optional[str] = None,
        specializations: Optional[str] = None,
        per_page: int = 1,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"per_page": per_page}
        if text:
            params["text"] = text
        if area:
            params["area"] = area
        if professional_role:
            params["professional_role"] = professional_role
        if employment_form:
            params["employment_form"] = employment_form
        if work_schedule_by_days:
            params["work_schedule_by_days"] = work_schedule_by_days
        if work_format:
            params["work_format"] = work_format
        if working_hours:
            params["working_hours"] = working_hours
        if experience:
            params["experience"] = experience
        if education:
            params["education"] = education
        if salary:
            params["salary"] = salary
        if currency:
            params["currency"] = currency
        if salary_frequency:
            params["salary_frequency"] = salary_frequency
        if salary_mode:
            params["salary_mode"] = salary_mode
        if industry:
            params["industry"] = industry
        if employer_id:
            params["employer_id"] = employer_id
        if label:
            params["label"] = label
        if type_:
            params["type"] = type_
        search_fields = []
        if not search_everywhere:
            if search_in_name:
                search_fields.append("name")
            if search_in_company_name:
                search_fields.append("company_name")
            if search_in_description:
                search_fields.append("description")
        if search_fields:
            params["search_field"] = search_fields
        if period:
            params["period"] = period
        if order_by:
            params["order_by"] = order_by
        if metro:
            params["metro"] = metro
        if specializations:
            params["specialization"] = specializations
        return params

    def _build_resume_params(
        self,
        *,
        text: Optional[str] = None,
        area: Optional[str] = None,
        professional_role: Optional[str] = None,
        text_logic: Optional[str] = None,
        text_field: Optional[str] = None,
        text_period: Optional[str] = None,
        education_levels: Optional[str] = None,
        relocation: Optional[str] = None,
        gender: Optional[str] = None,
        age_from: Optional[int] = None,
        age_to: Optional[int] = None,
        experience: Optional[str] = None,
        employment_form: Optional[str] = None,
        work_format: Optional[str] = None,
        salary_from: Optional[int] = None,
        salary_to: Optional[int] = None,
        currency: Optional[str] = None,
        language: Optional[str] = None,
        language_level: Optional[str] = None,
        skill: Optional[str] = None,
        period: Optional[int] = None,
        order_by: Optional[str] = None,
        job_search_status: Optional[str] = None,
        label: Optional[str] = None,
        per_page: int = 1,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"per_page": per_page}
        if text:
            params["text"] = text
        if area:
            params["area"] = area
        if professional_role:
            params["professional_role"] = professional_role
        if text:
            field = text_field if text_field else "title"
            params["text.field"] = field
            params["text.logic"] = text_logic if text_logic else "all"
            if text_period:
                params["text.period"] = text_period
            elif field.startswith("experience"):
                params["text.period"] = "all_time"
            else:
                params["text.period"] = "all_time"
        if education_levels:
            params["education_levels"] = education_levels
        if relocation:
            params["relocation"] = relocation
        if gender:
            params["gender"] = gender
        if age_from:
            params["age_from"] = age_from
        if age_to:
            params["age_to"] = age_to
        if experience:
            params["experience"] = experience
        if employment_form:
            params["employment_form"] = employment_form
        if work_format:
            params["work_format"] = work_format
        if salary_from:
            params["salary_from"] = salary_from
        if salary_to:
            params["salary_to"] = salary_to
        if currency:
            params["currency"] = currency
        if language and language_level:
            params["language"] = f"{language.strip()}.{language_level.strip()}"
        elif language:
            params["language"] = language.strip()
        if skill:
            params["skill"] = skill
        if period:
            params["period"] = period
        if order_by:
            params["order_by"] = order_by
        if job_search_status:
            params["job_search_status"] = job_search_status
        if label:
            params["label"] = label
        return params

    def search_vacancies_detail(self, **kwargs) -> Dict[str, Any]:
        params = self._build_vacancy_params(**kwargs)
        result = self._make_request("/vacancies", params)
        return {
            "found": result.get("found", 0),
            "params": params,
            "url": self.build_full_url("/vacancies", params),
        }

    def search_resumes_detail(self, **kwargs) -> Dict[str, Any]:
        if not self.token_manager.access_token:
            raise Exception(
                "Нет access token для поиска резюме. "
                "Укажите токены доступа или авторизуйтесь через /auth/login"
            )
        params = self._build_resume_params(**kwargs)
        print(f"\n[RESUME SEARCH REQUEST]")
        print(f"URL: {self.build_full_url('/resumes', params)}")
        result = self._make_request("/resumes", params)
        found = result.get("found", 0)
        print(f"[RESUME SEARCH RESPONSE] Found: {found}\n")
        return {
            "found": found,
            "params": params,
            "url": self.build_full_url("/resumes", params),
        }
    
    def search_vacancies(
        self,
        # Basic filters
        text: Optional[str] = None,
        area: Optional[str] = None,
        professional_role: Optional[str] = None,
        # Search fields
        search_everywhere: bool = True,
        search_in_name: bool = False,
        search_in_company_name: bool = False,
        search_in_description: bool = False,
        # Employment filters (new API)
        employment_form: Optional[str] = None,  # FULL, PART, PROJECT, FLY_IN_FLY_OUT, SIDE_JOB
        work_schedule_by_days: Optional[str] = None,  # SIX_ON_ONE_OFF, FIVE_ON_TWO_OFF, etc
        work_format: Optional[str] = None,  # ON_SITE, REMOTE, HYBRID, FIELD_WORK
        working_hours: Optional[str] = None,  # HOURS_2, HOURS_4, etc or FLEXIBLE
        experience: Optional[str] = None,  # noExperience, between1And3, between3And6, moreThan6
        # Education filter
        education: Optional[str] = None,  # not_required_or_not_specified, special_secondary, higher
        # Salary filters
        salary: Optional[int] = None,  # Single salary value
        currency: Optional[str] = None,  # RUR, USD, EUR, etc
        salary_frequency: Optional[str] = None,  # DAILY, WEEKLY, TWICE_PER_MONTH, MONTHLY, PER_PROJECT
        salary_mode: Optional[str] = None,  # MONTH, SHIFT, HOUR, FLY_IN_FLY_OUT, SERVICE
        # Additional filters
        industry: Optional[str] = None,
        employer_id: Optional[str] = None,
        label: Optional[str] = None,  # with_salary, accept_handicapped, accept_kids, etc
        type_: Optional[str] = None,  # open, closed, anonymous, direct
        period: Optional[int] = None,  # days (1, 3, 7, 30)
        order_by: Optional[str] = None,  # publication_time, salary_desc, salary_asc, relevance, distance
        # Geo filters
        metro: Optional[str] = None,
        specializations: Optional[str] = None,
        per_page: int = 1
    ) -> int:
        """
        Search vacancies and return total count
        
        Args:
            text: Search text
            area: Region ID
            professional_role: Professional role ID
            search_everywhere: Search in all fields (if False, use specific search fields)
            search_in_name: Search in vacancy name
            search_in_company_name: Search in company name
            search_in_description: Search in vacancy description
            employment_form: Employment form (FULL, PART, PROJECT, FLY_IN_FLY_OUT, SIDE_JOB)
            work_schedule_by_days: Work schedule by days (SIX_ON_ONE_OFF, FIVE_ON_TWO_OFF, etc)
            work_format: Work format (ON_SITE, REMOTE, HYBRID, FIELD_WORK)
            working_hours: Working hours per day (HOURS_2, HOURS_4, FLEXIBLE, etc)
            experience: Experience level (noExperience, between1And3, between3And6, moreThan6)
            education: Education requirement (not_required_or_not_specified, special_secondary, higher)
            salary: Desired salary amount
            currency: Currency code (RUR, USD, EUR, etc)
            salary_frequency: Salary frequency (DAILY, WEEKLY, TWICE_PER_MONTH, MONTHLY, PER_PROJECT)
            salary_mode: Salary mode (MONTH, SHIFT, HOUR, FLY_IN_FLY_OUT, SERVICE)
            industry: Industry ID
            employer_id: Specific employer ID
            label: Special labels (with_salary, accept_handicapped, accept_kids, etc)
            type_: Vacancy type (open, closed, anonymous, direct)
            period: Publication period in days (1, 3, 7, 30)
            order_by: Sort order (publication_time, salary_desc, salary_asc, relevance, distance)
            metro: Metro station ID
            specializations: Professional specializations
            per_page: Number of items per page (we only need count)
            
        Returns:
            Total number of found vacancies
        """
        return self.search_vacancies_detail(
            text=text,
            area=area,
            professional_role=professional_role,
            search_everywhere=search_everywhere,
            search_in_name=search_in_name,
            search_in_company_name=search_in_company_name,
            search_in_description=search_in_description,
            employment_form=employment_form,
            work_schedule_by_days=work_schedule_by_days,
            work_format=work_format,
            working_hours=working_hours,
            experience=experience,
            education=education,
            salary=salary,
            currency=currency,
            salary_frequency=salary_frequency,
            salary_mode=salary_mode,
            industry=industry,
            employer_id=employer_id,
            label=label,
            type_=type_,
            period=period,
            order_by=order_by,
            metro=metro,
            specializations=specializations,
            per_page=per_page,
        )["found"]
    
    def search_resumes(
        self,
        # Basic filters
        text: Optional[str] = None,
        area: Optional[str] = None,
        professional_role: Optional[str] = None,
        # Search fields - text.* triad
        text_logic: Optional[str] = None,  # all, any, phrase, except
        text_field: Optional[str] = None,  # everywhere, title, education, skills, experience, experience_company, experience_position, experience_description
        text_period: Optional[str] = None,  # all_time, last_year, last_three_years, last_six_years
        # Personal filters
        education_levels: Optional[str] = None,
        relocation: Optional[str] = None,  # living_or_relocation, living, living_but_relocation, relocation
        gender: Optional[str] = None,  # male, female
        age_from: Optional[int] = None,
        age_to: Optional[int] = None,
        # Work filters
        experience: Optional[str] = None,  # noExperience, between1And3, between3And6, moreThan6
        employment_form: Optional[str] = None,  # FULL, PART_TIME, INTERNSHIP, VOLUNTEER
        work_format: Optional[str] = None,  # ON_SITE, REMOTE, HYBRID, FIELD_WORK, FLY_IN_FLY_OUT
        # Salary filters
        salary_from: Optional[int] = None,
        salary_to: Optional[int] = None,
        currency: Optional[str] = None,
        # Additional filters
        language: Optional[str] = None,  # Language code, combined with level as eng.c1
        language_level: Optional[str] = None,  # a1, a2, b1, b2, c1, c2, l1
        skill: Optional[str] = None,  # Skill ID
        period: Optional[int] = None,  # days since last update
        order_by: Optional[str] = None,  # publication_time, salary_desc, salary_asc, relevance
        job_search_status: Optional[str] = None,  # active_search, looking_for_offers, not_looking_for_job, has_job_offer, accepted_job_offer
        label: Optional[str] = None,  # only_with_photo, only_with_salary, only_with_age, only_with_gender, only_with_vehicle, etc
        per_page: int = 1
    ) -> int:
        """
        Search resumes and return total count
        Note: Requires access token with appropriate permissions
        
        Args:
            text: Search text
            area: Region ID
            professional_role: Professional role ID
            text_logic: Search logic (all, any, phrase, except)
            text_field: Search field (everywhere, title, education, skills, experience, experience_company, experience_position, experience_description)
            text_period: Experience period (all_time, last_year, last_three_years, last_six_years)
            education_levels: Education level id from education_level dictionary
            relocation: Relocation from resume_search_relocation dictionary
            gender: Gender (male, female)
            age_from: Minimum age
            age_to: Maximum age
            experience: Experience level (noExperience, between1And3, between3And6, moreThan6)
            employment_form: From resume_employment_form dictionary (FULL, PART_TIME, etc.)
            work_format: From resume_work_format dictionary (ON_SITE, REMOTE, etc.)
            salary_from: Minimum desired salary
            salary_to: Maximum desired salary
            currency: Currency code (RUR, USD, EUR, etc)
            language: Language code (eng, deu, fra, etc) — sent as language.level
            language_level: Language level (a1, a2, b1, b2, c1, c2, l1)
            skill: Key skill ID
            period: Period since last update in days
            order_by: Sort order (publication_time, salary_desc, salary_asc, relevance)
            job_search_status: Job search status (active_search, looking_for_offers, not_looking_for_job, has_job_offer, accepted_job_offer)
            label: Special labels (only_with_photo, only_with_salary, only_with_age, only_with_gender, only_with_vehicle)
            per_page: Number of items per page
            
        Returns:
            Total number of found resumes
        """
        return self.search_resumes_detail(
            text=text,
            area=area,
            professional_role=professional_role,
            text_logic=text_logic,
            text_field=text_field,
            text_period=text_period,
            education_levels=education_levels,
            relocation=relocation,
            gender=gender,
            age_from=age_from,
            age_to=age_to,
            experience=experience,
            employment_form=employment_form,
            work_format=work_format,
            salary_from=salary_from,
            salary_to=salary_to,
            currency=currency,
            language=language,
            language_level=language_level,
            skill=skill,
            period=period,
            order_by=order_by,
            job_search_status=job_search_status,
            label=label,
            per_page=per_page,
        )["found"]
    
    def get_areas(self) -> List[Dict[str, Any]]:
        """Get list of regions/areas"""
        result = self._make_request("/areas")
        return self._flatten_areas(result)
    
    def _flatten_areas(self, areas: List[Dict], parent_name: str = "") -> List[Dict[str, Any]]:
        """Flatten nested area structure"""
        flat = []
        for area in areas:
            full_name = f"{parent_name}, {area['name']}" if parent_name else area['name']
            flat.append({
                "id": area["id"],
                "name": full_name
            })
            if area.get("areas"):
                flat.extend(self._flatten_areas(area["areas"], full_name))
        return flat
    
    def get_professional_roles(self) -> List[Dict[str, Any]]:
        """Get list of professional roles"""
        result = self._make_request("/professional_roles")
        roles = []
        for category in result.get("categories", []):
            for role in category.get("roles", []):
                roles.append({
                    "id": role["id"],
                    "name": role["name"]
                })
        return roles

    def get_professional_roles_tree(self) -> List[Dict[str, Any]]:
        """Professional roles grouped by category (as returned by HH API)."""
        result = self._make_request("/professional_roles")
        return result.get("categories", [])

    def get_category_professional_roles(self, category_id: str) -> Dict[str, Any]:
        """Roles for one category, e.g. category_id='11' for IT."""
        for category in self.get_professional_roles_tree():
            if str(category.get("id")) == str(category_id):
                return {
                    "id": category["id"],
                    "name": category["name"],
                    "roles": [
                        {
                            "id": role["id"],
                            "name": role["name"],
                        }
                        for role in category.get("roles", [])
                    ],
                }
        raise ValueError(f"Category not found: {category_id}")

    IT_CATEGORY_ID = "11"

    def search_vacancies_list(
        self,
        *,
        page: int = 0,
        per_page: int = 100,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Search vacancies and return full API page (items, found, pages).
        HH limits: per_page <= 100, max 2000 items (page * per_page < 2000).
        """
        if per_page > 100:
            raise ValueError("per_page must be <= 100")
        if page * per_page >= 2000:
            raise ValueError("HH API allows at most 2000 vacancies per query")
        params = self._build_vacancy_params(per_page=per_page, **kwargs)
        params["page"] = page
        return self._make_request("/vacancies", params)

    def get_vacancy(self, vacancy_id: str) -> Dict[str, Any]:
        """Full vacancy card with key_skills and salary."""
        return self._make_request(f"/vacancies/{vacancy_id}")

    def get_vacancy_found(
        self,
        *,
        professional_role: Optional[str] = None,
        area: Optional[str] = None,
        experience: Optional[str] = None,
        period: Optional[int] = None,
    ) -> int:
        """Total vacancies count for a filter (one page, per_page=1)."""
        result = self.search_vacancies_list(
            page=0,
            per_page=1,
            professional_role=professional_role,
            area=area,
            experience=experience,
            period=period,
        )
        return int(result.get("found") or 0)

    def iter_vacancy_items(
        self,
        *,
        professional_role: Optional[str] = None,
        area: Optional[str] = None,
        experience: Optional[str] = None,
        period: Optional[int] = None,
        per_page: int = 100,
        max_pages: int = 20,
    ):
        """Yield {id, name} for vacancies matching filters (up to API page limit)."""
        for page in range(max_pages):
            result = self.search_vacancies_list(
                page=page,
                per_page=per_page,
                professional_role=professional_role,
                area=area,
                experience=experience,
                period=period,
            )
            items = result.get("items") or []
            if not items:
                break
            for item in items:
                vid = item.get("id")
                name = (item.get("name") or "").strip()
                if vid and name:
                    yield {"id": str(vid), "name": name}
            total_pages = result.get("pages") or 0
            if page + 1 >= total_pages:
                break

    def get_area_clusters(
        self,
        *,
        professional_role: str,
        experience: Optional[str] = None,
        exclude_area_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Area buckets from clusters=true (areas that have vacancies for this filter).
        Excludes aggregate Russia (113) by default.
        """
        import re

        exclude = set(exclude_area_ids or ["113"])
        params: Dict[str, Any] = {
            "professional_role": professional_role,
            "per_page": 1,
            "clusters": True,
        }
        if experience:
            params["experience"] = experience
        result = self._make_request("/vacancies", params)
        areas: List[Dict[str, Any]] = []
        for cluster in result.get("clusters") or []:
            if cluster.get("id") != "area":
                continue
            for item in cluster.get("items") or []:
                match = re.search(r"area=(\d+)", item.get("url") or "")
                if not match:
                    continue
                area_id = match.group(1)
                if area_id in exclude:
                    continue
                areas.append(
                    {
                        "id": area_id,
                        "name": item.get("name"),
                        "count": int(item.get("count") or 0),
                    }
                )
        return areas

    EXPERIENCE_LEVELS = [
        "noExperience",
        "between1And3",
        "between3And6",
        "moreThan6",
    ]

    def iter_vacancy_titles_for_role(
        self,
        professional_role: str,
        *,
        per_page: int = 100,
        max_pages: int = 20,
        **kwargs,
    ):
        """Yield vacancy names for a professional_role (up to max_pages)."""
        for page in range(max_pages):
            result = self.search_vacancies_list(
                page=page,
                per_page=per_page,
                professional_role=professional_role,
                **kwargs,
            )
            items = result.get("items") or []
            if not items:
                break
            for item in items:
                name = (item.get("name") or "").strip()
                if name:
                    yield name
            total_pages = result.get("pages") or 0
            if page + 1 >= total_pages:
                break
    
    def get_employments(self) -> List[Dict[str, Any]]:
        """Get list of employment types"""
        return self._make_request("/dictionaries").get("employment", [])
    
    def get_schedules(self) -> List[Dict[str, Any]]:
        """Get list of work schedules"""
        return self._make_request("/dictionaries").get("schedule", [])
    
    def get_experience_levels(self) -> List[Dict[str, Any]]:
        """Get list of experience levels"""
        return self._make_request("/dictionaries").get("experience", [])
    
    def get_education_levels(self) -> List[Dict[str, Any]]:
        """Get list of education levels"""
        return self._make_request("/dictionaries").get("education_level", [])

    def get_vacancy_keyword_suggests(self, text: str) -> List[str]:
        """Keyword suggestions for vacancy search field"""
        query = text.strip()
        if len(query) < 2:
            return []
        result = self._make_request("/suggests/vacancy_search_keyword", {"text": query})
        return [item["text"] for item in result.get("items", []) if item.get("text")]

    def get_professional_role_suggests(self, text: str) -> List[Dict[str, Any]]:
        """Professional role suggestions for keyword field"""
        query = text.strip()
        if len(query) < 2:
            return []
        result = self._make_request("/suggests/professional_roles", {"text": query})
        return result.get("items", [])


def get_auth_url() -> str:
    """Generate OAuth authorization URL for employer access"""
    client_id = os.getenv("HH_CLIENT_ID")
    redirect_uri = os.getenv("HH_REDIRECT_URI")
    return (
        f"https://hh.ru/oauth/authorize?"
        f"response_type=code&"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"role=employer"
    )


def exchange_code_for_token(code: str) -> Dict[str, Any]:
    """Exchange authorization code for access token"""
    client_id = os.getenv("HH_CLIENT_ID")
    client_secret = os.getenv("HH_CLIENT_SECRET")
    redirect_uri = os.getenv("HH_REDIRECT_URI")
    
    response = requests.post(
        HH_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri
        }
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Token exchange failed: {response.text}")


def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """Refresh access token using refresh token (HH API spec)"""
    response = requests.post(
        HH_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Token refresh failed: {response.text}")
