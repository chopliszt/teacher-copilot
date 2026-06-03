#!/usr/bin/env python3
"""
Tests for Tier-A voice actions persisted server-side by POST /api/voice.

The voice endpoint transcribes audio, asks Mistral for an action, then applies
state-changing actions to the DB before returning. These tests stub the audio
+ Mistral layers (so no network/API key is needed) and assert the DB side
effects for:
  - complete_task  → deletes a teacher task
  - complete_task  → dismisses an action-required email (soft, via dismissed_at)
  - log_session    → upserts a class session note

UI-only actions (view_schedule_day, open_lesson_plan) have no server effect and
are covered by the frontend, so they're not exercised here.
"""

import json
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from main import app
from database import (
    Base,
    get_db,
    ClassSessionRecord,
    ImportantEmailRecord,
    UserTaskRecord,
)


@pytest.fixture()
def test_db():
    """Fresh in-memory SQLite shared across connections via StaticPool."""
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


class _VoiceStub:
    """Controller for the stubbed voice pipeline.

    Callable for backward-compat: ``stub({...})`` pins the action Mistral
    'returns'. Also exposes ``set_transcript`` and a ``calls`` log capturing
    every (transcript, history) the endpoint passed to call_voice_mistral —
    used to assert conversation memory.
    """

    def __init__(self):
        self.action = None
        self.transcript = "test transcript"
        self.calls = []

    def __call__(self, action):
        self.action = action

    def set_transcript(self, text):
        self.transcript = text


@pytest.fixture()
def stub_voice(monkeypatch):
    stub = _VoiceStub()

    async def fake_transcribe(audio_bytes, filename, language=None):
        return stub.transcript

    async def fake_tts(text):
        return None

    async def fake_voice_mistral(transcript, context, history=None):
        stub.calls.append({"transcript": transcript, "history": history})
        reply = "Done, profe."
        return {
            "response": reply,
            "action": stub.action,
            "raw_json": json.dumps({"response": reply, "action": stub.action}),
        }

    monkeypatch.setattr(main, "transcribe_audio", fake_transcribe)
    monkeypatch.setattr(main, "text_to_speech", fake_tts)
    monkeypatch.setattr(main, "call_voice_mistral", fake_voice_mistral)

    return stub


client = TestClient(app)
_DUMMY_AUDIO = {"audio": ("rec.webm", b"\x00\x01\x02", "audio/webm")}


class TestCompleteTask:
    def test_completes_user_task(self, test_db, stub_voice):
        """complete_task with a 'user_<id>' reference deletes the task row."""
        db = test_db()
        db.add(UserTaskRecord(
            id="abc123", title="Send Toddle report", priority="medium",
            due_date=None, created_at=datetime.now(timezone.utc).isoformat(),
        ))
        db.commit()
        db.close()

        stub_voice({"type": "complete_task", "id": "user_abc123"})
        resp = client.post("/api/voice", files=_DUMMY_AUDIO)
        assert resp.status_code == 200

        db = test_db()
        assert db.get(UserTaskRecord, "abc123") is None
        db.close()

    def test_completes_user_task_by_title_fallback(self, test_db, stub_voice):
        """A mismatched id still resolves via title substring match."""
        db = test_db()
        db.add(UserTaskRecord(
            id="xyz789", title="Grade 10A1 final projects", priority="high",
            due_date=None, created_at=datetime.now(timezone.utc).isoformat(),
        ))
        db.commit()
        db.close()

        # Wrong id, but a title hint that matches the stored task.
        stub_voice({"type": "complete_task", "id": "user_wrong", "title": "10A1 final"})
        resp = client.post("/api/voice", files=_DUMMY_AUDIO)
        assert resp.status_code == 200

        db = test_db()
        assert db.get(UserTaskRecord, "xyz789") is None
        db.close()

    def test_dismisses_email(self, test_db, stub_voice):
        """complete_task with an email id soft-dismisses it (sets dismissed_at)."""
        db = test_db()
        db.add(ImportantEmailRecord(
            id="email_1", subject="Cover request", sender="fabiola.jimenez@goldenvalley.ed.cr",
            snippet="Can you cover 6B1?", date=datetime.now(timezone.utc).isoformat(),
            category="action_required", dismissed_at=None,
        ))
        db.commit()
        db.close()

        stub_voice({"type": "complete_task", "id": "email_1"})
        resp = client.post("/api/voice", files=_DUMMY_AUDIO)
        assert resp.status_code == 200

        db = test_db()
        rec = db.get(ImportantEmailRecord, "email_1")
        assert rec is not None and rec.dismissed_at is not None
        db.close()


class TestDismissMarksGmailRead:
    """Dismissing an action email anywhere (voice, single, bulk) clears its
    UNREAD flag in Gmail so the teacher never handles the same email twice."""

    def _seed(self, db, *ids):
        for i in ids:
            db.add(ImportantEmailRecord(
                id=i, subject="Cover request", sender="fabiola.jimenez@goldenvalley.ed.cr",
                snippet="Can you cover 6B1?", date=datetime.now(timezone.utc).isoformat(),
                category="action_required", dismissed_at=None,
            ))
        db.commit()

    def test_voice_dismiss_marks_read(self, test_db, stub_voice, monkeypatch):
        marked = []
        monkeypatch.setattr(main, "_mark_gmail_read", lambda ids: marked.extend(ids))

        db = test_db(); self._seed(db, "email_1"); db.close()
        stub_voice({"type": "complete_task", "id": "email_1"})
        assert client.post("/api/voice", files=_DUMMY_AUDIO).status_code == 200
        assert marked == ["email_1"]

    def test_single_dismiss_endpoint_marks_read(self, test_db, monkeypatch):
        marked = []
        monkeypatch.setattr(main, "_mark_gmail_read", lambda ids: marked.extend(ids))

        db = test_db(); self._seed(db, "email_1"); db.close()
        assert client.delete("/api/important-emails/email_1").status_code == 200
        assert marked == ["email_1"]

    def test_bulk_dismiss_endpoint_marks_all_read(self, test_db, monkeypatch):
        marked = []
        monkeypatch.setattr(main, "_mark_gmail_read", lambda ids: marked.extend(ids))

        db = test_db(); self._seed(db, "email_1", "email_2"); db.close()
        assert client.delete("/api/important-emails").status_code == 200
        assert set(marked) == {"email_1", "email_2"}


class TestVoiceContextSessionLog:
    """_build_voice_context must make 'no session logged' EXPLICIT so the model
    says it has no record instead of hallucinating a lesson (the 7B/Figma bug)."""

    SCHEDULE = {"homeroom": {"group": "9A2"}, "classes": [
        {"day": 4, "periods": [{"group": "7B", "time": "11:30am"}, {"group": "6B2", "time": "10:10am"}]},
    ]}

    def test_unlogged_group_marked_no_record(self):
        ctx = main._build_voice_context(
            schedule_data=self.SCHEDULE,
            all_tasks=[],
            weekly_data=None,
            session_notes={},                 # nothing logged
            all_groups=["9A2", "7B", "6B2"],
        )
        assert "No session logged yet for:" in ctx
        assert "7B" in ctx
        assert "do NOT invent a lesson" in ctx

    def test_logged_group_shows_note_and_excludes_from_unlogged(self):
        ctx = main._build_voice_context(
            schedule_data=self.SCHEDULE,
            all_tasks=[],
            weekly_data=None,
            session_notes={"7B": {"notes": "Visited Microsoft HQ", "what_worked": ""}},
            all_groups=["9A2", "7B", "6B2"],
        )
        assert "Visited Microsoft HQ" in ctx
        # 7B is logged, so it must NOT appear in the "no session" list
        no_log_line = [ln for ln in ctx.splitlines() if ln.startswith("No session logged yet for:")]
        assert no_log_line and "7B" not in no_log_line[0]
        assert "6B2" in no_log_line[0]  # still unlogged


class TestLogSession:
    def test_logs_session(self, test_db, stub_voice):
        """log_session upserts a ClassSessionRecord for the group/today."""
        stub_voice({
            "type": "log_session",
            "group": "9A1",
            "notes": "Finished the logo project",
            "what_worked": "Pair work",
        })
        resp = client.post("/api/voice", files=_DUMMY_AUDIO)
        assert resp.status_code == 200

        today = date.today().isoformat()
        db = test_db()
        rows = db.query(ClassSessionRecord).filter(
            ClassSessionRecord.group == "9A1", ClassSessionRecord.date == today
        ).all()
        assert len(rows) == 1
        assert rows[0].notes == "Finished the logo project"
        assert rows[0].what_worked == "Pair work"
        db.close()

    def test_log_session_ignored_without_notes(self, test_db, stub_voice):
        """Missing notes → no row written (nothing to record)."""
        stub_voice({"type": "log_session", "group": "9A1", "notes": ""})
        resp = client.post("/api/voice", files=_DUMMY_AUDIO)
        assert resp.status_code == 200

        db = test_db()
        assert db.query(ClassSessionRecord).count() == 0
        db.close()


class TestConversationMemory:
    """Short-term memory: recent voice turns are replayed as chat history."""

    def test_first_turn_has_no_history(self, test_db, stub_voice):
        stub_voice.set_transcript("what did I do with 7B")
        client.post("/api/voice", files=_DUMMY_AUDIO)
        assert stub_voice.calls[0]["history"] == []

    def test_prior_turn_replayed_as_history(self, test_db, stub_voice):
        """The second turn sees the first turn's transcript + reply as history."""
        stub_voice.set_transcript("what did I do with 7B")
        client.post("/api/voice", files=_DUMMY_AUDIO)   # turn 1 — persists a VoiceLogRecord

        stub_voice.set_transcript("we visited Microsoft headquarters")
        client.post("/api/voice", files=_DUMMY_AUDIO)   # turn 2

        history = stub_voice.calls[-1]["history"]
        roles = [m["role"] for m in history]
        contents = " ".join(m["content"] for m in history)
        assert roles == ["user", "assistant"]
        assert "what did I do with 7B" in contents   # user turn 1 carried forward
        assert "Done, profe." in contents            # assistant turn 1 carried forward

    def test_stale_turn_excluded_from_history(self, test_db, stub_voice):
        """A turn older than the memory window is not replayed."""
        from database import VoiceLogRecord

        old_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        db = test_db()
        db.add(VoiceLogRecord(
            id="old1", transcript="ancient question", created_at=old_ts,
            mistral_response=json.dumps({"response": "old reply"}), parsed_action=None,
        ))
        db.commit()
        db.close()

        stub_voice.set_transcript("fresh question")
        client.post("/api/voice", files=_DUMMY_AUDIO)
        assert stub_voice.calls[-1]["history"] == []
