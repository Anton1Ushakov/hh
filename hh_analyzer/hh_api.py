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
RATE_LIMIT_DELAY = 0.2  # seconds between requests (max 10 req/sec)


class HHAPIClient:
    """Client for HH.ru API with automatic token refresh"""
    
    def __init__(self, access_token: Optional[str] = None, refresh_token: Optional[str] = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.last_request_time = 0
        self.user_agent = os.getenv("HH_USER_AGENT", "HH-Analytics-App/1.0")
    
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
        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        
        # Prepare headers
        headers = {
            "User-Agent": self.user_agent
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        # Make request
        url = f"{HH_API_BASE}{endpoint}"
        response = requests.get(url, headers=headers, params=params or {})
        self.last_request_time = time.time()
        
        # Handle 401 - try to refresh token
        if response.status_code == 401 and retry_with_refresh and self.refresh_token:
            print("Token expired, refreshing...")
            try:
                new_tokens = refresh_access_token(self.refresh_token)
                self.access_token = new_tokens.get("access_token")
                self.refresh_token = new_tokens.get("refresh_token")
                
                # Update environment variables
                os.environ["HH_ACCESS_TOKEN"] = self.access_token
                os.environ["HH_REFRESH_TOKEN"] = self.refresh_token
                
                print("Token refreshed successfully!")
                
                # Retry request with new token
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
        params = {"per_page": per_page}
        
        # Basic filters
        if text:
            params["text"] = text
        if area:
            params["area"] = area
        if professional_role:
            params["professional_role"] = professional_role
        
        # Employment filters (new API)
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
        
        # Education filter
        if education:
            params["education"] = education
        
        # Salary filters
        if salary:
            params["salary"] = salary
        if currency:
            params["currency"] = currency
        if salary_frequency:
            params["salary_frequency"] = salary_frequency
        if salary_mode:
            params["salary_mode"] = salary_mode
        
        # Additional filters
        if industry:
            params["industry"] = industry
        if employer_id:
            params["employer_id"] = employer_id
        if label:
            params["label"] = label
        if type_:
            params["type"] = type_
        
        # Search fields - build search field list
        # If 'everywhere' is checked or no specific fields selected, don't limit search
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
        
        # Geo filters
        if metro:
            params["metro"] = metro
        if specializations:
            params["specialization"] = specializations
        
        result = self._make_request("/vacancies", params)
        return result.get("found", 0)
    
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
        education: Optional[str] = None,
        relocation: Optional[str] = None,  # living_or_relocation, living, living_but_relocation, relocation
        gender: Optional[str] = None,  # male, female
        age_from: Optional[int] = None,
        age_to: Optional[int] = None,
        # Work filters
        experience: Optional[str] = None,  # noExperience, between1And3, between3And6, moreThan6
        employment: Optional[str] = None,
        schedule: Optional[str] = None,
        # Salary filters
        salary_from: Optional[int] = None,
        salary_to: Optional[int] = None,
        currency: Optional[str] = None,
        # Additional filters
        language: Optional[str] = None,  # Language code
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
            education: Education level (secondary, special_secondary, unfinished_higher, higher, bachelor, master, candidate, doctorate)
            relocation: Relocation (living_or_relocation, living, living_but_relocation, relocation)
            gender: Gender (male, female)
            age_from: Minimum age
            age_to: Maximum age
            experience: Experience level (noExperience, between1And3, between3And6, moreThan6)
            employment: Employment type (full, part, project, volunteer, probation)
            schedule: Work schedule (fullDay, shift, flexible, remote, flyInFlyOut)
            salary_from: Minimum desired salary
            salary_to: Maximum desired salary
            currency: Currency code (RUR, USD, EUR, etc)
            language: Language code (eng, deu, fra, etc)
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
        if not self.access_token:
            # Return mock data if no token
            return 0
        
        params = {"per_page": per_page}
        
        # Basic filters
        if text:
            params["text"] = text
        if area:
            params["area"] = area
        if professional_role:
            params["professional_role"] = professional_role
        
        # Search fields - use text.* triad for resumes
        # text.logic: all, any, phrase, except
        # text.field: everywhere, title, education, skills, experience, experience_company, experience_position, experience_description
        # text.period: all_time, last_year, last_three_years, last_six_years (required when text.field is experience-related)
        # Default: text.field=everywhere, text.logic=all
        if text:
            params["text.field"] = text_field if text_field else "everywhere"
            params["text.logic"] = text_logic if text_logic else "all"
            if text_period:
                params["text.period"] = text_period
            elif text_field and text_field.startswith("experience"):
                # Default period for experience fields
                params["text.period"] = "all_time"
        
        # Personal filters
        if education:
            params["education"] = education
        if relocation:
            params["relocation"] = relocation
        if gender:
            params["gender"] = gender
        if age_from:
            params["age_from"] = age_from
        if age_to:
            params["age_to"] = age_to
        
        # Work filters
        if experience:
            params["experience"] = experience
        if employment:
            params["employment"] = employment
        if schedule:
            params["schedule"] = schedule
        
        # Salary filters
        if salary_from:
            params["salary_from"] = salary_from
        if salary_to:
            params["salary_to"] = salary_to
        if currency:
            params["currency"] = currency
        
        # Additional filters
        if language:
            params["language"] = language
        if language_level:
            params["language_level"] = language_level
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
        
        try:
            # Log the request params
            print(f"\n[RESUME SEARCH REQUEST]")
            print(f"URL: https://api.hh.ru/resumes")
            print(f"Params: {params}")
            print(f"Full URL: https://api.hh.ru/resumes?{requests.compat.urlencode(params, doseq=True)}")
            result = self._make_request("/resumes", params)
            print(f"[RESUME SEARCH RESPONSE] Found: {result.get('found', 0)}\n")
            return result.get("found", 0)
        except Exception as e:
            # If resume search fails, return 0
            print(f"[RESUME SEARCH ERROR] {e}")
            return 0
    
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


def get_auth_url() -> str:
    """Generate OAuth authorization URL"""
    client_id = os.getenv("HH_CLIENT_ID")
    redirect_uri = os.getenv("HH_REDIRECT_URI")
    return (
        f"https://hh.ru/oauth/authorize?"
        f"response_type=code&"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}"
    )


def exchange_code_for_token(code: str) -> Dict[str, Any]:
    """Exchange authorization code for access token"""
    client_id = os.getenv("HH_CLIENT_ID")
    client_secret = os.getenv("HH_CLIENT_SECRET")
    redirect_uri = os.getenv("HH_REDIRECT_URI")
    
    response = requests.post(
        "https://hh.ru/oauth/token",
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
    """Refresh access token using refresh token"""
    client_id = os.getenv("HH_CLIENT_ID")
    client_secret = os.getenv("HH_CLIENT_SECRET")
    
    response = requests.post(
        "https://hh.ru/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token
        }
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Token refresh failed: {response.text}")
