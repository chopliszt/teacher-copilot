# Validation — Calendar Event Inclusion (experimental)

How we know the slice works and can be merged. Because this is experimental, "merge"
means **slice 1 (groups 1–4 + 7–8)** is solid; group 5 ("Coming up") and group 6
(Google Calendar read) are explicitly *not* required for merge.

## 1. Events are captured from both sources

- [ ] An email describing a meeting (date/time/location) produces one `EventRecord`
      with the right fields.
- [ ] A **brand-new** Google Calendar invite (no "updated/Changed" wording) is extracted
      just as well as an update — extraction is **not** gated on those words.
- [ ] An **update** ("Changed: time") **edits the existing** event (dedup by `eid`) and
      reflects the new time — it does **not** create a duplicate.
- [ ] When an invite has **both** a physical place and a Meet link, the physical place
      (e.g. "biblioteca") is captured as **primary** and shown prominently; the Meet link
      is stored but secondary.
- [ ] An email with **no** event produces none (no false events).
- [ ] Saying to Marimba "I have a meeting tomorrow at noon" creates a correct
      `EventRecord` via the `add_event` voice action, saved immediately.
- [ ] The same meeting arriving from two sources collapses into **one** row (dedup).

## 2. The *right* events reach the schedule (correctness, not just count)

The core of the feature: the gate must let the meaningful ones through and hold the
noise back. Validate against concrete scenarios, end-to-end (extraction → gate →
actually appears, or not, on the timeline):

- [ ] **Director's direct invite** (carolina.marin@ / kimberly.fonseca@) for today →
      `shown` **and visibly on today's timeline**.
- [ ] **Fabiola cover/substitute request** → `shown` (treated as urgent).
- [ ] **Reshapes her teaching day** (room change, schedule shift, a meeting in a class
      slot) → `shown`.
- [ ] **School-wide announcement not naming her** (assembly, "the musical is Friday") →
      `hidden`, never on the timeline.
- [ ] **CC-only / FYI thread** where she isn't expected to act → `hidden`.
- [ ] Manual/voice events are always `shown`.
- [ ] No **false events** (an email with no real event yields none) and no **dropped**
      true events (a clear invite is never silently lost).
- [ ] The relevance eval set passes **with margin** (principle-first, not overfit to
      literal phrases — per `CLAUDE.md`).

## 3. Today's timeline shows events correctly

- [ ] Today's `shown` events appear **interleaved with classes in time order** in
      `TodaySchedule` (a meeting between two classes sits between them).
- [ ] Events are visually distinguishable by **icon + amber accent + position**, not by
      color alone (readable in grayscale).
- [ ] Tapping a row reveals details (location / attendees / source); collapsed row still
      shows time + one-line title.
- [ ] The expanded card has **exactly two actions**, both working and both loading the
      event as context: **"Chat about this"** → drawer chat (text), and the **🦊 fox** →
      Marimba voice. No "Prep" / "Got it" / calendar button.
- [ ] The quiet `×` soft-dismisses (row disappears immediately) **and** writes a
      relevance-feedback record; the dismissed event is **still findable** (Marimba can
      answer "what was that meeting?"). No hard delete, no dead end.

## 4. Conversation about an event is grounded and useful (not hallucinated)

Opening a conversation from an event must mean Marimba *actually holds that event* and
answers truthfully. Test from **both** entry points — "Chat about this" (drawer) and the
🦊 voice widget — since the flow is: it opens → the teacher asks her question → she
replies.

- [ ] **Context is really passed.** When opened from an event, Marimba's context
      contains that event's real fields (title, date, time, location, attendees, source).
- [ ] **Truthful recall.** Asked "what is this?" she restates the **actual** details —
      no invented time, location, or attendees.
- [ ] **Honest about gaps.** If a field is unknown (e.g. no location), she says so
      rather than fabricating one.
- [ ] **Useful, grounded action.** Asked for help, she suggests a relevant next step
      drawn from the real event (reply to the sender, add to calendar *with* the confirm
      step, jot a prep note) — not generic boilerplate, not invented facts.
- [ ] **No cross-event bleed.** She talks about *this* event, not a different meeting.
- [ ] A **formal automated grounded-reply eval** passes and **gates merge** — coded like
      the triage evals: asserts the event's fields are present in Marimba's context, the
      reply contains the real facts, and it omits forbidden hallucinations (invented
      time/location/attendees). Scenarios cover truthful recall, honest-about-gaps, and
      no cross-event bleed.

## 5. Graceful degradation & safety

- [ ] No `MISTRAL_API_KEY` → no extraction runs, app still loads, no crash.
- [ ] No secrets or personal data added to the versioned tree; `.env` stays ignored.

## 6. Tests & checks pass

- [ ] `cd backend && pytest tests/ -v` green (incl. new event/dedup/voice tests).
- [ ] `cd frontend && npm run type-check` and `npm run lint` clean.

## Definition of "ready for merge" (slice 1)

Sections 1–6 ✅, tree clean of secrets, existing tests still pass. **Not required:**
"Coming up" (group 5) and Google Calendar read (group 6) — both are follow-on slices.

## Cognitive-load check (qualitative — the real point)

- [ ] **ADHD:** the timeline answers "what's my day, in order?" at a glance; every event
      has a one-tap done/dismiss; nothing stale accumulates.
- [ ] **Anxiety:** for same-day items nothing relevant is hidden behind a click — the
      existence + time + title are always visible; only detail is tucked away.
- [ ] **Dyslexia:** short labels, left-aligned, redundant cues (icon + position + color),
      no wall of text.
- [ ] **"One tab" preserved:** the teacher never has to leave the app to know about a
      meeting; Google Calendar is a backup alarm, not the source of truth.

## "Coming up" (group 5) — ✅ approved + built

- [x] Teacher saw the mockup and chose to build it, horizon = **next 2 days**.
- [ ] Shows shown, not-dismissed events for the next 2 days; absent (no empty state) when
      nothing's upcoming; tap expands the event card; `×` dismisses.
- Known limitation: future *weekly-newsletter* meetings aren't included yet (they only map
  to today) — a later follow-up.
