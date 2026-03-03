#!/usr/bin/env python3
"""
TeacherPilot Backend - FastAPI Application

Core API server for the TeacherPilot application, providing endpoints
for priority management, classroom data, and AI-powered assistance.
"""

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from context_builder import build_context  # noqa: F401 (re-exported for tests)
from database import (
    AbsenceRecord,
    ClassSessionRecord,
    ImportantEmailRecord,
    UserTaskRecord,
    WeeklyScheduleRecord,
    get_db,
    init_db,
)
from dotenv import load_dotenv
from email_processor import EmailBatch, process_batch
from fastapi import Depends, FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from mistral_client import call_mistral
from prompts.voice import call_voice_mistral
from prompts.weekly_schedule import extract_weekly_schedule
from pydantic import BaseModel
from schedule_day import get_current_schedule_day, set_schedule_day
from sqlalchemy.orm import Session
from stt import transcribe_audio
from tts import text_to_speech

# Load environment variables
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create tables on startup (no-op if they already exist)
    yield


# Create FastAPI app
app = FastAPI(
    title="TeacherPilot API",
    description="Backend API for TeacherPilot - AI Command Center for Educators",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    """
    Root endpoint - Health check and basic info

    Returns:
        dict: Basic application information
    """
    return {
        "name": "TeacherPilot API",
        "version": "0.1.0",
        "status": "healthy",
        "message": "Welcome to TeacherPilot - The AI Command Center for Educators",
    }


@app.get("/api/health")
async def health_check() -> dict:
    """
    Health check endpoint.
    Includes Mistral configuration status so you can verify the AI is wired up.
    """
    api_key = os.getenv("MISTRAL_API_KEY", "")
    el_key = os.getenv("ELEVENLABS_API_KEY", "")
    el_voice = os.getenv("ELEVENLABS_VOICE_ID", "")
    return {
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "api_version": "0.1.0",
        "mistral": {
            "configured": bool(api_key),
            "model_priorities": "mistral-large-latest",
            "model_extraction": "mistral-small-latest",
        },
        "elevenlabs": {
            "configured": bool(el_key and el_voice),
            "voice_id_set": bool(el_voice),
        },
    }


@app.get("/api/schedule")
async def get_teacher_schedule() -> dict:
    """
    Get teacher's schedule data

    Security Considerations (OWASP Top 10):
    - Input validation: No user input processed
    - Authentication: Should be protected in production
    - Sensitive data: No personal data exposed
    - Error handling: Basic error handling implemented

    Returns:
        dict: Teacher schedule data from JSON file
    """
    try:
        schedule_path = Path(__file__).parent / "data" / "teacher_schedule.json"
        with open(schedule_path, "r", encoding="utf-8") as f:
            schedule_data = json.load(f)
        schedule_data["current_day"] = get_current_schedule_day()
        return schedule_data
    except FileNotFoundError:
        return {"error": "Schedule data not found"}
    except json.JSONDecodeError:
        return {"error": "Invalid schedule data format"}
    except Exception:
        # Generic error handling to prevent information leakage (OWASP)
        return {"error": "Failed to load schedule data"}


def _load_priority_data() -> Optional[Dict[str, Any]]:
    """
    Load priority data from JSON file with error handling

    Security: File path constructed safely, no user input

    Returns:
        Optional[Dict]: Priority data or None if error occurs
    """
    try:
        priority_path = Path(__file__).parent / "data" / "mock_priorities.json"
        with open(priority_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        return None


def _load_schedule_data() -> Optional[Dict[str, Any]]:
    """
    Load teacher schedule data from JSON file with error handling

    Security: File path constructed safely, no user input

    Returns:
        Optional[Dict]: Schedule data or None if error occurs
    """
    try:
        schedule_path = Path(__file__).parent / "data" / "teacher_schedule.json"
        with open(schedule_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        return None


def _get_current_time() -> datetime:
    """
    Get current time for priority calculation

    Returns:
        datetime: Current datetime (mockable for testing)
    """
    return datetime.now()


def _calculate_priority_score(task: Dict[str, Any], current_time: datetime) -> int:
    """
    Calculate priority score for a task based on multiple factors

    Args:
        task: Task dictionary with priority information
        current_time: Current datetime for comparison

    Returns:
        int: Priority score (higher = more urgent)
    """
    score = 0

    # Priority level
    priority_map = {"high": 3, "medium": 2, "low": 1}
    score += priority_map.get(task.get("priority", "low"), 1) * 100

    # Time sensitivity
    try:
        due_date = datetime.fromisoformat(task.get("due_date", ""))
        time_diff = (due_date - current_time).total_seconds()
        if time_diff < 0:
            score += 500  # Overdue
        elif time_diff < 86400:  # Less than 24 hours
            score += 300
        elif time_diff < 172800:  # Less than 48 hours
            score += 150
    except (ValueError, TypeError):
        pass

    # Estimated time (shorter tasks get slight priority)
    try:
        estimated_minutes = _parse_estimated_time(task.get("estimated_time", ""))
        if estimated_minutes > 0:
            score += max(0, 50 - estimated_minutes)  # Max 50 points for quick tasks
    except (ValueError, TypeError):
        pass

    return score


def _parse_estimated_time(time_str: str) -> int:
    """
    Parse estimated time string to minutes

    Args:
        time_str: Time string like "2 hours" or "30 minutes"

    Returns:
        int: Time in minutes
    """
    if not time_str:
        return 0

    parts = time_str.split()
    if len(parts) != 2:
        return 0

    try:
        value = int(parts[0])
        unit = parts[1].lower()

        if unit.startswith("hour"):
            return value * 60
        elif unit.startswith("min"):
            return value
        return 0
    except (ValueError, IndexError):
        return 0


def _filter_tasks_by_schedule(
    tasks: List[Dict[str, Any]], schedule_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Filter tasks by current/relevant classes from schedule

    Args:
        tasks: List of task dictionaries
        schedule_data: Teacher schedule data

    Returns:
        List[Dict]: Filtered tasks
    """
    current_schedule_day = get_current_schedule_day()
    current_class_groups = set()

    # Find classes for current schedule day
    for day_schedule in schedule_data.get("classes", []):
        if day_schedule.get("day") == current_schedule_day:
            for period in day_schedule.get("periods", []):
                current_class_groups.add(period.get("group"))
            break

    # Always include homeroom class (homeroom happens every day)
    homeroom_group = schedule_data.get("homeroom", {}).get("group")
    if homeroom_group:
        current_class_groups.add(homeroom_group)

    # Filter tasks related to current classes or all classes
    filtered_tasks = []
    for task in tasks:
        related_class = task.get("related_class", "")
        if related_class in current_class_groups or related_class == "All":
            filtered_tasks.append(task)

    return filtered_tasks


def _email_to_task(email: ImportantEmailRecord) -> Dict[str, Any]:
    """Convert a stored action-required email into the task format Mistral expects."""
    return {
        "id": email.id,
        "title": email.subject,
        "description": email.snippet,
        "priority": "high",
        "due_date": "",
        "estimated_time": "15 minutes",
        "related_class": "All",
        "related_subject": "Email",
    }


def _meeting_to_task(meeting: dict, idx: int) -> Dict[str, Any]:
    """Convert a weekly-schedule meeting into the task format Mistral expects."""
    return {
        "id": f"meeting_{idx}",
        "title": f"{meeting['description']} — {meeting.get('time', '')}",
        "description": f"Location: {meeting.get('location', 'TBD')}",
        "priority": "high" if meeting.get("mandatory") else "medium",
        "due_date": "",
        "estimated_time": "60 minutes",
        "related_class": "All",
        "related_subject": "Meeting",
    }


def _action_item_to_task(item: str, idx: int) -> Dict[str, Any]:
    """Convert a weekly-schedule action item into the task format Mistral expects."""
    return {
        "id": f"action_{idx}",
        "title": item[:80],
        "description": item,
        "priority": "medium",
        "due_date": "",
        "estimated_time": "10 minutes",
        "related_class": "All",
        "related_subject": "Announcement",
    }


def _user_task_to_task(record: "UserTaskRecord") -> Dict[str, Any]:
    """Convert a user-created task record into the Mistral task format."""
    return {
        "id": f"user_{record.id}",
        "title": record.title,
        "description": record.title,
        "priority": record.priority,
        "due_date": record.due_date or "",
        "estimated_time": "30 minutes",
        "related_class": "All",
        "related_subject": "Personal",
    }


@app.get("/api/priorities")
async def get_priorities(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get top 3 priority tasks for the teacher.

    Pools tasks from real sources only:
      1. User-added tasks (manual task inbox)
      2. Action-required emails from the DB
      3. Today's meetings from the weekly schedule
      4. Action items from the weekly schedule (first 5)

    Mistral ranks the combined pool and picks the top 3, returning a reason
    per task that surfaces as the Marimba note in the UI.

    Returns:
        Dict: Top 3 priorities with metadata and marimba_note
    """
    try:
        schedule_data = _load_schedule_data()

        if not schedule_data:
            return {"error": "Schedule data not available"}

        from sqlalchemy import select

        # User-added tasks
        user_task_records = db.execute(select(UserTaskRecord)).scalars().all()

        # Action-required emails
        email_records = (
            db.execute(
                select(ImportantEmailRecord).where(
                    ImportantEmailRecord.category == "action_required"
                )
            )
            .scalars()
            .all()
        )

        # Weekly schedule data (meetings + action items)
        current_schedule_day = get_current_schedule_day()
        weekly_record = db.get(WeeklyScheduleRecord, "current")
        weekly_data: Optional[Dict[str, Any]] = None
        if weekly_record:
            weekly_data = json.loads(weekly_record.data)

        meeting_tasks: List[Dict[str, Any]] = []
        action_tasks: List[Dict[str, Any]] = []
        if weekly_data:
            todays_meetings = [
                m
                for m in weekly_data.get("meetings", [])
                if m.get("schedule_day") == current_schedule_day
            ]
            meeting_tasks = [
                _meeting_to_task(m, i) for i, m in enumerate(todays_meetings)
            ]
            action_tasks = [
                _action_item_to_task(item, i)
                for i, item in enumerate(weekly_data.get("action_items", [])[:5])
            ]

        all_tasks = (
            [_user_task_to_task(r) for r in user_task_records]
            + [_email_to_task(e) for e in email_records]
            + meeting_tasks
            + action_tasks
        )

        current_time = _get_current_time()

        # Try Mistral-powered prioritization first
        mistral_results = await call_mistral(
            all_tasks, schedule_data, current_time, weekly_data=weekly_data
        )

        reasons: Dict[str, str] = {}
        if mistral_results:
            task_dict = {task["id"]: task for task in all_tasks}
            top_3_tasks = []
            for item in mistral_results:
                tid = item["id"]
                if tid in task_dict:
                    top_3_tasks.append(task_dict[tid])
                    reasons[tid] = item["reason"]
        else:
            # Fallback: schedule-filter + scoring algorithm
            filtered_tasks = _filter_tasks_by_schedule(all_tasks, schedule_data)

            if not filtered_tasks:
                return {"priorities": [], "message": "No relevant tasks found"}

            scored_tasks = [
                {"task": task, "score": _calculate_priority_score(task, current_time)}
                for task in filtered_tasks
            ]
            scored_tasks.sort(key=lambda x: x["score"], reverse=True)
            top_3_tasks = [task["task"] for task in scored_tasks[:3]]

        # Format response — includes marimba_note when Mistral provided a reason
        priorities_out = []
        for task in top_3_tasks:
            item: Dict[str, Any] = {
                "id": task["id"],
                "title": task["title"],
                "priority": task["priority"],
                "estimated_time": task.get("estimated_time", "Unknown"),
                "due_date": task.get("due_date", ""),
                "class": task.get("related_class", ""),
                "subject": task.get("related_subject", ""),
            }
            reason = reasons.get(task["id"])
            if reason:
                item["marimba_note"] = reason
            priorities_out.append(item)

        response = {
            "priorities": priorities_out,
            "generated_at": datetime.now().isoformat(),
            "count": len(priorities_out),
        }

        return response

    except Exception:
        # Generic error to prevent information leakage
        return {"error": "Failed to generate priorities"}


@app.get("/api/schedule-day")
async def get_schedule_day() -> Dict[str, Any]:
    """
    Get today's schedule day number (1–6).

    Returns:
        dict: {"date": "YYYY-MM-DD", "day": N}
    """
    from datetime import date

    day = get_current_schedule_day()
    return {"date": date.today().isoformat(), "day": day}


@app.post("/api/schedule-day")
async def post_schedule_day(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Manual override for the rolling schedule day calculator.

    Body: {"date": "YYYY-MM-DD", "day": N}

    Returns:
        dict: {"date": "...", "day": N, "updated": true}
    """
    date_str = body.get("date", "")
    day = body.get("day")

    if not date_str or day not in range(1, 7):
        return {"error": "Provide a valid 'date' (YYYY-MM-DD) and 'day' (1–6)"}

    set_schedule_day(date_str, int(day))
    return {"date": date_str, "day": int(day), "updated": True}


@app.post("/api/emails")
async def receive_emails(
    batch: EmailBatch,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Webhook receiver for n8n Gmail batches.

    n8n POSTs a JSON array of unread messages every 15 minutes.
    One Mistral call classifies the entire batch into:
      - action_required  → saved to important_emails
      - absence          → saved to absences (student + group extracted)
      - weekly_schedule  → saved to important_emails for separate processing
      - ignore           → discarded

    Idempotent — already-stored email IDs are silently skipped.
    """
    return await process_batch(batch, db)


@app.get("/api/absences")
async def get_absences(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """All recorded student absences (most recent first)."""
    from sqlalchemy import select

    records = db.execute(select(AbsenceRecord)).scalars().all()
    return [
        {
            "id": r.id,
            "student_name": r.student_name,
            "group_name": r.group_name,
            "date": r.date,
        }
        for r in records
    ]


@app.get("/api/important-emails")
async def get_important_emails(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Action-required emails (excludes weekly_schedule — those are processed separately)."""
    from sqlalchemy import select

    records = (
        db.execute(
            select(ImportantEmailRecord).where(
                ImportantEmailRecord.category == "action_required"
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "subject": r.subject,
            "sender": r.sender,
            "snippet": r.snippet,
            "date": r.date,
        }
        for r in records
    ]


class AddTaskRequest(BaseModel):
    title: str
    priority: str = "medium"  # high / medium / low
    due_date: Optional[str] = None  # YYYY-MM-DD


@app.post("/api/tasks")
async def add_task(
    body: AddTaskRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Add a teacher-created task to the priority pool."""
    import uuid

    record = UserTaskRecord(
        id=str(uuid.uuid4()),
        title=body.title,
        priority=body.priority
        if body.priority in ("high", "medium", "low")
        else "medium",
        due_date=body.due_date,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(record)
    db.commit()
    return {
        "id": record.id,
        "title": record.title,
        "priority": record.priority,
        "due_date": record.due_date,
        "created_at": record.created_at,
    }


@app.get("/api/tasks")
async def list_tasks(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Return all teacher-created tasks."""
    from sqlalchemy import select

    records = db.execute(select(UserTaskRecord)).scalars().all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "priority": r.priority,
            "due_date": r.due_date,
            "created_at": r.created_at,
        }
        for r in records
    ]


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Delete a teacher-created task."""
    record = db.get(UserTaskRecord, task_id)
    if not record:
        return {"error": "Task not found"}
    db.delete(record)
    db.commit()
    return {"deleted": task_id}


class WeeklyScheduleRequest(BaseModel):
    document_text: str


@app.post("/api/weekly-schedule")
async def post_weekly_schedule(
    body: WeeklyScheduleRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Receive the Google Doc text from n8n and extract structured agenda data.

    n8n fetches the Google Doc linked in the "Anuncios Semanales" email and
    POSTs the plain text here. Mistral extracts meetings, class disruptions,
    action items, and upcoming dates.

    Overwrites the previous weekly schedule (only the current week is kept).
    """
    data = await extract_weekly_schedule(body.document_text)
    if not data:
        return {"error": "Could not extract schedule — check MISTRAL_API_KEY"}

    import json
    from datetime import date

    record = db.get(WeeklyScheduleRecord, "current")
    if record:
        record.week_label = data.get("week_label", "")
        record.data = json.dumps(data, ensure_ascii=False)
        record.created_at = date.today().isoformat()
    else:
        db.add(
            WeeklyScheduleRecord(
                id="current",
                week_label=data.get("week_label", ""),
                data=json.dumps(data, ensure_ascii=False),
                created_at=date.today().isoformat(),
            )
        )
    db.commit()
    return data


@app.get("/api/weekly-schedule")
async def get_weekly_schedule(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Return the most recently extracted weekly schedule.
    Returns empty lists when no schedule has been loaded yet.
    """
    import json

    record = db.get(WeeklyScheduleRecord, "current")
    if not record:
        return {
            "week_label": "",
            "meetings": [],
            "class_disruptions": [],
            "action_items": [],
            "upcoming_dates": [],
            "absences": [],
        }
    return json.loads(record.data)


class LogSessionRequest(BaseModel):
    notes: str
    what_worked: Optional[str] = None


@app.post("/api/class/{group}/session")
async def log_class_session(
    group: str,
    body: LogSessionRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Log (or update) a session note for a class group.

    Upserts by id = "{group}_{date}_{schedule_day}".
    Returns the saved record.
    """
    from datetime import date as _date

    today = _date.today().isoformat()
    sday = get_current_schedule_day()
    record_id = f"{group}_{today}_{sday}"
    now_str = datetime.now(timezone.utc).isoformat()

    existing = db.get(ClassSessionRecord, record_id)
    if existing:
        existing.notes = body.notes
        existing.what_worked = body.what_worked
        existing.created_at = now_str
    else:
        db.add(
            ClassSessionRecord(
                id=record_id,
                group=group,
                schedule_day=sday,
                date=today,
                notes=body.notes,
                what_worked=body.what_worked,
                created_at=now_str,
            )
        )
    db.commit()

    record = db.get(ClassSessionRecord, record_id)
    return {
        "id": record.id,
        "group": record.group,
        "schedule_day": record.schedule_day,
        "date": record.date,
        "notes": record.notes,
        "what_worked": record.what_worked,
        "created_at": record.created_at,
    }


@app.get("/api/class/{group}/last-session")
async def get_last_session(
    group: str,
    db: Session = Depends(get_db),
) -> Optional[Dict[str, Any]]:
    """
    Return the most recent session log for a class group, or null if none exists.
    """
    from sqlalchemy import desc, select

    record = (
        db.execute(
            select(ClassSessionRecord)
            .where(ClassSessionRecord.group == group)
            .order_by(
                desc(ClassSessionRecord.date), desc(ClassSessionRecord.schedule_day)
            )
            .limit(1)
        )
        .scalars()
        .first()
    )

    if not record:
        return None

    return {
        "id": record.id,
        "group": record.group,
        "schedule_day": record.schedule_day,
        "date": record.date,
        "notes": record.notes,
        "what_worked": record.what_worked,
        "created_at": record.created_at,
    }


def _build_voice_context(
    schedule_data: Dict[str, Any],
    all_tasks: List[Dict[str, Any]],
    weekly_data: Optional[Dict[str, Any]],
) -> str:
    """Build a concise plain-text context summary for the voice Mistral call."""
    current_day = get_current_schedule_day()

    today_periods: List[Dict[str, Any]] = []
    for day_sched in schedule_data.get("classes", []):
        if day_sched.get("day") == current_day:
            today_periods = day_sched.get("periods", [])
            break

    homeroom = schedule_data.get("homeroom", {})
    classes_parts = []
    if homeroom:
        classes_parts.append(
            f"{homeroom.get('group')} (homeroom) at {homeroom.get('time')}"
        )
    for p in today_periods:
        classes_parts.append(f"{p.get('group')} at {p.get('time')}")
    classes_str = ", ".join(classes_parts) or "no classes today"

    tasks_str = (
        "\n".join(f"- {t['title']} ({t['priority']})" for t in all_tasks[:8])
        or "no tasks"
    )

    meetings_str = ""
    if weekly_data:
        meetings = [
            m
            for m in weekly_data.get("meetings", [])
            if m.get("schedule_day") == current_day
        ]
        if meetings:
            meetings_str = "\nToday's meetings: " + ", ".join(
                f"{m.get('description')} at {m.get('time')}" for m in meetings
            )

    return (
        f"Schedule day {current_day}. Today's classes: {classes_str}.{meetings_str}\n\n"
        f"Pending tasks:\n{tasks_str}"
    )


@app.post("/api/voice")
async def handle_voice(
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Handle a teacher's spoken query routed through Marimba.

    Pipeline:
      1. Receive raw audio from browser (WebM/Opus or MP4/AAC on Safari)
      2. Voxtral Mini transcribes it → plain text
      3. Build today's context (schedule + tasks + meetings)
      4. Mistral Large reasons about the query → {response, action?}
      5. ElevenLabs TTS converts the response → base64 MP3 (optional)
      6. Return {text, audio?, action?} to the frontend

    Same MISTRAL_API_KEY is used for both Voxtral and Mistral Large.
    """
    audio_bytes = await audio.read()
    transcript = await transcribe_audio(audio_bytes, audio.filename or "recording.webm")

    if not transcript:
        return {"error": "Empty transcript"}

    try:
        schedule_data = _load_schedule_data() or {}

        from database import (
            ImportantEmailRecord,
            UserTaskRecord,
            VoiceLogRecord,
            WeeklyScheduleRecord,
        )
        from sqlalchemy import select

        user_task_records = db.execute(select(UserTaskRecord)).scalars().all()
        email_records = (
            db.execute(
                select(ImportantEmailRecord).where(
                    ImportantEmailRecord.category == "action_required"
                )
            )
            .scalars()
            .all()
        )

        weekly_record = db.get(WeeklyScheduleRecord, "current")
        weekly_data: Optional[Dict[str, Any]] = None
        if weekly_record:
            weekly_data = json.loads(weekly_record.data)

        all_tasks = [_user_task_to_task(r) for r in user_task_records] + [
            _email_to_task(e) for e in email_records
        ]

        context = _build_voice_context(schedule_data, all_tasks, weekly_data)

        mistral_result = await call_voice_mistral(transcript, context)

        if not mistral_result:
            return {
                "text": "Sorry, I can't connect right now. Please try again.",
                "audio": None,
                "action": None,
            }

        spoken_text = mistral_result["response"]
        action = mistral_result.get("action")

        # If action is add_task, persist it to DB immediately
        if action and action.get("type") == "add_task":
            import uuid

            task_title = action.get("title", "").strip()
            task_priority = action.get("priority", "medium")
            if task_title and task_priority in ("high", "medium", "low"):
                record = UserTaskRecord(
                    id=str(uuid.uuid4()),
                    title=task_title,
                    priority=task_priority,
                    due_date=None,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                db.add(record)
                db.commit()

        # Log the interaction for Evals
        import uuid

        log_record = VoiceLogRecord(
            id=str(uuid.uuid4()),
            transcript=transcript,
            mistral_response=mistral_result.get("raw_json", "{}"),
            parsed_action=action.get("type") if action else None,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        db.add(log_record)
        db.commit()

        audio_b64 = await text_to_speech(spoken_text)

        return {
            "text": spoken_text,
            "audio": audio_b64,
            "action": action,
        }

    except Exception:
        return {
            "text": "Something went wrong. Please try again.",
            "audio": None,
            "action": None,
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
