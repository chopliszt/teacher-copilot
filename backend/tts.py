"""
ElevenLabs TTS — converts Marimba's text responses to speech.

Requires:
  ELEVENLABS_API_KEY  — ElevenLabs API key
  ELEVENLABS_VOICE_ID — Voice ID for Marimba's consistent persona

Falls back gracefully (returns None) when either variable is missing.
The frontend plays audio only when audio is present; otherwise just shows
the text response.
"""

import base64
import os
from typing import Optional


async def text_to_speech(text: str) -> Optional[str]:
    """
    Convert text to speech using the ElevenLabs API.

    Args:
        text: The text Marimba should speak (1–3 sentences)

    Returns:
        Optional[str]: Base64-encoded MP3 audio string, or None if not configured
                       or if the API call fails.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID")

    if not api_key or not voice_id:
        return None

    try:
        import httpx

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    },
                },
                timeout=20.0,
            )

        if response.status_code == 200:
            return base64.b64encode(response.content).decode("utf-8")

        return None

    except Exception as e:
        print(f"TTS Error: {e}")
        return None
