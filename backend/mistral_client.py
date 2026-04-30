#!/usr/bin/env python3
"""
Mistral Client — makes the AI API call for task prioritization.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from context_builder import build_context


async def call_mistral(
    tasks: List[Dict[str, Any]],
    schedule_data: Dict[str, Any],
    current_time: datetime,
    weekly_data: Optional[Dict[str, Any]] = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    Ask Mistral to rank the top 3 tasks with reasons.

    Returns None immediately if MISTRAL_API_KEY is not set or on any error,
    allowing the caller to fall back to the scoring algorithm.

    Args:
        tasks: All pending tasks
        schedule_data: Teacher schedule data
        current_time: Current datetime
        weekly_data: Extracted weekly schedule for richer context

    Returns:
        Optional[List[Dict]]: List of 3 dicts with {"id": str, "reason": str}, or None
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return None

    try:
        from mistralai import Mistral

        client = Mistral(api_key=api_key)
        prompt = build_context(tasks, schedule_data, current_time, weekly_data=weekly_data)

        response = await client.chat.complete_async(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        parsed = json.loads(content)
        priorities = parsed.get("priorities", [])

        if (
            isinstance(priorities, list)
            and len(priorities) == 3
            and all(isinstance(p, dict) and "id" in p and "reason" in p for p in priorities)
        ):
            return [{"id": str(p["id"]), "reason": str(p["reason"])} for p in priorities]

        return None

    except Exception as e:
        print(f"[Mistral] Error during priority ranking: {type(e).__name__}: {e}")
        return None
