# CONCLUSIONS — Should we upgrade triage to Mistral Small 4 + reasoning?

**Verdict: NO (for now). Do not upgrade triage to reasoning.**
Decided 2026-06-04 from real-inbox evidence. This branch is kept as the record so
the idea isn't re-attempted from scratch. If you're reading this because you had
the "let's make triage smarter with reasoning_effort=high" idea again — the
experiment was done; read on before redoing it.

## TL;DR

- The **real win** was a prompt fix (teaching the model "teaching a group ≠ being
  its homeroom teacher"), NOT the model upgrade. That fix works on the cheap
  current model and was cherry-picked to `main` (commit *Triage no longer nags…*).
  Production stays on **Mistral Small 3 + mistralai v1, no reasoning**.
- Reasoning (Small 4, `reasoning_effort="high"`) **regressed** on real inbox mail
  at production batch size. It is NOT worth the cost/risk for triage today.

## What was tried (all on this branch)

1. Bumped `mistralai` 1.12.4 → 2.4.9 and migrated all 8 SDK call sites (the only
   breaking change was the import path: `from mistralai import Mistral` →
   `from mistralai.client import Mistral`).
2. Enabled `reasoning_effort="high"` on the two Small-model calls (email_triage,
   weekly_schedule). Extracted a chunk-safe parser to `prompts/_reasoning.py`
   (reasoning returns content as `[thinking, text]` chunks, not a string).
3. Built a real-inbox eval: fetched 100 inbox emails (read-only) and ran them
   through Small-4+reasoning vs Small-3, both on the same prompt.

## Key findings

**Migration cost is low.** v1→v2 was a one-line import change ×8 files; 60 unit
tests passed under v2. So the SDK bump itself was not the blocker.

**Reasoning works and is *observable*.** The `thinking` trace is a genuine
benefit — we debugged a misclassification by literally reading the model's mind
(it conflated "teaches 8A1" with "is 8A1's homeroom teacher"). Worth remembering
if reasoning is ever used elsewhere: you can log traces to diagnose misses.

**But reasoning REGRESSED on real triage at scale.** On 100 real emails
(15-per-batch, same prompt with the principle):
- **Absences: 3 detected vs Small-3's 6.** Reasoning "rationalized" absence
  forwards into `ignore` ("this asks nothing of me") — half of them missed. A
  core category, systematically degraded.
- **Missed a direct @-mention** ("@Camilo … quedamos atentas a su confirmación")
  → reasoning said ignore; Small-3 correctly said action_required.
- **Dropped an item from a batch** (returned no verdict for one email — the
  `None` reliability blip recurred).
- **The homeroom principle was fragile under load**: 8/10 correct in isolation,
  but it still over-flagged the Carolina form inside a noisy 15-email batch.
- Net: ~2 wins vs ~6 clear losses against the cheap baseline.

**The clean eval set could NOT tell the models apart** (both 17/17). Easy,
small-batch evals hide the regression. A real verdict required production-scale
(big, noisy batch) testing.

## The overthinking experiment (2026-06-04, learning)

Re-ran the missed absence email through different settings (raw HTTP, no SDK):
- `high` effort: ~2536 chars of deliberation, wrong 4/5 (talked itself into ignore).
- `high` + "decide quickly, don't overthink obvious cases" instruction: deliberation
  halved (~1286 chars), wrong 3/5 — a *partial* improvement.
- no reasoning (default): wrong 5/5 — BUT Small-3 (older model) got this right.

**Lesson:** reasoning helps on ambiguous, multi-step problems and HURTS on
pattern-recognition tasks where the answer is obvious — deliberation manufactures
doubt. Triage is mostly pattern-recognition (absences, automated notices), so
reasoning backfired. Prompt steering reduces overthinking but doesn't cure it.
Part of the absence regression is also Small-4-vs-Small-3, independent of reasoning.

## SDK insight (answering "why did we even need the SDK?")

A model call is just an HTTPS POST with JSON — the SDK is **not** required (the
smoke test and the overthinking experiment both used raw `curl`/`httpx` and passed
`reasoning_effort` fine). The v2 SDK was only "needed" because the codebase calls
the API *through* the SDK, and v1's typed `complete_async()` had no
`reasoning_effort` parameter. There were three paths, not two:
1. Upgrade the whole SDK to v2 (what we tried — touches all 8 sites).
2. Stay on v1 SDK (impossible — can't pass the param).
3. **A thin raw-HTTP helper for the triage call only** — reasoning on one endpoint,
   no SDK upgrade, no touching the other 7 sites. The lightest path if reasoning
   on triage is ever revisited.

## If you revisit this

Don't, unless you first:
1. Fix Small-4's **absence under-detection** (it rationalizes format-based
   categories into ignore) — likely needs explicit "X-form is ALWAYS category Y,
   don't deliberate" guidance, and even then it's only a partial fix.
2. Handle the **dropped-item** failure (default missing IDs to a category or
   re-query) before trusting batch reasoning in production.
3. Build a **production-scale eval** (large, noisy batches) — clean small evals
   gave a false 100%/100% tie.
4. Consider **path #3 (raw HTTP for triage only)** instead of the full SDK
   migration, and weigh the added **latency + thinking-token cost**.

## State of this branch

- `requirements.txt` pins `mistralai==2.4.9`; running this branch needs
  `pip install -r requirements.txt` (the env was restored to v1 for `main`).
- Contains the full v2 migration + reasoning enablement + `prompts/_reasoning.py`.
- The homeroom principle + 3 real eval cases were cherry-picked to `main`; they
  are NOT separately committed here (they don't depend on v2).
