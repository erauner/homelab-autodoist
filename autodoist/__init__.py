"""
Autodoist - GTD automation for Todoist.

Re-exports public API for backwards compatibility with existing tests.
"""

from .api import (
    flatten_paginator,
    get_attr_name,
    get_attr_id,
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
