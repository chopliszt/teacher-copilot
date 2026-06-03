# Validation — how we know this is done and mergeable

Merge gate (chosen): **BOTH must hold** — the v2 migration breaks nothing AND
reasoning measurably helps triage. Either one failing blocks merge.

---

## Gate 1 — Nothing broke under the v2 SDK

- [ ] `cd backend && pip install -r requirements.txt` installs `mistralai==2.4.9`
      cleanly.
- [ ] `python -c "import mistralai; print(mistralai.__version__)"` prints `2.4.9`.
- [ ] `cd backend && pytest tests/ -v` → **all tests pass** (the 46-test baseline,
      adjusted for any tests intentionally updated in this branch).
- [ ] All 8 SDK call sites import and execute without `TypeError`/`AttributeError`:
      `mistral_client.py`, `prompts/{email_triage, weekly_schedule, voice,
      meeting_summary, task_chat, lesson_plan}.py`, `stt.py`.
- [ ] Tool calling still works: a `task_chat` / `lesson_plan` round-trip produces
      the same action it did on v1 (manual smoke test or test coverage).
- [ ] STT still transcribes (a `stt.py` live or mocked call returns a transcript).

## Gate 2 — Reasoning actually helps triage

- [ ] Triage with `reasoning_effort="high"` on `mistral-small-latest` (Small 4)
      returns correctly structured results (clean JSON, no thinking leakage into
      the parsed output).
- [ ] Triage evals run against **both**:
      - baseline: Small-3 (`mistral-small-2506`), no reasoning
      - candidate: Small-4 (`mistral-small-latest`), `reasoning_effort="high"`
- [ ] Candidate **matches or beats** baseline on the eval set (accuracy /
      precision / recall — especially the broadcast-deliverable and
      bare-deadline cases that motivated this).
- [ ] No regression on the negative cases (Cc-only, encouragement broadcasts,
      grades 11–12) — reasoning must not start over-flagging.

## Informational (not a gate, but record it)

- [ ] Per-batch latency delta vs. baseline (reasoning adds thinking tokens).
- [ ] Per-batch token-cost delta vs. baseline.
- These don't block merge but belong in the PR description so the cost of
      "more intelligent" triage is visible.

---

## What success looks like

The branch merges only when:
1. The whole app runs on `mistralai==2.4.9` with the test suite green, AND
2. Reasoning-enabled triage is at least as accurate as Small-3 (ideally better on
   the hard cases), with the latency/cost trade-off documented.

If Gate 1 passes but Gate 2 does not, **do not merge** — the SDK bump alone
carries migration risk with no payoff. Either tune the prompt/effort and re-eval,
or shelve the branch.

## Quick commands

```bash
# Gate 1
cd backend && pip install -r requirements.txt
python -c "import mistralai; print(mistralai.__version__)"   # expect 2.4.9
cd backend && pytest tests/ -v                                # expect all pass

# Gate 2 (eval harness — adjust path to the triage eval entrypoint)
cd backend && python -m tests.evals.run_triage_evals          # baseline vs candidate
```
