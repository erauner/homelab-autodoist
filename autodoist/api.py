"""
Todoist API wrapper.

Encapsulates REST API, Sync API, and SDK interactions.
Provides queue management for batching label updates.
"""

from __future__ import annotations
import json
import logging
import time
from typing import Any, Optional, TYPE_CHECKING

import requests
from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Task, Section, Project

from .types import get_attr_name, get_attr_id

if TYPE_CHECKING:
    pass

# Re-export helpers for backwards compatibility
__all__ = [
    'flatten_paginator',
    'get_attr_name',
    'get_attr_id',
    'initialise_sync_api',
    'verify_label_existance',
    'TodoistClient',
]


def flatten_paginator(paginator: Any) -> list[Any]:
    """
    Flatten SDK v3.x ResultsPaginator into a list.
    
    SDK v3.x returns ResultsPaginator objects instead of lists.
    Iterating over a paginator yields pages (lists of items).
    This function flattens all pages into a single list.
    
    Args:
        paginator: A ResultsPaginator or list from the SDK
        
    Returns:
        Flattened list of all items
    """
    result = []
    try:
        for page in paginator:
            if isinstance(page, list):
                result.extend(page)
            else:
                # Single item or different format
                result.append(page)
    except TypeError:
        # Not iterable, return as-is wrapped in list
        if paginator is not None:
            result = [paginator] if not isinstance(paginator, list) else paginator
    return result


def initialise_sync_api(api: TodoistAPI, api_token: str) -> dict[str, Any]:
    """
    Perform initial full sync with Todoist Sync API.
    
    Args:
        api: TodoistAPI instance (not used directly, kept for compatibility)
        api_token: Todoist API token
        
    Returns:
        Dict containing sync_token and other sync data
        
    Raises:
        KeyError: If response doesn't contain sync_token
        requests.HTTPError: If API request fails
    """
    bearer_token = f'Bearer {api_token}'
    
    headers = {
        'Authorization': bearer_token,
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = 'sync_token=*&resource_types=["all"]'
    
    try:
        response = requests.post(
            'https://api.todoist.com/api/v1/sync',
            headers=headers,
            data=data
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logging.error("HTTP error during sync API init: %s", e)
        logging.error("Response: %s", response.text)
        raise
    except Exception as e:
        logging.error("Error during sync API init: %s", e)
        raise
    
    result = json.loads(response.text)
    
    if 'sync_token' not in result:
        logging.error(
            "Unexpected API response - missing sync_token. Keys: %s",
            list(result.keys())
        )
        raise KeyError("sync_token not found in API response")
    
    return result


def verify_label_existance(
    api: TodoistAPI,
    label_name: str,
    prompt_mode: int = 2
) -> list[Any]:
    """
    Verify that a label exists, creating it if necessary.
    
    Note: Historical misspelling of 'existence' preserved for compatibility.
    
    Args:
        api: TodoistAPI instance
        label_name: Name of the label to verify/create
        prompt_mode: 0 = fail if missing, 1 = prompt (now auto-creates), 2 = auto-create
        
    Returns:
        List of all labels
    """
    labels = flatten_paginator(api.get_labels())
    label = [x for x in labels if get_attr_name(x) == label_name]
    
    if len(label) > 0:
        label_id = get_attr_id(label[0])
        logging.debug("Label '%s' found as id %s", label_name, label_id)
    else:
        logging.info("\n\nLabel '%s' doesn't exist in your Todoist\n", label_name)
        
        if prompt_mode == 0:
            logging.error("Label '%s' not found and auto-create disabled", label_name)
            raise ValueError(f"Label '{label_name}' not found")
        
        # Auto-create the label (no interactive prompt)
        try:
            api.add_label(name=label_name)
            logging.info("Label '%s' has been created!", label_name)
        except Exception as error:
            logging.warning("Error creating label: %s", error)
            raise
        
        # Refresh labels list
        labels = flatten_paginator(api.get_labels())
    
    return labels


class TodoistClient:
    """
    High-level Todoist client with queue management.
    
    Wraps the SDK and Sync API, providing:
    - Automatic pagination flattening
    - Batched label updates via sync queue
    - Consistent error handling
    """
    
    def __init__(self, api_key: str) -> None:
        """
        Initialize the client.
        
        Args:
            api_key: Todoist API key
        """
        self.api_key = api_key
        self.api = TodoistAPI(token=api_key)
        self.sync_token: str = "*"
        self._queue: list[dict[str, Any]] = []
        self._updated_ids: list[str] = []  # Track IDs updated via REST API
    
    def initial_sync(self) -> None:
        """Perform initial sync to get sync token."""
        sync_result = initialise_sync_api(self.api, self.api_key)
        self.sync_token = sync_result['sync_token']
        logging.info("Autodoist has successfully connected to Todoist!")
    
    def ensure_label_exists(self, label_name: str) -> None:
        """Ensure a label exists, creating it if necessary."""
        verify_label_existance(self.api, label_name, prompt_mode=2)
    
    def get_all_projects(self) -> list[Project]:
        """Get all projects as a flat list."""
        return flatten_paginator(self.api.get_projects())
    
    def get_all_sections(self) -> list[Section]:
        """Get all sections as a flat list."""
        return flatten_paginator(self.api.get_sections())
    
    def get_all_tasks(self) -> list[Task]:
        """Get all tasks as a flat list."""
        return flatten_paginator(self.api.get_tasks())
    
    def get_labels(self) -> list[Any]:
        """Get all labels as a flat list."""
        return flatten_paginator(self.api.get_labels())
    
    def queue_label_update(self, task_id: str, labels: list[str]) -> None:
        """
        Queue a label update for batch sync.
        
        Args:
            task_id: ID of the task to update
            labels: New complete labels list for the task
        """
        uuid = str(time.perf_counter())
        data = {
            "type": "item_update",
            "uuid": uuid,
            "args": {"id": task_id, "labels": labels}
        }
        self._queue.append(data)
    
    def update_task_via_rest(self, task_id: str, **kwargs: Any) -> None:
        """
        Update a task immediately via REST API.
        
        Used for header modifications that need immediate effect.
        """
        try:
            self.api.update_task(task_id=task_id, **kwargs)
            self._updated_ids.append(task_id)
        except Exception as e:
            logging.warning("Error updating task %s: %s", task_id, e)
    
    def update_section_via_rest(self, section_id: str, **kwargs: Any) -> None:
        """Update a section immediately via REST API."""
        try:
            self.api.update_section(section_id=section_id, **kwargs)
            self._updated_ids.append(section_id)
        except Exception as e:
            logging.warning("Error updating section %s: %s", section_id, e)
    
    def update_project_via_rest(self, project_id: str, **kwargs: Any) -> None:
        """Update a project immediately via REST API."""
        try:
            self.api.update_project(project_id=project_id, **kwargs)
            self._updated_ids.append(project_id)
        except Exception as e:
            logging.warning("Error updating project %s: %s", project_id, e)
    
    def flush_queue(self) -> int:
        """
        Sync all queued changes to Todoist.
        
        Returns:
            Number of changes synced (queue items + REST updates)
        """
        num_changes = len(self._queue) + len(self._updated_ids)
        
        if not self._queue:
            # Reset tracking
            self._updated_ids.clear()
            return num_changes
        
        try:
            bearer_token = f'Bearer {self.api_key}'
            
            headers = {
                'Authorization': bearer_token,
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            data = f'sync_token={self.sync_token}&commands={json.dumps(self._queue)}'
            
            response = requests.post(
                'https://api.todoist.com/api/v1/sync',
                headers=headers,
                data=data
            )
            
            if response.status_code == 200:
                result = response.json()
                # Update sync token if provided
                if 'sync_token' in result:
                    self.sync_token = result['sync_token']
            else:
                response.raise_for_status()
                
        except Exception as e:
            logging.exception('Error syncing with Todoist API: %s', e)
            raise
        finally:
            # Clear queue after sync attempt
            self._queue.clear()
            self._updated_ids.clear()
        
        return num_changes
    
    @property
    def pending_changes(self) -> int:
        """Number of changes pending in the queue."""
        return len(self._queue) + len(self._updated_ids)
