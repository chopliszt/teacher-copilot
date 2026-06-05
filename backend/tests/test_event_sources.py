#!/usr/bin/env python3
"""
Group 2 — event sources: extracting events from triaged emails.

Stubs triage_batch (no Mistral/network) and asserts process_batch persists the
event via events.create_or_update_event: physical location primary + Meet link
secondary, eid-based update (not duplicate), the visibility gate (model value
wins; category bridge only as fallback), and no event → no row.

The voice add_event source is covered in test_voice_actions.py::TestAddEvent.
"""

import asyncio

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, EventRecord
import email_processor
from email_processor import EmailBatch, EmailPayload, IncomingEmail, process_batch


@pytest.fixture()
def db():
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


def _email(id="m1", subject="Reunión secundaria", body="Nos vemos en la biblioteca"):
    return IncomingEmail(
        id=id,
        threadId="t1",
        snippet="snip",
        payload=EmailPayload(mimeType="text/plain"),
        internalDate="1700000000000",
        subject=subject,
        sender="Priscilla Noguera <rh@goldenvalley.ed.cr>",
        recipient="camilo.infante@goldenvalley.ed.cr",
        body=body,
    )


def _patch_triage(monkeypatch, results):
    async def fake_triage(_payload):
        return results
    monkeypatch.setattr(email_processor, "triage_batch", fake_triage)


def test_email_event_extracted_with_location_primary(db, monkeypatch):
    _patch_triage(monkeypatch, [{
        "id": "m1",
        "category": "action_required",
        "event": {
            "title": "Reunión secundaria",
            "date": "2026-06-05",
            "start_time": "12:00",
            "end_time": "12:45",
            "location": "biblioteca",
            "meet_link": "https://meet.google.com/ixh-zdnb-ifk",
            "attendees": ["Camilo Infante", "Priscilla Noguera"],
            "eid": "EID999",
        },
    }])
    res = asyncio.run(process_batch(EmailBatch(emails=[_email()]), db))

    assert res["events_saved"] == 1
    event = db.execute(select(EventRecord)).scalars().one()
    assert event.title == "Reunión secundaria"
    assert event.location == "biblioteca"           # physical place — primary
    assert event.meet_link.endswith("ixh-zdnb-ifk")  # video link — secondary, separate
    assert event.eid == "EID999"
    assert event.source == "email" and event.source_ref == "m1"
    # no model visibility here → category bridge: action_required → shown
    assert event.visibility == "shown"


def test_email_update_edits_same_event_by_eid(db, monkeypatch):
    """A second invite with the same eid (changed time) edits the row, not dupes."""
    _patch_triage(monkeypatch, [{
        "id": "m1", "category": "action_required",
        "event": {"title": "Reunión secundaria", "date": "2026-06-05",
                  "start_time": "12:00", "eid": "EID999"},
    }])
    asyncio.run(process_batch(EmailBatch(emails=[_email(id="m1")]), db))

    _patch_triage(monkeypatch, [{
        "id": "m2", "category": "action_required",
        "event": {"title": "Reunión secundaria", "date": "2026-06-05",
                  "start_time": "13:00", "eid": "EID999"},  # changed time, same eid
    }])
    asyncio.run(process_batch(EmailBatch(emails=[_email(id="m2")]), db))

    rows = db.execute(select(EventRecord)).scalars().all()
    assert len(rows) == 1
    assert rows[0].start_time == "13:00"
    assert rows[0].updated_at is not None


def test_event_in_ignored_email_falls_back_to_hidden(db, monkeypatch):
    """No model visibility + ignore category → category bridge hides it."""
    _patch_triage(monkeypatch, [{
        "id": "m1", "category": "ignore",
        "event": {"title": "Whole-school assembly", "date": "2026-06-10",
                  "start_time": "09:00"},
    }])
    asyncio.run(process_batch(EmailBatch(emails=[_email(subject="Assembly")]), db))

    event = db.execute(select(EventRecord)).scalars().one()
    assert event.visibility == "hidden"


def test_model_visibility_shown_overrides_ignore_category(db, monkeypatch):
    """The relevance gate wins: a guest invite in an 'ignore' email still shows."""
    _patch_triage(monkeypatch, [{
        "id": "m1", "category": "ignore",  # email expects no reply
        "event": {"title": "Reunión secundaria", "date": "2026-06-05",
                  "start_time": "12:00", "visibility": "shown"},  # but she's a guest
    }])
    asyncio.run(process_batch(EmailBatch(emails=[_email()]), db))

    event = db.execute(select(EventRecord)).scalars().one()
    assert event.visibility == "shown"


def test_model_visibility_hidden_overrides_action_category(db, monkeypatch):
    """And the reverse: a school-wide event in an action email can be hidden."""
    _patch_triage(monkeypatch, [{
        "id": "m1", "category": "action_required",
        "event": {"title": "All-staff assembly", "date": "2026-06-09",
                  "start_time": "09:00", "visibility": "hidden"},
    }])
    asyncio.run(process_batch(EmailBatch(emails=[_email()]), db))

    event = db.execute(select(EventRecord)).scalars().one()
    assert event.visibility == "hidden"


def test_no_event_means_no_row(db, monkeypatch):
    _patch_triage(monkeypatch, [{"id": "m1", "category": "action_required"}])
    res = asyncio.run(process_batch(EmailBatch(emails=[_email()]), db))
    assert res["events_saved"] == 0
    assert db.execute(select(EventRecord)).scalars().all() == []
