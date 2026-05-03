"""
PARSE OCTOPARSE JSON EXPORT
Organize extracted data for database loading
"""

import json
from datetime import datetime

def parse():
    print("📥 Reading extracted_data.json...")
    
    # Read Octoparse export
    try:
        with open('extracted_data.json', 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except FileNotFoundError:
        print("❌ extracted_data.json not found!")
        print("   Make sure file is in current directory")
        return
    except json.JSONDecodeError:
        print("❌ Invalid JSON format!")
        return
    
    # Octoparse puts data in "data" key or returns list
    records = raw.get('data', []) if isinstance(raw, dict) else raw
    
    print(f"✅ Found {len(records)} records\n")
    
    # Organize data
    organized = {
        "hospital": {
            "name": "Universal Hospitals Abu Dhabi",
            "website": "https://universalhospitals.com",
            "last_scraped": datetime.now().isoformat()
        },
        "doctors": [],
        "departments": [],
        "services": [],
        "contact": {}
    }
    
    # Sort records by type
    for record in records:
        # Check what type of record this is
        record_str = str(record).lower()
        
        # DOCTORS: has specialization, experience, consultation
        if any(x in record_str for x in ['specialization', 'experience', 'consultation', 'doctor']):
            organized["doctors"].append(record)
        
        # DEPARTMENTS: has department, ward, services offered
        elif any(x in record_str for x in ['department', 'ward', 'services', 'cardiology', 'orthopedics']):
            organized["departments"].append(record)
        
        # SERVICES: has lab, imaging, pharmacy, emergency
        elif any(x in record_str for x in ['laboratory', 'imaging', 'pharmacy', 'emergency', 'service']):
            organized["services"].append(record)
        
        # CONTACT: has phone, email, address
        elif any(x in record_str for x in ['phone', 'email', 'address', 'contact']):
            if isinstance(record, dict):
                organized["contact"].update(record)
    
    # Save organized
    with open('hospital-complete-data.json', 'w', encoding='utf-8') as f:
        json.dump(organized, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("="*60)
    print("✅ PARSED & ORGANIZED")
    print("="*60)
    print(f"👨‍⚕️  Doctors: {len(organized['doctors'])}")
    print(f"🏥 Departments: {len(organized['departments'])}")
    print(f"🔧 Services: {len(organized['services'])}")
    print(f"📞 Contact Info: {len(organized['contact'])} fields")
    print("="*60)
    print("📝 Saved as: hospital-complete-data.json")
    print("="*60)

if __name__ == "__main__":
    parse()