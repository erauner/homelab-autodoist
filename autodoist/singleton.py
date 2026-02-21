"""
Shared helpers for singleton-label reconciliation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def parse_iso8601_to_epoch_ms(ts: Optional[str]) -> Optional[int]:
    """Parse an ISO-8601 timestamp string to epoch milliseconds."""
    if not ts:
        return None
    try:
        value = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)
    except (ValueError, TypeError):
        return None


def normalize_task_id(task_id: Any) -> str:
    return str(task_id)


def task_updated_epoch_ms(task: Any) -> Optional[int]:
    """Best-effort updated-at extraction from dicts or SDK model objects."""
    updated_at = task.get("updated_at") if isinstance(task, dict) else getattr(task, "updated_at", None)
    if isinstance(updated_at, datetime):
        parsed = updated_at if updated_at.tzinfo is not None else updated_at.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)
    if isinstance(updated_at, str):
        return parse_iso8601_to_epoch_ms(updated_at)
    return None


def choose_singleton_winner(
    tasks: list[Any],
    *,
    sticky_task_id: Optional[str] = None,
    assigned_at_by_task_id: Optional[dict[str, Optional[int]]] = None,
    preferred_task_id: Optional[str] = None,
) -> Optional[Any]:
    """Pick singleton winner deterministically."""
    if not tasks:
        return None

    if preferred_task_id is not None:
        for task in tasks:
            task_id = normalize_task_id(task["id"] if isinstance(task, dict) else getattr(task, "id"))
            if task_id == preferred_task_id:
                return task

    if sticky_task_id is not None:
        for task in tasks:
            task_id = normalize_task_id(task["id"] if isinstance(task, dict) else getattr(task, "id"))
            if task_id == sticky_task_id:
                return task

    assigned_lookup = assigned_at_by_task_id or {}

    def rank(task: Any) -> tuple[int, int, str]:
        task_id = normalize_task_id(task["id"] if isinstance(task, dict) else getattr(task, "id"))
        assigned_at = assigned_lookup.get(task_id)
        assigned_rank = assigned_at if assigned_at is not None else -1
        updated_rank = task_updated_epoch_ms(task)
        return (assigned_rank, updated_rank if updated_rank is not None else -1, task_id)

    return max(tasks, key=rank)

