"""
Database — SQLAlchemy setup for TeacherPilot.

Uses Supabase (PostgreSQL) when DATABASE_URL is set in the environment,
otherwise falls back to local SQLite (used by tests and offline dev).
"""

import os
from pathlib import Path

from sqlalchemy import Boolean, Column, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_sqlite_url = f"sqlite:///{Path(__file__).parent / 'data' / 'teacher_pilot.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", _sqlite_url)

# Supabase requires SSL; add it automatically if the caller forgot
if DATABASE_URL.startswith("postgresql") and "sslmode" not in DATABASE_URL:
    DATABASE_URL += "?sslmode=require"

if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(DATABASE_URL)
else:
    # check_same_thread is SQLite-only
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class ImportantEmailRecord(Base):
    """
    Emails that require action from the teacher.
    category: "action_required" | "weekly_schedule"

    body / thread_id / rfc822_message_id power the "chat to solve" feature:
    the chat needs the full body to draft a meaningful reply, and the two
    threading fields let us send Re: replies that land inside the original
    Gmail conversation rather than as disconnected new emails.

    Older rows (ingested before these columns existed) leave them NULL;
    they are lazy-backfilled the first time the user opens the chat for
    that email, by hitting Gmail with the stored message id.
    """

    __tablename__ = "important_emails"

    id = Column(String, primary_key=True, index=True)
    subject = Column(String, nullable=False)
    sender = Column(String, nullable=False)
    snippet = Column(Text, nullable=False)
    date = Column(String, nullable=False)  # ISO-8601 UTC string
    category = Column(String, nullable=False, default="action_required")
    body = Column(Text, nullable=True)
    thread_id = Column(String, nullable=True)
    rfc822_message_id = Column(String, nullable=True)


class AbsenceRecord(Base):
    """
    Student absence notifications extracted from forwarded emails.
    Used to flag missing students in the class briefing chips.
    """

    __tablename__ = "absences"

    id = Column(String, primary_key=True)  # source email id
    student_name = Column(String, nullable=False)
    group_name = Column(String, nullable=False)  # e.g. "6B1"
    date = Column(String, nullable=False)  # ISO-8601 UTC string
    raw_snippet = Column(Text, nullable=False)  # original text for reference


class WeeklyScheduleRecord(Base):
    """
    Extracted weekly schedule data from the "Anuncios Semanales" Google Doc.
    Only one row ever exists (id="current") — overwritten each week.

    data: JSON blob — {week_label, meetings, class_disruptions, action_items,
                        upcoming_dates, absences}
    """

    __tablename__ = "weekly_schedule"

    id = Column(String, primary_key=True, default="current")
    week_label = Column(String, nullable=False, default="")
    data = Column(Text, nullable=False)  # full JSON from Mistral extraction
    created_at = Column(String, nullable=False)  # ISO date when last updated


class UserTaskRecord(Base):
    """
    Tasks added manually by the teacher (text or voice).
    These join the Mistral priority pool and compete with emails and newsletter items.
    """

    __tablename__ = "user_tasks"

    id = Column(String, primary_key=True)  # UUID
    title = Column(String, nullable=False)
    priority = Column(String, nullable=False, default="medium")  # high/medium/low
    due_date = Column(String, nullable=True)  # YYYY-MM-DD, optional
    created_at = Column(String, nullable=False)


class ClassSessionRecord(Base):
    """
    Session log written by the teacher after each class.

    id format: "{group}_{YYYY-MM-DD}_{schedule_day}" — upserted on save.
    what_worked is nullable; Phase 5 will query WHERE what_worked IS NOT NULL
    to build cross-group suggestions.
    """

    __tablename__ = "class_sessions"

    id = Column(String, primary_key=True)
    group = Column(String, nullable=False, index=True)
    schedule_day = Column(Integer, nullable=False)
    date = Column(String, nullable=False)  # YYYY-MM-DD
    notes = Column(Text, nullable=False)  # how the class went
    what_worked = Column(Text, nullable=True)  # optional — feeds Phase 5
    created_at = Column(String, nullable=False)


class VoiceLogRecord(Base):
    """
    Logs of teacher voice interactions to analyze accuracy and improve the prompt/evals.
    """

    __tablename__ = "voice_logs"

    id = Column(String, primary_key=True)  # UUID
    transcript = Column(Text, nullable=False)  # what the teacher said
    mistral_response = Column(Text, nullable=False)  # raw json text mistral gave back
    parsed_action = Column(
        Text, nullable=True
    )  # the extracted action type (e.g., "open_class"), or null
    created_at = Column(String, nullable=False)  # ISO UTC timestamp


class MeetingRecord(Base):
    """
    A recorded school meeting: stores the transcription, AI-generated summary,
    action items, and optional email send status.
    """

    __tablename__ = "meetings"

    id = Column(String, primary_key=True)  # UUID
    created_at = Column(String, nullable=False)  # ISO-8601 UTC
    transcription = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    action_items = Column(Text, nullable=False)  # JSON-encoded list[str]
    suggested_subject = Column(String, nullable=True)
    email_body = Column(Text, nullable=True)
    email_sent = Column(Boolean, default=False, nullable=False)
    recipient = Column(String, nullable=True)


class PriorityFeedbackRecord(Base):
    """
    Each time a priority item is surfaced in the Top 3, its outcome is recorded here.
    rating: "relevant" (marked done) | "noise" (dismissed as not relevant)

    This table is the raw dataset for future few-shot prompt injection and,
    when large enough, for LoRA / RLHF fine-tuning of a small classifier.
    context_json stores the full task dict so all features are available later.
    """

    __tablename__ = "priority_feedback"

    id = Column(String, primary_key=True)          # UUID
    task_id = Column(String, nullable=False)        # e.g. "user_abc", "email_xyz"
    task_title = Column(Text, nullable=False)
    source = Column(String, nullable=False)         # user_task/email/meeting/action_item
    priority_level = Column(String, nullable=False) # high/medium/low
    rating = Column(String, nullable=False)         # "relevant" | "noise"
    context_json = Column(Text, nullable=False)     # full task JSON for ML
    created_at = Column(String, nullable=False)     # ISO-8601 UTC


class EmailRecipientRecord(Base):
    """
    Tracks email addresses used in meeting email sends.
    Ordered by use_count desc to power autocomplete in the compose form.
    """

    __tablename__ = "email_recipients"

    email = Column(String, primary_key=True)
    label = Column(String, nullable=True)   # optional friendly name (e.g. "Sec. Dept.")
    use_count = Column(Integer, nullable=False, default=1)
    last_used_at = Column(String, nullable=False)  # ISO-8601 UTC


def init_db() -> None:
    """Create all tables. Safe to call on every startup (no-op if they exist)."""
    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """
    Lightweight migration — adds nullable columns that were introduced after
    the table was first created. SQLAlchemy's create_all does NOT modify
    existing tables, so without this any new Column on an existing table is
    silently invisible to the ORM.

    For each (table, column, ddl) tuple below, we issue an ALTER TABLE that
    is idempotent: ADD COLUMN IF NOT EXISTS on Postgres, and a try/except
    for SQLite (which lacks IF NOT EXISTS for columns until 3.35+).
    """
    from sqlalchemy import inspect, text

    additions = [
        ("important_emails", "body",              "TEXT"),
        ("important_emails", "thread_id",         "TEXT"),
        ("important_emails", "rfc822_message_id", "TEXT"),
    ]

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, col, ddl in additions:
            if table not in inspector.get_table_names():
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            if col in existing:
                continue
            try:
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {ddl}'))
            except Exception as e:
                print(f"[DB] Could not add {table}.{col}: {e}")


def get_db():
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
