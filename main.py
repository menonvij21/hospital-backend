from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid
import json
import os
import re
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

# Database Setup
MONGODB_URL = os.getenv("MONGODB_URL")
DB_NAME = os.getenv("DB_NAME")

client = AsyncIOMotorClient(
    MONGODB_URL,
    tls=True,
    tlsAllowInvalidCertificates=True
)
db = client[DB_NAME]

appointments_collection = db["appointments"]
calls_collection = db["calls"]
patients_collection = db["patients"]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# HELPER FUNCTIONS
# ============================================
def detect_language(transcript: str) -> str:
    arabic_chars = sum(1 for c in transcript
                      if '\u0600' <= c <= '\u06FF')
    if arabic_chars > 10:
        return "Arabic"
    return "English"

def detect_outcome(transcript: str) -> str:
    transcript_lower = transcript.lower()
    if any(word in transcript_lower for word in
           ['appointment', 'booked', 'confirmed', 'scheduled',
            'موعد', 'حجز', 'تأكيد']):
        return "Appointment Booked"
    elif any(word in transcript_lower for word in
             ['emergency', 'urgent', 'طوارئ', 'عاجل']):
        return "Emergency Handled"
    elif any(word in transcript_lower for word in
             ['transfer', 'connect you', 'human', 'staff',
              'تحويل', 'موظف']):
        return "Transferred to Human"
    elif any(word in transcript_lower for word in
             ['reschedule', 'cancel', 'إلغاء', 'تغيير']):
        return "Appointment Modified"
    else:
        return "Information Provided"

def extract_name(transcript: str) -> str:
    patterns = [
        r'name is ([A-Za-z\s]+)',
        r'my name[\'s]* ([A-Za-z\s]+)',
        r'اسمي ([^\n]+)',
        r'Name: ([A-Za-z\s]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:50]
    return "Unknown Patient"

def extract_phone(transcript: str, call_data: dict) -> str:
    if call_data.get("from_number"):
        return call_data["from_number"]
    patterns = [
        r'(\+971[\s-]?\d{2}[\s-]?\d{3}[\s-]?\d{4})',
        r'(05\d[\s-]?\d{3}[\s-]?\d{4})',
        r'(\d{10,12})',
    ]
    for pattern in patterns:
        match = re.search(pattern, transcript)
        if match:
            return match.group(1)
    return "Not provided"

def extract_doctor(transcript: str) -> str:
    doctors = [
        "Dr. Mohammed Al Rashidi", "Dr. Priya Sharma",
        "Dr. James Williams", "Dr. Ahmed Al Mansouri",
        "Dr. Sarah Johnson", "Dr. Khalid Al Zaabi",
        "Dr. David Chen", "Dr. Rajan Patel",
        "Dr. Fatima Al Hashimi", "Dr. Hassan Al Nuaimi",
        "Dr. Anil Kumar", "Dr. Hessa Al Qubaisi",
        "Dr. Smitha Rajan", "Dr. Moza Al Ketbi",
        "Dr. Vinod Kumar", "Dr. Sultan Al Dhaheri",
        "Dr. Amna Al Marzooqi", "Dr. Mansoor Al Bloushi",
        "Dr. Aisha Al Muhairi", "Dr. Noura Al Shamsi",
    ]
    for doctor in doctors:
        if doctor.lower() in transcript.lower():
            return doctor
    return "To Be Assigned"

def extract_specialty(transcript: str) -> str:
    specialties = {
        "cardiology": "Cardiology",
        "heart": "Cardiology",
        "orthopedic": "Orthopedic Surgery",
        "bone": "Orthopedic Surgery",
        "knee": "Orthopedic Surgery",
        "dermatology": "Dermatology",
        "skin": "Dermatology",
        "neurology": "Neurology",
        "brain": "Neurology",
        "gynecology": "Obstetrics & Gynecology",
        "obstetrics": "Obstetrics & Gynecology",
        "paediatric": "Paediatrics",
        "children": "Paediatrics",
        "gastro": "Gastroenterology",
        "stomach": "Gastroenterology",
        "urology": "Urology",
        "kidney": "Nephrology",
        "psychiatry": "Psychiatry",
        "mental": "Psychiatry",
        "pulmonary": "Pulmonary Medicine",
        "lung": "Pulmonary Medicine",
        "rheumatology": "Rheumatology",
        "joint": "Rheumatology",
        "ophthalmology": "Ophthalmology",
        "eye": "Ophthalmology",
        "ent": "ENT",
        "ear": "ENT",
        "dental": "Dentistry",
        "teeth": "Dentistry",
    }
    transcript_lower = transcript.lower()
    for keyword, specialty in specialties.items():
        if keyword in transcript_lower:
            return specialty
    return "General Medicine"

def extract_date(transcript: str) -> str:
    patterns = [
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}',
        r'(tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
    ]
    for pattern in patterns:
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            return match.group(1)
    return "To Be Confirmed"

def extract_time(transcript: str) -> str:
    patterns = [
        r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))',
        r'(\d{1,2}\s*(?:AM|PM|am|pm))',
        r'(morning|afternoon|evening)',
    ]
    for pattern in patterns:
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            return match.group(1)
    return "To Be Confirmed"

def extract_appointment(transcript: str, call_id: str, call_data: dict):
    transcript_lower = transcript.lower()
    booking_keywords = [
        'appointment is confirmed',
        'appointment confirmed',
        'booked your appointment',
        'تم تأكيد موعدك',
        'تم الحجز'
    ]
    if not any(kw in transcript_lower for kw in booking_keywords):
        return None
    return {
        "appointment_id": f"UH-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}",
        "call_id": call_id,
        "patient_name": extract_name(transcript),
        "patient_phone": extract_phone(transcript, call_data),
        "doctor_name": extract_doctor(transcript),
        "specialty": extract_specialty(transcript),
        "date": extract_date(transcript),
        "time": extract_time(transcript),
        "language": detect_language(transcript),
        "status": "confirmed",
        "call_type": call_data.get("direction", "inbound"),
        "created_at": datetime.now()
    }

# ============================================
# RETELL AI WEBHOOK
# ============================================
@app.post("/retell-webhook")
async def retell_webhook(request: Request):
    try:
        body = await request.json()
        print(f"📨 Retell Webhook: {json.dumps(body, indent=2)}")

        event = body.get("event", "")
        call_data = body.get("data", {})

        if event == "call_started":
            call_id = call_data.get("call_id", str(uuid.uuid4()))
            await calls_collection.insert_one({
                "call_id": call_id,
                "call_type": call_data.get("direction", "inbound"),
                "caller_phone": call_data.get("from_number", ""),
                "status": "ongoing",
                "language": "unknown",
                "outcome": "ongoing",
                "appointment_booked": False,
                "created_at": datetime.now()
            })
            print(f"✅ Call started: {call_id}")

        elif event == "call_ended":
            call_id = call_data.get("call_id", "")
            transcript = call_data.get("transcript", "")
            duration = call_data.get("duration_ms", 0)
            duration_sec = duration // 1000
            duration_str = f"{duration_sec // 60}:{duration_sec % 60:02d}"
            language = detect_language(transcript)
            outcome = detect_outcome(transcript)

            await calls_collection.update_one(
                {"call_id": call_id},
                {"$set": {
                    "status": "completed",
                    "duration": duration_str,
                    "transcript": transcript,
                    "language": language,
                    "outcome": outcome,
                    "ended_at": datetime.now()
                }}
            )

            appointment = extract_appointment(transcript, call_id, call_data)
            if appointment:
                await appointments_collection.insert_one(appointment)
                await calls_collection.update_one(
                    {"call_id": call_id},
                    {"$set": {
                        "appointment_booked": True,
                        "appointment_id": appointment["appointment_id"]
                    }}
                )
                await patients_collection.update_one(
                    {"phone": appointment["patient_phone"]},
                    {
                        "$set": {
                            "name": appointment["patient_name"],
                            "phone": appointment["patient_phone"],
                            "last_visit": datetime.now(),
                        },
                        "$push": {
                            "appointments": appointment["appointment_id"]
                        },
                        "$inc": {"total_visits": 1}
                    },
                    upsert=True
                )
                print(f"✅ Appointment saved!")

        return {"status": "success"}

    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# DASHBOARD API ENDPOINTS
# ============================================
@app.get("/")
async def health():
    return {"status": "running", "message": "Universal Hospital Backend"}

@app.get("/api/dashboard/stats")
async def get_stats():
    today = datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return {
        "total_appointments": await appointments_collection.count_documents({}),
        "total_patients": await patients_collection.count_documents({}),
        "total_calls": await calls_collection.count_documents({}),
        "todays_appointments": await appointments_collection.count_documents(
            {"created_at": {"$gte": today}}
        ),
        "todays_calls": await calls_collection.count_documents(
            {"created_at": {"$gte": today}}
        ),
        "confirmed": await appointments_collection.count_documents(
            {"status": "confirmed"}
        ),
        "pending": await appointments_collection.count_documents(
            {"status": "pending"}
        ),
        "cancelled": await appointments_collection.count_documents(
            {"status": "cancelled"}
        ),
    }

@app.get("/api/appointments")
async def get_appointments(limit: int = 50, skip: int = 0):
    appointments = await appointments_collection.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"appointments": appointments, "total": len(appointments)}

@app.get("/api/calls")
async def get_calls(limit: int = 50, skip: int = 0):
    calls = await calls_collection.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"calls": calls, "total": len(calls)}

@app.get("/api/patients")
async def get_patients(limit: int = 50, skip: int = 0):
    patients = await patients_collection.find(
        {}, {"_id": 0}
    ).sort("last_visit", -1).skip(skip).limit(limit).to_list(limit)
    return {"patients": patients, "total": len(patients)}

@app.patch("/api/appointments/{appointment_id}")
async def update_appointment(appointment_id: str, request: Request):
    body = await request.json()
    await appointments_collection.update_one(
        {"appointment_id": appointment_id},
        {"$set": body}
    )
    return {"status": "updated"}

@app.delete("/api/appointments/{appointment_id}")
async def delete_appointment(appointment_id: str):
    await appointments_collection.delete_one(
        {"appointment_id": appointment_id}
    )
    return {"status": "deleted"}

@app.get("/api/calls/{call_id}")
async def get_call(call_id: str):
    call = await calls_collection.find_one(
        {"call_id": call_id}, {"_id": 0}
    )
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)