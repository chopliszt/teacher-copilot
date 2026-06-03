"""
Shared helper for parsing reasoning-mode chat responses.

When a Mistral call sets ``reasoning_effort`` (Mistral Small 4 and the reasoning
models), the model may (a) return ``message.content`` as a LIST of chunks — a
``thinking`` chunk followed by a ``text`` chunk — instead of a plain string, and
/or (b) prepend a ``<think>...</think>`` block before the JSON. A plain
``json.loads(content)`` chokes on either. ``response_to_json_text`` normalises
both shapes (and the ordinary plain-string case) down to the JSON text payload:
keep only text chunks, strip any inline think block, then isolate the outermost
``{ ... }`` so stray prose can't break the parse.
"""

import re
from typing import Any


def response_to_json_text(content: Any) -> str:
    # 1. Flatten list-of-chunks (reasoning) down to its text parts.
    if isinstance(content, str):
        text = content
    else:
        parts: list[str] = []
        for chunk in content or []:
            ctype = getattr(chunk, "type", None)
            piece = getattr(chunk, "text", None)
            if ctype is None and isinstance(chunk, dict):
                ctype = chunk.get("type")
                piece = chunk.get("text")
            # Skip 'thinking'/'reasoning' chunks; keep text (or untyped) ones.
            if ctype in (None, "text") and piece:
                parts.append(piece)
        text = "".join(parts)

    # 2. Drop any <think>...</think> the model emitted inline.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # 3. Isolate the outermost JSON object so stray prose can't break the parse.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return text
