from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from collections import defaultdict
import uuid
import json
import os
import httpx
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
    if not transcript:
        return "English"
    arabic_chars = sum(1 for c in transcript
                      if '\u0600' <= c <= '\u06FF')
    hindi_chars = sum(1 for c in transcript
                     if '\u0900' <= c <= '\u097F')
    if arabic_chars > 10:
        return "Arabic"
    if hindi_chars > 10:
        return "Hindi"
    return "English"

def detect_outcome(transcript: str) -> str:
    if not transcript:
        return "Information Provided"
    transcript_lower = transcript.lower()
    if any(word in transcript_lower for word in
           ['appointment', 'booked', 'confirmed', 'scheduled',
            'موعد', 'حجز', 'تأكيد', 'appointment confirm',
            'booking confirmed', 'aapka appointment']):
        return "Appointment Booked"
    elif any(word in transcript_lower for word in
             ['emergency', 'urgent', 'طوارئ', 'عاجل',
              'seena dard', 'heart attack']):
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
        r'(?:my name is|name is|I am|I\'m|this is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)',
        r'(?:اسمي|أنا)\s+([^\n\.،]+)',
        r'(?:mera naam|main hoon|naam hai)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)',
        r'Name:\s*([A-Za-z]+(?:\s+[A-Za-z]+)*)',
    ]
    for pattern in patterns:
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            stop_words = ['the', 'a', 'an', 'is', 'are', 'was', 'going', 'to']
            words = [w for w in name.split() if w.lower() not in stop_words]
            if words:
                return ' '.join(words[:3])[:50]
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
    from datetime import datetime, timedelta

    transcript_lower = transcript.lower()
    today = datetime.now()

    # Relative dates
    if 'today' in transcript_lower or 'اليوم' in transcript_lower or 'aaj' in transcript_lower:
        return today.strftime('%Y-%m-%d')

    if 'tomorrow' in transcript_lower or 'غدا' in transcript_lower or 'kal' in transcript_lower or 'next day' in transcript_lower:
        return (today + timedelta(days=1)).strftime('%Y-%m-%d')

    # Day names
    days_map = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2,
        'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
    }
    for day_name, day_num in days_map.items():
        if day_name in transcript_lower:
            days_ahead = day_num - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')

    # Explicit date patterns
    patterns = [
        r'(\d{4}-\d{2}-\d{2})',
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}',
    ]
    for pattern in patterns:
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            return match.group(1)

    # Default to tomorrow if nothing found
    return (today + timedelta(days=1)).strftime('%Y-%m-%d')

def extract_time(transcript: str) -> str:
    """Extract appointment time from transcript"""
    patterns = [
        r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))',
        r'(\d{1,2}\s*(?:AM|PM|am|pm))',
        r'at\s+(\d{1,2})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            time_str = match.group(1).upper()
            # Normalize format
            if ':' not in time_str:
                # Extract hour and add :00
                hour_match = re.search(r'(\d{1,2})', time_str)
                if hour_match:
                    hour = hour_match.group(1)
                    period = 'AM' if 'AM' in time_str else 'PM'
                    return f"{hour}:00 {period}"
            return time_str
    
    return "To Be Confirmed"

def process_transcript(raw_transcript) -> str:
    if not raw_transcript:
        return ""
    if isinstance(raw_transcript, str):
        return raw_transcript
    if isinstance(raw_transcript, list):
        parts = []
        for item in raw_transcript:
            if isinstance(item, dict):
                role = item.get("role", "")
                content = (
                    item.get("content", "") or
                    item.get("text", "") or
                    item.get("message", "") or ""
                )
                if role and content:
                    parts.append(f"{role.capitalize()}: {content}")
                elif content:
                    parts.append(content)
        return "\n".join(parts)
    return str(raw_transcript)

def extract_appointment(
    transcript: str,
    call_id: str,
    call_data: dict
):
    transcript_lower = transcript.lower()
    booking_keywords = [
        'appointment is confirmed',
        'appointment confirmed',
        'booked your appointment',
        'your appointment has been',
        'scheduled an appointment',
        'تم تأكيد موعدك',
        'تم الحجز',
        'aapka appointment confirm',
        'booking is confirmed'
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

        print(f"📨 FULL WEBHOOK: {json.dumps(body, indent=2, default=str)[:2000]}")

        event = (
            body.get("event") or
            body.get("type") or
            body.get("name") or ""
        )

        call_data = (
            body.get("data") or
            body.get("call") or
            body.get("call_data") or
            body
        )

        print(f"📨 Event: {event}")
        print(f"📨 Call ID: {call_data.get('call_id', 'not found')}")

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

            # Extract transcript from multiple possible fields
            raw_transcript = (
                call_data.get("transcript") or
                call_data.get("transcription") or
                call_data.get("transcript_object") or
                call_data.get("full_transcript") or
                ""
            )

            transcript = process_transcript(raw_transcript)

            # Extract call analysis
            call_analysis = call_data.get("call_analysis", {})
            call_summary = call_analysis.get("call_summary", "")
            user_sentiment = call_analysis.get("user_sentiment", "")
            call_successful = call_analysis.get(
                "call_successful", False
            )

            # Use summary as fallback if no transcript
            working_text = transcript or call_summary or ""

            duration = call_data.get("duration_ms", 0)
            duration_sec = duration // 1000 if duration else 0
            duration_str = (
                f"{duration_sec // 60}:{duration_sec % 60:02d}"
            )

            language = detect_language(working_text)
            outcome = detect_outcome(working_text)

            # Override outcome if call was successful appointment
            if (call_successful and
                    "appointment" in call_summary.lower()):
                outcome = "Appointment Booked"

            print(f"📝 Transcript: {len(transcript)} chars")
            print(f"📋 Summary: {call_summary[:100]}")
            print(f"🌐 Language: {language}")
            print(f"📊 Outcome: {outcome}")
            print(f"😊 Sentiment: {user_sentiment}")

            await calls_collection.update_one(
                {"call_id": call_id},
                {"$set": {
                    "status": "completed",
                    "duration": duration_str,
                    "transcript": transcript,
                    "call_summary": call_summary,
                    "user_sentiment": user_sentiment,
                    "call_successful": call_successful,
                    "language": language,
                    "outcome": outcome,
                    "ended_at": datetime.now()
                }},
                upsert=True
            )

            appointment = extract_appointment(
                working_text, call_id, call_data
            )
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
                print(f"✅ Appointment saved: {appointment['appointment_id']}")

            print(f"✅ Call completed: {call_id}")

        return {"status": "success"}

    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# HEALTH CHECK
# ============================================
@app.get("/")
async def health():
    return {
        "status": "running",
        "message": "Universal Hospital Backend"
    }

# ============================================
# DASHBOARD STATS
# ============================================
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

# ============================================
# REAL CHART DATA
# ============================================
@app.get("/api/dashboard/chart-data")
async def get_chart_data():
    try:
        all_appointments = await appointments_collection.find(
            {}, {"_id": 0, "created_at": 1, "status": 1, "specialty": 1}
        ).to_list(1000)

        all_calls = await calls_collection.find(
            {}, {"_id": 0, "created_at": 1, "outcome": 1}
        ).to_list(1000)

        # Group by day of week
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        day_data = defaultdict(
            lambda: {'calls': 0, 'appointments': 0, 'patients': 0}
        )

        for apt in all_appointments:
            if apt.get('created_at'):
                try:
                    day = apt['created_at'].strftime('%a')
                    day_data[day]['appointments'] += 1
                    day_data[day]['patients'] += 1
                except Exception:
                    pass

        for call in all_calls:
            if call.get('created_at'):
                try:
                    day = call['created_at'].strftime('%a')
                    day_data[day]['calls'] += 1
                except Exception:
                    pass

        chart_data = []
        for day in days:
            chart_data.append({
                'day': day,
                'calls': day_data[day]['calls'],
                'appointments': day_data[day]['appointments'],
                'patients': day_data[day]['patients']
            })

        # Specialty breakdown
        specialty_counts = defaultdict(int)
        for apt in all_appointments:
            specialty = apt.get('specialty', 'General Medicine')
            if specialty:
                specialty_counts[specialty] += 1

        total_apts = sum(specialty_counts.values()) or 1
        colors = [
            '#6366f1', '#8b5cf6', '#a78bfa',
            '#c4b5fd', '#e0e7ff'
        ]
        specialty_data = []
        sorted_specialties = sorted(
            specialty_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        for i, (name, count) in enumerate(sorted_specialties):
            specialty_data.append({
                'name': name,
                'value': round((count / total_apts) * 100),
                'color': colors[i % len(colors)]
            })

        # Outcome breakdown
        outcome_counts = defaultdict(int)
        for call in all_calls:
            outcome = call.get('outcome', 'Information Provided')
            if outcome and outcome != 'ongoing':
                outcome_counts[outcome] += 1

        total_calls = sum(outcome_counts.values()) or 1
        outcome_colors = [
            '#10b981', '#6366f1', '#ef4444', '#f59e0b'
        ]
        outcome_data = []
        for i, (name, count) in enumerate(outcome_counts.items()):
            outcome_data.append({
                'name': name,
                'value': round((count / total_calls) * 100),
                'color': outcome_colors[i % len(outcome_colors)]
            })

        return {
            'chart_data': chart_data,
            'specialty_data': specialty_data,
            'outcome_data': outcome_data
        }

    except Exception as e:
        print(f"❌ Chart data error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# APPOINTMENTS
# ============================================
@app.get("/api/appointments")
async def get_appointments(limit: int = 50, skip: int = 0):
    appointments = await appointments_collection.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"appointments": appointments, "total": len(appointments)}

@app.patch("/api/appointments/{appointment_id}")
async def update_appointment(
    appointment_id: str,
    request: Request
):
    body = await request.json()
    result = await appointments_collection.update_one(
        {"appointment_id": appointment_id},
        {"$set": body}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"status": "updated"}

@app.delete("/api/appointments/{appointment_id}")
async def delete_appointment(appointment_id: str):
    result = await appointments_collection.delete_one(
        {"appointment_id": appointment_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"status": "deleted"}

# ============================================
# CALLS
# ============================================
@app.get("/api/calls")
async def get_calls(limit: int = 50, skip: int = 0):
    calls = await calls_collection.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"calls": calls, "total": len(calls)}

@app.get("/api/calls/{call_id}")
async def get_call(call_id: str):
    call = await calls_collection.find_one(
        {"call_id": call_id}, {"_id": 0}
    )
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call

# ============================================
# PATIENTS
# ============================================
@app.get("/api/patients")
async def get_patients(limit: int = 50, skip: int = 0):
    patients = await patients_collection.find(
        {}, {"_id": 0}
    ).sort("last_visit", -1).skip(skip).limit(limit).to_list(limit)
    return {"patients": patients, "total": len(patients)}

# ============================================
# CREATE WEB CALL
# ============================================
@app.post("/create-web-call")
async def create_web_call(request: Request):
    try:
        body = await request.json()
        agent_id = body.get("agent_id")

        if not agent_id:
            raise HTTPException(status_code=400, detail="agent_id is required")

        RETELL_API_KEY = os.getenv("RETELL_API_KEY")

        if not RETELL_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="RETELL_API_KEY not configured"
            )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.retellai.com/v2/create-web-call",
                headers={
                    "Authorization": f"Bearer {RETELL_API_KEY.strip()}",
                    "Content-Type": "application/json"
                },
                json={"agent_id": agent_id},
                timeout=10.0
            )
            response.raise_for_status()

        data = response.json()
        print(f"✅ Web call: {data.get('call_id', 'unknown')}")
        return data

    except httpx.HTTPError as e:
        print(f"❌ HTTP error: {e}")
        raise HTTPException(status_code=502, detail=f"Retell API error: {str(e)}")
    except Exception as e:
        print(f"❌ Web call error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# CALENDAR ENDPOINTS
# ============================================
@app.get("/api/calendar/slots")
async def get_available_slots(doctor_name: str, date: str):
    try:
        booked = await appointments_collection.find({
            "doctor_name": doctor_name,
            "date": date,
            "status": {"$ne": "cancelled"}
        }, {"_id": 0, "time": 1}).to_list(100)

        booked_times = [
            apt["time"] for apt in booked if apt.get("time")
        ]

        all_slots = []
        for hour in range(8, 20):
            for minute in [0, 30]:
                period = "AM" if hour < 12 else "PM"
                display_hour = hour if hour <= 12 else hour - 12
                if display_hour == 0:
                    display_hour = 12
                time_str = f"{display_hour}:{minute:02d} {period}"
                is_booked = time_str in booked_times
                all_slots.append({
                    "time": time_str,
                    "available": not is_booked,
                    "status": "booked" if is_booked else "available"
                })

        return {
            "doctor": doctor_name,
            "date": date,
            "slots": all_slots,
            "total_available": sum(
                1 for s in all_slots if s["available"]
            ),
            "total_booked": sum(
                1 for s in all_slots if not s["available"]
            )
        }

    except Exception as e:
        print(f"❌ Calendar slots error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/calendar/month")
async def get_month_appointments(year: int, month: int):
    try:
        all_apts = await appointments_collection.find(
            {}, {"_id": 0}
        ).to_list(1000)

        calendar_data = {}

        for apt in all_apts:
            date = apt.get("date", "")
            if not date or date == "To Be Confirmed":
                continue

            if date not in calendar_data:
                calendar_data[date] = {
                    "total": 0,
                    "confirmed": 0,
                    "pending": 0,
                    "cancelled": 0,
                    "appointments": []
                }

            calendar_data[date]["total"] += 1
            status = apt.get("status", "pending")
            if status in calendar_data[date]:
                calendar_data[date][status] += 1

            calendar_data[date]["appointments"].append({
                "id": apt.get("appointment_id"),
                "patient": apt.get("patient_name"),
                "doctor": apt.get("doctor_name"),
                "specialty": apt.get("specialty"),
                "time": apt.get("time"),
                "status": apt.get("status")
            })

        return {
            "year": year,
            "month": month,
            "data": calendar_data
        }

    except Exception as e:
        print(f"❌ Calendar month error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/calendar/book")
async def book_appointment_with_check(request: Request):
    try:
        body = await request.json()
        doctor_name = body.get("doctor_name")
        date = body.get("date")
        time = body.get("time")
        patient_name = body.get("patient_name")
        patient_phone = body.get("patient_phone")
        specialty = body.get("specialty", "General Medicine")

        # Validate required fields
        if not all([doctor_name, date, time, patient_name, patient_phone]):
            raise HTTPException(
                status_code=400,
                detail="Missing required fields"
            )

        # CHECK DOUBLE BOOKING
        existing = await appointments_collection.find_one({
            "doctor_name": doctor_name,
            "date": date,
            "time": time,
            "status": {"$ne": "cancelled"}
        })

        if existing:
            return {
                "success": False,
                "error": f"This slot is already booked by {existing.get('patient_name', 'another patient')}"
            }

        appointment = {
            "appointment_id": f"UH-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}",
            "patient_name": patient_name,
            "patient_phone": patient_phone,
            "doctor_name": doctor_name,
            "specialty": specialty,
            "date": date,
            "time": time,
            "status": "confirmed",
            "call_type": "manual",
            "language": "English",
            "created_at": datetime.now()
        }

        await appointments_collection.insert_one(appointment)

        await patients_collection.update_one(
            {"phone": patient_phone},
            {
                "$set": {
                    "name": patient_name,
                    "phone": patient_phone,
                    "last_visit": datetime.now()
                },
                "$push": {
                    "appointments": appointment["appointment_id"]
                },
                "$inc": {"total_visits": 1}
            },
            upsert=True
        )

        return {
            "success": True,
            "appointment": appointment
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Booking error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True
    )
