"""
Email Processor — Pydantic models and batch triage logic.

Incoming JSON from n8n uses capitalised header keys (Subject, From, To).
Pydantic's Field(alias=...) maps them to clean Python names internally.

Triage is handled by prompts/email_triage.py — edit that file to tune
classification behaviour without touching this one.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from database import ImportantEmailRecord, AbsenceRecord
from prompts.email_triage import triage_batch


# ── Pydantic models ───────────────────────────────────────────────────────────

class EmailLabel(BaseModel):
    id:   str
    name: str


class EmailPayload(BaseModel):
    mimeType: str


class IncomingEmail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id:           str
    threadId:     str
    snippet:      str
    payload:      EmailPayload
    internalDate: str                              # Unix ms as string
    labels:       list[EmailLabel] = []
    subject:      str = Field(alias="Subject")
    sender:       str = Field(alias="From")
    recipient:    str = Field(alias="To", default="")


class EmailBatch(BaseModel):
    emails: list[IncomingEmail]


# ── Batch processor ───────────────────────────────────────────────────────────

async def process_batch(
    batch: EmailBatch,
    db: Session,
) -> dict[str, Any]:
    """
    Triage a batch of emails with one Mistral call, then persist results.

    Categories:
      action_required  → saved to important_emails
      absence          → saved to absences (student + group extracted by Mistral)
      weekly_schedule  → saved to important_emails (separate n8n flow reads the doc)
      ignore           → discarded

    Returns a summary dict suitable for the API response.
    """
    emails = batch.emails
    if not emails:
        return {"status": "success", "emails_processed": 0, "emails_saved": 0, "absences_saved": 0}

    # Build the payload for the triage prompt
    triage_input = [
        {"id": e.id, "subject": e.subject, "snippet": e.snippet}
        for e in emails
    ]
    results = await triage_batch(triage_input)

    # Index by id for fast lookup
    result_map: dict[str, dict] = {r["id"]: r for r in results}

    emails_saved  = 0
    absences_saved = 0

    for email in emails:
        result   = result_map.get(email.id, {})
        category = result.get("category", "ignore")

        date_str = datetime.fromtimestamp(
            int(email.internalDate) / 1000, tz=timezone.utc
        ).isoformat()

        if category in ("action_required", "weekly_schedule"):
            if not db.get(ImportantEmailRecord, email.id):
                db.add(ImportantEmailRecord(
                    id=email.id,
                    subject=email.subject,
                    sender=email.sender,
                    snippet=email.snippet,
                    date=date_str,
                    category=category,
                ))
                emails_saved += 1

        elif category == "absence":
            if not db.get(AbsenceRecord, email.id):
                db.add(AbsenceRecord(
                    id=email.id,
                    student_name=result.get("student_name", "Unknown"),
                    group_name=result.get("group", "Unknown"),
                    date=date_str,
                    raw_snippet=email.snippet,
                ))
                absences_saved += 1

        # "ignore" → do nothing

    db.commit()

    return {
        "status": "success",
        "emails_processed": len(emails),
        "emails_saved": emails_saved,
        "absences_saved": absences_saved,
    }
