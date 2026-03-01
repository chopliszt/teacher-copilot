"""
Voxtral STT — transcribes audio using Mistral's Voxtral Mini model.

Uses the same MISTRAL_API_KEY as the rest of the app — no extra credentials.
Model: voxtral-mini-latest  ($0.003/min — very cheap for short teacher queries)
"""

import os
from typing import Optional


async def transcribe_audio(
    audio_bytes: bytes, filename: str = "recording.webm"
) -> Optional[str]:
    """
    Transcribe audio bytes using Voxtral Mini.

    Args:
        audio_bytes: Raw audio from the browser (WebM/Opus or MP4/AAC on Safari)
        filename: Original filename — used to hint the audio format

    Returns:
        Optional[str]: Transcribed text, or None on error / missing key
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key or not audio_bytes:
        return None

    try:
        from mistralai import Mistral

        client = Mistral(api_key=api_key)

        response = await client.audio.transcriptions.complete_async(
            model="voxtral-mini-latest",
            file={"content": audio_bytes, "file_name": filename},  # bytes, not BytesIO
            language="en",  # English
        )

        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        return None

    except Exception as e:
        print(f"STT Error: {e}")
        return None
