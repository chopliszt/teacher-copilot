"""
Tests for email batch processor.

Uses sample_emails.json — four real-world-style emails (one per category):
  msg_weekly_001  → weekly_schedule
  msg_absence_001 → absence         (Maria Gomez, 6B1)
  msg_action_001  → action_required (Design Cat 1)
  msg_ignore_001  → ignore

Mistral is always mocked so these tests run without an API key.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, ImportantEmailRecord, AbsenceRecord
from email_processor import EmailBatch, process_batch

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_session():
    """In-memory SQLite session, torn down after each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_batch() -> EmailBatch:
    """Load the four-email fixture batch."""
    raw = json.loads((FIXTURES_DIR / "sample_emails.json").read_text())
    return EmailBatch(**raw)


def _mock_triage(results: list):
    """Return an async callable that returns `results`."""
    async def _inner(emails):
        return results
    return _inner


FULL_TRIAGE = [
    {"id": "msg_weekly_001",  "category": "weekly_schedule"},
    {"id": "msg_absence_001", "category": "absence",
     "student_name": "Maria Gomez", "group": "6B1"},
    {"id": "msg_action_001",  "category": "action_required"},
    {"id": "msg_ignore_001",  "category": "ignore"},
]


# ── Category routing ──────────────────────────────────────────────────────────

class TestCategoryRouting:

    def test_weekly_schedule_saved_to_important_emails(self, db_session, sample_batch, monkeypatch):
        monkeypatch.setattr("email_processor.triage_batch", _mock_triage(FULL_TRIAGE))
        asyncio.get_event_loop().run_until_complete(process_batch(sample_batch, db_session))

        rec = db_session.get(ImportantEmailRecord, "msg_weekly_001")
        assert rec is not None
        assert rec.category == "weekly_schedule"
        assert "Anuncios semanales" in rec.subject

    def test_absence_saved_to_absences_table(self, db_session, sample_batch, monkeypatch):
        monkeypatch.setattr("email_processor.triage_batch", _mock_triage(FULL_TRIAGE))
        asyncio.get_event_loop().run_until_complete(process_batch(sample_batch, db_session))

        rec = db_session.get(AbsenceRecord, "msg_absence_001")
        assert rec is not None
        assert rec.student_name == "Maria Gomez"
        assert rec.group_name == "6B1"
        assert "Gomez" in rec.raw_snippet  # real snippet preserved

    def test_action_required_saved_to_important_emails(self, db_session, sample_batch, monkeypatch):
        monkeypatch.setattr("email_processor.triage_batch", _mock_triage(FULL_TRIAGE))
        asyncio.get_event_loop().run_until_complete(process_batch(sample_batch, db_session))

        rec = db_session.get(ImportantEmailRecord, "msg_action_001")
        assert rec is not None
        assert rec.category == "action_required"
        assert "Design Cat" in rec.subject

    def test_ignored_email_not_persisted(self, db_session, sample_batch, monkeypatch):
        monkeypatch.setattr("email_processor.triage_batch", _mock_triage(FULL_TRIAGE))
        asyncio.get_event_loop().run_until_complete(process_batch(sample_batch, db_session))

        assert db_session.get(ImportantEmailRecord, "msg_ignore_001") is None
        assert db_session.get(AbsenceRecord, "msg_ignore_001") is None

    def test_summary_counts_are_correct(self, db_session, sample_batch, monkeypatch):
        monkeypatch.setattr("email_processor.triage_batch", _mock_triage(FULL_TRIAGE))
        result = asyncio.get_event_loop().run_until_complete(
            process_batch(sample_batch, db_session)
        )

        assert result["status"] == "success"
        assert result["emails_processed"] == 4
        assert result["emails_saved"] == 2    # weekly_schedule + action_required
        assert result["absences_saved"] == 1


# ── Idempotency ───────────────────────────────────────────────────────────────

class TestIdempotency:

    def test_posting_same_batch_twice_does_not_duplicate(self, db_session, sample_batch, monkeypatch):
        monkeypatch.setattr("email_processor.triage_batch", _mock_triage(FULL_TRIAGE))

        asyncio.get_event_loop().run_until_complete(process_batch(sample_batch, db_session))
        result2 = asyncio.get_event_loop().run_until_complete(
            process_batch(sample_batch, db_session)
        )

        # Second pass saves nothing new
        assert result2["emails_saved"] == 0
        assert result2["absences_saved"] == 0

        # Still only one record each in the DB
        from sqlalchemy import select
        important_count = db_session.execute(
            select(ImportantEmailRecord)
        ).scalars().all()
        absence_count = db_session.execute(
            select(AbsenceRecord)
        ).scalars().all()
        assert len(important_count) == 2
        assert len(absence_count) == 1


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_batch_returns_zero_counts(self, db_session):
        empty_batch = EmailBatch(emails=[])
        result = asyncio.get_event_loop().run_until_complete(
            process_batch(empty_batch, db_session)
        )
        assert result["emails_processed"] == 0
        assert result["emails_saved"] == 0
        assert result["absences_saved"] == 0

    def test_triage_failure_results_in_nothing_saved(self, db_session, sample_batch, monkeypatch):
        """If Mistral errors out (returns []), no records are written."""
        monkeypatch.setattr("email_processor.triage_batch", _mock_triage([]))
        result = asyncio.get_event_loop().run_until_complete(
            process_batch(sample_batch, db_session)
        )
        assert result["emails_saved"] == 0
        assert result["absences_saved"] == 0

    def test_absence_without_student_name_uses_unknown(self, db_session, sample_batch, monkeypatch):
        """Mistral may omit student_name for a malformed absence — default to 'Unknown'."""
        partial_triage = [
            {"id": "msg_absence_001", "category": "absence"},  # no student_name or group
        ]
        monkeypatch.setattr("email_processor.triage_batch", _mock_triage(partial_triage))
        asyncio.get_event_loop().run_until_complete(process_batch(sample_batch, db_session))

        rec = db_session.get(AbsenceRecord, "msg_absence_001")
        assert rec is not None
        assert rec.student_name == "Unknown"
        assert rec.group_name == "Unknown"
