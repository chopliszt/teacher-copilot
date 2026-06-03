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

from database import ImportantEmailRecord, AbsenceRecord, EmailRecipientRecord
from prompts.email_triage import triage_batch


def _extract_email_address(raw: str) -> str:
    """Pull 'x@y.com' out of headers like 'Display Name <x@y.com>' or 'x@y.com'."""
    import re
    m = re.search(r"<([^>]+)>", raw)
    return (m.group(1) if m else raw).strip()


# ── Pydantic models ───────────────────────────────────────────────────────────

class EmailLabel(BaseModel):
    id:   str
    name: str


class EmailPayload(BaseModel):
    mimeType: str


class IncomingEmail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id:                 str
    threadId:           str
    snippet:            str
    payload:            EmailPayload
    internalDate:       str                              # Unix ms as string
    labels:             list[EmailLabel] = []
    subject:            str = Field(alias="Subject")
    sender:             str = Field(alias="From")
    recipient:          str = Field(alias="To", default="")
    # Raw Cc header value, e.g. "Alice <a@x.com>, Bob <b@y.com>". Empty
    # string when the original email had no CC. Parsed into individual
    # addresses at API response time so the composer can render chips.
    cc:                 str = Field(alias="Cc", default="")
    body:               str = ""
    rfc822_message_id:  str = ""


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

    # Build the payload for the triage prompt — include body so direct
    # mentions buried in thread replies are visible (snippets often miss them).
    triage_input = [
        {
            "id": e.id,
            "subject": e.subject,
            "snippet": e.snippet,
            "body": e.body or "",
            # From/To/Cc let the model gate on "addressed to me" vs broadcast/
            # Cc-only — without these the key-sender and CC rules ran blind.
            "sender": e.sender,
            "to": e.recipient,
            "cc": e.cc or "",
        }
        for e in emails
    ]
    results = await triage_batch(triage_input)

    # Index by id for fast lookup
    result_map: dict[str, dict] = {r["id"]: r for r in results}

    emails_saved  = 0
    absences_saved = 0
    # Gmail message ids of absence emails in this batch. They're pure FYI and
    # already captured in the app, so the caller marks them read in Gmail to
    # keep the teacher's unread count honest (see _run_gmail_sync).
    absence_ids: list[str] = []
    seeded_recipients: set[str] = set()  # deduplicate within this batch

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
                    body=email.body or None,
                    thread_id=email.threadId or None,
                    rfc822_message_id=email.rfc822_message_id or None,
                    cc=email.cc or None,
                ))
                emails_saved += 1

                # Seed the autocomplete addressbook with this sender so when the
                # teacher wants to reply or forward, the address surfaces in
                # the composer's recipient dropdown.
                sender_addr = _extract_email_address(email.sender)
                if sender_addr and "@" in sender_addr and sender_addr not in seeded_recipients:
                    seeded_recipients.add(sender_addr)
                    existing_recipient = db.get(EmailRecipientRecord, sender_addr)
                    if not existing_recipient:
                        db.add(EmailRecipientRecord(
                            email=sender_addr,
                            use_count=0,                  # inbox-only signal
                            last_used_at=date_str,
                        ))

        elif category == "absence":
            # Mark read in Gmail regardless of whether it's new to the DB —
            # it's freshly fetched and needs no action either way.
            absence_ids.append(email.id)
            if not db.get(AbsenceRecord, email.id):
                db.add(AbsenceRecord(
                    id=email.id,
                    student_name=result.get("student_name") or "Unknown",
                    group_name=result.get("group") or "Unknown",
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
        "absence_ids": absence_ids,
    }
