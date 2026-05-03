import json
import re
import os
from datetime import datetime
from database import SessionLocal, init_db
from models import Doctor, Department, Service

def extract_number(text):
    if not text:
        return 0
    match = re.search(r'(\d+)', str(text))
    return int(match.group(1)) if match else 0

def extract_fee(text):
    if not text:
        return 0.0
    cleaned = re.sub(r'[^\d.]', ' ', str(text))
    match = re.search(r'(\d+(?:\.\d+)?)', cleaned)
    return float(match.group(1)) if match else 0.0

def clean(text, default=""):
    if not text:
        return default
    return str(text).strip()

def find_json_file():
    locations = [
        'hospital-complete-data.json',
        '../hospital-complete-data.json',
        os.path.join(os.path.dirname(__file__), 'hospital-complete-data.json'),
        os.path.join(os.path.dirname(__file__), '..', 'hospital-complete-data.json')
    ]
    for path in locations:
        if os.path.exists(path):
            return path
    return None

def load():
    print("\n" + "="*60)
    print("🏥 UNIVERSAL HOSPITALS - DATA LOADER")
    print("="*60)

    # Find JSON file
    json_path = find_json_file()
    if not json_path:
        print("❌ hospital-complete-data.json NOT FOUND!")
        print("Run parse_data.py first")
        return
    
    print(f"✅ Found: {json_path}")

    # Initialize database
    init_db()

    # Read data
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    db = SessionLocal()

    try:
        # ===== DOCTORS =====
        print("\n👨‍⚕️  Loading Doctors...")
        doctors = data.get("doctors", [])
        doctor_count = 0

        for doc in doctors:
            try:
                name = clean(doc.get("name"), "Unknown")
                
                # Skip if already exists
                exists = db.query(Doctor).filter(Doctor.name == name).first()
                if exists:
                    continue
                
                doctor = Doctor(
                    name=name,
                    specialization=clean(doc.get("specialization"), "General"),
                    department=clean(doc.get("department") or doc.get("specialization"), "General"),
                    experience_years=extract_number(doc.get("experience")),
                    consultation_fee=extract_fee(doc.get("consultation_fee")),
                    available_days=clean(doc.get("available_days"), "Sunday-Thursday"),
                    available_hours=clean(doc.get("available_hours"), "09:00 AM-05:00 PM"),
                    created_at=datetime.utcnow()
                )
                db.add(doctor)
                doctor_count += 1
                print(f"   ✅ {name}")
            
            except Exception as e:
                print(f"   ⚠️  Skipped: {str(e)[:40]}")
                continue

        db.commit()
        print(f"\n✅ {doctor_count} Doctors Loaded!")

        # ===== DEPARTMENTS =====
        print("\n🏥 Loading Departments...")
        departments = data.get("departments", [])
        dept_count = 0

        for dept in departments:
            try:
                name = clean(dept.get("name"), "Unknown")
                
                exists = db.query(Department).filter(Department.name == name).first()
                if exists:
                    continue
                
                department = Department(
                    name=name,
                    description=clean(dept.get("description")),
                    services=clean(dept.get("services")),
                    phone=clean(dept.get("phone")),
                    hours=clean(dept.get("hours")),
                    created_at=datetime.utcnow()
                )
                db.add(department)
                dept_count += 1
                print(f"   ✅ {name}")
            
            except Exception as e:
                print(f"   ⚠️  Skipped: {str(e)[:40]}")
                continue

        db.commit()
        print(f"\n✅ {dept_count} Departments Loaded!")

        # ===== SERVICES =====
        print("\n🔧 Loading Services...")
        services = data.get("services", [])
        service_count = 0

        for svc in services:
            try:
                name = clean(svc.get("name"), "Unknown")
                
                exists = db.query(Service).filter(Service.name == name).first()
                if exists:
                    continue
                
                service = Service(
                    name=name,
                    description=clean(svc.get("description")),
                    phone=clean(svc.get("phone")),
                    hours=clean(svc.get("hours")),
                    created_at=datetime.utcnow()
                )
                db.add(service)
                service_count += 1
                print(f"   ✅ {name}")
            
            except Exception as e:
                print(f"   ⚠️  Skipped: {str(e)[:40]}")
                continue

        db.commit()
        print(f"\n✅ {service_count} Services Loaded!")

        # ===== FINAL SUMMARY =====
        print("\n" + "="*60)
        print("📊 DATABASE SUMMARY")
        print("="*60)
        
        total_doctors = db.query(Doctor).count()
        total_departments = db.query(Department).count()
        total_services = db.query(Service).count()
        
        print(f"👨‍⚕️  Doctors:     {total_doctors}")
        print(f"🏥 Departments: {total_departments}")
        print(f"🔧 Services:    {total_services}")
        
        print("\n📋 Doctors in Database:")
        all_docs = db.query(Doctor).all()
        for doc in all_docs:
            print(f"   • {doc.name} | {doc.specialization} | {doc.experience_years} yrs | AED {doc.consultation_fee}")
        
        print("\n" + "="*60)
        print("✅ ALL DATA LOADED SUCCESSFULLY!")
        print("🎉 DEMO DATABASE IS READY!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    load()