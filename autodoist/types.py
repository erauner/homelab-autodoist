"""
Shared types, helpers, and SDK v3.x compatibility shims.

Type String Convention
======================
A type_str is a 1-3 character string from {s, p, x} that controls labeling behavior:

For projects (3 chars):
  - Position 0: How sections are processed ('s' = first section only, 'p' = all sections)
  - Position 1: How parentless tasks within a section are processed  
  - Position 2: How subtasks under a task are processed

For sections (2 chars, prefixed with 'x'):
  - Position 1: How parentless tasks are processed
  - Position 2: How subtasks are processed

For tasks (1 char, prefixed with 'xx'):
  - Position 2: How subtasks are processed

Meanings:
  - 's' = sequential (only first actionable item gets label)
  - 'p' = parallel (all actionable items get labels)
  - 'x' = inherit from parent level / no override

Examples:
  - 'sss' = sequential at all levels (project ending with '---')
  - 'ppp' = parallel at all levels (project ending with '===')
  - 'xsp' = no project-level override, sequential parentless tasks, parallel subtasks
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional, Any, Protocol, TypeAlias


# Type aliases
EntityKind: TypeAlias = Literal["project", "section", "task"]
TypeChar: TypeAlias = Literal["s", "p", "x"]
TaskId: TypeAlias = str
LabelName: TypeAlias = str


class HasId(Protocol):
    """Protocol for objects with an id attribute."""
    id: str | int


class HasName(Protocol):
    """Protocol for objects with a name attribute."""
    name: str


class NoSection:
    """
    Placeholder for tasks not in any section (SDK v3.x compatible).
    
    The Todoist SDK v3.x Section class requires specific arguments,
    so we use this placeholder for project-level tasks that don't
    belong to any section.
    """
    
    def __init__(self, project_id: str) -> None:
        self.id: Optional[str] = None
        self.name: Optional[str] = None
        self.project_id = project_id
        self.is_collapsed = False
        self.order = 0


def get_attr_name(x: Any) -> Optional[str]:
    """
    Get name from object or dict.
    
    Works with SDK model objects, dicts from Sync API, or any object
    with a 'name' attribute.
    """
    if hasattr(x, 'name'):
        return x.name
    elif isinstance(x, dict):
        return x.get('name')
    return None


def get_attr_id(x: Any) -> Optional[str]:
    """
    Get id from object or dict.
    
    Works with SDK model objects, dicts from Sync API, or any object
    with an 'id' attribute.
    """
    if hasattr(x, 'id'):
        return x.id
    elif isinstance(x, dict):
        return x.get('id')
    return None


def normalize_parent_id(parent_id: Optional[str]) -> str:
    """
    Normalize parent_id for sorting.
    
    SDK v3.x uses None for parentless tasks (not 0 like older versions).
    This converts None to empty string so parentless tasks sort first.
    """
    return '' if parent_id is None else str(parent_id)


def is_parentless(parent_id: Optional[str]) -> bool:
    """
    Check if a task is parentless (top-level in section).

    Handles both SDK v3.x behavior (None for parentless) and the normalized
    form used in labeling ('' empty string for sorting). Both are falsy.
    """
    return not parent_id


def is_subtask(parent_id: Optional[str]) -> bool:
    """Check if a task is a subtask (has a parent)."""
    return bool(parent_id)


def expand_type_str(type_str: Optional[str], width: int = 3) -> Optional[str]:
    """
    Expand a shortened type string to full width.
    
    If fewer characters than width are provided, the last character
    is repeated to fill. E.g., for width=3:
      - '=' -> 'ppp' (if '=' maps to 'p')
      - 'sp' -> 'spp'
      - 'sps' -> 'sps' (already full width)
    
    Args:
        type_str: The type string to expand (already converted to s/p chars)
        width: Target width (3 for projects, 2 for sections, 1 for tasks)
    
    Returns:
        Expanded type string or None if input is None
    """
    if type_str is None or len(type_str) == 0:
        return None
    
    if len(type_str) >= width:
        return type_str[:width]
    
    # Pad with last character
    return type_str + type_str[-1] * (width - len(type_str))


def pad_type_str_to_three(type_str: Optional[str]) -> Optional[str]:
    """
    Pad a type string with 'x' prefix to make it 3 characters.
    
    This ensures consistent indexing:
      - Position 0: section-level behavior
      - Position 1: parentless-task-level behavior  
      - Position 2: subtask-level behavior
    
    Examples:
      - 'sps' -> 'sps' (project type, already 3 chars)
      - 'sp' -> 'xsp' (section type, 2 chars)
      - 's' -> 'xxs' (task type, 1 char)
    """
    if type_str is None:
        return None
    
    if len(type_str) >= 3:
        return type_str[:3]
    elif len(type_str) == 2:
        return 'x' + type_str
    elif len(type_str) == 1:
        return 'xx' + type_str
    else:
        return None


@dataclass(frozen=True)
class LabelChanges:
    """Tracks label changes to be applied in a batch."""
    
    # task_id -> new full labels list
    to_update: dict[str, list[str]]
    # Count of add operations per task
    add_count: dict[str, int]
    # Count of remove operations per task
    remove_count: dict[str, int]
    
    @classmethod
    def empty(cls) -> "LabelChanges":
        return cls(to_update={}, add_count={}, remove_count={})
