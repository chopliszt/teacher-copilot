# Teacher Pilot — Feature Backlog

Ranked by urgency and ADHD value. Work top to bottom. Don't start item N+1 until N is shipped and stable.

---

## 🟡 Next features (in order)

### 1. Email reply tracking — automatic "you never heard back"
**What:** If you sent an email and got no reply after 7 days, it surfaces in Top 3 as "Waiting on reply from X — sent 5 days ago." Fully automatic, no manual logging.
**How it works:**
- New Gmail connector function queries `in:sent newer_than:7d`.
- For each sent thread: check if the last message is from you and older than the threshold.
- Mistral Small makes a quick pass: "does this sent email expect a reply?" (filters out purely informational sends).
- Flagged threads saved to `pending_replies` table → enter the priority pool automatically.
**New table:** `pending_replies` (thread_id, recipient, subject, sent_at, resolved)
**Effort:** ~5 hours

### 2. Meeting scheduling via voice — "schedule a meeting with Fabiola tomorrow at 10"
**What:** Marimba creates a Google Calendar event after a verbal confirmation step ("I'll book: Fabiola, tomorrow 10am. Say confirm to save.") — required to prevent hallucinated events.
**How it works:**
- `connectors/gcalendar.py` already has `create_event()` — just needs an endpoint + voice action.
- New voice action `schedule_meeting {person, date_str, time_str, location}`.
- Contacts resolved via a `contacts` table: name, aliases (["Fabiola", "Fabi"]), email.
- **Auto-populate contacts:** on sync, pull top 50 recipients from Gmail sent history into the contacts table. No manual entry needed for regular collaborators. You can add aliases for anyone new.
**Effort:** ~5 hours (including contacts auto-import)

---

## 🟢 When you have data (no rush)

### 3. Plan-to-outcome learning loop
**What:** After a class, compare `class_sessions.notes` (what actually happened) against the `lesson_plans.plan_text` (what was proposed). Tag each plan with `feedback`: `used_as_is | used_modified | discarded` automatically based on semantic similarity (cheap Mistral Small call). Use as training signal for future proposals.
**Why:** Closes the loop between planning and reality. Same pattern as priority_feedback but for lesson plans. Lets the next proposal say "the last 3 times you used hands-on activities for 8A1 they worked, want to do that again?".
**Effort:** ~3 hours
**Status:** Schema is ready (`feedback` column exists on `lesson_plans`). Just needs a passive background job + the comparison prompt.

### 4. ML priority personalization
**Status:** Already collecting data silently. Three signals now:
- "Mark done" → `rating: relevant` (positive training signal)
- "doesn't apply this week" → `rating: skip` (neutral — clears at next weekly upload, kept separate from training data)
- "not relevant for me" → `rating: noise` (strong negative training signal)

**Activation path:**
- ~20 noise examples → inject as few-shot negatives in Mistral prompt. Instant improvement.
- ~100 examples → fine-tune small classifier (export via `GET /api/priority-feedback/export` → JSONL for LoRA/Mistral fine-tune API).
- The `context_json` field stores all features needed: title, source, priority level, class, subject, estimated time.

**Note:** Don't add more feedback UI. The three current signals are enough — this is an enhancement, not a fix.

### 5. Session history view per class
**What:** Inside the class briefing panel, an expandable "view past sessions" list for that group.
**Status:** All data is in DB. Needs `GET /api/class/{group}/sessions` endpoint + small UI component in `TodaySchedule.tsx`.
**Effort:** ~1 hour

### 6. Toddle API push
**What:** Once a `lesson` plan + `assignment` description are agreed in the drawer, a single "Push to Toddle" button creates the lesson + assignment records in Toddle directly — no copy-paste.
**How it works:** Investigate Toddle API (auth + endpoints). Likely needs OAuth or API key. Map lesson_plans + assignment block → Toddle's data model.
**Why now-ish:** This is the killer integration. Cuts the last manual step out of the planning loop.
**Effort:** ~4 hours (depending on Toddle's API quality)

### 7. Per-group student rosters + Marimba-generated briefing notes
**What:** A `student_rosters` table with full name lists per group (not just flagged students). Total student count comes from row count. Replace the removed mock "Marimba's note" with a real Mistral-generated one-liner that reads recent sessions + flags + absences and surfaces "the one thing to remember" for today's class.
**Why:** The current briefing is honest now (no mock) but a little sparse. A real Marimba note ("Sofía's been quiet 2 sessions in a row — check in early") would bring back the polish without lying.
**Effort:** ~3 hours

### 8. "Save as Gmail draft" button on inline composer
**What:** Alongside "Send", add a "Save as draft" button on both the reply preview (TaskChatDrawer) and the freeform composer (EmailComposer). It saves the email to Gmail's Drafts folder instead of sending. The teacher opens the draft from Gmail's web/app UI to finish — letting them use Gmail's native address book for recipient lookup (parents, etc. that aren't in TeacherPilot's autocomplete yet).
**Why:** Cuts out the "I don't have the parent's email handy" friction without building a contacts system. Gmail's address book is already authoritative.
**How it works:** New `create_draft()` in `connectors/gmail.py` using Gmail API's `users.messages.drafts.create` (same MIME envelope as send, different endpoint). New `/api/emails/{id}/save-draft` + `/api/emails/save-draft` endpoints mirroring the send ones. Two buttons in the UI instead of one.
**Effort:** ~30 minutes

---

## 🔵 Probably skip (re-evaluate when needed)

- **Student roster** — no concrete use case yet. Re-evaluate if voice journaling or email tracking creates a need.
- **Notion integration** — email reply tracking + User Tasks covers the core follow-up need without a dependency.

---

## How to use this file

- Items 1–3 are the roadmap. Don't jump ahead.
- When an item ships, move it to a `## Done` section at the bottom.
- Add new ideas to the bottom of the relevant tier, not the top.

---

## ✅ Done

- **Lesson plan drawer + Marimba writes to class_sessions** (2026-05-22) — "Plan lesson" button on each class card opens a chat drawer. Marimba opens with 3 distinct pedagogical proposals (or a Socratic question if there's no group history). Teacher picks one or proposes their own, Marimba elaborates into a ```lesson artifact card. Three footer actions: Save plan (writes to `lesson_plans`), Copy as prompt (Claude/ChatGPT-ready meta-prompt), + Assignment description (Toddle-ready ```assignment block). Marimba also has a new `log_class_session` tool — when the teacher describes what happened last class, she confirms then writes to `class_sessions` directly; a green chip appears above the message showing it actually persisted. Briefing card de-mocked: unit, Marimba note, inert source buttons all removed; flag count + flagged-students list now come from `data/student_flags.json` via the new `/api/student-flags` endpoint.
- **Triage uses personal_context + flags direct mentions** (2026-05-21) — Email triage now injects the teacher's "About me / How I work" block (roles, key collaborators, ongoing initiatives), adds a direct-mention override rule (any email naming the teacher + an action verb = action_required regardless of sender), and passes the first 800 chars of the body so @mentions buried in thread replies aren't missed.
- **Marimba can search the inbox + sent mail via tool calling** (2026-05-20) — Chat to solve now exposes three Gmail tools to Marimba (`search_sent_emails`, `search_inbox`, `get_full_email`), scoped to the last 90 days. She decides when to call them based on what the teacher asks. Tool-call loop caps at 3 iterations. The UI shows small "Searched sent emails — 2 matches" chips above her reply so the teacher sees what she actually did.
- **Email composer in chat + attachments + addressbook seeding** (2026-05-20) — Marimba drafts new emails inline as a structured composer (To with autocomplete, Subject, Body, file attachments up to 20 MB). `email_recipients` is now seeded from inbox senders too.
- **Chat polish — schedule context, markdown rendering, copy buttons, personal context, artifact cards, skip rating** (2026-05-20) — Chat now knows today's schedule (no more "your class is 7B" when the UI says 9A1). Markdown is rendered, every assistant reply has a copy button, and code-fenced artifacts render as a styled card with their own copy button. Settings modal now has two fields: "About me / How I work" (style guidance, ADHD considerations) and "Ignore rules" (filter signal). Third dismissal option added: "doesn't apply this week" — clears at next weekly announcements upload, doesn't pollute the future ML training set.
- **Chat to solve** (2026-05-20) — Every Top 3 card opens a right-side drawer. Marimba chats with full task context, drafts email replies that thread back into the original Gmail conversation, plays the canned audio on send.
- **Personal ignore rules** (2026-05-19) — Gear-icon settings modal; ignore rules injected into both priority and email-triage prompts. Plus pre-rendered "Listo profe" audio that plays on every successful meeting-email send.
- **Supabase migration** (2026-05-19) — DB now persists across Railway restarts. `DATABASE_URL` env var drives the connection; SQLite fallback kept for tests.
- **Auto Gmail sync at 7am Costa Rica** (2026-05-19) — APScheduler background job + `sync_state.json`; persistent UI banner surfaces auth failures instead of silently reporting "no emails".
- **Weekly announcements processing fixes** (2026-05-19) — timeout extended to 90s, null/string fields in Mistral output now handled gracefully.
