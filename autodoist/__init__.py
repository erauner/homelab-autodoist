"""
Autodoist - GTD automation for Todoist.

Re-exports public API for backwards compatibility with existing tests.
"""

# Import from canonical modules for explicit dependency chain
from .types import get_attr_name, get_attr_id
from .api import (
    flatten_paginator,
    initialise_sync_api,
    verify_label_existance,  # Note: historical misspelling preserved for compatibility
)

__version__ = "2.0.0"
__all__ = [
    "flatten_paginator",
    "get_attr_name",
    "get_attr_id",
    "initialise_sync_api",
    "verify_label_existance",
]
