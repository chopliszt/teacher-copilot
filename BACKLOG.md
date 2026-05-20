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

### 3. Personal ignore rules
**What:** A single editable text field: *"chairs at end of day, uniform checks unless direct parent complaint, grade 11-12 emails with no direct ask to me."* Injected into Mistral triage and priority prompts.
**How:** `data/user_preferences.json` → one field `ignore_rules: str`. Gear icon somewhere unobtrusive → modal with one textarea. Two backend endpoints: GET + PUT.
**Effort:** ~2 hours

---

## 🟢 When you have data (no rush)

### 4. ML priority personalization
**Status:** Already collecting data silently.
- "Mark done" → `completed: true` (feature, not label)
- "not relevant for me" → `rating: noise` (the training label)
- Implicit positive: shown in Top 3 and NOT dismissed as noise

**Activation path:**
- ~20 noise examples → inject as few-shot negatives in Mistral prompt. Instant improvement.
- ~100 examples → fine-tune small classifier (export via `GET /api/priority-feedback/export` → JSONL for LoRA/Mistral fine-tune API).
- The `context_json` field stores all features needed: title, source, priority level, class, subject, estimated time.

**Note:** Don't add more feedback UI. One "not relevant" signal is enough. The system is already working well — this is an enhancement, not a fix.

### 5. Session history view per class
**What:** Inside the class briefing panel, an expandable "view past sessions" list for that group.
**Status:** All data is in DB. Needs `GET /api/class/{group}/sessions` endpoint + small UI component in `TodaySchedule.tsx`.
**Effort:** ~1 hour

### 6. General-purpose assistant — context-aware drafting + parent FAQ
**What:** Marimba should handle open-ended asks tied to school context, not just trigger actions. Concrete trigger: parents keep emailing about the Microsoft trip even though the answer is already in past emails — the teacher wants to say *"draft a reply with the trip context"* or *"summarize what I've already told parents about this trip and propose an auto-reply"* and have Marimba do it.

**Recommended shape (single agent + tools, NOT multi-agent):**
- One Marimba, more tools. New voice/chat actions: `draft_email(recipient, topic, tone?)`, `summarize_thread(query)`, `find_sent_context(topic)`.
- The teacher describes intent in natural language; Marimba picks the right tool. Same model behavior Claude Code uses — keeps one mental model for the user, one prompt to debug, no routing logic.

**Why not a fleet of specialized clones:**
- More plumbing (routing, handoff prompts, separate contexts) for the same end result.
- Specialization hides where mistakes come from; with one assistant you always know who to blame and where to edit the prompt.
- Worth revisiting only if/when one domain (e.g., a recurring trip with weeks of artifacts) grows so much that its context crowds out everything else.

**Tied to:** item 3 (ignore rules) and the "memory" question — once memory injection is solid, this just becomes "Marimba + email drafting tool".

**Effort:** ~6–8 hours (Gmail thread search tool + draft-mode UI + prompt updates).

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

- **Supabase migration** (2026-05-19) — DB now persists across Railway restarts. `DATABASE_URL` env var drives the connection; SQLite fallback kept for tests.
- **Auto Gmail sync at 7am Costa Rica** (2026-05-19) — APScheduler background job + `sync_state.json`; persistent UI banner surfaces auth failures instead of silently reporting "no emails".
- **Weekly announcements processing fixes** (2026-05-19) — timeout extended to 90s, null/string fields in Mistral output now handled gracefully.
