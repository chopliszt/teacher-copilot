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

### 3. General-purpose assistant — Marimba as drafting + parent-FAQ tool
**What:** Today's "Chat to solve" drawer handles per-task questions. Next step: let the teacher ask broader, context-spanning things ("draft a reply to all parents asking about the Microsoft trip using what I've already sent", "summarize what I've told 8th grade families this month") without leaving the app.

**Recommended shape (single agent + tools, NOT multi-agent):**
- One Marimba, more tools. New chat actions: `draft_broadcast(topic, audience)`, `summarize_thread(query)`, `find_sent_context(topic)`.
- The teacher describes intent in natural language; Marimba picks the right tool. Same approach Claude Code uses — one mental model for the user, one prompt to debug, no routing logic.

**Why not a fleet of specialized clones:**
- More plumbing (routing, handoff prompts, separate contexts) for the same end result.
- Specialization hides where mistakes come from; with one assistant you always know where to edit the prompt.

**Effort:** ~6–8 hours (Gmail thread search tool + broadcast composer + prompt updates).

---

## 🟢 When you have data (no rush)

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

- **Chat polish — schedule context, markdown rendering, copy buttons, personal context, artifact cards, skip rating** (2026-05-20) — Chat now knows today's schedule (no more "your class is 7B" when the UI says 9A1). Markdown is rendered, every assistant reply has a copy button, and code-fenced artifacts render as a styled card with their own copy button. Settings modal now has two fields: "About me / How I work" (style guidance, ADHD considerations) and "Ignore rules" (filter signal). Third dismissal option added: "doesn't apply this week" — clears at next weekly announcements upload, doesn't pollute the future ML training set.
- **Chat to solve** (2026-05-20) — Every Top 3 card opens a right-side drawer. Marimba chats with full task context, drafts email replies that thread back into the original Gmail conversation, plays the canned audio on send.
- **Personal ignore rules** (2026-05-19) — Gear-icon settings modal; ignore rules injected into both priority and email-triage prompts. Plus pre-rendered "Listo profe" audio that plays on every successful meeting-email send.
- **Supabase migration** (2026-05-19) — DB now persists across Railway restarts. `DATABASE_URL` env var drives the connection; SQLite fallback kept for tests.
- **Auto Gmail sync at 7am Costa Rica** (2026-05-19) — APScheduler background job + `sync_state.json`; persistent UI banner surfaces auth failures instead of silently reporting "no emails".
- **Weekly announcements processing fixes** (2026-05-19) — timeout extended to 90s, null/string fields in Mistral output now handled gracefully.
