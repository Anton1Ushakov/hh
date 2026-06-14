"""
Script to initialize cached dictionaries from HH.ru API
Run this once to populate the database with areas, roles, etc.
"""

import os
import json
from database import init_db, SessionLocal, CachedDictionary
from hh_api import HHAPIClient
from dotenv import load_dotenv

load_dotenv()

def init_dictionaries():
    """Fetch and cache all dictionaries from HH API"""
    print("Initializing dictionaries from HH.ru API...")
    
    # Initialize database
    init_db()
    db = SessionLocal()
    
    # Create API client (no token needed for public endpoints)
    client = HHAPIClient()
    
    try:
        # Fetch and cache areas
        print("Fetching areas...")
        areas = client.get_areas()
        cache_dict(db, "areas", areas)
        print(f"  Cached {len(areas)} areas")
        
        # Fetch and cache professional roles
        print("Fetching professional roles...")
        roles = client.get_professional_roles()
        cache_dict(db, "professional_roles", roles)
        print(f"  Cached {len(roles)} roles")
        
        # Fetch and cache dictionaries
        print("Fetching dictionaries...")
        dicts = client._make_request("/dictionaries")
        
        cache_dict(db, "employments", dicts.get("employment", []))
        print(f"  Cached {len(dicts.get('employment', []))} employment types")
        
        cache_dict(db, "schedules", dicts.get("schedule", []))
        print(f"  Cached {len(dicts.get('schedule', []))} schedules")
        
        cache_dict(db, "experiences", dicts.get("experience", []))
        print(f"  Cached {len(dicts.get('experience', []))} experience levels")
        
        cache_dict(db, "educations", dicts.get("education_level", []))
        print(f"  Cached {len(dicts.get('education_level', []))} education levels")
        
        print("\nAll dictionaries initialized successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


def cache_dict(db, dict_type, data):
    """Cache dictionary in database"""
    from datetime import datetime
    
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
    init_dictionaries()
