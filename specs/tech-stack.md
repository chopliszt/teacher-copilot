# Tech Stack

The authoritative snapshot of *what we build with* and *where the gaps are*. When a
choice changes, update this file and `MODEL_REGISTRY.md` together.

## At a glance

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React 19 + TypeScript, Vite 7 | SPA, no SSR |
| Styling | Tailwind CSS v4, Radix UI, class-variance-authority | "Quiet Premium" — see `DESIGN.md` |
| Data fetching | TanStack React Query v5, Axios, Zod v4 | Zod schemas are the source of truth for API shapes |
| Routing | react-router-dom v7 | |
| Markdown / toasts | react-markdown + remark-gfm, sonner | For chat artifacts + feedback |
| Backend | Python 3.11, FastAPI, Uvicorn | All endpoints under `/api/`, no versioning |
| ORM / DB | SQLAlchemy 2.0 | Postgres in prod, SQLite for local + tests |
| Background jobs | APScheduler | 7am Costa Rica Gmail sync |
| AI — reasoning | Mistral Large (`mistral-large-latest`) | priorities, voice, chat-to-solve, lesson plans, meeting summary |
| AI — triage/extract | Mistral Small (`mistral-small-latest`) | email triage, weekly schedule extraction |
| AI — speech-to-text | Voxtral Mini (`voxtral-mini-latest`) | same `MISTRAL_API_KEY` |
| AI — text-to-speech | ElevenLabs | consistent voice ID = Marimba's persona |
| SDK | `mistralai` 1.12.x | v1 line — `prompt_mode="reasoning"` only; `reasoning_effort` is v2 (breaking) |
| Email | Native Gmail OAuth2 connector | `connectors/gmail.py`; read + `gmail.send` scope |

## Deployment — two paths, know which is live

There are **two** deployment stories in this repo, and they don't fully agree yet:

- **Documented (README):** home server → Docker Compose (backend + frontend + tunnel)
  → Cloudflare Tunnel → public hostname. Self-host friendly.
- **Current reality (per `BACKLOG.md` "Done"):** migrated to **Railway + Supabase
  (Postgres)** so the DB persists across restarts. `DATABASE_URL` drives the
  connection; **SQLite is the fallback, kept for tests**.

> ⚠️ Drift to fix: the README still describes only the home-server/Cloudflare path.
> Reconcile the docs to name Railway + Supabase as the live production target (or
> document both explicitly as supported).

## Architecture shape

- **Backend module map** lives in `CLAUDE.md` — the canonical table. Key files:
  `main.py` (all endpoints + lifespan), `context_builder.py` (prompt + `TEACHER_PROFILE`),
  `mistral_client.py`, `prompts/*` (one module per LLM task), `connectors/*`,
  `schedule_day.py`, `database.py`, `events.py`, `preferences.py`, `student_flags.py`.
- **Two pipelines:** the **priority pipeline** (`GET /api/priorities` → pool from
  tasks + emails + meetings + events + action items → Mistral Large → top 3, or local
  fallback scoring) and the **voice pipeline** (audio → Voxtral → Mistral Large →
  ElevenLabs → reply + UI action).
- **Frontend data flow:** all server state owned by React Query hooks in
  `src/lib/hooks/`; `App.tsx` owns the voice hook and fans state down; Zod schemas in
  `src/lib/api/client.ts` define every response shape.
- **Graceful degradation is structural:** every Mistral/ElevenLabs call is gated
  behind its env key and returns `None`/falls back on any error.

## Model split philosophy

Use the **smallest model that clears the eval bar with margin**. Small forces explicit
prompting (good discipline); move up to Large only when *evals* — not cost or vibes —
say the task needs reasoning from principles. Full table + experiment tips in
`MODEL_REGISTRY.md`.

## Known gaps (recorded deliberately)

These are the stack's honest weak points right now. They drive the roadmap.

### 1. Connectors are half-built — the integration layer is the main gap
- ✅ **Live:** Gmail (OAuth2, read + send, Mistral Small triage); weekly-announcement
  paste (Mistral Small extraction).
- 🚧 **Stub / dormant:** `connectors/gcalendar.py` (read-from-Calendar not wired as an
  input source yet — only event *extraction from email* exists), `connectors/sheets.py`
  (full 272-student rosters), `connectors/toddle.py` (grades, assignments, submission
  status — the "killer integration", still no API work done).
- **Why it matters:** the mission is to absorb the *whole* firehose. Until Calendar,
  Sheets, and Toddle are real inputs, the teacher still checks other tools.

### 2. The ML personalization loop is collecting but not learning
- Feedback signals **are** being recorded — priority `relevant | skip | noise`
  ratings, triage corrections, event-dismiss relevance records — but **nothing
  consumes them yet**. No few-shot injection of accrued negatives, no fine-tune.
- The plumbing is intentional (data first, model later), but until activation the
  classifier and ranker can't get smarter from real use.
- **Activation thresholds (from `BACKLOG.md`):** ~15–20 triage corrections or ~20
  priority "noise" examples → inject as few-shot; ~100 → consider a fine-tune /
  exported JSONL.

### 3. Evals exist but are not in CI
- `tests/evals/run_triage_evals.py` (Small) and `run_voice_evals.py` (Large) call the
  **real production functions**, so they follow whatever model the code uses — but they
  run **manually**. There is **no CI gate** catching a prompt regression before it
  ships.
- **Why it matters:** prompts are the product here. A silent regression in triage
  (a missed director email) is exactly the high-consequence failure the mission is
  built to prevent — and right now nothing automated guards it.

## Conventions that constrain the stack

- **Fetch current docs via context7, not memory.** For any library, framework, SDK,
  API, CLI, or cloud service (React, Vite, FastAPI, SQLAlchemy, `mistralai`,
  `elevenlabs`, Tailwind, Supabase, Railway…) use the `ctx7` CLI / `find-docs` skill
  to pull up-to-date documentation before writing code against it — even for
  well-known libraries, since training data lags real API changes. Prefer this over
  web search for library docs. (Standing rule: `~/.claude/rules/context7.md`.)
- **Verify external interfaces before coding** — `pydoc` / `inspect.signature` /
  a REPL, never assume signatures from memory (`mistralai`, `elevenlabs`,
  SQLAlchemy). Codified in `CLAUDE.md`. This is the runtime-inspection complement to
  the docs lookup above.
- **Descriptive names** in code, DB columns, JSON fields, and prompt enum values —
  no invented abbreviations.
- **Principle-first prompts** over brittle rule-matching.
- **Tests:** `cd backend && pytest tests/ -v`; `conftest.py` puts `backend/` on
  `sys.path`; in-memory SQLite tests need `StaticPool`.
