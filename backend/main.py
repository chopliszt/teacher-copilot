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
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from database import (
    AbsenceRecord,
    ClassSessionRecord,
    EmailRecipientRecord,
    ImportantEmailRecord,
    LessonPlanRecord,
    MeetingRecord,
    PriorityFeedbackRecord,
    SessionLocal,
    UserTaskRecord,
    WeeklyScheduleRecord,
    get_db,
    init_db,
)
from dotenv import load_dotenv
from email_processor import EmailBatch, process_batch
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from mistral_client import call_mistral
from prompts.meeting_summary import summarize_meeting
from prompts.voice import call_voice_mistral
from prompts.weekly_schedule import extract_weekly_schedule
from pydantic import BaseModel
from schedule_day import get_current_schedule_day, set_schedule_day
from sqlalchemy.orm import Session
from stt import transcribe_audio
from tts import text_to_speech

# Load environment variables
load_dotenv()

# ── Sync state ──────────────────────────────────────────────────────────────
# Lightweight JSON file that persists the last successful Gmail sync timestamp
# across restarts, independent of the DB.

_SYNC_STATE_PATH = Path(__file__).parent / "data" / "sync_state.json"


def _read_sync_state() -> Dict[str, Any]:
    try:
        return json.loads(_SYNC_STATE_PATH.read_text())
    except Exception:
        return {}


def _write_sync_state(status: str, emails_found: int) -> None:
    try:
        _SYNC_STATE_PATH.write_text(
            json.dumps({
                "last_sync_at": datetime.now(timezone.utc).isoformat(),
                "emails_found": emails_found,
                "status": status,
            })
        )
    except Exception as e:
        print(f"[SyncState] Could not write sync_state.json: {e}")


# ── Core Gmail sync logic (shared by the endpoint and the scheduler) ─────────

def _mark_gmail_read(message_ids: List[str]) -> None:
    """
    Best-effort: clear the UNREAD flag in Gmail for emails the teacher has
    already handled in the app (absences on sync, action emails on dismiss).

    Never raises — a Gmail hiccup must not fail the sync or the dismiss that
    the teacher just performed. The emails stay in the inbox either way.
    """
    ids = [m for m in message_ids if m]
    if not ids:
        return
    try:
        from connectors.gmail import mark_emails_read
        mark_emails_read(ids)
    except Exception as e:
        print(f"[Gmail] Could not mark {len(ids)} email(s) read: {e}")


async def _run_gmail_sync(db: Session) -> Dict[str, Any]:
    from connectors.gmail import fetch_unread_emails, is_configured, _get_gmail_service

    if not is_configured():
        return {
            "status": "error",
            "message": "Gmail is not configured. Run auth_gmail.py first.",
            "emails_processed": 0,
        }

    # Explicitly test the service so an expired/revoked token surfaces as an
    # error instead of silently returning "no unread emails".
    service = _get_gmail_service()
    if not service:
        result: Dict[str, Any] = {
            "status": "error",
            "message": "Gmail token expired or revoked — run auth_gmail.py to re-authenticate.",
            "emails_processed": 0,
        }
        _write_sync_state("error", 0)
        return result

    fetched_emails = fetch_unread_emails()
    if not fetched_emails:
        result = {"status": "success", "message": "No unread emails", "emails_processed": 0}
    else:
        batch = EmailBatch(emails=fetched_emails)
        result = await process_batch(batch, db)
        # Absence emails are pure FYI and already captured in the app. Clear
        # their unread flag in Gmail so they stop adding to the teacher's
        # unread count — they stay in the inbox, just no longer bold.
        _mark_gmail_read(result.get("absence_ids") or [])

    _write_sync_state(result.get("status", "success"), result.get("emails_processed", 0))
    return result


async def _scheduled_gmail_sync() -> None:
    """Runs daily at 7 AM Costa Rica time via APScheduler — no request context."""
    print("[Scheduler] Running scheduled Gmail sync")
    db = SessionLocal()
    try:
        result = await _run_gmail_sync(db)
        db.commit()
        print(f"[Scheduler] Sync complete: {result.get('emails_processed', 0)} emails processed")
    except Exception as e:
        print(f"[Scheduler] Gmail sync error: {e}")
    finally:
        db.close()


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception as e:
        msg = str(e)
        if "could not translate host name" in msg or "nodename nor servname" in msg:
            print("\n[DB] ❌ Cannot reach Supabase — check your internet connection.\n")
        raise

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _scheduled_gmail_sync,
        CronTrigger(hour=7, minute=0, timezone="America/Costa_Rica"),
        id="daily_gmail_sync",
        replace_existing=True,
    )
    scheduler.start()
    print("[Scheduler] Daily Gmail sync scheduled at 07:00 America/Costa_Rica")

    yield

    scheduler.shutdown(wait=False)


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
    Calculate priority score for a task based on multiple factors.

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

    # Staleness boost — a task sitting untouched for several days is being avoided;
    # surface it before the avoidance becomes a crisis.
    created_at_str = task.get("created_at", "")
    if created_at_str:
        try:
            created = datetime.fromisoformat(created_at_str)
            if created.tzinfo is not None:
                created = created.replace(tzinfo=None)
            age_days = (current_time - created).days
            if age_days >= 7:
                score += 150
            elif age_days >= 4:
                score += 80
            elif age_days >= 2:
                score += 30
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
    """Convert a user-created task record into the Mistral task format.

    Priority is escalated to "high" at runtime when the due date is today or
    tomorrow — the stored label stays unchanged; this is only for ranking.
    created_at is forwarded so the scoring algorithm can apply a staleness boost.
    """
    from datetime import date as _date, timedelta as _timedelta

    effective_priority = record.priority
    if record.due_date:
        try:
            due = _date.fromisoformat(record.due_date)
            tomorrow = _date.today() + _timedelta(days=1)
            if due <= tomorrow:
                effective_priority = "high"
        except ValueError:
            pass

    return {
        "id": f"user_{record.id}",
        "title": record.title,
        "description": record.title,
        "priority": effective_priority,
        "due_date": record.due_date or "",
        "estimated_time": "30 minutes",
        "related_class": "All",
        "related_subject": "Personal",
        "created_at": record.created_at or "",
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
            print("[Priorities] schedule data missing — check teacher_schedule.json")
            return {
                "priorities": [],
                "generated_at": datetime.now().isoformat(),
                "count": 0,
            }

        from sqlalchemy import select

        # User-added tasks
        user_task_records = db.execute(select(UserTaskRecord)).scalars().all()

        # Action-required emails (exclude soft-dismissed ones)
        email_records = (
            db.execute(
                select(ImportantEmailRecord).where(
                    ImportantEmailRecord.category == "action_required",
                    ImportantEmailRecord.dismissed_at.is_(None),
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

        # Filter out tasks the teacher has explicitly dismissed.
        #
        # Two rating signals are honoured here:
        #   "noise"  → categorically not for this teacher. 14-day window so a
        #              repeated action item stays suppressed across the week.
        #   "skip"   → "doesn't apply this week". Stays suppressed until a NEW
        #              weekly_schedule is uploaded (i.e. a fresh Friday batch).
        #              Falls back to a 7-day window if no weekly_schedule
        #              exists yet, so the feature still works on day one.
        from sqlalchemy import select as sql_select
        from datetime import timedelta

        noise_cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        noise_titles = {
            row.task_title.strip().lower()
            for row in db.execute(
                sql_select(PriorityFeedbackRecord).where(
                    PriorityFeedbackRecord.rating == "noise",
                    PriorityFeedbackRecord.created_at >= noise_cutoff,
                )
            ).scalars().all()
        }

        if weekly_record and weekly_record.created_at:
            skip_cutoff = weekly_record.created_at
        else:
            skip_cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        skip_titles = {
            row.task_title.strip().lower()
            for row in db.execute(
                sql_select(PriorityFeedbackRecord).where(
                    PriorityFeedbackRecord.rating == "skip",
                    PriorityFeedbackRecord.created_at >= skip_cutoff,
                )
            ).scalars().all()
        }

        suppressed = noise_titles | skip_titles
        if suppressed:
            all_tasks = [
                t for t in all_tasks
                if t["title"].strip().lower() not in suppressed
            ]

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
                return {
                    "priorities": [],
                    "generated_at": datetime.now().isoformat(),
                    "count": 0,
                }

            scored_tasks = [
                {"task": task, "score": _calculate_priority_score(task, current_time)}
                for task in filtered_tasks
            ]
            scored_tasks.sort(key=lambda x: x["score"], reverse=True)
            top_3_tasks = [task["task"] for task in scored_tasks[:3]]

        # Format response — includes marimba_note when Mistral provided a reason
        priorities_out = []
        for task in top_3_tasks:
            tid = task["id"]
            if tid.startswith("user_"):
                source = "user_task"
            elif tid.startswith("meeting_"):
                source = "meeting"
            elif tid.startswith("action_"):
                source = "action_item"
            else:
                source = "email"

            item: Dict[str, Any] = {
                "id": tid,
                "source": source,
                "title": task["title"],
                "priority": task["priority"],
                "estimated_time": task.get("estimated_time", "Unknown"),
                "due_date": task.get("due_date", ""),
                "class": task.get("related_class", ""),
                "subject": task.get("related_subject", ""),
            }
            reason = reasons.get(tid)
            if reason:
                item["marimba_note"] = reason
            priorities_out.append(item)

        response = {
            "priorities": priorities_out,
            "generated_at": datetime.now().isoformat(),
            "count": len(priorities_out),
        }

        return response

    except Exception as e:
        import traceback
        print(f"[Priorities] Unhandled error: {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


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


@app.get("/api/preferences")
async def get_preferences() -> Dict[str, Any]:
    """Returns the teacher's personal preferences."""
    from preferences import get_ignore_rules, get_personal_context
    return {
        "ignore_rules": get_ignore_rules(),
        "personal_context": get_personal_context(),
    }


@app.put("/api/preferences")
async def put_preferences(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update the teacher's personal preferences. Either field may be omitted
    to leave it untouched.

    Body: {"ignore_rules"?: str, "personal_context"?: str}
    """
    from preferences import (
        get_ignore_rules,
        get_personal_context,
        set_ignore_rules,
        set_personal_context,
    )

    if "ignore_rules" in body:
        if not isinstance(body["ignore_rules"], str):
            raise HTTPException(status_code=400, detail="ignore_rules must be a string")
        set_ignore_rules(body["ignore_rules"])
    if "personal_context" in body:
        if not isinstance(body["personal_context"], str):
            raise HTTPException(status_code=400, detail="personal_context must be a string")
        set_personal_context(body["personal_context"])

    return {
        "ignore_rules": get_ignore_rules(),
        "personal_context": get_personal_context(),
        "updated": True,
    }


@app.post("/api/emails/sync")
async def sync_emails(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Manually trigger Gmail sync. Also called on frontend mount."""
    try:
        return await _run_gmail_sync(db)
    except Exception as e:
        import traceback
        print(f"[Sync] Error: {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Email processing failed: {type(e).__name__}: {e}")


@app.get("/api/emails/last-sync")
async def get_last_sync() -> Dict[str, Any]:
    """Returns timestamp of the last Gmail sync (scheduled or manual)."""
    state = _read_sync_state()
    return {
        "last_sync_at": state.get("last_sync_at"),
        "emails_found": state.get("emails_found", 0),
        "status": state.get("status", "unknown"),
    }


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


def _parse_cc_addresses(raw_cc: str | None) -> List[str]:
    """
    Parse a raw Cc header value into a list of clean email addresses.

    Input examples (any of these):
      "Alice <alice@school.cr>, bob@school.cr"
      "carolina.marin@goldenvalley.ed.cr"
      None / ""

    Returns clean addresses with display names stripped — the format the
    frontend composer wants for its chip list. Order is preserved so the
    teacher sees CCs in the same order Gmail did.
    """
    if not raw_cc:
        return []
    from email.utils import getaddresses
    out: List[str] = []
    seen: set[str] = set()
    for _, addr in getaddresses([raw_cc]):
        addr = (addr or "").strip()
        if addr and "@" in addr and addr not in seen:
            seen.add(addr)
            out.append(addr)
    return out


@app.delete("/api/important-emails/{email_id}")
async def dismiss_email(email_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Soft-dismiss a single action-required email.

    We stamp dismissed_at instead of deleting the row so Gmail sync cannot
    re-insert the same email on next app load (the row already exists, so
    process_batch's 'if not db.get(...)' check skips it permanently).
    """
    record = db.get(ImportantEmailRecord, email_id)
    if not record:
        raise HTTPException(status_code=404, detail="Email not found")
    record.dismissed_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    # Done in the app → done in Gmail: clear the unread flag so the teacher
    # doesn't have to handle the same email twice. (email_id IS the Gmail
    # message id.) Non-destructive — the email stays in the inbox.
    _mark_gmail_read([email_id])
    return {"deleted": True}


@app.delete("/api/important-emails")
async def dismiss_all_emails(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Soft-dismiss all action-required emails (clean slate)."""
    from sqlalchemy import select as sql_select
    records = db.execute(
        sql_select(ImportantEmailRecord).where(
            ImportantEmailRecord.category == "action_required",
            ImportantEmailRecord.dismissed_at.is_(None),
        )
    ).scalars().all()
    now = datetime.now(timezone.utc).isoformat()
    dismissed_ids = [r.id for r in records]
    for r in records:
        r.dismissed_at = now
    db.commit()
    _mark_gmail_read(dismissed_ids)
    return {"deleted": True}


@app.get("/api/important-emails")
async def get_important_emails(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Action-required emails (excludes weekly_schedule — those are processed separately)."""
    from sqlalchemy import select

    records = (
        db.execute(
            select(ImportantEmailRecord).where(
                ImportantEmailRecord.category == "action_required",
                ImportantEmailRecord.dismissed_at.is_(None),
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


@app.get("/api/important-emails/{email_id}")
async def get_email_detail(
    email_id: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Full record for one email — used by the task chat drawer so we can show
    the body and draft a contextual reply. Lazy-backfills body/thread_id/
    rfc822_message_id from Gmail if the row predates those columns.
    """
    record = db.get(ImportantEmailRecord, email_id)
    if not record:
        raise HTTPException(status_code=404, detail="Email not found")

    if not record.body or not record.rfc822_message_id or record.cc is None:
        try:
            from connectors.gmail import fetch_email_detail
            detail = fetch_email_detail(email_id)
            if detail:
                if detail.get("body") and not record.body:
                    record.body = detail["body"]
                if detail.get("thread_id") and not record.thread_id:
                    record.thread_id = detail["thread_id"]
                if detail.get("rfc822_message_id") and not record.rfc822_message_id:
                    record.rfc822_message_id = detail["rfc822_message_id"]
                # cc is "" when the original had no CC — store that (not None)
                # so we don't keep re-querying Gmail every time the chat opens.
                if record.cc is None:
                    record.cc = detail.get("cc", "") or ""
                db.commit()
        except Exception as e:
            print(f"[Chat] Lazy backfill failed for {email_id}: {e}")

    return {
        "id": record.id,
        "subject": record.subject,
        "sender": record.sender,
        "snippet": record.snippet,
        "body": record.body or "",
        "date": record.date,
        "category": record.category,
        "thread_id": record.thread_id or "",
        "rfc822_message_id": record.rfc822_message_id or "",
        "cc": _parse_cc_addresses(record.cc),
    }


# ── Task chat ────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class TaskChatRequest(BaseModel):
    task_id: str
    source: str  # "email" | "user_task" | "meeting" | "action_item"
    title: str
    messages: List[ChatMessage]


def _build_task_context(
    *, source: str, title: str, email: Optional[ImportantEmailRecord],
    event: Optional[Any] = None,
) -> str:
    """Assemble the natural-language task block the chat prompt embeds."""
    if source == "email" and email is not None:
        body = email.body or email.snippet or "(no body available)"
        return (
            f"Type: incoming email\n"
            f"From: {email.sender}\n"
            f"Subject: {email.subject}\n"
            f"Body:\n{body}"
        )
    if source == "event" and event is not None:
        when = event.start_time or "time TBD"
        if event.start_time and event.end_time:
            when = f"{event.start_time}–{event.end_time}"
        attendees = ""
        if event.attendees:
            try:
                attendees = ", ".join(json.loads(event.attendees))
            except Exception:
                attendees = ""
        lines = [
            "Type: calendar event / meeting",
            f"Title: {event.title}",
            f"When: {event.date} {when}",
            f"Where: {event.location or 'not stated in the invite'}",
        ]
        if attendees:
            lines.append(f"Attendees: {attendees}")
        if event.meet_link:
            lines.append(f"Video link: {event.meet_link}")
        return "\n".join(lines)
    label = {
        "user_task":   "manual task added by the teacher",
        "meeting":     "meeting on today's schedule",
        "action_item": "action item from the weekly announcements",
    }.get(source, "task")
    return f"Type: {label}\nTitle: {title}"


@app.post("/api/chat/task")
async def chat_task(
    body: TaskChatRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    One conversation turn inside the task drawer.
    Returns {"reply": str} — or an error message if Mistral isn't reachable.
    """
    from prompts.task_chat import call_task_chat
    from context_builder import format_schedule_block

    event_record = None
    if body.source == "event":
        import events as events_module
        event_record = events_module.get_event(db, body.task_id)

    email_record: Optional[ImportantEmailRecord] = None
    if body.source == "email":
        email_record = db.get(ImportantEmailRecord, body.task_id)
        # Lazy backfill so the chat has the body even for old rows
        if email_record and (
            not email_record.body
            or not email_record.rfc822_message_id
            or email_record.cc is None
        ):
            try:
                from connectors.gmail import fetch_email_detail
                detail = fetch_email_detail(body.task_id)
                if detail:
                    if detail.get("body") and not email_record.body:
                        email_record.body = detail["body"]
                    if detail.get("thread_id") and not email_record.thread_id:
                        email_record.thread_id = detail["thread_id"]
                    if detail.get("rfc822_message_id") and not email_record.rfc822_message_id:
                        email_record.rfc822_message_id = detail["rfc822_message_id"]
                    if email_record.cc is None:
                        email_record.cc = detail.get("cc", "") or ""
                    db.commit()
            except Exception as e:
                print(f"[Chat] Lazy backfill failed during chat: {e}")

    task_context = _build_task_context(
        source=body.source, title=body.title, email=email_record, event=event_record
    )
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    # Inject today's schedule + meetings + disruptions so Marimba can answer
    # "what's my next class?" correctly instead of guessing from the task title.
    schedule_block = ""
    schedule_data = _load_schedule_data() or {}
    weekly_record = db.get(WeeklyScheduleRecord, "current")
    weekly_data: Optional[Dict[str, Any]] = None
    if weekly_record:
        try:
            weekly_data = json.loads(weekly_record.data)
        except Exception:
            weekly_data = None
    if schedule_data:
        try:
            schedule_block = format_schedule_block(
                schedule_data, _get_current_time(), weekly_data
            )
        except Exception as e:
            print(f"[Chat] Could not build schedule block: {e}")

    reply, tool_calls = await call_task_chat(
        task_context, messages, schedule_block=schedule_block
    )
    if reply is None:
        raise HTTPException(
            status_code=503,
            detail="Mistral is not reachable right now. Try again in a moment.",
        )
    return {"reply": reply, "tool_calls": tool_calls}


class DraftReplyRequest(BaseModel):
    messages: List[ChatMessage]


@app.post("/api/emails/{email_id}/draft-reply")
async def draft_email_reply_endpoint(
    email_id: str,
    body: DraftReplyRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Draft a contextual reply to one email, informed by the chat so far."""
    from prompts.task_chat import draft_email_reply

    record = db.get(ImportantEmailRecord, email_id)
    if not record:
        raise HTTPException(status_code=404, detail="Email not found")

    body_text = record.body or record.snippet or ""
    draft = await draft_email_reply(
        original_subject=record.subject,
        original_sender=record.sender,
        original_body=body_text,
        chat_history=[{"role": m.role, "content": m.content} for m in body.messages],
    )
    if not draft:
        raise HTTPException(
            status_code=503,
            detail="Could not draft a reply right now. Try again in a moment.",
        )
    # Extract a clean "to" address from the sender header (e.g. 'Name <x@y.com>')
    import re
    match = re.search(r"<([^>]+)>", record.sender)
    suggested_to = match.group(1) if match else record.sender
    # original_cc lets the composer surface the original CC list as
    # opt-in chips. Excluded from the actual send by default — the teacher
    # has to toggle "Reply all" to include them.
    return {
        "to": suggested_to,
        "subject": draft["subject"],
        "body": draft["body"],
        "original_cc": _parse_cc_addresses(record.cc),
    }


class SendReplyRequest(BaseModel):
    to: str
    subject: str
    body: str
    # Optional comma-separated CC string. Composer only sends this when the
    # teacher explicitly opted in to "Reply all" or added chips manually —
    # the default reply path is to-sender-only.
    cc: Optional[str] = None


@app.post("/api/emails/{email_id}/reply")
async def send_email_reply(
    email_id: str,
    body: SendReplyRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Send a threaded reply to an action-required email. Uses In-Reply-To +
    References + Gmail threadId so the reply lands inside the original
    conversation on both sides.
    """
    from connectors.gmail import is_configured, send_reply

    if not is_configured():
        raise HTTPException(status_code=503, detail="Gmail is not configured.")

    record = db.get(ImportantEmailRecord, email_id)
    if not record:
        raise HTTPException(status_code=404, detail="Email not found")

    cc_clean = (body.cc or "").strip() or None
    sent = send_reply(
        to=body.to,
        subject=body.subject,
        body=body.body,
        in_reply_to_rfc822_id=record.rfc822_message_id or "",
        thread_id=record.thread_id or None,
        cc=cc_clean,
    )
    if not sent:
        raise HTTPException(status_code=500, detail="Reply send failed. Check backend logs.")

    # Track recipient(s) so they autocomplete next time. CC addresses count
    # as people the teacher has corresponded with, so seed them too.
    try:
        _upsert_recipients(db, body.to)
        if cc_clean:
            _upsert_recipients(db, cc_clean)
    except Exception as e:
        print(f"[send_email_reply] recipient tracking failed (non-fatal): {e}")

    return {"sent": True}


@app.post("/api/emails/{email_id}/save-draft")
async def save_email_reply_as_draft(
    email_id: str,
    body: SendReplyRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Save a threaded reply to Gmail Drafts instead of sending it."""
    from connectors.gmail import is_configured, create_draft_reply

    if not is_configured():
        raise HTTPException(status_code=503, detail="Gmail is not configured.")

    record = db.get(ImportantEmailRecord, email_id)
    if not record:
        raise HTTPException(status_code=404, detail="Email not found")

    cc_clean = (body.cc or "").strip() or None
    saved = create_draft_reply(
        to=body.to,
        subject=body.subject,
        body=body.body,
        in_reply_to_rfc822_id=record.rfc822_message_id or "",
        thread_id=record.thread_id or None,
        cc=cc_clean,
    )
    if not saved:
        raise HTTPException(status_code=500, detail="Draft save failed. Check backend logs.")

    return {"saved": True}


def _upsert_recipients(db: Session, to_field: str) -> None:
    """
    Bump the use_count for each address in a comma-separated 'To:' string,
    or insert new rows for first-time recipients. Powers the autocomplete
    list in /api/email-recipients.
    """
    if not to_field:
        return
    now = datetime.now(timezone.utc).isoformat()
    seen: set[str] = set()
    for raw in to_field.split(","):
        addr = raw.strip()
        if not addr or addr in seen:
            continue
        seen.add(addr)
        existing = db.get(EmailRecipientRecord, addr)
        if existing:
            existing.use_count += 1
            existing.last_used_at = now
        else:
            db.add(EmailRecipientRecord(email=addr, use_count=1, last_used_at=now))
    db.commit()


# ── Compose freeform email (with optional attachments) ───────────────────────

@app.post("/api/emails/compose")
async def compose_email(
    to: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    cc: str = Form(default=""),
    attachments: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Send a NEW (non-threaded) email from the chat composer. Used when
    Marimba drafts an email mid-conversation that is not a reply — e.g.
    forwarding an invoice, sending a fresh message to a colleague, etc.

    Body is multipart/form-data so file attachments can ride along.
    Cap total attachment size at 20 MB to stay well under Gmail's 25 MB limit.
    """
    from connectors.gmail import is_configured, send_email_with_attachments

    if not is_configured():
        raise HTTPException(status_code=503, detail="Gmail is not configured.")

    MAX_TOTAL_BYTES = 20 * 1024 * 1024  # 20 MB
    total = 0
    files_payload: list[Dict[str, Any]] = []
    for f in attachments or []:
        data = await f.read()
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Total attachment size exceeds 20 MB.",
            )
        files_payload.append({
            "filename": f.filename or "attachment.bin",
            "mime_type": f.content_type or "application/octet-stream",
            "data": data,
        })

    cc_clean = (cc or "").strip() or None
    sent = send_email_with_attachments(
        to=to,
        subject=subject,
        body=body,
        cc=cc_clean,
        attachments=files_payload or None,
    )
    if not sent:
        raise HTTPException(status_code=500, detail="Send failed. Check backend logs.")

    try:
        _upsert_recipients(db, to)
        if cc_clean:
            _upsert_recipients(db, cc_clean)
    except Exception as e:
        print(f"[compose_email] recipient tracking failed (non-fatal): {e}")

    return {"sent": True, "attachment_count": len(files_payload)}


class SaveDraftRequest(BaseModel):
    to: str = ""
    subject: str
    body: str
    cc: str = ""


@app.post("/api/emails/save-draft")
async def save_email_compose_as_draft(
    body: SaveDraftRequest,
) -> Dict[str, Any]:
    """Save a new (non-threaded) freeform email to Gmail Drafts."""
    from connectors.gmail import is_configured, create_draft

    if not is_configured():
        raise HTTPException(status_code=503, detail="Gmail is not configured.")

    cc_clean = (body.cc or "").strip() or None
    to_clean = (body.to or "").strip() or None
    saved = create_draft(
        to=to_clean,
        subject=body.subject,
        body=body.body,
        cc=cc_clean,
    )
    if not saved:
        raise HTTPException(status_code=500, detail="Draft save failed. Check backend logs.")

    return {"saved": True}


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


def _meeting_time_to_24h(part: str) -> Optional[str]:
    """Parse one clock time ("1:30pm", "10:50am", "9:00") into 24h "HH:MM"."""
    import re

    match = re.match(r"\s*(\d{1,2}):(\d{2})\s*(am|pm)?", part.strip().lower())
    if not match:
        return None
    hour = int(match.group(1))
    minute = match.group(2)
    meridiem = match.group(3)
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute}"


def _parse_meeting_time(time_str: str) -> tuple[Optional[str], Optional[str]]:
    """
    Split a weekly-meeting time string into (start, end) 24h strings.
    "1:30pm - 2:50pm" → ("13:30", "14:50"); "10:50am" → ("10:50", None);
    unparseable/empty → (None, None). Best-effort — am/pm only on one side is
    left as-is rather than guessed.
    """
    import re

    if not time_str:
        return (None, None)
    parts = re.split(r"[-–—]", time_str)
    start = _meeting_time_to_24h(parts[0])
    end = _meeting_time_to_24h(parts[1]) if len(parts) > 1 else None
    return (start, end)


def _reconcile_weekly_events(db: Session, target_date: str) -> None:
    """
    Materialize today's weekly-newsletter meetings as EventRecords so they share
    the timeline (and dedup) with email/voice events. Weekly meetings carry only
    a rotation `schedule_day` (1–6), not a date — so we map them onto TODAY when
    their schedule_day matches the current one. Idempotent: re-runs each read but
    only creates missing rows (update_if_exists=False), so a dismissed weekly
    meeting stays gone.
    """
    import events as events_module

    weekly_record = db.get(WeeklyScheduleRecord, "current")
    if not weekly_record:
        return
    try:
        weekly_data = json.loads(weekly_record.data)
    except Exception:
        return

    today_schedule_day = get_current_schedule_day()
    for meeting in weekly_data.get("meetings", []):
        if meeting.get("schedule_day") != today_schedule_day:
            continue
        title = (meeting.get("description") or "").strip()
        if not title:
            continue
        start_time, end_time = _parse_meeting_time(meeting.get("time") or "")
        events_module.create_or_update_event(
            db,
            title=title,
            date=target_date,
            start_time=start_time,
            end_time=end_time,
            location=(meeting.get("location") or None),
            source="weekly",
            visibility="shown",
            update_if_exists=False,
        )


@app.get("/api/events")
async def list_events(
    date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Shown, not-dismissed calendar events/meetings for one day (default today).

    These are the events that earned a place on the schedule timeline — the
    relevance gate marked them visibility="shown". Hidden and dismissed events
    are excluded here but stay in the DB (still findable by Marimba).
    """
    import events as events_module
    from datetime import date as date_class

    target_date = date or date_class.today().isoformat()
    # Fold today's weekly-newsletter meetings onto the timeline (they only map to
    # a date for *today*, via the current rotation day).
    if target_date == date_class.today().isoformat():
        _reconcile_weekly_events(db, target_date)
    records = events_module.list_events_for_day(db, target_date)
    return {
        "date": target_date,
        "events": [events_module.event_to_dict(record) for record in records],
        "count": len(records),
    }


@app.post("/api/events/{event_id}/dismiss")
async def dismiss_event_endpoint(
    event_id: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    The quiet × on an event row: soft-dismiss it (it leaves the timeline but
    stays findable) and log a 'noise' relevance signal for future eval/training.
    """
    import events as events_module

    dismissed = events_module.dismiss_event(db, event_id)
    if dismissed is None:
        return {"error": "Event not found"}
    return {"dismissed": event_id}


class PriorityFeedbackRequest(BaseModel):
    task_id: str
    task_title: str
    source: str          # user_task | email | meeting | action_item
    priority_level: str  # high | medium | low
    rating: str          # relevant | noise | skip
    context_json: str    # JSON-encoded full task dict


@app.post("/api/priority-feedback")
async def record_priority_feedback(
    body: PriorityFeedbackRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Save a teacher's implicit or explicit rating for a Top-3 priority item.

    Ratings:
      relevant → marked done; positive training signal.
      noise    → categorically not useful; strong negative training signal,
                 suppressed for 14 days at the priorities endpoint.
      skip     → "doesn't apply this week"; suppressed only until the next
                 weekly_schedule upload, neutral for future training.

    These records are the raw dataset for future few-shot prompt injection
    and potential LoRA fine-tuning of a small ranking model.
    """
    import uuid
    from datetime import datetime, timezone

    record = PriorityFeedbackRecord(
        id=str(uuid.uuid4()),
        task_id=body.task_id,
        task_title=body.task_title,
        source=body.source,
        priority_level=body.priority_level,
        rating=body.rating,
        context_json=body.context_json,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(record)
    db.commit()
    return {"saved": True}


@app.get("/api/priority-feedback/export")
async def export_priority_feedback(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Export all feedback records as a list — ready to convert to JSONL for fine-tuning.
    Each record contains: task_title, source, priority_level, rating, context_json.
    Filter by rating='relevant' for positive examples, 'noise' for negatives.
    """
    from sqlalchemy import select

    records = db.execute(select(PriorityFeedbackRecord).order_by(
        PriorityFeedbackRecord.created_at.desc()
    )).scalars().all()

    return [
        {
            "id": r.id,
            "task_id": r.task_id,
            "task_title": r.task_title,
            "source": r.source,
            "priority_level": r.priority_level,
            "rating": r.rating,
            "context": r.context_json,
            "created_at": r.created_at,
        }
        for r in records
    ]


class WeeklyScheduleRequest(BaseModel):
    document_text: str


@app.post("/api/weekly-schedule")
async def post_weekly_schedule(
    body: WeeklyScheduleRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Receive the Google Doc text and extract structured agenda data.

    Paste the plain text from the "Anuncios Semanales" Google Doc here.
    Mistral extracts meetings, class disruptions, action items, and upcoming dates.

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


@app.delete("/api/weekly-schedule")
async def delete_weekly_schedule(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Clear the stored weekly schedule so stale data stops feeding the Top 3."""
    record = db.get(WeeklyScheduleRecord, "current")
    if record:
        db.delete(record)
        db.commit()
    return {"deleted": True}


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


@app.get("/api/class/{group}/sessions")
async def get_group_sessions(
    group: str,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return all session logs for a class group, newest first."""
    from sqlalchemy import desc, select

    records = (
        db.execute(
            select(ClassSessionRecord)
            .where(ClassSessionRecord.group == group)
            .order_by(desc(ClassSessionRecord.date), desc(ClassSessionRecord.schedule_day))
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "group": r.group,
            "schedule_day": r.schedule_day,
            "date": r.date,
            "notes": r.notes,
            "what_worked": r.what_worked,
            "created_at": r.created_at,
        }
        for r in records
    ]


# ── Lesson plan ───────────────────────────────────────────────────────────────
#
# The "Plan lesson" drawer on each class card. Marimba opens with 3 distinct
# proposals (or a Socratic question if there's no history yet), the teacher
# refines via chat, and the final plan is saved against the group/date.

class LessonPlanChatRequest(BaseModel):
    messages: List[ChatMessage]


class LessonPlanAssignmentRequest(BaseModel):
    plan_text: str


class LessonPlanSaveRequest(BaseModel):
    date: str                      # YYYY-MM-DD
    plan_text: str
    context_snapshot: Optional[Dict[str, Any]] = None
    chosen_option: Optional[int] = None


def _parse_period_duration_min(time_label: str) -> int:
    """
    Parse "7:50am - 9:10am" → 80. Best effort; defaults to 80 (the most
    common period length) if anything looks off.
    """
    import re
    parts = re.split(r"\s*[-–]\s*", time_label.strip())
    if len(parts) != 2:
        return 80

    def to_minutes(s: str) -> Optional[int]:
        s = s.strip().lower().replace(" ", "")
        m = re.match(r"(\d{1,2}):?(\d{2})?(am|pm)?", s)
        if not m:
            return None
        hh = int(m.group(1))
        mm = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3)
        if ampm == "pm" and hh < 12:
            hh += 12
        elif ampm == "am" and hh == 12:
            hh = 0
        return hh * 60 + mm

    # If the first part lacks am/pm, copy from the second part
    if not re.search(r"(am|pm)", parts[0], re.IGNORECASE):
        m2 = re.search(r"(am|pm)", parts[1], re.IGNORECASE)
        if m2:
            parts[0] = parts[0] + m2.group(0)

    start = to_minutes(parts[0])
    end = to_minutes(parts[1])
    if start is None or end is None:
        return 80
    diff = end - start
    return diff if diff > 0 else 80


def _find_period_for_group(group: str, schedule_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Find the period dict for `group` on today's schedule day.
    Falls back to ANY day's period (so the drawer still works when the
    teacher peeks at tomorrow / yesterday). Returns None if the group
    isn't in the schedule at all.
    """
    today_day = get_current_schedule_day()
    fallback: Optional[Dict[str, Any]] = None
    for day_entry in schedule_data.get("classes", []):
        for period in day_entry.get("periods", []):
            if period.get("group") == group:
                if day_entry.get("day") == today_day:
                    return period
                if fallback is None:
                    fallback = period
    return fallback


def _build_lesson_plan_context(
    group: str, db: Session
) -> tuple[str, bool, Dict[str, Any]]:
    """
    Assemble the lesson-planning context block.

    Returns:
      context_block:    natural-language string fed to the system prompt
      has_history:      True if class_sessions OR lesson_plans exist for `group`
      context_snapshot: dict the frontend echoes back at save time, so the
                        saved LessonPlanRecord knows what Marimba saw
    """
    from sqlalchemy import desc, select
    from prompts.lesson_plan import format_lesson_context

    # Recent sessions (most recent first, up to 2)
    sessions = (
        db.execute(
            select(ClassSessionRecord)
            .where(ClassSessionRecord.group == group)
            .order_by(desc(ClassSessionRecord.date), desc(ClassSessionRecord.schedule_day))
            .limit(2)
        )
        .scalars()
        .all()
    )

    # Recent lesson plans (most recent first, up to 3)
    plans = (
        db.execute(
            select(LessonPlanRecord)
            .where(LessonPlanRecord.group == group)
            .order_by(desc(LessonPlanRecord.created_at))
            .limit(3)
        )
        .scalars()
        .all()
    )

    has_history = bool(sessions) or bool(plans)

    schedule_data = _load_schedule_data() or {}
    period = _find_period_for_group(group, schedule_data)
    subject = period.get("subject", "") if period else ""
    time_label = period.get("time", "") if period else ""
    duration_min = _parse_period_duration_min(time_label) if time_label else 80

    sessions_dicts = [
        {
            "date": s.date,
            "notes": s.notes,
            "what_worked": s.what_worked or "",
        }
        for s in sessions
    ]
    plans_dicts = [
        {"date": p.date, "plan_text": p.plan_text}
        for p in plans
    ]

    context_block = format_lesson_context(
        group=group,
        subject=subject,
        duration_min=duration_min,
        time_label=time_label,
        last_sessions=sessions_dicts,
        recent_plans=plans_dicts,
    )

    snapshot: Dict[str, Any] = {
        "group": group,
        "subject": subject,
        "time_label": time_label,
        "duration_min": duration_min,
        "last_sessions": sessions_dicts,
        "recent_plans": plans_dicts,
    }
    return context_block, has_history, snapshot


@app.post("/api/lesson-plan/{group}/chat")
async def lesson_plan_chat_endpoint(
    group: str,
    body: LessonPlanChatRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    One conversation turn for the lesson-planning drawer.

    Empty `messages` = first turn — Marimba opens (3 proposals if history
    exists, Socratic question if cold start).

    Returns {"reply": str, "context_snapshot": {...}}. The snapshot is
    handed back to the frontend so it can submit it unchanged at save time.
    """
    from prompts.lesson_plan import call_lesson_plan_chat

    context_block, has_history, snapshot = _build_lesson_plan_context(group, db)
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    reply, tool_calls = await call_lesson_plan_chat(
        group=group,
        messages=messages,
        context_block=context_block,
        has_history=has_history,
    )
    if reply is None:
        raise HTTPException(
            status_code=503,
            detail="Mistral is not reachable right now. Try again in a moment.",
        )
    return {"reply": reply, "context_snapshot": snapshot, "tool_calls": tool_calls}


@app.post("/api/lesson-plan/{group}/assignment")
async def lesson_plan_assignment_endpoint(
    group: str,
    body: LessonPlanAssignmentRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Given the current lesson plan text, ask Marimba to produce a
    copyable assignment description (```assignment block) tied to it.
    """
    from prompts.lesson_plan import call_assignment_description

    context_block, _, _ = _build_lesson_plan_context(group, db)
    reply = await call_assignment_description(
        plan_text=body.plan_text, group=group, context_block=context_block
    )
    if reply is None:
        raise HTTPException(
            status_code=503,
            detail="Mistral is not reachable right now. Try again in a moment.",
        )
    return {"reply": reply}


@app.post("/api/lesson-plan/{group}/save")
async def save_lesson_plan_endpoint(
    group: str,
    body: LessonPlanSaveRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Persist a finalized lesson plan against the given group and date.
    Returns the saved record id + timestamps.
    """
    import uuid
    record_id = str(uuid.uuid4())
    now_str = datetime.now(timezone.utc).isoformat()

    snapshot_json: Optional[str] = None
    if body.context_snapshot is not None:
        try:
            snapshot_json = json.dumps(body.context_snapshot, ensure_ascii=False)
        except Exception:
            snapshot_json = None

    db.add(
        LessonPlanRecord(
            id=record_id,
            group=group,
            date=body.date,
            plan_text=body.plan_text,
            context_snapshot=snapshot_json,
            chosen_option=body.chosen_option,
            feedback=None,
            notes=None,
            created_at=now_str,
        )
    )
    db.commit()

    return {
        "id": record_id,
        "group": group,
        "date": body.date,
        "created_at": now_str,
    }


@app.get("/api/lesson-plan/{group}/recent")
async def recent_lesson_plans_endpoint(
    group: str,
    limit: int = 3,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Return the N most recently saved lesson plans for the group.
    Surfaced as quick references inside the drawer.
    """
    from sqlalchemy import desc, select

    records = (
        db.execute(
            select(LessonPlanRecord)
            .where(LessonPlanRecord.group == group)
            .order_by(desc(LessonPlanRecord.created_at))
            .limit(max(1, min(limit, 20)))
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "group": r.group,
            "date": r.date,
            "plan_text": r.plan_text,
            "chosen_option": r.chosen_option,
            "created_at": r.created_at,
        }
        for r in records
    ]


@app.get("/api/student-flags")
async def get_student_flags() -> Dict[str, Any]:
    """
    Return the full per-group map of students who need academic support.
    Powers the briefing card's "students needing support" list and flag
    count. Source: backend/data/student_flags.json (manually maintained).
    """
    path = Path(__file__).parent / "data" / "student_flags.json"
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _build_voice_context(
    schedule_data: Dict[str, Any],
    all_tasks: List[Dict[str, Any]],
    weekly_data: Optional[Dict[str, Any]],
    session_notes: Optional[Dict[str, Dict[str, str]]] = None,
    all_groups: Optional[List[str]] = None,
) -> str:
    """Build a concise plain-text context summary for the voice Mistral call.

    Uses the SAME full 6-day schedule block as the priority and task-chat
    prompts (``format_schedule_block``) rather than injecting only today's
    periods. Injecting today alone left Marimba blind to tomorrow's class
    times — she would confabulate a plausible-but-wrong time (e.g. reporting
    7B at 10:50am when it actually meets at 11:30am). The block renders all
    six rotation days with TODAY/NEXT markers, plus today's meetings and
    disruptions, so she never has to guess.
    """
    from context_builder import format_schedule_block

    schedule_block = format_schedule_block(
        schedule_data, _get_current_time(), weekly_data
    )

    # Each task carries its id in brackets so Marimba can reference it with
    # the complete_task action ("mark X done"). The id encodes the source:
    # "user_…" is a teacher task, anything else is an action-required email.
    tasks_str = (
        "\n".join(
            f"- {t['title']} ({t['priority']}) [id: {t['id']}]" for t in all_tasks[:8]
        )
        or "no tasks"
    )

    # Last-session notes so Marimba can answer "what did we do last time with
    # 9A1?". Crucially, we ALSO list the groups that have NO log yet, and tell
    # Marimba to treat that as "no record" — never invent a lesson. LLMs are
    # bad at noticing absence ("9A1 isn't in the list, so I don't know"), so we
    # make the absence explicit rather than relying on omission.
    sessions_str = ""
    logged = []
    if session_notes:
        for group, notes in session_notes.items():
            note = notes.get("notes", "").strip()
            what_worked = notes.get("what_worked", "").strip()
            if note:
                entry = f"- {group}: \"{note}\""
                if what_worked:
                    entry += f" (what worked: {what_worked})"
                logged.append((group, entry))

    logged_groups = {g for g, _ in logged}
    unlogged = [g for g in (all_groups or []) if g not in logged_groups]

    if logged or unlogged:
        parts = ["\n\nCLASS SESSION LOG (what was last taught):"]
        if logged:
            parts.append("\n".join(entry for _, entry in logged))
        else:
            parts.append("(no class sessions have been logged yet)")
        if unlogged:
            parts.append(
                "No session logged yet for: "
                + ", ".join(unlogged)
                + ". If asked what happened in one of these, say you have no "
                "record of it and offer to log it — do NOT invent a lesson."
            )
        sessions_str = "\n".join(parts)

    # Absolute date so Marimba can resolve "tomorrow"/"Friday" into a concrete
    # YYYY-MM-DD for add_event (the schedule block only has TODAY/NEXT markers,
    # not the calendar date).
    today_str = _get_current_time().strftime("%Y-%m-%d (%A)")

    return (
        f"Today's date: {today_str}\n\n"
        f"{schedule_block}\n\n"
        f"Pending tasks:\n{tasks_str}"
        f"{sessions_str}"
    )


def _build_voice_history(
    db: Session,
    window_minutes: int = 10,
    max_turns: int = 3,
) -> List[Dict[str, str]]:
    """Reconstruct the last few voice turns as chat messages for short-term memory.

    The voice endpoint is otherwise stateless — each utterance is handled fresh.
    To make follow-ups like "yes, log it" resolve, we replay the recent
    conversation: each past turn becomes a user message (what the teacher said)
    + an assistant message (what Marimba replied). We only include turns from the
    last ``window_minutes`` so a conversation from hours ago doesn't bleed in —
    a burst of voice activity is one conversation; a gap ends it.

    Returns messages in chronological order, ready to slot between the system
    prompt and the current user message.
    """
    from datetime import timedelta

    from database import VoiceLogRecord
    from sqlalchemy import desc as sql_desc, select

    rows = (
        db.execute(
            select(VoiceLogRecord)
            .order_by(sql_desc(VoiceLogRecord.created_at))
            .limit(max_turns)
        )
        .scalars()
        .all()
    )

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    messages: List[Dict[str, str]] = []
    for row in reversed(rows):  # chronological (oldest of the window first)
        try:
            created = datetime.fromisoformat(row.created_at)
        except (ValueError, TypeError):
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created < cutoff:
            continue
        if row.transcript:
            messages.append({"role": "user", "content": row.transcript})
            try:
                reply = (json.loads(row.mistral_response) or {}).get("response", "")
            except (json.JSONDecodeError, TypeError):
                reply = ""
            if reply:
                messages.append({"role": "assistant", "content": reply})
    return messages


@app.post("/api/voice")
async def handle_voice(
    audio: UploadFile = File(...),
    focus: Optional[str] = Form(default=None),
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
        no_key = not os.getenv("MISTRAL_API_KEY")
        print(f"[Voice] Empty transcript — MISTRAL_API_KEY {'not set' if no_key else 'set, audio may be silent or corrupted'}")
        msg = (
            "MISTRAL_API_KEY no está configurado, profe. Sin esa clave no puedo escucharte."
            if no_key
            else "No pude escuchar nada en el audio. ¿Lo intentamos de nuevo?"
        )
        return {"text": msg, "audio": None, "action": None}

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
                    ImportantEmailRecord.category == "action_required",
                    ImportantEmailRecord.dismissed_at.is_(None),
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

        # Gather last-session notes for every class in today's schedule so Marimba
        # can answer questions about what happened in previous lessons —
        # for ANY group, not just today's. The teacher asks about classes on
        # other days too ("what did I do last with 7B?"). Gathering only
        # today's groups left those queries with no data, so Marimba would
        # confabulate a lesson. We collect every group the teacher teaches
        # (homeroom + all six rotation days) and pull each one's latest note.
        from database import ClassSessionRecord
        from sqlalchemy import desc as sql_desc

        all_groups: List[str] = []
        homeroom_group = (schedule_data.get("homeroom") or {}).get("group")
        if homeroom_group:
            all_groups.append(homeroom_group)
        for day_sched in schedule_data.get("classes", []):
            for p in day_sched.get("periods", []):
                if p.get("group"):
                    all_groups.append(p["group"])
        # Dedupe while preserving order
        all_groups = list(dict.fromkeys(all_groups))

        session_notes: Dict[str, Dict[str, str]] = {}
        for group in all_groups:
            last = (
                db.execute(
                    select(ClassSessionRecord)
                    .where(ClassSessionRecord.group == group)
                    .order_by(sql_desc(ClassSessionRecord.date), sql_desc(ClassSessionRecord.schedule_day))
                    .limit(1)
                )
                .scalars()
                .first()
            )
            if last:
                session_notes[group] = {
                    "notes": last.notes or "",
                    "what_worked": last.what_worked or "",
                }

        context = _build_voice_context(
            schedule_data, all_tasks, weekly_data, session_notes, all_groups
        )

        # The teacher tapped 🦊 on a specific event chip — surface it so Marimba
        # knows which meeting "this" refers to without the teacher repeating it.
        if focus:
            context += f"\n\nThe teacher is asking about this event:\n{focus}"

        # Short-term memory: replay the last few minutes of voice turns so
        # follow-ups ("yes, log it") keep the group/intent from the prior turn.
        history = _build_voice_history(db)

        mistral_result = await call_voice_mistral(transcript, context, history=history)

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

        # add_event: create a calendar event/meeting on the teacher's schedule.
        # Marimba resolves the absolute date from "Today's date" in the context;
        # we persist via the same events helper the email path uses (so dedup by
        # date+title applies). source="voice" — always shown (she created it).
        elif action and action.get("type") == "add_event":
            import events as events_mod

            ev_title = (action.get("title") or "").strip()
            ev_date = (action.get("date") or "").strip()
            if ev_title and ev_date:
                events_mod.create_or_update_event(
                    db,
                    title=ev_title,
                    date=ev_date,
                    start_time=(action.get("start_time") or None),
                    end_time=(action.get("end_time") or None),
                    location=(action.get("location") or None),
                    source="voice",
                    visibility="shown",
                )

        # complete_task: clear a teacher task or dismiss an action-required
        # email. The id was shown to Marimba in the context's task list; we
        # route by prefix ("user_…" = teacher task, else = email). If the id
        # doesn't match, fall back to a title substring match so a slightly
        # mis-copied id still resolves the right item.
        elif action and action.get("type") == "complete_task":
            target_id = (action.get("id") or "").strip()
            known_ids = {t["id"] for t in all_tasks}
            if target_id not in known_ids:
                title_q = (action.get("title") or "").strip().lower()
                if title_q:
                    for t in all_tasks:
                        if title_q in t["title"].lower():
                            target_id = t["id"]
                            break
            if target_id.startswith("user_"):
                rec = db.get(UserTaskRecord, target_id[len("user_"):])
                if rec:
                    db.delete(rec)
                    db.commit()
            elif target_id:
                rec = db.get(ImportantEmailRecord, target_id)
                if rec and rec.dismissed_at is None:
                    rec.dismissed_at = datetime.now(timezone.utc).isoformat()
                    db.commit()
                    # Dismissing by voice clears the unread flag in Gmail too,
                    # same as the in-app dismiss button.
                    _mark_gmail_read([target_id])

        # log_session: upsert today's session note for a class — same keying
        # ("{group}_{date}_{schedule_day}") as POST /api/class/{group}/session,
        # so logging by voice and by tapping write to the same row.
        elif action and action.get("type") == "log_session":
            from datetime import date as _date

            group = (action.get("group") or "").strip()
            notes = (action.get("notes") or "").strip()
            what_worked = (action.get("what_worked") or "").strip() or None
            if group and notes:
                today = _date.today().isoformat()
                sday = get_current_schedule_day()
                record_id = f"{group}_{today}_{sday}"
                now_str = datetime.now(timezone.utc).isoformat()
                existing = db.get(ClassSessionRecord, record_id)
                if existing:
                    existing.notes = notes
                    existing.what_worked = what_worked
                    existing.created_at = now_str
                else:
                    db.add(
                        ClassSessionRecord(
                            id=record_id,
                            group=group,
                            schedule_day=sday,
                            date=today,
                            notes=notes,
                            what_worked=what_worked,
                            created_at=now_str,
                        )
                    )
                db.commit()

        # view_schedule_day and open_lesson_plan are UI-only — no DB effect
        # here; the frontend handles them from the returned action.

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


class MeetingEmailSendRequest(BaseModel):
    to: str
    subject: str
    body: str


@app.post("/api/meetings/process")
async def process_meeting_audio(
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Transcribe a meeting recording and generate a Spanish email summary.

    Pipeline:
      1. Receive audio file (WebM/Opus or MP4/AAC, up to ~45 min)
      2. Voxtral Mini transcribes it in Spanish
      3. Mistral Large generates summary, action items, and email draft
      4. Persists a MeetingRecord to the database
      5. Returns meeting_id + full draft for the frontend review step

    The caller should use a long HTTP timeout (≥180 s) for large files.
    """
    import uuid

    try:
        audio_bytes = await audio.read()

        if not audio_bytes:
            raise HTTPException(status_code=422, detail="El archivo de audio estaba vacío.")

        print(f"[Meetings] Received audio: {len(audio_bytes)} bytes, filename={audio.filename}")

        # No language hint — Voxtral auto-detects; forcing a hint can hurt accuracy
        transcript = await transcribe_audio(audio_bytes, audio.filename or "meeting.webm")

        if not transcript:
            raise HTTPException(
                status_code=422,
                detail="No se pudo transcribir el audio. Verifica que el archivo tenga voz grabada y que MISTRAL_API_KEY esté configurado.",
            )

        print(f"[Meetings] Transcript ({len(transcript)} chars): {transcript[:120]}…")

        summary_result = await summarize_meeting(transcript)

        if not summary_result:
            raise HTTPException(
                status_code=422,
                detail="No se pudo generar el resumen. Verifica que MISTRAL_API_KEY esté configurado.",
            )

        meeting_id = str(uuid.uuid4())
        record = MeetingRecord(
            id=meeting_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            transcription=transcript,
            summary=summary_result["summary"],
            action_items=json.dumps(summary_result["action_items"], ensure_ascii=False),
            suggested_subject=summary_result["suggested_subject"],
            email_body=summary_result["email_body"],
            email_sent=False,
            recipient=None,
        )
        db.add(record)
        db.commit()

        return {
            "meeting_id": meeting_id,
            "transcription": transcript,
            "summary": summary_result["summary"],
            "action_items": summary_result["action_items"],
            "suggested_subject": summary_result["suggested_subject"],
            "email_body": summary_result["email_body"],
        }

    except HTTPException:
        raise  # let our own clean errors pass through unchanged
    except Exception as e:
        print(f"[Meetings] Unhandled error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado: {type(e).__name__}. Revisa la consola del servidor para más detalles.",
        )


@app.get("/api/email-recipients")
async def get_email_recipients(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Return stored email recipients ordered by most-used, for autocomplete."""
    rows = (
        db.query(EmailRecipientRecord)
        .order_by(EmailRecipientRecord.use_count.desc())
        .all()
    )
    return [
        {"email": r.email, "label": r.label, "use_count": r.use_count}
        for r in rows
    ]


@app.post("/api/meetings/{meeting_id}/send-email")
async def send_meeting_email(
    meeting_id: str,
    request: MeetingEmailSendRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Send the meeting summary email via Gmail and mark the record as sent.
    Requires the Gmail connector to be configured with the gmail.send scope.
    """
    from connectors.gmail import is_configured, send_email

    record = db.get(MeetingRecord, meeting_id)
    if not record:
        return {"sent": False, "error": "Reunión no encontrada."}

    if not is_configured():
        return {"sent": False, "error": "Gmail no está configurado. Ejecuta auth_gmail.py."}

    try:
        sent = send_email(to=request.to, subject=request.subject, body=request.body)
    except Exception as e:
        print(f"[send_meeting_email] unexpected error: {e}")
        return {"sent": False, "error": "Error inesperado al enviar. Revisa los logs del servidor."}

    if sent:
        record.email_sent = True
        record.recipient = request.to
        db.commit()

        try:
            now = datetime.now(timezone.utc).isoformat()
            existing = db.get(EmailRecipientRecord, request.to)
            if existing:
                existing.use_count += 1
                existing.last_used_at = now
            else:
                db.add(EmailRecipientRecord(email=request.to, use_count=1, last_used_at=now))
            db.commit()
        except Exception as e:
            print(f"[send_meeting_email] recipient tracking failed (non-fatal): {e}")

    return {"sent": sent}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
