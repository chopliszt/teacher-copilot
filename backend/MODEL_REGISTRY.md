# 🧠 Model Registry — TeacherPilot

All AI models and external services used in the project, centralized in one place.
When experimenting with different models, update this file and the corresponding source code.

## Mistral AI Models

| Purpose | Model | File | Why this model? |
| :--- | :--- | :--- | :--- |
| **Voice / Function Calling** (Marimba's brain) | `mistral-large-latest` | `prompts/voice.py` | Needs strong reasoning to understand intent and pick the right action |
| **Priority Ranking** | `mistral-large-latest` | `mistral_client.py` | Needs to reason about urgency, deadlines, and teacher context |
| **Chat-to-Solve** (task drawer + inbox tool-calling) | `mistral-large-latest` | `prompts/task_chat.py` | Multi-turn reasoning + Gmail tool calls — needs the strong model |
| **Meeting Summary** | `mistral-large-latest` | `prompts/meeting_summary.py` | Summarize + extract action items and draft an email — reasoning-heavy |
| **Lesson Plan** (drawer proposals + elaboration) | `mistral-large-latest` | `prompts/lesson_plan.py` | Pedagogical reasoning and tailored proposals |
| **Email Triage** | `mistral-small-latest` | `prompts/email_triage.py` | Classification task — smaller model is fast and cheap enough |
| **Weekly Schedule Extraction** | `mistral-small-latest` | `prompts/weekly_schedule.py` | Structured extraction from text — doesn't need heavy reasoning |
| **Speech-to-Text (STT)** | `voxtral-mini-latest` | `stt.py` | Mistral's dedicated audio transcription model |

> **Evals follow the model automatically.** The eval scripts call the real
> production functions, so they run on whatever model that function uses —
> `tests/evals/run_triage_evals.py` exercises **Small** (via `triage_batch`),
> `tests/evals/run_voice_evals.py` exercises **Large** (via `call_voice_mistral`).
> To A/B a model swap, change the one model line in the prompt file and re-run
> the matching eval — no eval changes needed.

## External Services

| Purpose | Service | Config (env var) |
| :--- | :--- | :--- |
| **Text-to-Speech (TTS)** — Marimba's voice | ElevenLabs | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` |

## Tips for Experimenting

- **Want smarter email triage?** Change the one model line in `prompts/email_triage.py` (inside `triage_batch`, look for `model="mistral-small-latest"`) to `model="mistral-large-latest"`. Then run `python -m tests.evals.run_triage_evals` to compare — the eval follows whichever model the file uses. Cost stays tiny because triage is low-volume.
- **Want to turn on reasoning (SDK v1)?** The installed `mistralai` 1.x exposes `prompt_mode="reasoning"` (on/off) on the same `complete_async` call — NOT the granular `reasoning_effort` levels. `reasoning_effort="low|medium|high"` arrived in the **v2 SDK**, which is a breaking upgrade affecting every model call. Decide deliberately before upgrading.
- **Want faster voice replies?** Try changing `prompts/voice.py` from `mistral-large-latest` to `mistral-small-latest`. Trade-off: may miss some actions.
- **Want cheaper priority ranking?** Try `mistral-small-latest` in `mistral_client.py`. The fallback scoring algorithm kicks in if Mistral fails.
- **Want a different voice?** Change `ELEVENLABS_VOICE_ID` in your `.env` file. Browse voices at [elevenlabs.io/voices](https://elevenlabs.io/voices).
