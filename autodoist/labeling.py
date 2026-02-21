"""
Core labeling logic for next action management.

This module contains the main labeling algorithm that:
1. Detects type suffixes on projects, sections, and tasks
2. Resolves the dominant type through the hierarchy
3. Applies sequential or parallel labeling rules
4. Handles headers (tasks starting with '*')
5. Respects hide_future settings
"""

from __future__ import annotations
import logging
import re
import time
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

from todoist_api_python.models import Task, Section, Project

from .types import NoSection, normalize_parent_id, is_parentless, pad_type_str_to_three
from .db import MetadataDB
from .singleton import choose_singleton_winner, task_updated_epoch_ms

if TYPE_CHECKING:
    from .config import Config
    from .api import TodoistClient


def parse_type_suffix(
    name: Optional[str],
    s_suffix: str,
    p_suffix: str,
    width: int,
) -> Optional[str]:
    """
    Parse type suffix from a project/section/task name.
    
    Looks for trailing sequences of s_suffix ('-') and p_suffix ('=')
    characters and converts them to a type string.
    
    Args:
        name: The name/content to parse
        s_suffix: Character indicating sequential (default '-')
        p_suffix: Character indicating parallel (default '=')
        width: Max chars to look for (3 for project, 2 for section, 1 for task)
    Returns:
        Type string like 'sss', 'sp', 's', or None if no suffix found
    """
    if name is None:
        return None
    
    try:
        # Match trailing suffix characters
        regex = f'[{re.escape(s_suffix)}{re.escape(p_suffix)}]{{1,{width}}}$'
        match = re.search(regex, name)
        
        if not match:
            return None
        
        suffix = match.group(0)
        
        # Expand short suffixes by repeating last char
        if len(suffix) < width:
            suffix += suffix[-1] * (width - len(suffix))
        
        # Convert to s/p notation
        type_str = ''
        for char in suffix:
            if char == s_suffix:
                type_str += 's'
            elif char == p_suffix:
                type_str += 'p'
        
        # Pad with 'x' prefix to always return 3 chars
        return pad_type_str_to_three(type_str)
        
    except Exception:
        logging.debug("Could not parse type from: %s", name)
        return None


def get_entity_type(
    db: MetadataDB,
    entity_kind: str,
    entity_id: str,
    name: Optional[str],
    s_suffix: str,
    p_suffix: str,
    width: int,
) -> tuple[Optional[str], bool]:
    """
    Get the type for an entity, detecting if it changed.
    
    Args:
        db: Database connection
        entity_kind: 'project', 'section', or 'task'
        entity_id: Entity ID
        name: Entity name/content
        s_suffix: Sequential suffix char
        p_suffix: Parallel suffix char
        width: Suffix width to parse
    Returns:
        Tuple of (type_str, changed) where changed is True if type differs from DB
    """
    # Parse current type from name
    current_type = parse_type_suffix(name, s_suffix, p_suffix, width)
    
    # Get stored type from DB
    old_type = db.get_type_str(entity_kind, str(entity_id))
    
    # Check if changed
    changed = old_type != current_type
    
    if changed:
        db.set_type_str(entity_kind, str(entity_id), current_type)
    
    return current_type, changed


def resolve_dominant_type(
    task_type: Optional[str],
    section_type: Optional[str],
    project_type: Optional[str]
) -> Optional[str]:
    """
    Determine which type controls labeling for a task.
    
    Priority: task_type > section_type > project_type
    
    Returns:
        The dominant type string (3 chars) or None
    """
    if task_type is not None:
        return task_type
    if section_type is not None:
        return section_type
    return project_type


def is_header_task(content: str) -> bool:
    """
    Check if a task is a header (starts with '*').

    Todoist uses '* ' prefix to make tasks uncheckable (headers).
    We also treat any task starting with '*' as a header to match
    the original behavior and avoid labeling tasks like '*important'.
    """
    return content.startswith('*')


def is_section_disabled(section: Section | NoSection) -> bool:
    """
    Check if labeling is disabled for a section.
    
    Sections with names starting or ending with '*' have labeling disabled.
    Useful for Kanban boards where you don't want automatic labels.
    """
    if isinstance(section, NoSection):
        return False
    
    if section.name:
        return section.name.startswith('*') or section.name.endswith('*')
    
    return False


def check_header_command(model: Any) -> tuple[bool, bool, Optional[str]]:
    """
    Check if a model has header/unheader command prefix.
    
    Commands:
    - '** ' prefix: Header all items in this level
    - '-* ' prefix: Unheader all items in this level
    
    Args:
        model: Project, Section, or Task
        
    Returns:
        Tuple of (header_all, unheader_all, new_name) where new_name
        is the name with prefix removed (or None if no command)
    """
    header_all = False
    unheader_all = False
    new_name = None
    
    if isinstance(model, NoSection):
        return False, False, None
    
    # Get name/content
    if isinstance(model, Task):
        text = model.content
    else:
        text = getattr(model, 'name', None)
    
    if not text:
        return False, False, None
    
    # Check for header command
    match_header = re.match(r'^(\*\*\s*)(.*)', text)
    if match_header:
        header_all = True
        new_name = match_header.group(2)
    
    # Check for unheader command
    match_unheader = re.match(r'^(-\*\s*)(.*)', text)
    if match_unheader:
        unheader_all = True
        new_name = match_unheader.group(2)
    
    return header_all, unheader_all, new_name


class LabelingEngine:
    """
    Orchestrates the labeling pass over all projects/sections/tasks.

    This class encapsulates the main labeling algorithm, tracking
    label changes to be applied in a batch.
    """

    def __init__(
        self,
        client: "TodoistClient",
        db: MetadataDB,
        config: "Config"
    ) -> None:
        self.client = client
        self.db = db
        self.config = config

        # Track original labels from SDK (frozen at first access)
        self._original_labels: dict[str, list[str]] = {}
        # Track desired final labels: task_id -> list of labels
        self._desired_labels: dict[str, list[str]] = {}

        # Track first-found flags for sequential labeling
        self._section_found: bool = False
        self._parentless_found: bool = False
    
    def run(self) -> int:
        """
        Run the labeling pass.
        
        Returns:
            Number of label changes queued
        """
        if not self.config.label and not self.config.focus_label:
            return 0
        label = self.config.label
        
        # Fetch all data
        try:
            all_projects = self.client.get_all_projects()
            all_sections = self.client.get_all_sections()
            all_tasks = self.client.get_all_tasks()
        except Exception as e:
            logging.error("Error fetching data: %s", e)
            return 0
        
        if label:
            for project in all_projects:
                # Skip inbox
                if project.is_inbox_project:
                    continue

                self._process_project(
                    project, all_sections, all_tasks, label
                )

        if self.config.focus_label:
            self._reconcile_singleton_label(all_tasks, self.config.focus_label)

        # Commit all DB changes batched during this pass
        self.db.commit()

        # Queue all label updates and return count
        return self._commit_label_changes()

    def _reconcile_singleton_label(self, all_tasks: list[Task], label_name: str) -> None:
        """
        Ensure only one non-completed task keeps the singleton label.

        Winner selection precedence:
        1) Most recent locally-observed assignment (`assigned_at`)
        2) Task `updated_at`
        3) Task ID (stable tie-break)
        """
        candidates: list[Task] = []
        current_active: set[str] = set()

        for task in all_tasks:
            if task.is_completed:
                continue
            labels = self._get_current_labels(task)
            if label_name in labels:
                candidates.append(task)
                current_active.add(str(task.id))

        db_active = set(self.db.get_active_singleton_tasks(label_name))

        # Mark tasks that were previously active but are no longer labeled as inactive.
        for task_id in db_active - current_active:
            self.db.set_singleton_state(label_name, task_id, is_active=False)

        assigned_at_by_task_id: dict[str, Optional[int]] = {}
        now_ms = int(time.time() * 1000)

        # Track currently labeled tasks and persist first-seen activation timestamps.
        for task in candidates:
            task_id = str(task.id)
            assigned_at = self.db.get_singleton_assigned_at(label_name, task_id)
            if task_id not in db_active:
                observed_updated_at = task_updated_epoch_ms(task)
                assigned_at = observed_updated_at if observed_updated_at is not None else now_ms
            assigned_at_by_task_id[task_id] = assigned_at
            self.db.set_singleton_state(
                label_name,
                task_id,
                is_active=True,
                assigned_at=assigned_at,
            )

        if len(candidates) <= 1:
            return

        winner = choose_singleton_winner(
            candidates,
            assigned_at_by_task_id=assigned_at_by_task_id,
        )
        if winner is None:
            return

        winner_id = str(winner.id)
        losers = [task for task in candidates if str(task.id) != winner_id]
        for task in losers:
            self._remove_label(task, label_name)
            self.db.set_singleton_state(label_name, str(task.id), is_active=False)

        logging.info(
            "Found %d tasks with @%s; keeping %s and removing from %d task(s).",
            len(candidates),
            label_name,
            winner_id,
            len(losers),
        )
    
    def _process_project(
        self,
        project: Project,
        all_sections: list[Section],
        all_tasks: list[Task],
        label: str
    ) -> None:
        """Process a single project."""
        # Ensure entity exists in DB
        self.db.ensure_entity('project', str(project.id))
        
        # Check for header commands on project
        header_all_p, unheader_all_p, new_name = check_header_command(project)
        if new_name is not None:
            self.client.update_project_via_rest(project.id, name=new_name)
        
        # Get project type
        project_type, project_type_changed = get_entity_type(
            self.db, 'project', str(project.id), project.name,
            self.config.s_suffix, self.config.p_suffix, 3
        )
        
        if project_type:
            logging.debug("Project '%s' identified as %s type", project.name, project_type)
        
        # Get tasks for this project
        project_tasks = [t for t in all_tasks if t.project_id == project.id]
        
        # If project type changed, clean all tasks in project
        if project_type_changed:
            for task in project_tasks:
                self._remove_label(task, label)
                self.db.clear_task_types(str(task.id))
        
        # Get sections for this project (plus NoSection for sectionless tasks)
        sections: list[Section | NoSection] = [
            s for s in all_sections if s.project_id == project.id
        ]
        sections.insert(0, NoSection(project.id))
        
        # Reset section-level first-found
        self._section_found = False
        
        for section in sections:
            self._process_section(
                section, project, project_tasks, project_type,
                header_all_p, unheader_all_p, label
            )
    
    def _process_section(
        self,
        section: Section | NoSection,
        project: Project,
        project_tasks: list[Task],
        project_type: Optional[str],
        header_all_p: bool,
        unheader_all_p: bool,
        label: str
    ) -> None:
        """Process a single section."""
        # Check if section labeling is disabled
        section_disabled = is_section_disabled(section)
        
        # Ensure entity exists
        if not isinstance(section, NoSection):
            self.db.ensure_entity('section', str(section.id))
        
        # Check for header commands
        header_all_s, unheader_all_s, new_name = check_header_command(section)
        if new_name is not None and not isinstance(section, NoSection):
            self.client.update_section_via_rest(section.id, name=new_name)
        
        # Get section type
        if isinstance(section, NoSection):
            section_type = None
            section_type_changed = False
        else:
            section_type, section_type_changed = get_entity_type(
                self.db, 'section', str(section.id), section.name,
                self.config.s_suffix, self.config.p_suffix, 2
            )
            
            if section_type:
                logging.debug(
                    "Section '%s > %s' identified as %s type",
                    project.name, section.name, section_type
                )
        
        # Get tasks for this section
        section_tasks = [t for t in project_tasks if t.section_id == section.id]

        # Normalize parent_id for sorting: SDK v3.x uses None for parentless tasks.
        # We mutate to '' (empty string) so parentless tasks sort first.
        # Note: is_parentless() handles both None and '' (both are falsy).
        for task in section_tasks:
            if not task.parent_id:
                task.parent_id = ''

        # Sort by parent_id then order
        section_tasks.sort(key=lambda t: (normalize_parent_id(t.parent_id), t.order))
        
        # If section type changed, clean all tasks
        if section_type_changed:
            for task in section_tasks:
                self._remove_label(task, label)
                self.db.clear_task_types(str(task.id))
        
        # Reset parentless first-found
        self._parentless_found = False
        
        # Get non-completed tasks for child lookups
        non_completed = [t for t in section_tasks if not t.is_completed]
        
        for task in section_tasks:
            self._process_task(
                task, section, project, section_tasks, non_completed,
                project_type, section_type, section_disabled,
                header_all_p, unheader_all_p, header_all_s, unheader_all_s,
                label
            )
        
        # Mark section as found if it had tasks
        if section_tasks and not self._section_found:
            self._section_found = True
    
    def _process_task(
        self,
        task: Task,
        section: Section | NoSection,
        project: Project,
        section_tasks: list[Task],
        non_completed: list[Task],
        project_type: Optional[str],
        section_type: Optional[str],
        section_disabled: bool,
        header_all_p: bool,
        unheader_all_p: bool,
        header_all_s: bool,
        unheader_all_s: bool,
        label: str
    ) -> None:
        """Process a single task."""
        # Ensure entity exists
        self.db.ensure_entity('task', str(task.id))
        
        # Get child tasks
        child_tasks_all = [t for t in section_tasks if t.parent_id == task.id]
        child_tasks = [t for t in non_completed if t.parent_id == task.id]
        
        # Check for header commands on task
        header_all_t, unheader_all_t, new_content = check_header_command(task)
        if new_content is not None:
            self.client.update_task_via_rest(task.id, content=new_content)
            task.content = new_content  # Update local copy
        
        # Apply header modifications
        self._apply_header_modifications(
            task, section_tasks,
            header_all_p, unheader_all_p,
            header_all_s, unheader_all_s,
            header_all_t, unheader_all_t
        )
        
        # Skip completed tasks
        if task.is_completed:
            return
        
        # Skip and clean headers and disabled sections
        if is_header_task(task.content) or section_disabled:
            self._remove_label(task, label)
            self.db.clear_task_types(str(task.id))
            
            # Clean all children too
            for child in child_tasks_all:
                self._remove_label(child, label)
                self.db.clear_task_types(str(child.id))
            return
        
        # Get task type
        task_type, task_type_changed = get_entity_type(
            self.db, 'task', str(task.id), task.content,
            self.config.s_suffix, self.config.p_suffix, 1
        )
        
        if task_type:
            logging.debug(
                "Task '%s' identified as %s type",
                task.content, task_type
            )
        
        # If task type changed, clean children
        if task_type_changed:
            for child in child_tasks_all:
                self._remove_label(child, label)
                self.db.clear_task_types(str(child.id))
        
        # Determine if any level has a type
        has_any_type = any([task_type, section_type, project_type])
        
        # If task has label but no type anywhere, remove it (user probably moved it)
        if not has_any_type and label in task.labels:
            self._remove_label(task, label)
            self.db.clear_task_types(str(task.id))
            return
        
        # Handle parentless tasks
        if is_parentless(task.parent_id):
            if not has_any_type:
                return  # No type defined, skip
            
            dominant_type = resolve_dominant_type(task_type, section_type, project_type)
            self._label_parentless_task(task, dominant_type, label)
        
        # Handle tasks with children (subtask cascade)
        if child_tasks:
            self._label_task_with_children(
                task, child_tasks, task_type, section_type, project_type, label
            )
        
        # Apply hide_future logic
        self._apply_hide_future(task, child_tasks, label)
        
        # Mark as first found
        if not self._parentless_found:
            self._parentless_found = True
    
    def _label_parentless_task(
        self,
        task: Task,
        dominant_type: Optional[str],
        label: str
    ) -> None:
        """Apply labeling logic for a parentless task."""
        if dominant_type is None:
            return
        
        # Position 0: section-level behavior
        # Position 1: parentless-task-level behavior
        section_mode = dominant_type[0]
        parentless_mode = dominant_type[1]
        
        # Determine if we should label this task
        should_label = False
        
        if section_mode == 's':
            # Sequential sections: only label in first section
            if not self._section_found:
                if parentless_mode == 's':
                    # Sequential parentless: only first task
                    if not self._parentless_found:
                        should_label = True
                elif parentless_mode == 'p':
                    # Parallel parentless: all tasks
                    should_label = True
        elif section_mode == 'p':
            # Parallel sections: label in all sections
            if parentless_mode == 's':
                if not self._parentless_found:
                    should_label = True
            elif parentless_mode == 'p':
                should_label = True
        elif section_mode == 'x':
            # No section-level override, use parentless mode
            if parentless_mode == 's':
                if not self._parentless_found:
                    should_label = True
            elif parentless_mode == 'p':
                should_label = True
        
        if should_label:
            self._add_label(task, label)
        elif label in task.labels:
            # Task has label but shouldn't - probably moved
            self._remove_label(task, label)
    
    def _label_task_with_children(
        self,
        task: Task,
        child_tasks: list[Task],
        task_type: Optional[str],
        section_type: Optional[str],
        project_type: Optional[str],
        label: str
    ) -> None:
        """Apply labeling cascade to children."""
        # Determine dominant type for subtask handling
        dominant_type: Optional[str] = None
        
        if is_parentless(task.parent_id):
            # Parentless task: resolve through hierarchy
            dominant_type = resolve_dominant_type(task_type, section_type, project_type)
        else:
            # Subtask: inherit from parent or use own type
            if task_type is None:
                # Try to inherit from DB-stored parent type
                stored_parent_type = self.db.get_parent_type(str(task.id))
                if stored_parent_type:
                    # Stored as single char ('s' or 'p'), pad it to 3 chars
                    # Guard: only use first char in case of corruption
                    dominant_type = 'xx' + stored_parent_type[0]

            if dominant_type is None:
                dominant_type = task_type
        
        if dominant_type is None:
            return
        
        # Position 2: subtask-level behavior
        subtask_mode = dominant_type[2]
        
        if subtask_mode == 's':
            # Sequential: label first non-completed child, remove from parent
            labeled_first = False
            for child in child_tasks:
                if is_header_task(child.content):
                    continue
                
                # Remove label from all children first
                self._remove_label(child, label)
                
                # Store parent type for child
                self.db.set_parent_type(str(child.id), subtask_mode)
                
                # Label first child if parent has label
                if not labeled_first and not child.is_completed and label in task.labels:
                    self._add_label(child, label)
                    self._remove_label(task, label)
                    labeled_first = True
                    
        elif subtask_mode == 'p':
            # Parallel: label all children, remove from parent
            if label in task.labels:
                self._remove_label(task, label)
            
            for child in child_tasks:
                if is_header_task(child.content):
                    continue
                
                self.db.set_parent_type(str(child.id), subtask_mode)
                
                if not child.is_completed:
                    self._add_label(child, label)
    
    def _apply_hide_future(
        self,
        task: Task,
        child_tasks: list[Task],
        label: str
    ) -> None:
        """Remove labels from tasks too far in the future."""
        if self.config.hide_future <= 0:
            return
        
        try:
            if task.due and task.due.date:
                due_date = datetime.strptime(task.due.date, "%Y-%m-%d")
                days_until_due = (due_date - datetime.today()).days
                
                if days_until_due >= self.config.hide_future:
                    self._remove_label(task, label)
                    for child in child_tasks:
                        self._remove_label(child, label)
        except Exception:
            pass  # Skip if date parsing fails
    
    def _apply_header_modifications(
        self,
        task: Task,
        section_tasks: list[Task],
        header_all_p: bool,
        unheader_all_p: bool,
        header_all_s: bool,
        unheader_all_s: bool,
        header_all_t: bool,
        unheader_all_t: bool
    ) -> None:
        """Apply header/unheader commands to tasks."""
        # Header from project or section level
        if header_all_p or header_all_s:
            if not task.content.startswith('* '):
                self.client.update_task_via_rest(
                    task.id, content='* ' + task.content
                )
        
        # Unheader from project or section level
        if unheader_all_p or unheader_all_s:
            if task.content.startswith('* '):
                self.client.update_task_via_rest(
                    task.id, content=task.content[2:]
                )
        
        # Header from task level (cascade to children)
        if header_all_t:
            if not task.content.startswith('* '):
                self.client.update_task_via_rest(
                    task.id, content='* ' + task.content
                )
            self._headerify_children(task, section_tasks, header=True)
        
        # Unheader from task level (cascade to children)
        if unheader_all_t:
            if task.content.startswith('* '):
                self.client.update_task_via_rest(
                    task.id, content=task.content[2:]
                )
            self._headerify_children(task, section_tasks, header=False)
    
    def _headerify_children(
        self,
        task: Task,
        section_tasks: list[Task],
        header: bool
    ) -> None:
        """Recursively add or remove header prefix from children."""
        children = [t for t in section_tasks if t.parent_id == task.id]
        
        for child in children:
            if header:
                if not child.content.startswith('* '):
                    self.client.update_task_via_rest(
                        child.id, content='* ' + child.content
                    )
            else:
                if child.content.startswith('* '):
                    self.client.update_task_via_rest(
                        child.id, content=child.content[2:]
                    )
            
            # Recurse to grandchildren
            self._headerify_children(child, section_tasks, header)
    
    def _get_current_labels(self, task: Task) -> list[str]:
        """
        Get current desired labels for a task.

        On first access, stores the original labels from the SDK.
        Returns the tracked desired state, or original if not yet tracked.
        """
        task_id = str(task.id)

        # Store original labels on first access
        if task_id not in self._original_labels:
            self._original_labels[task_id] = list(task.labels)

        # Return desired state if tracked, otherwise original
        return self._desired_labels.get(task_id, list(self._original_labels[task_id]))

    def _add_label(self, task: Task, label: str) -> None:
        """Track addition of a label to a task."""
        task_id = str(task.id)
        current = self._get_current_labels(task)

        if label not in current:
            logging.debug("Adding label to '%s'", task.content)
            current.append(label)
            self._desired_labels[task_id] = current

    def _remove_label(self, task: Task, label: str) -> None:
        """Track removal of a label from a task."""
        task_id = str(task.id)
        current = self._get_current_labels(task)

        if label in current:
            logging.debug("Removing label from '%s'", task.content)
            current.remove(label)
            self._desired_labels[task_id] = current

    def _commit_label_changes(self) -> int:
        """
        Queue all label changes where desired state differs from original.

        Returns:
            Number of tasks with label changes queued
        """
        changes = 0
        for task_id, desired in self._desired_labels.items():
            original = self._original_labels.get(task_id, [])

            # Only queue if labels actually changed
            if set(desired) != set(original):
                self.client.queue_label_update(task_id, desired)
                changes += 1

        return changes


def run_labeling_pass(
    client: "TodoistClient",
    db: MetadataDB,
    config: "Config"
) -> int:
    """
    Run a single labeling pass.
    
    Args:
        client: Todoist API client
        db: Metadata database
        config: Runtime configuration
        
    Returns:
        Number of label changes queued
    """
    engine = LabelingEngine(client, db, config)
    return engine.run()
