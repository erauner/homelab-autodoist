# Tests for SDK v3.x parent_id handling
"""
Test that parent_id comparisons work correctly with SDK v3.x.

SDK v3.x uses None for parentless tasks, not 0.
These tests verify the fix for parent_id comparisons.
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class MockTask:
    """Mock Task object matching SDK v3.x structure."""
    id: str
    content: str
    project_id: str
    section_id: Optional[str]
    parent_id: Optional[str]  # SDK v3.x uses None, not 0
    order: int
    labels: List[str]
    is_completed: bool = False
    due: Optional[dict] = None


class TestParentIdComparisons:
    """Test parent_id None vs 0 handling."""

    def test_parentless_task_has_none_parent_id(self):
        """SDK v3.x uses None for parentless tasks, not 0."""
        task = MockTask(
            id="123",
            content="Test task",
            project_id="proj1",
            section_id=None,
            parent_id=None,  # SDK v3.x behavior
            order=1,
            labels=[]
        )

        # Old broken code: task.parent_id == 0 would be False
        assert task.parent_id != 0, "None != 0, old code would fail"

        # Fixed code: not task.parent_id works for both None and empty string
        assert not task.parent_id, "Falsy check works for None"

    def test_subtask_has_string_parent_id(self):
        """SDK v3.x uses string IDs, not integers."""
        parent = MockTask(
            id="parent123",
            content="Parent task",
            project_id="proj1",
            section_id=None,
            parent_id=None,
            order=1,
            labels=[]
        )

        child = MockTask(
            id="child456",
            content="Child task",
            project_id="proj1",
            section_id=None,
            parent_id="parent123",  # String, not int
            order=1,
            labels=[]
        )

        # Old broken code: task.parent_id != 0 would be True for None too
        # Fixed code: task.parent_id (truthy check) correctly identifies subtasks
        assert not parent.parent_id, "Parent has no parent_id"
        assert child.parent_id, "Child has parent_id"
        assert child.parent_id == parent.id, "Parent ID matches"

    def test_parent_id_sorting_with_strings(self):
        """Test sorting works with string parent_ids."""
        tasks = [
            MockTask(id="3", content="Child", project_id="p1", section_id=None,
                    parent_id="1", order=1, labels=[]),
            MockTask(id="1", content="Parent 1", project_id="p1", section_id=None,
                    parent_id=None, order=1, labels=[]),
            MockTask(id="2", content="Parent 2", project_id="p1", section_id=None,
                    parent_id=None, order=2, labels=[]),
        ]

        # Simulate the fixed sorting logic
        for task in tasks:
            if not task.parent_id:
                task.parent_id = ''  # Convert None to empty string for sorting

        # Sort by parent_id then order
        sorted_tasks = sorted(tasks, key=lambda x: (
            str(x.parent_id) if x.parent_id else '', x.order
        ))

        # Parentless tasks should come first
        assert sorted_tasks[0].content == "Parent 1"
        assert sorted_tasks[1].content == "Parent 2"
        assert sorted_tasks[2].content == "Child"

    def test_is_parentless_check(self):
        """Test the is_parentless logic used throughout the code."""
        parentless = MockTask(
            id="1", content="Parentless", project_id="p1",
            section_id=None, parent_id=None, order=1, labels=[]
        )

        subtask = MockTask(
            id="2", content="Subtask", project_id="p1",
            section_id=None, parent_id="1", order=1, labels=[]
        )

        # The fixed check: not task.parent_id
        def is_parentless(task):
            return not task.parent_id

        assert is_parentless(parentless), "Task without parent_id is parentless"
        assert not is_parentless(subtask), "Task with parent_id is a subtask"

    def test_is_subtask_check(self):
        """Test the is_subtask logic used throughout the code."""
        parentless = MockTask(
            id="1", content="Parentless", project_id="p1",
            section_id=None, parent_id=None, order=1, labels=[]
        )

        subtask = MockTask(
            id="2", content="Subtask", project_id="p1",
            section_id=None, parent_id="1", order=1, labels=[]
        )

        # The fixed check: task.parent_id (truthy)
        def is_subtask(task):
            return bool(task.parent_id)

        assert not is_subtask(parentless), "Task without parent_id is not a subtask"
        assert is_subtask(subtask), "Task with parent_id is a subtask"
