# Roadmap

Forward-looking only. **Hard-yes items live here; maybes go to `BACKLOG.md`.** Shipped
work moves to `BACKLOG.md`'s `## Done` (a roadmap shouldn't carry its own history).

**Rules:** work top to bottom; finish a phase before starting the next; check the code
before adding a phase (a built feature is clutter — YAGNI).

---

## Phase 1 — Real-world validation (does it actually work?)
Not a feature — the teacher uses the app daily and collects concrete scenarios where it
works and where it fails. Each failure becomes a fixture for evals + prompt fixes.
This is the lens that feeds every phase below.
- **First bug to chase:** a manually-added task from ~a week ago still never reaches
  Top 3 — by now it should. Find the scoring/surfacing bug.
- Keep a running list of "the model misread my intent" cases (see Prompt-quality track).

## Phase 2 — Real meeting scheduling (drawer + voice → Google Calendar)
Today `add_event` only adds an event *inside the app*. `gcalendar.py::create_event()`
exists but is unwired — close the loop so Marimba can actually **book**.
- Two entry points, same action: from the **Top-3 drawer** (email is the context) and by
  **voice**. A short confirm step before booking ("I'll book Fabiola, tomorrow 10am —
  confirm?") so nothing hallucinated gets saved.
- `contacts` table auto-filled from Gmail sent recipients — no manual entry.

## Phase 3 — Activate ML priority personalization (few-shot)
We collect `relevant/skip/noise` and already suppress noise titles — but the model never
learns. Inject accrued examples as few-shot positives/negatives into the priority prompt
so it generalizes instead of matching exact titles. Data + export endpoint already exist;
this is mostly prompt wiring.
- **Capture the *why*, minimally.** The reason is the highest-value signal — it's the
  discriminator that makes a few-shot example teach instead of overfitting a title (per
  CLAUDE.md). Keep dismissal one tap; *after* it, show an optional one-line "why?
  (optional)", answerable by **voice** or text and skippable at zero cost. Store it as a
  nullable `reason` on the existing `priority_feedback` record — no new signal, no
  always-on field. Pairs with Phase 1 validation (that's when you'll most want to say
  *why* something's wrong).

## Phase 4 — Act on a task now (don't wait for Top 3)
A one-tap "work on this" on manually-added tasks that opens the same drawer/act flow Top 3
uses. ADHD: if I want to do it now, I shouldn't have to wait for the ranker to surface it.
(Small — could pull forward if Phase 1 makes it urgent.)

## Phase 5 — Email reply tracking ("you never heard back")
No reply in 7 days → surfaces in Top 3 as "Waiting on reply from X — sent 5 days ago."
New `pending_replies` table; `in:sent` scan (plumbing exists in `gmail.py`); a Mistral
Small "does this expect a reply?" filter.

## Phase 6 — Triage recovery ("recently ignored" + mark important)
Useful, not urgent. Persist *every* triaged email (incl. `ignore`) ~14 days in a
`triage_log` table; add a "Recently ignored" view + one-tap "↑ Mark important". Removes
the anxiety of trusting the filter — nothing is ever truly lost. (Learning-from-corrections
is a later, separate slice — mirrors Phase 3.)

## Last — Toddle push
Important, but **only after the basics above are solid.** One "Push to Toddle" button turns
an agreed lesson + assignment into real Toddle records. Real API work + complexity — don't
take it on while core surfaces still need tuning.

---

## Continuous track — Prompt quality (principle-first, not rules)
As validation surfaces failures, fix prompts by reasoning from intent — **not** by piling
on literal rules. Known failure patterns to watch:
- **Drafts that change my situation/context** — the reply rewrites the topic or audience
  (a wellness/teacher-targeted message comes out as if the situation were different).
  Keep my framing; don't re-imagine it.
- **Parent emails auto-offering an online call** — drop it. The email *is* the message;
  don't volunteer my time by default.
- **Brittle rule creep** — e.g. a past rule ignored emails that opened with pleasantries;
  but a polite email can still carry a real task (already fixed once — `3156d9d`). Strip
  rules like this; let the model reason from intent.

## Continuous track — Evals in CI
Triage + voice eval scripts already call the real production functions but run manually.
Wire them as a CI gate so a prompt regression can't ship silently. Validation failures
(Phase 1) become new eval cases. *Open question to revisit: can it also learn passively
from everyday use, not only from hand-picked examples?*

---

## Parked (not a hard yes — re-evaluate on real need)
- **Plan-to-outcome learning loop** — dropped. The class log already captures *what we did*
  + *what worked*; a similarity-tagging job would over-complicate that.
- **Triage escalation, per-group rosters, Notion, calendar export/sync** — no concrete need
  yet.

> Note: the "why does this matter to me" idea is **not** parked — it's folded into Phase 3
> as an optional, voice-first reason on dismiss (not an always-on per-card textbox).
