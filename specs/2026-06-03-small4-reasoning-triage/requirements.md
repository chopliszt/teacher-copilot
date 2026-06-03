# Requirements — Small 4 reasoning for triage (and weekly schedule)

**Branch:** `experiment/small4-reasoning-triage`
**Date:** 2026-06-03
**Status:** scoped, not yet implemented

## Goal

Make email triage (and the weekly-schedule extractor) more intelligent by having
the Mistral Small model *reason* before classifying, using the new
`reasoning_effort="high"` parameter introduced with **Mistral Small 4**
(`mistral-small-2603`, released 2026-03-16; `mistral-small-latest` now resolves
to it).

## Why now

Previously, reasoning on Mistral was gated server-side to Magistral models — the
API rejected reasoning on the Small line (HTTP 400). Mistral Small 4 unifies
reasoning, multimodal, and instruct into one model with a configurable
`reasoning_effort` (`none|low|medium|high`). This means we can get
reasoning-grade triage on the *cheap Small tier* — no Magistral, no cost-tier
premium.

## Smoke-test findings (verified live 2026-06-03, before this branch)

These facts are established and do not need re-discovery:

1. `mistral-small-2603` AND `mistral-small-latest` accept `reasoning_effort="high"`
   → HTTP 200, real step-by-step reasoning followed by clean JSON.
2. The response `content` comes back as a **list of chunks**: a `thinking` chunk
   then a `text` chunk (not a plain string).
3. `email_triage._response_to_json_text()` **already** handles that shape (keeps
   `type in (None, "text")`, drops thinking) → triage needs **zero** parse changes.
4. The installed SDK `mistralai==1.12.4` **rejects** `reasoning_effort`
   (`TypeError: unexpected keyword argument`). The v2 SDK is required — there is
   no v1 shortcut.

## Decisions (from feature-spec Q&A)

| Decision | Choice | Rationale |
|---|---|---|
| **Scope** | All Small-model sites: `email_triage.py` + `weekly_schedule.py` | Both already use `mistral-small-latest`; both benefit from reasoning. Voice/tool-calling stay on Large and are NOT given reasoning. |
| **Effort level** | `reasoning_effort="high"` | Matches the "more intelligent" goal; deep step-by-step reasoning. |
| **SDK pin** | `mistralai==2.4.9` | Exact pin for reproducibility, matching the existing `==1.12.4` style. |
| **Merge gate** | Tests green AND eval win | Strictest: v2 migration must break nothing AND reasoning must measurably help. See `validation.md`. |

## Scope boundaries

**In scope**
- Bump `mistralai` 1.12.4 → 2.4.9 (done on this branch).
- Migrate all 8 SDK call sites to the v2 API surface (whatever changed).
- Add `reasoning_effort="high"` to the two Small-model calls (triage, weekly schedule).
- Update the one test that hand-rolls an SDK response shape if v2 changed it.

**Out of scope**
- Adding reasoning to voice / priorities / meeting summary / task chat / lesson plan.
- Changing prompts' classification logic (principle-first prompt stays as-is).
- Frontend changes.
- Removing/replacing Magistral references elsewhere.

## Affected files (blast radius)

All 8 import the same `mistralai` package, so all are touched by the v2 bump even
though only two get the reasoning param.

| File | Model | Change under v2 |
|---|---|---|
| `prompts/email_triage.py` | Small | v2 migration + add `reasoning_effort="high"` (parser already safe) |
| `prompts/weekly_schedule.py` | Small | v2 migration + add `reasoning_effort="high"` |
| `mistral_client.py` | Large | v2 migration only (no reasoning) |
| `prompts/voice.py` | Large | v2 migration only |
| `prompts/meeting_summary.py` | Large | v2 migration only |
| `prompts/task_chat.py` | Large | **Highest risk** — tool calling under v2 |
| `prompts/lesson_plan.py` | Large | **Highest risk** — tool calling under v2 |
| `stt.py` | Voxtral | v2 migration — `audio.transcriptions` surface |
| `requirements.txt` | — | pin bump (done) |
| `tests/test_weekly_schedule.py` | — | only test hand-rolling a fake SDK response shape |

## Key risk

The model ID is irrelevant to migration risk — the **package version** is what
bites. `task_chat.py` and `lesson_plan.py` use tool calling, the surface most
likely to have changed v1→v2. These get the most attention even though they are
not the feature target.
