# 🧠 Model Registry — TeacherPilot

All AI models and external services used in the project, centralized in one place.
When experimenting with different models, update this file and the corresponding source code.

## Mistral AI Models

| Purpose | Model | File | Why this model? |
| :--- | :--- | :--- | :--- |
| **Voice / Function Calling** (Marimba's brain) | `mistral-large-latest` | `prompts/voice.py` | Needs strong reasoning to understand intent and pick the right action |
| **Priority Ranking** | `mistral-large-latest` | `mistral_client.py` | Needs to reason about urgency, deadlines, and teacher context |
| **Email Triage** | `mistral-small-latest` | `prompts/email_triage.py` | Classification task — smaller model is fast and cheap enough |
| **Weekly Schedule Extraction** | `mistral-small-latest` | `prompts/weekly_schedule.py` | Structured extraction from text — doesn't need heavy reasoning |
| **Speech-to-Text (STT)** | `voxtral-mini-latest` | `stt.py` | Mistral's dedicated audio transcription model |

## External Services

| Purpose | Service | Config (env var) |
| :--- | :--- | :--- |
| **Text-to-Speech (TTS)** — Marimba's voice | ElevenLabs | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` |

## Tips for Experimenting

- **Want faster voice replies?** Try changing `prompts/voice.py` from `mistral-large-latest` to `mistral-small-latest`. Trade-off: may miss some actions.
- **Want cheaper priority ranking?** Try `mistral-small-latest` in `mistral_client.py`. The fallback scoring algorithm kicks in if Mistral fails.
- **Want a different voice?** Change `ELEVENLABS_VOICE_ID` in your `.env` file. Browse voices at [elevenlabs.io/voices](https://elevenlabs.io/voices).
