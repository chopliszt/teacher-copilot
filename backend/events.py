"""
Events — CRUD + dedup helpers for calendar events / meetings (EventRecord).

Pure functions that take a SQLAlchemy Session, so they unit-test without FastAPI.
An "event" is a time-anchored commitment that is not a class (a department
meeting, an AI training, a director's call). See database.EventRecord.

Dedup rule: if a calendar event id (`eid`) is known we match on that — it is
stable across "this event was updated" edits, so the update lands on the same
row. Otherwise we fall back to (date + normalized title), which catches the same
meeting arriving from two sources (e.g. the newsletter and an email).
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import date as date_cls
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import EventRecord, PriorityFeedbackRecord


def _now_iso() -> str:
    """Current UTC time as an ISO-8601 string (matches the rest of the DB)."""
    return datetime.now(timezone.utc).isoformat()


def _normalize_title(title: str) -> str:
    """Lowercase, trim, collapse whitespace — the fuzzy key for title-based dedup."""
    return re.sub(r"\s+", " ", title or "").strip().lower()


def _attendees_to_json(attendees: Optional[List[str]]) -> Optional[str]:
    return json.dumps(attendees) if attendees else None


def _find_existing(
    db: Session, *, eid: Optional[str], date: str, title: str
) -> Optional[EventRecord]:
    """Locate an event to update: prefer the calendar `eid`, else date + title."""
    if eid:
        match = db.execute(
            select(EventRecord).where(EventRecord.eid == eid)
        ).scalar_one_or_none()
        if match:
            return match
    # Fall back to fuzzy match on the same day + title.
    same_day = db.execute(
        select(EventRecord).where(EventRecord.date == date)
    ).scalars().all()
    norm = _normalize_title(title)
    for record in same_day:
        if _normalize_title(record.title) == norm:
            return record
    return None


def create_or_update_event(
    db: Session,
    *,
    title: str,
    date: str,  # YYYY-MM-DD
    source: str,  # email | voice | weekly | gcal
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    location: Optional[str] = None,
    meet_link: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    source_ref: Optional[str] = None,  # id of the origin record (e.g. Gmail message id)
    eid: Optional[str] = None,
    visibility: str = "shown",  # shown | hidden — set by the relevance gate
    update_if_exists: bool = True,
) -> EventRecord:
    """
    Insert a new event, or edit the existing one if this is a known event
    (matched by `eid`, else date + title). Returns the persisted record.

    On update we refresh the mutable fields (time/location/etc.) and stamp
    `updated_at` — this is how an "this event has been updated, changed: time"
    invite lands on the same row instead of duplicating. `dismissed_at` is left
    untouched on update (a dismissed event stays dismissed).

    `update_if_exists=False` returns a matching row untouched instead of editing
    it — used by the weekly-meeting reconciler, which re-runs on every read and
    must be idempotent (no churn, and a dismissed weekly meeting stays dismissed).
    """
    existing = _find_existing(db, eid=eid, date=date, title=title)
    if existing is not None:
        if not update_if_exists:
            return existing
        existing.title = title
        existing.date = date
        existing.start_time = start_time
        existing.end_time = end_time
        existing.location = location
        existing.meet_link = meet_link
        existing.attendees = _attendees_to_json(attendees)
        existing.visibility = visibility
        if eid:
            existing.eid = eid
        existing.updated_at = _now_iso()
        db.commit()
        db.refresh(existing)
        return existing

    record = EventRecord(
        id=str(uuid.uuid4()),
        title=title,
        date=date,
        start_time=start_time,
        end_time=end_time,
        location=location,
        meet_link=meet_link,
        attendees=_attendees_to_json(attendees),
        source=source,
        source_ref=source_ref,
        eid=eid,
        visibility=visibility,
        created_at=_now_iso(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_event(db: Session, event_id: str) -> Optional[EventRecord]:
    """Fetch one event by id (dismissed or not — dismissed events stay findable)."""
    return db.get(EventRecord, event_id)


def list_events_for_day(db: Session, date: str) -> List[EventRecord]:
    """Shown, not-dismissed events on a given day, ordered by start time."""
    rows = db.execute(
        select(EventRecord).where(
            EventRecord.date == date,
            EventRecord.visibility == "shown",
            EventRecord.dismissed_at.is_(None),
        )
    ).scalars().all()
    # All-day events (no start_time) sort first; the rest by "HH:MM".
    return sorted(rows, key=lambda e: e.start_time or "")


def list_upcoming_events(
    db: Session, after_date: str, horizon_days: int
) -> List[EventRecord]:
    """
    Shown, not-dismissed events strictly after `after_date` and within
    `horizon_days` of it — the data behind a future "Coming up" peek. The UI for
    that is deferred, but the query is cheap to have ready and to test.
    """
    start = date_cls.fromisoformat(after_date)
    end = start + timedelta(days=horizon_days)
    rows = db.execute(
        select(EventRecord).where(
            EventRecord.visibility == "shown",
            EventRecord.dismissed_at.is_(None),
            EventRecord.date > after_date,
            EventRecord.date <= end.isoformat(),
        )
    ).scalars().all()
    return sorted(rows, key=lambda e: (e.date, e.start_time or ""))


def set_visibility(
    db: Session, event_id: str, visibility: str
) -> Optional[EventRecord]:
    """Flip an event between 'shown' and 'hidden'. Returns the row or None."""
    record = db.get(EventRecord, event_id)
    if record is None:
        return None
    record.visibility = visibility
    db.commit()
    db.refresh(record)
    return record


def record_event_feedback(
    db: Session, event: EventRecord, rating: str = "noise"
) -> None:
    """
    Log a relevance signal for an event into the shared PriorityFeedbackRecord
    table (source="event"). A dismiss is "noise" — labeled data for tuning the
    triage prompt + evals later, exactly like priority-item feedback.
    """
    db.add(
        PriorityFeedbackRecord(
            id=str(uuid.uuid4()),
            task_id=event.id,
            task_title=event.title,
            source="event",
            priority_level=event.visibility or "n/a",
            rating=rating,
            context_json=json.dumps(event_to_dict(event)),
            created_at=_now_iso(),
        )
    )
    db.commit()


def dismiss_event(db: Session, event_id: str) -> Optional[EventRecord]:
    """
    The quiet `×`: soft-dismiss (set dismissed_at — the event stays findable) AND
    record a 'noise' relevance signal. Returns the row, or None if not found.
    """
    record = db.get(EventRecord, event_id)
    if record is None:
        return None
    record.dismissed_at = _now_iso()
    db.commit()
    record_event_feedback(db, record, rating="noise")
    db.refresh(record)
    return record


def event_to_dict(record: EventRecord) -> Dict[str, Any]:
    """Serialize an event for the API / for the feedback context blob."""
    return {
        "id": record.id,
        "title": record.title,
        "date": record.date,
        "start_time": record.start_time,
        "end_time": record.end_time,
        "location": record.location,
        "meet_link": record.meet_link,
        "attendees": json.loads(record.attendees) if record.attendees else [],
        "source": record.source,
        "source_ref": record.source_ref,
        "eid": record.eid,
        "visibility": record.visibility,
        "dismissed_at": record.dismissed_at,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }
