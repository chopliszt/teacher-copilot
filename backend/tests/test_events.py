#!/usr/bin/env python3
"""
Test suite for events.py — the CRUD + dedup helpers behind calendar-event
inclusion (Group 1 of features/2026-06-04-calendar-event-inclusion).

Covers: create, update-by-eid (the "this event was updated" case),
dedup-by-date+title, today/upcoming queries, soft-dismiss + feedback signal,
relevance muting, and physical-location-vs-meet-link storage.
"""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, EventRecord, PriorityFeedbackRecord
import events


@pytest.fixture()
def db():
    """Fresh in-memory SQLite session (StaticPool so one DB is shared)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _make(db, **overrides):
    """Helper: create an event with sensible defaults."""
    params = dict(
        title="Reunión secundaria",
        date="2026-06-05",
        start_time="12:00",
        end_time="12:45",
        source="email",
    )
    params.update(overrides)
    return events.create_or_update_event(db, **params)


# ── create ─────────────────────────────────────────────────────────────────

def test_create_event_persists_fields(db):
    rec = _make(db, location="biblioteca", meet_link="https://meet.google.com/abc")
    assert rec.id
    assert rec.title == "Reunión secundaria"
    assert rec.date == "2026-06-05"
    assert rec.start_time == "12:00"
    assert rec.relevance == "surfaced"
    assert rec.created_at
    # physical place and video link are stored separately
    assert rec.location == "biblioteca"
    assert rec.meet_link == "https://meet.google.com/abc"


def test_attendees_round_trip(db):
    rec = _make(db, attendees=["Camilo Infante", "Priscilla Noguera"])
    assert events.event_to_dict(rec)["attendees"] == [
        "Camilo Infante",
        "Priscilla Noguera",
    ]


# ── dedup / update ───────────────────────────────────────────────────────────

def test_update_by_eid_edits_same_row(db):
    """An 'updated' invite (same eid) edits the row instead of duplicating."""
    first = _make(db, eid="EID123", start_time="12:00")
    second = events.create_or_update_event(
        db,
        title="Reunión secundaria",
        date="2026-06-05",
        start_time="13:00",  # changed time
        source="email",
        eid="EID123",
    )
    assert second.id == first.id
    assert second.start_time == "13:00"
    assert second.updated_at is not None
    assert db.execute(select(EventRecord)).scalars().all().__len__() == 1


def test_dedup_by_date_and_title_when_no_eid(db):
    """Same meeting from two sources (no eid) collapses to one row."""
    _make(db, source="weekly", start_time=None)
    _make(db, source="email", start_time="12:00")  # same title+date
    rows = db.execute(select(EventRecord)).scalars().all()
    assert len(rows) == 1
    assert rows[0].start_time == "12:00"  # the later write wins


def test_different_title_same_day_is_a_separate_event(db):
    _make(db, title="Reunión secundaria")
    _make(db, title="Consejo de profesores")
    assert len(db.execute(select(EventRecord)).scalars().all()) == 2


# ── queries ──────────────────────────────────────────────────────────────────

def test_list_for_day_orders_by_start_time_and_excludes_muted(db):
    _make(db, title="Late", start_time="15:00")
    _make(db, title="Early", start_time="08:00")
    _make(db, title="Hidden", start_time="09:00", relevance="muted")
    titles = [e.title for e in events.list_events_for_day(db, "2026-06-05")]
    assert titles == ["Early", "Late"]  # muted excluded, sorted by time


def test_list_upcoming_respects_horizon(db):
    _make(db, title="Tomorrow", date="2026-06-05")
    _make(db, title="Way later", date="2026-06-20")
    upcoming = events.list_upcoming_events(db, after_date="2026-06-04", horizon_days=2)
    assert [e.title for e in upcoming] == ["Tomorrow"]


# ── dismiss + feedback ───────────────────────────────────────────────────────

def test_dismiss_soft_deletes_and_logs_feedback(db):
    rec = _make(db)
    events.dismiss_event(db, rec.id)

    # leaves the day surface...
    assert events.list_events_for_day(db, "2026-06-05") == []
    # ...but stays findable
    found = events.get_event(db, rec.id)
    assert found is not None and found.dismissed_at is not None
    # ...and writes one 'noise' relevance signal for source="event"
    fb = db.execute(select(PriorityFeedbackRecord)).scalars().all()
    assert len(fb) == 1
    assert fb[0].source == "event" and fb[0].rating == "noise"
    assert fb[0].task_id == rec.id


def test_dismiss_missing_event_returns_none(db):
    assert events.dismiss_event(db, "nope") is None


def test_set_relevance_mutes_event(db):
    rec = _make(db)
    events.set_relevance(db, rec.id, "muted")
    assert events.list_events_for_day(db, "2026-06-05") == []
