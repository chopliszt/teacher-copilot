# Plan — Calendar Event Inclusion (experimental)

Numbered task groups. Each group is a small, reviewable unit. Build top to bottom;
the timeline (group 4) is the payoff slice — stop and demo there before going further.

> Legend: ⏸ = paused pending teacher approval · 🔭 = phase 2 (after slice 1 proves out).

## 1. Data model — the `event` concept

1.1. Add `EventRecord` to `database.py` (distinct from `MeetingRecord`, which stores
     *recorded* meetings). Fields: `id`, `title`, `date`, `start_time`, `end_time?`,
     `location?` (physical/in-person place — primary), `meet_link?` (video URL —
     secondary), `attendees?`, `source` (`email`/`voice`/`weekly`/`gcal`), `source_ref?`
     (e.g. email id), `eid?` (calendar event id — dedup/update key), `relevance`
     (`surfaced`/`muted`), `prep_note?`, `dismissed_at?`, `created_at`.
1.2. CRUD helpers: create, list-for-day, list-upcoming, soft-dismiss (`dismissed_at`),
     set-relevance. Dismissed events stay findable (queryable by Marimba), just hidden
     from the surface.
1.3. Decide dedup key (date + start_time + fuzzy title) so the same event from two
     sources collapses into one row.
1.4. Relevance feedback: reuse the existing `PriorityFeedbackRecord` / `priority_feedback`
     pattern (extend `source` to include `event`) so a dismissal logs a negative signal —
     labeled data for tuning the triage prompt + evals later.

## 2. Event sources

2.1. **Email extraction.** Extend the triage step (`prompts/email_triage.py` /
     `email_processor.py`) so that, for each email, the model *also* returns any event it
     describes (title, date, time, location, Meet link, who's expected). Principle-first
     prompt — describe what an event *is*, don't pattern-match phrases. Persist as
     `EventRecord`. Specifics this must cover:
     - **New *and* updated invites** alike — never gate extraction on "updated/Changed"
       wording. That wording only routes create-vs-edit (see 1.3/1.4 dedup by `eid`).
     - **Location resolution:** prefer a **physical/in-person place** found anywhere
       (incl. prose like "en la biblioteca") as the primary location; store the Meet link
       separately and secondary. Don't let an auto-attached Meet link mask the real room.
2.2. **Manual / voice add.** Add an `add_event` voice action in `prompts/voice.py`
     (mirror `add_task`): Marimba parses "I have a meeting tomorrow at noon" → structured
     event; backend saves it immediately (like `add_task` today). Add a minimal manual
     add path for parity.
2.3. **Reconcile with weekly-schedule meetings.** Today's `weekly_data["meetings"]`
     (`main.py:_meeting_to_task`) should flow through the same `EventRecord` path / dedup
     instead of staying a parallel concept.

## 3. Relevance gate (clutter control, upstream)

3.1. Define the gate as a principle: an event surfaces if the teacher is personally
     expected, it reshapes her teaching day, it carries prep/action, or it's from a key
     sender (directors, Fabiola). Otherwise `relevance = muted`.
3.2. Apply automatically to email- and gcal-sourced events; manual/voice events are
     always `surfaced` (she created them).
3.3. Build a tiny eval set (relevant vs. noise pairs, same-sender contrasts) and tune
     the prompt against it — let evals, not vibes, decide.

## 4. Display — today's timeline (the payoff)

4.1. Backend: expose today's `surfaced` events through the data the schedule view reads
     (alongside classes + disruptions), time-ordered.
4.2. `TodaySchedule.tsx`: interleave events with classes in one time-ordered list.
4.3. Visual encoding per DESIGN.md: distinct **icon + amber hairline + position** — never
     color alone (dyslexia / colorblind safe). Quiet, not a loud block.
4.4. Progressive disclosure: row shows time + one-line title always; tap expands
     location / attendees / source.
4.5. Calm expanded card — **two actions, both "talk about this"**, each loading the event
     as context: (a) **"Chat about this"** → existing **drawer chat component** (text);
     (b) the **🦊 fox icon** → **Marimba voice**. No "Prep", no "Got it", no calendar
     button. (Future: a conversation can surface a small action popup — out of this slice.)
4.6. Dismiss = relevance signal: a quiet `×` on the collapsed row → soft-dismiss (row
     disappears immediately, event stays findable) **and** write a feedback record
     (group 1.4). No labeled dismiss button in the expanded view.
4.7. Calendar export is conversational: an `add_to_calendar` flow where Marimba
     **confirms date / time / concept before sending** (builds on connectors/gmail-style
     send + the existing voice action dispatch). Not a button on the card.

## 5. ⏸ "Coming up" heads-up (DO NOT BUILD YET)

5.1. First: produce a static mockup of the "Coming up" line and get teacher sign-off on
     usefulness + look-ahead horizon (tomorrow vs. 48h). **Gate the rest of group 5 on
     that approval.**
5.2. (after approval) Backend: list upcoming `surfaced` events within the chosen horizon.
5.3. (after approval) Frontend: render the quiet one-line heads-up; it graduates onto the
     timeline when its day arrives; one-tap dismiss.

## 6. 🔭 Google Calendar read (phase 2 — after slice 1 proves out)

6.1. Activate the dormant `connectors/calendar` stub with **read-only** OAuth scope.
6.2. Pull upcoming events → same `EventRecord` path + dedup + relevance gate.
6.3. Decide poll cadence and a calendar-selection filter to pre-trim noise.

## 7. Tests & evals

7.1. Backend unit tests: `EventRecord` CRUD, dedup collapse, today/upcoming queries.
7.2. Triage extraction test: emails that contain an event vs. those that don't.
7.3. Relevance-gate eval set (group 3.3) passes with margin.
7.4. Voice `add_event` action test (mock Mistral) — saved correctly.
7.5. Frontend: timeline renders interleaved class + event in correct order; dismiss
     removes the row.
7.6. **Conversation-grounding check** — from both entry points (drawer + 🦊), assert the
     event's real fields reach Marimba's context, and a grounded-reply check set passes
     (truthful recall, honest about gaps, no invented fields, no cross-event bleed).
     Rigor (formal eval vs. manual acceptance script) — confirm with teacher.

## 8. Quality & close

8.1. `cd backend && pytest tests/ -v` green; `cd frontend && npm run type-check && npm run lint` clean.
8.2. Graceful degradation: no `MISTRAL_API_KEY` → no extraction, no crash.
8.3. No secrets / personal data added to the tree; `.env` stays ignored.
8.4. Update `BACKLOG.md` / project memory; suggest a PM-framed commit message (no
     auto-commit, per workflow preference).
