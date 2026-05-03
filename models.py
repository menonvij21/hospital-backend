from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Doctor(Base):
    __tablename__ = "doctors"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    specialization = Column(String(255))
    department = Column(String(255))
    experience_years = Column(Integer, default=0)
    consultation_fee = Column(Float, default=0.0)
    available_days = Column(String(255))
    available_hours = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

class Department(Base):
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    description = Column(Text)
    services = Column(Text)
    phone = Column(String(50))
    hours = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

class Service(Base):
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    description = Column(Text)
    phone = Column(String(50))
    hours = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)