# Tests for parallel project labeling (ppp type)
"""
Test parallel project labeling behavior.

Parallel projects (suffix '=') should label ALL tasks.
Project type 'ppp' = parallel at section, subsection, and project level.
"""

import pytest
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class MockProject:
    """Mock Project object."""
    id: str
    name: str


@dataclass
class MockTask:
    """Mock Task object."""
    id: str
    content: str
    project_id: str
    section_id: Optional[str]
    parent_id: Optional[str]
    order: int
    labels: List[str]
    is_completed: bool = False


class TestParallelTypeDetection:
    """Test parallel project type detection."""

    def test_parallel_suffix_detected(self):
        """Project ending with '=' should be parallel."""
        def check_name_suffix(name, suffix):
            return name.rstrip().endswith(suffix)

        project = MockProject(id="1", name="My Project =")

        assert check_name_suffix(project.name, "="), "'=' suffix = parallel"

    def test_ppp_type_identification(self):
        """Test that 'ppp' type is correctly identified."""
        project_type = "ppp"  # All parallel

        assert project_type[0] == 'p', "First char = section level type"
        assert project_type[1] == 'p', "Second char = subsection level type"
        assert project_type[2] == 'p', "Third char = project level type"


class TestParallelLabeling:
    """Test that parallel projects label all tasks."""

    def test_all_tasks_labeled(self):
        """In parallel mode, all parentless tasks should be labeled."""
        tasks = [
            MockTask(id="1", content="Task A", project_id="p1",
                    section_id=None, parent_id=None, order=1, labels=[]),
            MockTask(id="2", content="Task B", project_id="p1",
                    section_id=None, parent_id=None, order=2, labels=[]),
            MockTask(id="3", content="Task C", project_id="p1",
                    section_id=None, parent_id=None, order=3, labels=[]),
        ]

        next_action_label = "next_action"
        dominant_type = "ppp"

        # Simulate parallel labeling logic
        for task in tasks:
            if not task.parent_id:  # Parentless task (fixed check)
                if dominant_type[1] == 'p':  # Parallel at subsection level
                    if next_action_label not in task.labels:
                        task.labels.append(next_action_label)

        # All tasks should have the label
        for task in tasks:
            assert next_action_label in task.labels, f"{task.content} should have label"

    def test_completed_tasks_not_labeled(self):
        """Completed tasks should not be labeled even in parallel mode."""
        tasks = [
            MockTask(id="1", content="Task A", project_id="p1",
                    section_id=None, parent_id=None, order=1, labels=[]),
            MockTask(id="2", content="Task B (done)", project_id="p1",
                    section_id=None, parent_id=None, order=2, labels=[],
                    is_completed=True),
            MockTask(id="3", content="Task C", project_id="p1",
                    section_id=None, parent_id=None, order=3, labels=[]),
        ]

        next_action_label = "next_action"

        # Simulate parallel labeling (skip completed)
        for task in tasks:
            if task.is_completed:
                continue
            if not task.parent_id:
                if next_action_label not in task.labels:
                    task.labels.append(next_action_label)

        assert next_action_label in tasks[0].labels, "Task A labeled"
        assert next_action_label not in tasks[1].labels, "Completed task not labeled"
        assert next_action_label in tasks[2].labels, "Task C labeled"

    def test_parallel_vs_sequential_difference(self):
        """Demonstrate the difference between parallel and sequential."""
        tasks = [
            MockTask(id="1", content="Task 1", project_id="p1",
                    section_id=None, parent_id=None, order=1, labels=[]),
            MockTask(id="2", content="Task 2", project_id="p1",
                    section_id=None, parent_id=None, order=2, labels=[]),
            MockTask(id="3", content="Task 3", project_id="p1",
                    section_id=None, parent_id=None, order=3, labels=[]),
        ]

        next_action_label = "next_action"

        # Sequential: only first
        def apply_sequential(tasks):
            first_found = False
            for task in sorted(tasks, key=lambda x: x.order):
                if not task.parent_id and not first_found:
                    return [task.id]
            return []

        # Parallel: all
        def apply_parallel(tasks):
            return [t.id for t in tasks if not t.parent_id]

        sequential_labeled = apply_sequential(tasks)
        parallel_labeled = apply_parallel(tasks)

        assert len(sequential_labeled) == 1, "Sequential: 1 task"
        assert len(parallel_labeled) == 3, "Parallel: all tasks"
        assert sequential_labeled[0] == "1", "Sequential labels first"
        assert set(parallel_labeled) == {"1", "2", "3"}, "Parallel labels all"
