# Mission

## The one sentence

**Marimba is a daily command center that does 100 things so an overwhelmed teacher
only has to see 3.**

## Why this exists

This project was born from a real, specific pain: a teacher managing 272 students
across 13 groups, drowning in administrative noise — parent emails, coordinator
requests, meetings, trainings, events, attendance flags, lesson prep — scattered
across Gmail, Toddle, Sheets, Calendar, and paper newsletters, with **no coherent
picture of what actually matters right now**. The cost was not just lost time.
Missed emails, forgotten meetings, and a permanent low-grade dread were degrading
the teacher's well-being *and* their teaching.

Marimba's job is to absorb that firehose and hand back a calm, decisive answer to
one question: *what do I need to do next?*

> "The AI did 100 things. You see 3."

## Who it's for

**Primary user: an ADHD teacher under administrative overload** — concretely, the
teacher who builds it (C. Infante, Golden Valley School, Costa Rica), and people
shaped like them.

ADHD is not an afterthought or an accessibility checkbox here — it is the
**defining design constraint**, the thing that decides every disagreement:

- The screen shows **what needs attention and nothing else**. Comprehensiveness is
  a feature for other apps; here it is a failure mode.
- **Every actionable item has a one-tap way out** — done or dismiss. No dead ends,
  no stale piles. An unresolved item left on screen is an anxiety generator, so
  dismissal is always available.
- **Feedback is immediate and visible** — the item disappears, the count drops —
  not buried behind a modal or a confirmation dialog.
- **Nothing on screen should require explanation.** The hardest constraint, and the
  one we keep.

## Ambition: me first, others later

Marimba is built **for one teacher first**, and that is a feature — it lets us tune
to a real workflow instead of a hypothetical average. But we **architect so it can
generalize**: avoid one-off hacks that would block another teacher from using it
later. Teacher-specific facts (schedule, key senders, "about me") live in **data and
configuration**, not hard-coded in logic. When we must choose, we choose the
personal win now — but we don't burn the bridge to a second user.

We are **not** yet building multi-tenant accounts, onboarding flows, or a generalized
product. That's a someday, earned only after the single-user tool is genuinely loved.

## What Marimba is — and is not

**It is** a companion. Marimba (a fox, after the founder's border collie; named for
the Colombian instrument) greets the teacher by time of day, speaks in complete
sentences, acknowledges the weight of the work, and gets things done. The aim is for
the teacher to feel **supported, not monitored**. Emotional connection over raw
utility; cognitive ease over completeness.

**It is not** another dashboard, another chat box that demands prompt engineering, or
another inbox to check. If a piece of information doesn't reduce a decision, it's
noise and it doesn't earn a place on screen.

## How we know it's working

- The teacher opens **one tab**, not six.
- The teacher stops *missing* high-consequence things (a director's request, a cover
  ask from Fabiola, a meeting tomorrow at noon).
- The surface stays **quiet** — three things, not thirty — even on a heavy week.
- The teacher trusts the filter enough to *not* double-check everything, because
  recovery is always possible (nothing important is ever truly lost).
- The app **replaces** manual work instead of duplicating it — the teacher is not doing
  the same task by hand *and* in the app. Double work means the surface failed its job.

## Principles that govern decisions

1. **ADHD-first, always.** Every decision — UI, data, scope — is made with ADHD in
   mind. This is the standing lens, never traded away. It does not compete with the
   principles below; they are the *same* instinct applied to scope and code. A
   simpler system is a calmer system.
2. **KISS — keep it simple.** The simplest thing that solves the real problem wins.
   Complexity is a tax the ADHD user pays twice — once in the code, once on screen.
   KISS and ADHD-first reinforce each other; they never pull in opposite directions.
3. **YAGNI — you aren't gonna need it.** Build the slice the teacher needs *now*,
   not the speculative general case. Don't build a feature "for later"; don't keep a
   phase on the roadmap that the code already shipped. Check the code before adding
   work — redundant phases are themselves a form of clutter, the very thing
   ADHD-first exists to prevent.
4. **Filter at the source, not on screen.** Clutter is a triage problem solved
   upstream by the AI — never a layout problem solved by scrolling.
5. **Principle-first prompts, not brittle rules.** Tell the model the underlying
   intent and let it reason; don't encode literal phrase-matching. (See `CLAUDE.md`.)
6. **Graceful degradation, always.** Every AI call is gated behind a key and falls
   back silently. No key, no crash — the app still works.
7. **Names say what they are.** The teacher is also a learner and a developer; code,
   columns, and UI labels read plainly, never in invented shorthand.
8. **Quiet Premium.** Stone and amber, low opacity, whisper not shout. (See `DESIGN.md`.)
