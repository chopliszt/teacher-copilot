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
) -> Optional[List[str]]:
    """
    Ask Mistral to rank the top 3 task IDs.

    Returns None immediately if MISTRAL_API_KEY is not set or on any error,
    allowing the caller to fall back to the scoring algorithm.

    Args:
        tasks: All pending tasks
        schedule_data: Teacher schedule data
        current_time: Current datetime

    Returns:
        Optional[List[str]]: Ordered list of 3 task IDs, or None
    """
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return None

    try:
        from mistralai import Mistral

        client = Mistral(api_key=api_key)
        prompt = build_context(tasks, schedule_data, current_time)

        response = await client.chat.complete_async(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        parsed = json.loads(content)
        task_ids = parsed.get("task_ids", [])

        if isinstance(task_ids, list) and len(task_ids) == 3:
            return [str(tid) for tid in task_ids]

        return None

    except Exception:
        return None
