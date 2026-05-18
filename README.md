# Universal Hospital Backend

AI-powered FastAPI backend for Universal Hospital’s intelligent reception and appointment management platform.

This backend integrates with Retell AI voice agents to automate appointment booking, patient call handling, dashboard analytics, scheduling workflows, and hospital operations in real time.

---

# Features

- AI-powered appointment booking via voice calls
- Retell AI webhook integration
- Real-time patient and appointment management
- Calendar scheduling and slot availability system
- Hospital dashboard analytics APIs
- Multi-language call handling support
- MongoDB-based data storage
- Automated cleanup and maintenance endpoints
- Structured booking workflow without transcript parsing

---

# Tech Stack

| Layer | Technology |
|---|---|
| Backend Framework | FastAPI |
| Language | Python 3.10 |
| Database | MongoDB |
| Async Driver | Motor |
| AI Voice Platform | Retell AI |
| HTTP Client | httpx |
| Environment Management | python-dotenv |
| Server | Uvicorn |
| Deployment | Render |

---

# System Architecture

```text
Patient Call
      ↓
Retell AI Voice Agent
      ↓
FastAPI Backend APIs
      ↓
MongoDB Database
      ↓
Hospital Dashboard
```

---

# Project Structure

```bash
backend/
│
├── main.py
├── models.py
├── database.py
├── config.py
├── requirements.txt
├── .env
└── README.md
```

---

# Core Modules

## AI Appointment Booking
The voice assistant collects:
- patient details
- symptoms
- preferred doctor
- appointment date and time

The backend validates scheduling availability and stores confirmed appointments in MongoDB.

---

## Dashboard APIs
Supports:
- hospital KPI analytics
- patient statistics
- appointment tracking
- calendar scheduling
- call monitoring
- reporting data

---

## Retell AI Integration
Supports webhook events:
- `call_started`
- `call_ended`
- `call_analyzed`

and custom booking tool integrations.

---

# Local Development Setup

## 1. Clone Repository

```bash
git clone https://github.com/menonvij21/hospital-backend.git
cd hospital-backend
```

---

## 2. Create Virtual Environment

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

If required:

```bash
pip install fastapi uvicorn motor pymongo python-dotenv httpx
```

---

## 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
MONGODB_URL=your_mongodb_connection_string
DB_NAME=universal_hospital
RETELL_API_KEY=your_retell_api_key
```

---

## 5. Run the Backend Server

```bash
uvicorn main:app --reload --port 8000
```

Backend server runs at:

```bash
http://localhost:8000
```

Interactive Swagger documentation:

```bash
http://localhost:8000/docs
```

---

# API Overview

## Health Check

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Backend health status |

---

## Retell AI Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/retell-webhook` | Receives Retell AI webhook events |
| POST | `/api/retell-book` | AI appointment booking endpoint |
| POST | `/create-web-call` | Creates web-based AI call sessions |

---

## Dashboard Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/dashboard/stats` | KPI statistics |
| GET | `/api/dashboard/chart-data` | Dashboard analytics data |

---

## Appointment Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/appointments` | Retrieve appointments |
| PATCH | `/api/appointments/{id}` | Update appointment |
| DELETE | `/api/appointments/{id}` | Delete appointment |

---

## Calendar Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/calendar/slots` | Available appointment slots |
| GET | `/api/calendar/month` | Monthly appointment calendar |
| POST | `/api/calendar/book` | Manual appointment booking |

---

# AI Booking Workflow

```text
1. Patient calls hospital
2. Retell AI answers the call
3. AI collects appointment information
4. Backend validates slot availability
5. Appointment is stored in MongoDB
6. Dashboard updates automatically
7. AI confirms booking to patient
```

---

# Database Collections

| Collection | Purpose |
|---|---|
| appointments | Appointment records |
| calls | AI call logs and transcripts |
| patients | Patient information and history |

---

# Deployment Guide (Render)

## 1. Push Repository to GitHub

```bash
git push origin master
```

---

## 2. Create Render Web Service

- Open Render dashboard
- Create a new Web Service
- Connect GitHub repository

---

## 3. Configure Deployment

### Build Command

```bash
pip install -r requirements.txt
```

### Start Command

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 4. Add Environment Variables

Add:
- `MONGODB_URL`
- `DB_NAME`
- `RETELL_API_KEY`

inside Render Environment settings.

---

## 5. Deploy Application

After deployment:

```bash
https://your-backend.onrender.com
```

---

# Retell AI Configuration

## Webhook URL

```bash
https://your-backend.onrender.com/retell-webhook
```

Enable:
- `call_started`
- `call_ended`
- `call_analyzed`

---

## Custom Booking Tool

| Field | Value |
|---|---|
| Name | `book_appointment` |
| Method | POST |
| URL | `https://your-backend.onrender.com/api/retell-book` |

---

# Security Notes

- Environment variables securely store API keys
- Sensitive credentials are never committed
- MongoDB access should be IP restricted
- HTTPS deployment is recommended for production

---

# Future Improvements

- Authentication and authorization
- Role-based access control
- AI-generated call summaries
- Real-time WebSocket updates
- Advanced hospital analytics
- EMR integration
- Multi-agent AI workflows
- Automated doctor availability prediction