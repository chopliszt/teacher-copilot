# Requirements — Calendar Event Inclusion (experimental)

> Branch: `feature/calendar-event-inclusion`
> Status: **experimental** — explore the smallest useful slice before committing to it.

## The problem

The app already shows the teacher's whole day in one place: today's classes and any
disruptions from the weekly newsletter. What it does **not** do is surface
*time-anchored commitments that are not classes* — a department meeting tomorrow at
12, an AI training, a director's call. These arrive (today) mostly as **emails**, and
the teacher has no single, trustworthy place that answers *"what does my day actually
look like, in order?"* including meetings.

The fear is clutter: a high school generates dozens of events, most irrelevant to this
teacher. A naive "show all events" view would bury the signal and raise anxiety.

## Core reframe (the decision that shapes everything)

This is **two problems, not one**:

1. **Triage** — *which* events deserve to be on screen. Solved upstream by the AI,
   reusing the same principle-first philosophy as email triage. Clutter is a filtering
   problem, not a layout problem.
2. **Display** — *where* a surviving event lives. A meeting is the same kind of object
   as a class (it has a start time and you must be somewhere), so it belongs **on the
   timeline with classes**, not in a separate calendar panel.

We keep the "one tab" promise. We do **not** build a calendar and we do **not** push
events out to Google Calendar — the teacher just wants the event to live in the app /
Marimba. (Reading *from* Google Calendar as an extra input source is still a candidate —
see below — but that's import, not export.)

## Scope — what's IN (experimental slice)

- **Event sources (multiple):**
  - **Triaged emails.** When triage classifies an email, it also extracts any event it
    describes (title, date, start/end time, location, who's expected).
  - **Manual / voice add.** The teacher can create an event by voice through Marimba
    ("I have a meeting tomorrow at noon") — a new voice action — or via a quick manual
    add. Reuses the existing voice pipeline + `add_task`-style action dispatch.
- **Relevance gate.** An event only surfaces if it matters to *this* teacher: she's
  personally expected, it reshapes her teaching day, it carries prep/action, or it's
  from a key sender (directors, Fabiola). Generic school-wide announcements stay quiet.
  (Manual/voice events are always relevant — the teacher created them.)
- **Display — today:** **Today + time-anchored** events interleave into `TodaySchedule`
  with classes, visually distinct (icon + amber accent + position), in correct time order.
- **Display — future: "Coming up"** (⏸ **pending approval — example first**). A quiet
  one-line heads-up for tomorrow+ events that graduates onto the timeline when its day
  arrives. Do **not** build until the teacher has seen a mockup and confirmed it's
  useful (see Open questions).
- **Progressive disclosure.** For same-day items, existence + time + one-line title are
  always visible (anxiety-safe). Details (location, attendees, source email) are one tap
  away.
- **Calm expanded card — two actions, both "talk about this".** The expanded event
  shows details plus exactly **two** entry points into a conversation, both loading the
  event as context: **(a) "Chat about this"** → the existing **drawer chat component**
  (text-first, low pressure for a quick glance); **(b) the 🦊 fox icon** → a **Marimba
  voice** conversation. No "Prep" (a stress-word that names an obligation on sight), no
  "Got it", no calendar button. The two are the same intent in two modes — not the
  four-option pile that felt anxious. Anything actionable — suggesting next steps,
  adding to calendar — happens *in the conversation, on demand*, never as pre-loaded
  pressure on the card. (Later, a conversation can surface a small **action popup** for
  a genuinely useful next step — rather than the card carrying task buttons up front.)
- **Dismiss = a relevance signal, not a delete.** A quiet `×` on the collapsed row
  (ADHD: no dead ends). The teacher rarely needs it *if triage works* — she'd tap it
  only when an event isn't relevant, was a "Coming up" she's already acknowledged, or
  the surface feels cluttered. So treat the tap as **negative feedback that trains the
  triage**, not a destructive action:
  - The event **stays findable** (Marimba can still answer "what was that meeting?"); it
    just leaves the surface (soft-dismiss, `dismissed_at` set).
  - Each dismissal writes a **relevance-feedback record** (reuse the existing
    `PriorityFeedbackRecord` / `priority_feedback` pattern) so we accrue labeled data
    for better prompts + evals later.

## Candidate source — Google Calendar read (under evaluation)

Reading **from** Google Calendar (so events arrive even when they never came as email)
is likely useful and worth pursuing — but as its own slice *after* the email + voice
path proves out, so we don't widen the experiment too fast. It activates the dormant
`connectors/calendar` stub and needs read OAuth scope. Same relevance gate applies.
Treated as **phase 2 of this feature**, not out of scope.

## Scope — what's OUT (on purpose, to keep the experiment small)

- ❌ A standalone calendar / month / agenda view.
- ❌ Two-way sync or RSVP handling (export to Google is one-way).
- ❌ Recurring-event logic.

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Build a calendar UI? | **No** | Events are timeline citizens; preserves "one tab". |
| Primary surface | **Existing `TodaySchedule` timeline** | Sequence is the highest-value view for ADHD. |
| Clutter control | **AI relevance gate (upstream)** | Filter at the source, not on screen. |
| Triage style | **Principle-first** (per `CLAUDE.md`) | Reason from intent, not brittle phrase-matching. |
| Future events | **"Coming up" heads-up that graduates** | Self-cleaning; only today's events sit in the timeline. |
| Visual encoding | **Icon + amber accent + position** | Never color alone (dyslexia / colorblind safe). |
| Expanded card actions | **Two: "Chat about this" (text drawer) + 🦊 (voice)** | Same intent, two modes — not the four-option pile that felt anxious. |
| Google Calendar (export/push) | **Dropped** | Teacher only wants the event in the app/Marimba; no send-to-Google flow. |
| Dismiss `×` | **Soft-dismiss + relevance feedback (not delete)** | Triage decides importance; the tap is a training signal, event stays findable. |
| Schedule appearance | **Independent, via event logic — not a manual Top-3 promotion** | Less friction; the schedule reflects reality automatically. Events may *also* appear in priorities/Top 3; the two surfaces coexist. |
| Calendar-invite emails | **First-class input — new *and* updates** | Recognize a calendar event by its nature (organizer/when/guests/Meet), not by "updated" wording (principle-first). New → create; "Changed/updated" → edit the existing event (dedup by `eid`), never duplicate. |
| Location vs. Meet link | **Physical/in-person place is primary; Meet link secondary** | Invites auto-attach a Meet link even for in-person meetings, and rarely state the room — so when the body *does* (e.g. "en la biblioteca"), that's the high-value signal. Surface it prominently; keep the Meet link but below it. |
| Google Calendar (read) | **Phase 2 source — under evaluation** | Catches events that never arrive as email; widen later. |
| Event sources (slice 1) | **Triaged emails + manual/voice** | Invites arrive as email; voice for everything else, no new integration. |
| "Coming up" surface | **Deferred — mockup first** | Show the teacher an example; build only if it proves useful. |
| New concept name | **"event" (new `EventRecord`)** | Avoid collision with existing `meetings` table. |

## Context — existing plumbing to reuse, not reinvent

- `prompts/email_triage.py` — Mistral Small, principle-first classifier. The event
  extractor should ride alongside it (same email already in hand).
- `prompts/weekly_schedule.py` — already extracts `meetings` from the pasted newsletter;
  `main.py:_meeting_to_task` (~line 447) turns *today's* ones into `meeting_*` tasks in
  the priority pool (~line 552). New email-sourced events should merge with this, not
  duplicate it.
- `database.py` — note: `MeetingRecord` / `meetings` table already exists but stores
  **recorded** (transcribed + summarized) meetings. The new calendar-event concept is
  distinct → introduce `EventRecord`.
- `TodaySchedule.tsx` — already renders today's classes + disruptions; the timeline is
  the insertion point.
- Key senders (from project memory): Fabiola Jiménez (substitute coordinator),
  directors carolina.marin@ and kimberly.fonseca@goldenvalley.ed.cr.

## Reference example — known-positive fixture

A real invite the teacher confirmed as relevant (Marimba's triage already flagged it; it
appeared in Top 3). Use as a **must-pass positive** in the evals.

```
From: Priscilla Noguera <rh@goldenvalley.ed.cr>   (HR)
Subject/Body: "This event has been updated — Changed: time"
Title:    Reunión secundaria
When:     Friday Jun 5, 2026 · 12:00pm – 12:45pm  (America/Costa_Rica)
Where:    "Nos vemos en la biblioteca"  (location is in prose, not a field)
Meet:     https://meet.google.com/ixh-zdnb-ifk
Guests:   Priscilla Noguera (organizer) … Camilo Infante … (+ ~12 others)
```

What it must exercise:
- **Recognize a Google Calendar invite email** and extract structured fields — works the
  same for a **brand-new invite** as for an update. Do **not** gate extraction on
  "updated/Changed" wording (principle-first, not keyword-matching).
- **New vs. update routing:** a new invite → create an event; "Changed: time" → edit the
  existing event (dedup by `eid`), reflect the new time, ideally a subtle "time changed"
  cue. Never create a duplicate.
- **Physical location wins.** Capture "en la biblioteca" as the **primary** location and
  surface it prominently; capture the Meet link but keep it secondary. (This invite is
  in person *despite* carrying a Meet link — the room is the valuable bit.)
- **Relevance:** Camilo is a named guest → `shown` (personally expected).
- **Horizon:** it's *tomorrow* (today = Thu Jun 4). Slice 1 → lives in priorities today,
  **graduates onto Friday's timeline at 12:00**. (When "Coming up" ships, it shows there
  today too.)

## Constraints inherited from the project

- **ADHD-first:** decisive surfaces, every actionable item has a one-tap done/dismiss,
  no stale accumulation, immediate visible feedback.
- **Quiet Premium design:** stone + amber, low opacity, icons not emoji, `text-xs/sm`.
- **Graceful degradation:** all Mistral calls gated behind `MISTRAL_API_KEY`; no key →
  no extraction, no crash.

## Open questions (flag before/while building)

1. **"Coming up" — decide after the mockup.** A visual example will be shown; the
   teacher decides whether it's useful before we build it, and how far ahead it should
   look (proposed: tomorrow only, or next 48h).
2. **Dedup across sources** — if the same meeting appears in the newsletter, an email,
   *and* (phase 2) Google Calendar, how do we merge into one event (which source wins on
   time/location)?
3. **Google Calendar read (phase 2)** — read-only scope, how often to poll, and whether
   the relevance gate or a calendar-selection filter does the de-cluttering.
4. ~~Dismiss affordance~~ — **resolved:** quiet `×` on the collapsed row; soft-dismiss
   (event stays findable) + writes a relevance-feedback record for future eval/training.
