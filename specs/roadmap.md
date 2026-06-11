# Roadmap

Forward-looking only. **Hard-yes items live here; maybes go to `BACKLOG.md`.** Shipped
work moves to `BACKLOG.md`'s `## Done` (a roadmap shouldn't carry its own history).

**Rules:** work top to bottom; finish a phase before starting the next; check the code
before adding a phase (a built feature is clutter — YAGNI).

---

## Phase 1 — Real-world validation (is it actually earning its place?)
Not a feature — the teacher uses the app daily and collects concrete scenarios where it
works and where it fails. Each failure becomes a fixture for evals + prompt fixes. This is
the lens that feeds every phase below.

**The honest test of this phase:** is the app *replacing* manual work, or am I doing the
job twice — once by hand, once in the app? Anything that creates double work is a failure to
fix or cut, not a feature to keep (KISS / YAGNI). For each surface, ask: does this reduce a
decision, or just display one?

- **First bug to chase — stale tasks never escalate.** A manually-added task from ~a week
  ago ("enviar artículo a José Daniel") still never reaches Top 3 — by now it should.
  *Root cause (confirmed in code):* escalation is split, and the live path doesn't enforce
  it. The deterministic Python staleness boost (`_calculate_priority_score`: +150 at ≥7d,
  +80 at ≥4d) only runs in **fallback** mode (no API key). In production the **LLM owns
  ranking** and is given only a soft `waiting=Nd` hint in the prompt (`context_builder.py`)
  that it is free to ignore — so old tasks silently rot. **Decision to make:** move
  escalation to a deterministic **Python age-floor that applies in both paths** — Python
  guarantees a week-old task a Top-3 slot (or force-escalates its priority *before* the pool
  reaches Mistral); the LLM only ranks *within* those floors. A high-consequence guarantee
  shouldn't depend on the model's mood — floors are policy, not vibes.
- **See the context before starting.** A Top-3 card is too truncated to act on. If an email
  is behind an item, I should be able to read it *in the drawer* before I start — not go hunt
  for it in Gmail. The body is already fetchable (`/api/tasks/.../chat` lazy-backfill);
  surface it in the Top-3 drawer. (Pairs with Phase 2's "email is the context".)
- Keep a running list of "the model misread my intent" cases (see Prompt-quality track).

### Questions to revisit with the teacher (don't assume — ask)
Validation isn't only bug-hunting; it's periodically asking whether the app should get
*simpler*, not just more capable. Recurring questions worth surfacing:
- Which surface did I trust enough this week to *not* double-check? Which did I bypass?
- What did I end up doing manually anyway — and why didn't the app catch it?
- What's on screen that I never act on? (Candidate to cut.)
- Improve vs. simplify: is the next move adding a capability, or removing friction?

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
A one-tap "work on this" that opens the same drawer/act flow Top 3 uses — on **manually-added
tasks *and* action-required emails**, not only items the ranker chose to surface. ADHD: if I
want to do something now, I shouldn't have to wait for the model to select it. Anything
actionable should be directly workable. (Small — could pull forward if Phase 1 makes it urgent.)

## Phase 5 — Email reply tracking ("you never heard back")
No reply in 7 days → surfaces in Top 3 as "Waiting on reply from X — sent 5 days ago."
New `pending_replies` table; `in:sent` scan (plumbing exists in `gmail.py`); a Mistral
Small "does this expect a reply?" filter.

## Phase 6 — Triage recovery ("recently ignored" + mark important)
Useful, not urgent. Persist *every* triaged email (incl. `ignore`) ~14 days in a
`triage_log` table; add a "Recently ignored" view + one-tap "↑ Mark important". Removes
the anxiety of trusting the filter — nothing is ever truly lost. (Learning-from-corrections
is a later, separate slice — mirrors Phase 3.)

## Phase 7 — Answer feedback ("was this right?")
A lightweight thumbs-up / thumbs-down on Marimba's voice & chat answers (à la ChatGPT), so I
can mark when a reply was correct or off. **Distinct from Phase 3:** that tunes Top-3
*ranking*; this is signal on *answer quality* — voice reasoning, drafts, summaries. Stored
per interaction; feeds the eval set and, later, prompt fixes. One tap, zero friction,
ADHD-safe — no mandatory comment box.

## Last — Toddle push
Important, but **only after the basics above are solid.** One "Push to Toddle" button turns
an agreed lesson + assignment into real Toddle records. Real API work + complexity — don't
take it on while core surfaces still need tuning.

---

## Small cleanups (do anytime — low risk, removes clutter)
- **Remove the unused theme switcher.** The `<select>` in `MarimbaGreeting.tsx` (+ the
  `[data-theme="ocean"|"forest"]` overrides in `index.css`) swaps palettes — never used; the
  default stone/amber is the only one wanted. Delete the control and the alt-theme CSS.
  **Keep `DESIGN.md` and the design principles untouched — those stay.** One fewer decision
  on screen (ADHD-first).
- **Rename the browser tab** `TeacherPilot` → `Marimba` (`frontend/index.html` `<title>`).

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
- **Experiment — triage on Mistral Large vs Small.** Triage runs on Small today. Run the
  existing harness (`run_triage_evals.py`) against **Large** and compare scores head-to-head
  before deciding anything — the model-split rule is *let the evals decide*, not cost or
  vibes (see `tech-stack.md`). This is a **plain Large-vs-Small** comparison: a prior
  *reasoning-mode* triage test already regressed vs Small and was rejected, so don't redo
  that — measure straight, then keep Small unless Large clears the bar with real margin.

---

## Parked (not a hard yes — re-evaluate on real need)
- **Plan-to-outcome learning loop** — dropped. The class log already captures *what we did*
  + *what worked*; a similarity-tagging job would over-complicate that.
- **Triage escalation, per-group rosters, Notion, calendar export/sync** — no concrete need
  yet.

> Note: the "why does this matter to me" idea is **not** parked — it's folded into Phase 3
> as an optional, voice-first reason on dismiss (not an always-on per-card textbox).
