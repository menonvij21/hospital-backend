import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hospital.db")
    PORT = int(os.getenv("PORT", 8000))
    HOSPITAL_NAME = os.getenv("HOSPITAL_NAME", "Universal Hospitals Abu Dhabi")
    HOSPITAL_WEBSITE = os.getenv("HOSPITAL_WEBSITE", "https://universalhospitals.com")