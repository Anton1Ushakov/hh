"""
Script to initialize cached dictionaries from HH.ru API
Run this once to populate the database with areas, roles, etc.
"""

from dotenv import load_dotenv

from database import init_db, SessionLocal
from dict_service import refresh_all_dictionaries
from hh_api import HHAPIClient

load_dotenv()


def init_dictionaries():
    print("Initializing dictionaries from HH.ru API...")
    init_db()
    db = SessionLocal()
    client = HHAPIClient()
    try:
        refresh_all_dictionaries(db, client)
        print("All dictionaries initialized successfully!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    init_dictionaries()
