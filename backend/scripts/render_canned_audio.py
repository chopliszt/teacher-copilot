"""
One-off script to render Marimba's canned voice responses to MP3.

Why: these responses fire on common UI events (email sent, etc.) and never
change — paying ElevenLabs per playback is wasteful and adds latency. We
render once, commit the MP3, and the frontend plays it as a static asset.

Run from backend/:
    python scripts/render_canned_audio.py

Requires ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in env (loaded from .env).
"""

import asyncio
import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from tts import text_to_speech

load_dotenv()

OUTPUT_DIR = Path(__file__).parent.parent.parent / "frontend" / "public" / "audio"

CANNED = {
    "email_sent.mp3": "Listo profe, el correo fue enviado.",
}


async def render_one(filename: str, text: str) -> bool:
    print(f"  → rendering {filename}: {text!r}")
    encoded = await text_to_speech(text)
    if not encoded:
        print(f"     ✗ failed (check ELEVENLABS_API_KEY / VOICE_ID)")
        return False
    audio_bytes = base64.b64decode(encoded)
    out_path = OUTPUT_DIR / filename
    out_path.write_bytes(audio_bytes)
    print(f"     ✓ wrote {len(audio_bytes)} bytes to {out_path}")
    return True


async def main() -> None:
    if not os.getenv("ELEVENLABS_API_KEY") or not os.getenv("ELEVENLABS_VOICE_ID"):
        print("ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID must be set.")
        sys.exit(1)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Rendering canned audio to {OUTPUT_DIR}")
    results = await asyncio.gather(*(render_one(f, t) for f, t in CANNED.items()))
    if not all(results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
