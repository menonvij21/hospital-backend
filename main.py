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
    arabic_chars = sum(1 for c in transcript if '\u0600' <= c <= '\u06FF')
    hindi_chars = sum(1 for c in transcript if '\u0900' <= c <= '\u097F')
    if arabic_chars > 10:
        return "Arabic"
    if hindi_chars > 10:
        return "Hindi"
    return "English"

def detect_outcome(transcript: str) -> str:
    if not transcript:
        return "Information Provided"
    transcript_lower = transcript.lower()
    if any(word in transcript_lower for word in [
        'appointment', 'booked', 'confirmed', 'scheduled',
        'موعد', 'حجز', 'تأكيد', 'appointment confirm',
        'booking confirmed', 'aapka appointment'
    ]):
        return "Appointment Booked"
    elif any(word in transcript_lower for word in [
        'emergency', 'urgent', 'طوارئ', 'عاجل', 'seena dard', 'heart attack'
    ]):
        return "Emergency Handled"
    elif any(word in transcript_lower for word in [
        'transfer', 'connect you', 'human', 'staff', 'تحويل', 'موظف'
    ]):
        return "Transferred to Human"
    elif any(word in transcript_lower for word in [
        'reschedule', 'cancel', 'إلغاء', 'تغيير'
    ]):
        return "Appointment Modified"
    else:
        return "Information Provided"

def extract_name(transcript: str) -> str:
    # Only search USER lines to avoid matching "I am Sara" as patient name
    user_lines = []
    for line in transcript.split("\n"):
        stripped = line.strip()
        lower = stripped.lower()
        # Skip agent/Sara lines
        if lower.startswith("agent:") or lower.startswith("sara:") or lower.startswith("assistant:"):
            continue
        cleaned = re.sub(r"^(user|patient|caller):\s*", "", stripped, flags=re.IGNORECASE)
        user_lines.append(cleaned)

    search_text = "\n".join(user_lines) if user_lines else transcript

    patterns = [
        r"(?:my name is|name is|I am|I\'m|this is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)",
        r"(?:اسمي|أنا)\s+([^\n\.،]+)",
        r"(?:mera naam|main hoon|naam hai)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)",
        r"Name:\s*([A-Za-z]+(?:\s+[A-Za-z]+)*)",
    ]
    # Never return these as a patient name
    blacklist = {"sara", "universal", "hospital", "agent", "assistant", "ai"}

    for pattern in patterns:
        match = re.search(pattern, search_text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            stop_words = ["the", "a", "an", "is", "are", "was", "going", "to"]
            words = [w for w in name.split() if w.lower() not in stop_words]
            words = [w for w in words if w.lower() not in blacklist]
            if words:
                return " ".join(words[:3])[:50]
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
    from datetime import timedelta
    transcript_lower = transcript.lower()
    today = datetime.now()

    if 'today' in transcript_lower or 'اليوم' in transcript_lower or 'aaj' in transcript_lower:
        return today.strftime('%Y-%m-%d')
    if 'tomorrow' in transcript_lower or 'غدا' in transcript_lower or 'kal' in transcript_lower or 'next day' in transcript_lower:
        return (today + timedelta(days=1)).strftime('%Y-%m-%d')

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

    patterns = [
        r'(\d{4}-\d{2}-\d{2})',
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}',
    ]
    for pattern in patterns:
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            return match.group(1)

    return (today + timedelta(days=1)).strftime('%Y-%m-%d')

def extract_time(transcript: str) -> str:
    patterns = [
        r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))',
        r'(\d{1,2}\s*(?:AM|PM|am|pm))',
        r'at\s+(\d{1,2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, transcript, re.IGNORECASE)
        if match:
            time_str = match.group(1).upper()
            if ':' not in time_str:
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

def extract_appointment(transcript: str, call_id: str, call_data: dict):
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
# RETELL CUSTOM TOOL — BOOK APPOINTMENT
# Called by Sara MID-CALL the moment patient confirms.
# Sara passes structured data directly — no parsing needed.
# Set this URL in Retell dashboard under Agent → Tools.
# ============================================
@app.post("/api/retell-book")
async def retell_book(request: Request):
    try:
        body = await request.json()

        # Log everything so we can see exactly what Retell sends
        print(f"🔧 Retell tool RAW BODY: {json.dumps(body, default=str)}")
        print(f"🔧 Body keys: {list(body.keys())}")

        # Retell can send args in multiple formats:
        # Format 1: { "args": { "patient_name": ... } }
        # Format 2: { "patient_name": ... }  (flat)
        # Format 3: { "parameters": { ... } }
        args = (
            body.get("args") or
            body.get("parameters") or
            body.get("input") or
            body
        )

        print(f"🔧 Resolved args: {json.dumps(args, default=str)}")

        # Use str() to safely handle None values before stripping
        patient_name  = str(args.get("patient_name") or "").strip()
        patient_phone = str(args.get("patient_phone") or "").strip() or "Not provided"
        doctor_name   = str(args.get("doctor_name") or "").strip() or "To Be Assigned"
        specialty     = str(args.get("specialty") or "").strip() or "General Medicine"
        date          = str(args.get("date") or "").strip()
        time          = str(args.get("time") or "").strip()
        language      = str(args.get("language") or "English").strip()
        call_id       = str(args.get("call_id") or body.get("call_id") or "").strip()

        # If name is missing or invalid, try to get it from the call transcript
        blacklisted_names = {"unknown patient", "sara", "universal", "hospital", "agent", "assistant", ""}
        if patient_name.lower() in blacklisted_names:
            # Try to pull from the call record in MongoDB
            if call_id:
                try:
                    call_record = await calls_collection.find_one({"call_id": call_id}, {"_id": 0, "transcript": 1})
                    if call_record and call_record.get("transcript"):
                        extracted = extract_name(call_record["transcript"])
                        if extracted.lower() not in blacklisted_names:
                            patient_name = extracted
                except Exception as ne:
                    print(f"⚠️ Name extraction fallback error: {ne}")
            # Final fallback
            if patient_name.lower() in blacklisted_names:
                patient_name = "Unknown Patient"

        # Fix wrong year — if Retell sends a past date, correct the year to current/next year
        if date:
            try:
                from datetime import timedelta
                parsed = datetime.strptime(date, "%Y-%m-%d")
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                if parsed < today:
                    # Move to same month/day in current or next year
                    corrected = parsed.replace(year=today.year)
                    if corrected < today:
                        corrected = parsed.replace(year=today.year + 1)
                    date = corrected.strftime("%Y-%m-%d")
                    print(f"📅 Date corrected from {parsed.strftime('%Y-%m-%d')} to {date}")
            except Exception as e:
                print(f"⚠️ Date parse error: {e}")

        # Normalize time — "2 PM" → "2:00 PM"
        if time and ':' not in time:
            import re as _re
            m = _re.match(r'^(\d{1,2})\s*(AM|PM)$', time.strip(), _re.IGNORECASE)
            if m:
                time = f"{m.group(1)}:00 {m.group(2).upper()}"

        # Validate required fields — Sara will read the message aloud
        if not date:
            return {"result": "missing_info", "message": "I need the appointment date to complete the booking."}
        if not time:
            return {"result": "missing_info", "message": "I need the preferred time to complete the booking."}
        if not doctor_name or doctor_name == "To Be Assigned":
            return {"result": "missing_info", "message": "Please confirm which doctor you would like to see."}

        # Check for double booking
        existing = await appointments_collection.find_one({
            "doctor_name": doctor_name,
            "date": date,
            "time": time,
            "status": {"$ne": "cancelled"}
        })
        if existing:
            return {
                "result": "slot_unavailable",
                "message": f"I'm sorry, that slot is already taken. Could you please choose a different time?"
            }

        # Create the appointment
        appointment_id = f"UH-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
        appointment = {
            "appointment_id": appointment_id,
            "call_id": call_id,
            "patient_name": patient_name,
            "patient_phone": patient_phone,
            "doctor_name": doctor_name,
            "specialty": specialty,
            "date": date,
            "time": time,
            "language": language,
            "status": "confirmed",
            "call_type": "inbound",
            "booked_via": "retell_tool",   # so you can distinguish from manual bookings
            "created_at": datetime.now()
        }

        await appointments_collection.insert_one(appointment)

        # Upsert patient record
        await patients_collection.update_one(
            {"phone": patient_phone},
            {
                "$set": {
                    "name": patient_name,
                    "phone": patient_phone,
                    "last_visit": datetime.now(),
                },
                "$push": {"appointments": appointment_id},
                "$inc": {"total_visits": 1}
            },
            upsert=True
        )

        # Mark the call as booked and store patient details so dashboard can show name
        if call_id:
            await calls_collection.update_one(
                {"call_id": call_id},
                {"$set": {
                    "appointment_booked": True,
                    "appointment_id": appointment_id,
                    "outcome": "Appointment Booked",
                    "caller_name": patient_name,
                    "caller_phone": patient_phone,
                }}
            )

        print(f"✅ Retell tool booked: {appointment_id} — {patient_name} with {doctor_name} on {date} at {time}")

        # This message is read aloud by Sara to the patient
        return {
            "result": "success",
            "appointment_id": appointment_id,
            "message": f"Your appointment is confirmed with {doctor_name} on {date} at {time}. Please arrive 15 minutes early and bring your Emirates ID."
        }

    except Exception as e:
        print(f"❌ Retell tool error: {e}")
        import traceback
        traceback.print_exc()
        # Return a speakable error — Sara will say this to the patient
        return {
            "result": "error",
            "message": "I'm sorry, there was an issue saving your appointment. Please hold while I connect you to our team."
        }


# ============================================
# RETELL AI WEBHOOK
# Handles call_started and call_ended events.
# extract_appointment() is kept as a fallback in case
# the Retell tool didn't fire (e.g. tool config issue).
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

            raw_transcript = (
                call_data.get("transcript") or
                call_data.get("transcription") or
                call_data.get("transcript_object") or
                call_data.get("full_transcript") or
                ""
            )

            transcript = process_transcript(raw_transcript)

            call_analysis = call_data.get("call_analysis", {})
            call_summary = call_analysis.get("call_summary", "")
            user_sentiment = call_analysis.get("user_sentiment", "")
            call_successful = call_analysis.get("call_successful", False)

            working_text = transcript or call_summary or ""

            duration = call_data.get("duration_ms", 0)
            duration_sec = duration // 1000 if duration else 0
            duration_str = f"{duration_sec // 60}:{duration_sec % 60:02d}"

            language = detect_language(working_text)
            outcome = detect_outcome(working_text)

            if call_successful and "appointment" in call_summary.lower():
                outcome = "Appointment Booked"

            print(f"📝 Transcript: {len(transcript)} chars")
            print(f"📋 Summary: {call_summary[:100]}")
            print(f"🌐 Language: {language}")
            print(f"📊 Outcome: {outcome}")
            print(f"😊 Sentiment: {user_sentiment}")

            # Extract caller name from transcript for display in call logs
            blacklisted = {"unknown patient", "sara", "universal", "hospital", "agent", "assistant", ""}
            caller_name_extracted = extract_name(working_text)
            if caller_name_extracted.lower() in blacklisted:
                caller_name_extracted = ""

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
                    "ended_at": datetime.now(),
                    # Only set caller_name if we found a real one and it isn't already set
                    **({"caller_name": caller_name_extracted} if caller_name_extracted else {})
                }},
                upsert=True
            )

            # Check if Retell tool already booked this — don't double-book
            existing_call = await calls_collection.find_one({"call_id": call_id})
            already_booked = existing_call and existing_call.get("appointment_booked", False)

            if not already_booked:
                # Fallback: try to extract from transcript
                print("⚠️ Retell tool did not book — attempting transcript fallback...")
                appointment = extract_appointment(working_text, call_id, call_data)
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
                            "$push": {"appointments": appointment["appointment_id"]},
                            "$inc": {"total_visits": 1}
                        },
                        upsert=True
                    )
                    print(f"✅ Fallback appointment saved: {appointment['appointment_id']}")
                else:
                    print("⚠️ No appointment keywords found in transcript — nothing saved")
            else:
                print(f"✅ Already booked via Retell tool — skipping fallback")

            print(f"✅ Call completed: {call_id}")

        return {"status": "success"}

    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))




# ============================================
# CLEANUP — Fix bad patient/appointment records
# Call POST /api/cleanup once to fix existing data
# ============================================
@app.post("/api/cleanup")
async def cleanup_bad_records():
    """
    One-time cleanup:
    1. Delete appointments with patient_name = Unknown Patient
    2. Delete patient records with name = Unknown Patient or Sara
    3. Merge duplicate patients with same phone number
    """
    results = {}

    # 1. Delete bad appointments
    bad_names = ["Unknown Patient", "Sara", "Unknown", ""]
    del_apts = await appointments_collection.delete_many(
        {"patient_name": {"$in": bad_names}}
    )
    results["deleted_appointments"] = del_apts.deleted_count

    # 2. Delete bad patient records
    del_patients = await patients_collection.delete_many(
        {"name": {"$in": bad_names}}
    )
    results["deleted_patients"] = del_patients.deleted_count

    # 3. Backfill caller_name for existing calls that have a transcript but no name
    blacklisted = {"unknown patient", "sara", "universal", "hospital", "agent", "assistant", ""}
    all_calls = await calls_collection.find(
        {"transcript": {"$exists": True, "$ne": ""}, "caller_name": {"$exists": False}},
        {"_id": 0, "call_id": 1, "transcript": 1}
    ).to_list(500)

    backfilled = 0
    for call in all_calls:
        transcript = call.get("transcript", "")
        if not transcript:
            continue
        name = extract_name(transcript)
        if name and name.lower() not in blacklisted:
            await calls_collection.update_one(
                {"call_id": call["call_id"]},
                {"$set": {"caller_name": name}}
            )
            backfilled += 1

    results["backfilled_caller_names"] = backfilled

    print(f"🧹 Cleanup done: {results}")
    return {"status": "done", "results": results}

# ============================================
# HEALTH CHECK
# ============================================
@app.get("/")
async def health():
    return {"status": "running", "message": "Universal Hospital Backend"}


# ============================================
# DASHBOARD STATS
# ============================================
@app.get("/api/dashboard/stats")
async def get_stats():
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
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
        "confirmed": await appointments_collection.count_documents({"status": "confirmed"}),
        "pending": await appointments_collection.count_documents({"status": "pending"}),
        "cancelled": await appointments_collection.count_documents({"status": "cancelled"}),
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

        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        day_data = defaultdict(lambda: {'calls': 0, 'appointments': 0, 'patients': 0})

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

        chart_data = [
            {
                'day': day,
                'calls': day_data[day]['calls'],
                'appointments': day_data[day]['appointments'],
                'patients': day_data[day]['patients']
            }
            for day in days
        ]

        specialty_counts = defaultdict(int)
        for apt in all_appointments:
            specialty = apt.get('specialty', 'General Medicine')
            if specialty:
                specialty_counts[specialty] += 1

        total_apts = sum(specialty_counts.values()) or 1
        colors = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#e0e7ff']
        specialty_data = [
            {
                'name': name,
                'value': round((count / total_apts) * 100),
                'color': colors[i % len(colors)]
            }
            for i, (name, count) in enumerate(
                sorted(specialty_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            )
        ]

        outcome_counts = defaultdict(int)
        for call in all_calls:
            outcome = call.get('outcome', 'Information Provided')
            if outcome and outcome != 'ongoing':
                outcome_counts[outcome] += 1

        total_calls_count = sum(outcome_counts.values()) or 1
        outcome_colors = ['#10b981', '#6366f1', '#ef4444', '#f59e0b']
        outcome_data = [
            {
                'name': name,
                'value': round((count / total_calls_count) * 100),
                'color': outcome_colors[i % len(outcome_colors)]
            }
            for i, (name, count) in enumerate(outcome_counts.items())
        ]

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
async def update_appointment(appointment_id: str, request: Request):
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
    result = await appointments_collection.delete_one({"appointment_id": appointment_id})
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
    call = await calls_collection.find_one({"call_id": call_id}, {"_id": 0})
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
            raise HTTPException(status_code=500, detail="RETELL_API_KEY not configured")

        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
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

        booked_times = [apt["time"] for apt in booked if apt.get("time")]

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
            "total_available": sum(1 for s in all_slots if s["available"]),
            "total_booked": sum(1 for s in all_slots if not s["available"])
        }

    except Exception as e:
        print(f"❌ Calendar slots error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/calendar/month")
async def get_month_appointments(year: int, month: int):
    try:
        all_apts = await appointments_collection.find({}, {"_id": 0}).to_list(1000)
        calendar_data = {}

        for apt in all_apts:
            date = apt.get("date", "")
            if not date or date == "To Be Confirmed":
                continue

            if date not in calendar_data:
                calendar_data[date] = {
                    "total": 0, "confirmed": 0,
                    "pending": 0, "cancelled": 0, "appointments": []
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

        return {"year": year, "month": month, "data": calendar_data}

    except Exception as e:
        print(f"❌ Calendar month error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/calendar/book")
async def book_appointment_with_check(request: Request):
    try:
        body = await request.json()
        doctor_name   = body.get("doctor_name")
        date          = body.get("date")
        time          = body.get("time")
        patient_name  = body.get("patient_name")
        patient_phone = body.get("patient_phone")
        specialty     = body.get("specialty", "General Medicine")

        if not all([doctor_name, date, time, patient_name, patient_phone]):
            raise HTTPException(status_code=400, detail="Missing required fields")

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
                "$push": {"appointments": appointment["appointment_id"]},
                "$inc": {"total_visits": 1}
            },
            upsert=True
        )

        return {"success": True, "appointment": appointment}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Booking error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
