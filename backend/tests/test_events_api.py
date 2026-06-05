#!/usr/bin/env python3
"""
Group 4a — the events HTTP API that feeds the schedule timeline.

  GET  /api/events?date=YYYY-MM-DD   → shown, not-dismissed events for that day
  POST /api/events/{id}/dismiss      → soft-dismiss + 'noise' feedback signal

Uses the same in-memory StaticPool + get_db override pattern as the other API
tests, and seeds events through the events helper module.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db, EventRecord, PriorityFeedbackRecord
import events


@pytest.fixture()
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSession
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def test_get_events_returns_shown_events_for_a_day(test_db):
    db = test_db()
    events.create_or_update_event(
        db, title="Dept meeting", date="2026-06-05", start_time="12:00",
        location="library", source="email",
    )
    events.create_or_update_event(
        db, title="Hidden assembly", date="2026-06-05", start_time="09:00",
        source="email", visibility="hidden",
    )
    db.close()

    response = client.get("/api/events", params={"date": "2026-06-05"})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1                       # hidden one excluded
    assert body["events"][0]["title"] == "Dept meeting"
    assert body["events"][0]["location"] == "library"


def test_get_events_filters_by_date(test_db):
    db = test_db()
    events.create_or_update_event(db, title="Today", date="2026-06-05", source="voice")
    events.create_or_update_event(db, title="Other day", date="2026-06-09", source="voice")
    db.close()

    body = client.get("/api/events", params={"date": "2026-06-05"}).json()
    assert [event["title"] for event in body["events"]] == ["Today"]


def test_dismiss_removes_from_list_and_logs_feedback(test_db):
    db = test_db()
    created = events.create_or_update_event(
        db, title="Dept meeting", date="2026-06-05", source="email",
    )
    event_id = created.id
    db.close()

    dismiss = client.post(f"/api/events/{event_id}/dismiss")
    assert dismiss.status_code == 200
    assert dismiss.json() == {"dismissed": event_id}

    # gone from the day's list
    body = client.get("/api/events", params={"date": "2026-06-05"}).json()
    assert body["count"] == 0

    # still findable + a 'noise' feedback row was written
    db = test_db()
    still_there = db.get(EventRecord, event_id)
    assert still_there is not None and still_there.dismissed_at is not None
    feedback = db.execute(select(PriorityFeedbackRecord)).scalars().all()
    assert len(feedback) == 1 and feedback[0].source == "event"
    db.close()


def test_dismiss_missing_event_returns_error(test_db):
    response = client.post("/api/events/nope/dismiss")
    assert response.status_code == 200
    assert "error" in response.json()


def test_event_chat_context_includes_real_fields():
    """'Chat about this' feeds Marimba the event's real fields (no hallucination)."""
    import json
    from types import SimpleNamespace
    import main

    event = SimpleNamespace(
        title="Reunión secundaria",
        date="2026-06-05",
        start_time="12:00",
        end_time="12:45",
        location="biblioteca",
        meet_link="https://meet.google.com/abc",
        attendees=json.dumps(["Priscilla Noguera", "Camilo Infante"]),
    )
    context = main._build_task_context(
        source="event", title="Reunión secundaria", email=None, event=event
    )
    assert "Reunión secundaria" in context
    assert "2026-06-05" in context and "12:00–12:45" in context
    assert "biblioteca" in context                 # physical location surfaced
    assert "Priscilla Noguera" in context          # attendees surfaced
    assert "meet.google.com/abc" in context


# ── 4c: weekly-meeting reconciliation ────────────────────────────────────────

import json as _json
from datetime import date as _date

import main
from database import WeeklyScheduleRecord


def test_parse_meeting_time():
    assert main._parse_meeting_time("1:30pm - 2:50pm") == ("13:30", "14:50")
    assert main._parse_meeting_time("10:50am") == ("10:50", None)
    assert main._parse_meeting_time("12:00pm") == ("12:00", None)
    assert main._parse_meeting_time("") == (None, None)


def _seed_weekly_meeting(db, schedule_day, description="Reunión de departamento", time="1:30pm - 2:00pm"):
    db.add(WeeklyScheduleRecord(
        id="current",
        week_label="demo week",
        data=_json.dumps({"meetings": [
            {"description": description, "day": "Mon", "schedule_day": schedule_day,
             "time": time, "location": "Sala", "mandatory": True},
        ]}),
        created_at="2026-06-05",
    ))
    db.commit()


def test_weekly_meeting_appears_on_today_timeline(test_db, monkeypatch):
    monkeypatch.setattr(main, "get_current_schedule_day", lambda: 3)
    db = test_db()
    _seed_weekly_meeting(db, schedule_day=3)
    db.close()

    today = _date.today().isoformat()
    body = client.get("/api/events", params={"date": today}).json()
    titles = [event["title"] for event in body["events"]]
    assert "Reunión de departamento" in titles
    meeting = next(e for e in body["events"] if e["title"] == "Reunión de departamento")
    assert meeting["start_time"] == "13:30" and meeting["source"] == "weekly"


def test_weekly_meeting_for_other_day_is_not_shown(test_db, monkeypatch):
    monkeypatch.setattr(main, "get_current_schedule_day", lambda: 3)
    db = test_db()
    _seed_weekly_meeting(db, schedule_day=5)   # not today's rotation day
    db.close()

    today = _date.today().isoformat()
    body = client.get("/api/events", params={"date": today}).json()
    assert body["count"] == 0


def test_weekly_reconcile_is_idempotent_and_dismiss_sticks(test_db, monkeypatch):
    monkeypatch.setattr(main, "get_current_schedule_day", lambda: 3)
    db = test_db()
    _seed_weekly_meeting(db, schedule_day=3)
    db.close()
    today = _date.today().isoformat()

    # Two reads → still exactly one row (no duplication, no churn).
    first = client.get("/api/events", params={"date": today}).json()
    second = client.get("/api/events", params={"date": today}).json()
    assert first["count"] == 1 and second["count"] == 1

    # Dismiss it, then read again → it is NOT recreated by the reconciler.
    event_id = second["events"][0]["id"]
    client.post(f"/api/events/{event_id}/dismiss")
    after = client.get("/api/events", params={"date": today}).json()
    assert after["count"] == 0
