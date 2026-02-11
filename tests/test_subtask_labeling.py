# Tests for subtask labeling behavior
"""
Test subtask labeling behavior.

When a parent task has subtasks:
- Sequential: Label cascades to first subtask (the first actionable item)
- Parallel: All subtasks get labeled

This follows GTD methodology where you work on the first actionable item.
"""

import pytest
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class MockTask:
    """Mock Task object."""
    id: str
    content: str
    project_id: str
    section_id: Optional[str]
    parent_id: Optional[str]  # SDK v3.x uses None, not 0
    order: int
    labels: List[str] = field(default_factory=list)
    is_completed: bool = False


class TestSubtaskIdentification:
    """Test subtask identification with SDK v3.x."""

    def test_identify_subtasks_by_parent_id(self):
        """Subtasks have non-None parent_id in SDK v3.x."""
        parent = MockTask(
            id="parent1", content="Parent", project_id="p1",
            section_id=None, parent_id=None, order=1
        )

        child1 = MockTask(
            id="child1", content="Child 1", project_id="p1",
            section_id=None, parent_id="parent1", order=1
        )

        child2 = MockTask(
            id="child2", content="Child 2", project_id="p1",
            section_id=None, parent_id="parent1", order=2
        )

        # Find children of parent
        all_tasks = [parent, child1, child2]
        children = [t for t in all_tasks if t.parent_id == parent.id]

        assert len(children) == 2, "Parent has 2 children"
        assert child1 in children
        assert child2 in children

    def test_find_parentless_tasks(self):
        """Parentless tasks have None parent_id."""
        tasks = [
            MockTask(id="1", content="Parent 1", project_id="p1",
                    section_id=None, parent_id=None, order=1),
            MockTask(id="2", content="Child of 1", project_id="p1",
                    section_id=None, parent_id="1", order=1),
            MockTask(id="3", content="Parent 2", project_id="p1",
                    section_id=None, parent_id=None, order=2),
        ]

        # Fixed check: not task.parent_id (works for None)
        parentless = [t for t in tasks if not t.parent_id]

        assert len(parentless) == 2, "Two parentless tasks"
        assert tasks[0] in parentless
        assert tasks[2] in parentless


class TestSubtaskSequentialLabeling:
    """Test subtask labeling in sequential projects."""

    def test_label_cascades_to_first_subtask(self):
        """In sequential mode, label goes to first subtask, not parent."""
        parent = MockTask(
            id="parent1", content="Parent task", project_id="p1",
            section_id=None, parent_id=None, order=1
        )

        child1 = MockTask(
            id="child1", content="First subtask", project_id="p1",
            section_id=None, parent_id="parent1", order=1
        )

        child2 = MockTask(
            id="child2", content="Second subtask", project_id="p1",
            section_id=None, parent_id="parent1", order=2
        )

        all_tasks = [parent, child1, child2]
        next_action_label = "next_action"
        dominant_type = "s"  # Sequential

        # Find children
        child_tasks = [t for t in all_tasks if t.parent_id == parent.id]

        # Simulate sequential subtask labeling (from autodoist.py ~line 1456)
        if dominant_type == 's' and len(child_tasks) > 0:
            # Sort children by order
            child_tasks = sorted(child_tasks, key=lambda x: x.order)

            # Label first incomplete child
            for child in child_tasks:
                if not child.is_completed:
                    child.labels.append(next_action_label)
                    break

        # Verify: first child gets label, not parent
        assert next_action_label not in parent.labels, "Parent not labeled"
        assert next_action_label in child1.labels, "First child labeled"
        assert next_action_label not in child2.labels, "Second child not labeled"

    def test_second_subtask_labeled_after_first_complete(self):
        """When first subtask is done, second gets labeled."""
        parent = MockTask(
            id="parent1", content="Parent task", project_id="p1",
            section_id=None, parent_id=None, order=1
        )

        child1 = MockTask(
            id="child1", content="First subtask", project_id="p1",
            section_id=None, parent_id="parent1", order=1,
            is_completed=True  # Already done
        )

        child2 = MockTask(
            id="child2", content="Second subtask", project_id="p1",
            section_id=None, parent_id="parent1", order=2
        )

        all_tasks = [parent, child1, child2]
        next_action_label = "next_action"

        # Find children
        child_tasks = sorted(
            [t for t in all_tasks if t.parent_id == parent.id],
            key=lambda x: x.order
        )

        # Label first incomplete child
        for child in child_tasks:
            if not child.is_completed:
                child.labels.append(next_action_label)
                break

        assert next_action_label not in child1.labels, "Completed child not labeled"
        assert next_action_label in child2.labels, "Second child now labeled"


class TestSubtaskParallelLabeling:
    """Test subtask labeling in parallel projects."""

    def test_all_subtasks_labeled_in_parallel(self):
        """In parallel mode, all subtasks get labeled."""
        parent = MockTask(
            id="parent1", content="Parent task", project_id="p1",
            section_id=None, parent_id=None, order=1
        )

        child1 = MockTask(
            id="child1", content="Subtask 1", project_id="p1",
            section_id=None, parent_id="parent1", order=1
        )

        child2 = MockTask(
            id="child2", content="Subtask 2", project_id="p1",
            section_id=None, parent_id="parent1", order=2
        )

        all_tasks = [parent, child1, child2]
        next_action_label = "next_action"
        dominant_type = "p"  # Parallel

        # Find children
        child_tasks = [t for t in all_tasks if t.parent_id == parent.id]

        # Simulate parallel subtask labeling
        if dominant_type == 'p' and len(child_tasks) > 0:
            for child in child_tasks:
                if not child.is_completed:
                    child.labels.append(next_action_label)

        # Verify: all children get labels
        assert next_action_label in child1.labels, "Child 1 labeled"
        assert next_action_label in child2.labels, "Child 2 labeled"


class TestNestedSubtasks:
    """Test deeply nested subtask handling."""

    def test_nested_subtasks_sdk_v3x(self):
        """Test that nested subtasks work with string parent_ids."""
        parent = MockTask(
            id="parent1", content="Parent", project_id="p1",
            section_id=None, parent_id=None, order=1
        )

        child = MockTask(
            id="child1", content="Child", project_id="p1",
            section_id=None, parent_id="parent1", order=1
        )

        grandchild = MockTask(
            id="grandchild1", content="Grandchild", project_id="p1",
            section_id=None, parent_id="child1", order=1
        )

        all_tasks = [parent, child, grandchild]

        # Build parent-child relationships
        def get_children(task_id, tasks):
            return [t for t in tasks if t.parent_id == task_id]

        parent_children = get_children(parent.id, all_tasks)
        child_children = get_children(child.id, all_tasks)

        assert len(parent_children) == 1, "Parent has 1 child"
        assert parent_children[0].id == "child1"

        assert len(child_children) == 1, "Child has 1 grandchild"
        assert child_children[0].id == "grandchild1"

        # Verify parent_id chain (all strings in SDK v3.x)
        assert parent.parent_id is None, "Parent has no parent"
        assert child.parent_id == "parent1", "Child -> Parent"
        assert grandchild.parent_id == "child1", "Grandchild -> Child"
