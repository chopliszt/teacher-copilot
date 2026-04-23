"""
Voxtral STT — transcribes audio using Mistral's Voxtral Mini model.

Uses the same MISTRAL_API_KEY as the rest of the app — no extra credentials.
Model: voxtral-mini-latest  ($0.003/min — very cheap for short teacher queries)
"""

import os
from typing import Optional


async def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "recording.webm",
    language: Optional[str] = None,
) -> Optional[str]:
    """
    Transcribe audio bytes using Voxtral Mini.

    Args:
        audio_bytes: Raw audio from the browser (WebM/Opus or MP4/AAC on Safari)
        filename: Original filename — used to hint the audio format to the API
        language: Optional BCP-47 hint (e.g. "en", "es"). If None, Voxtral
                  auto-detects — preferred since the model is multilingual and
                  forcing a hint can hurt accuracy for mixed-language audio.

    Returns:
        Optional[str]: Transcribed text, or None on error / missing key
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key or not audio_bytes:
        return None

    try:
        from mistralai import Mistral

        client = Mistral(api_key=api_key)

        call_kwargs: dict = {
            "model": "voxtral-mini-latest",
            "file": {"content": audio_bytes, "file_name": filename},
            "timeout_ms": 180_000,  # 3-minute hard timeout on the API call itself
        }
        if language:
            call_kwargs["language"] = language

        print(f"[STT] Calling Voxtral for {filename} ({len(audio_bytes):,} bytes)…")
        response = await client.audio.transcriptions.complete_async(**call_kwargs)

        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            print(f"[STT] Transcription OK — {len(text.strip())} chars")
            return text.strip()

        print(f"[STT] Voxtral returned empty text for {filename}")
        return None

    except Exception as e:
        print(f"[STT] Error: {type(e).__name__}: {e}")
        return None
