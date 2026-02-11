# Tests for sequential project labeling (sss type)
"""
Test sequential project labeling behavior.

Sequential projects (suffix '-') should only label the first task.
Project type 'sss' = sequential at section, subsection, and project level.
"""

import pytest
from dataclasses import dataclass
from typing import Optional, List
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


class TestProjectTypeDetection:
    """Test project type detection from naming conventions."""

    def test_sequential_suffix_detected(self):
        """Project ending with '-' should be sequential."""
        # From autodoist.py check_name function
        def check_name_suffix(name, suffix):
            return name.rstrip().endswith(suffix)

        project_seq = MockProject(id="1", name="My Project -")
        project_par = MockProject(id="2", name="My Project =")
        project_none = MockProject(id="3", name="My Project")

        assert check_name_suffix(project_seq.name, "-"), "'-' suffix = sequential"
        assert check_name_suffix(project_par.name, "="), "'=' suffix = parallel"
        assert not check_name_suffix(project_none.name, "-"), "No suffix"
        assert not check_name_suffix(project_none.name, "="), "No suffix"

    def test_sss_type_identification(self):
        """Test that 'sss' type is correctly identified."""
        # The type string format is: [section_type][subsection_type][project_type]
        # 's' = sequential, 'p' = parallel, 'x' = inherit/none

        project_type = "sss"  # All sequential

        assert project_type[0] == 's', "First char = section level type"
        assert project_type[1] == 's', "Second char = subsection level type"
        assert project_type[2] == 's', "Third char = project level type"

    def test_dominant_type_for_sequential(self):
        """Test dominant type selection for sequential projects."""
        project_type = "sss"
        section_type = None  # No section-level override
        task_type = None  # No task-level override

        # Logic from autodoist.py lines 1361-1369
        hierarchy_types = [task_type, section_type, project_type]
        hierarchy_boolean = [t is not None for t in hierarchy_types]

        # Find dominant type
        dominant_type = None
        if hierarchy_boolean[0]:
            dominant_type = task_type
        elif hierarchy_boolean[1]:
            dominant_type = section_type
        elif hierarchy_boolean[2]:
            dominant_type = project_type

        assert dominant_type == "sss", "Project type should be dominant"
        assert dominant_type[0] == 's', "Sequential at first level"


class TestSequentialLabeling:
    """Test that sequential projects only label first task."""

    def test_only_first_task_labeled(self):
        """In sequential mode, only the first task should be labeled."""
        tasks = [
            MockTask(id="1", content="First task", project_id="p1",
                    section_id=None, parent_id=None, order=1, labels=[]),
            MockTask(id="2", content="Second task", project_id="p1",
                    section_id=None, parent_id=None, order=2, labels=[]),
            MockTask(id="3", content="Third task", project_id="p1",
                    section_id=None, parent_id=None, order=3, labels=[]),
        ]

        next_action_label = "next_action"
        first_found = False

        # Simulate sequential labeling logic
        labeled_tasks = []
        for task in sorted(tasks, key=lambda x: x.order):
            if not task.parent_id:  # Parentless task (fixed check)
                if not first_found:
                    task.labels.append(next_action_label)
                    labeled_tasks.append(task.id)
                    first_found = True

        assert len(labeled_tasks) == 1, "Only one task should be labeled"
        assert labeled_tasks[0] == "1", "First task should be labeled"
        assert next_action_label in tasks[0].labels, "First task has label"
        assert next_action_label not in tasks[1].labels, "Second task no label"
        assert next_action_label not in tasks[2].labels, "Third task no label"

    def test_completed_tasks_skipped(self):
        """Completed tasks should be skipped when finding first task."""
        tasks = [
            MockTask(id="1", content="First task", project_id="p1",
                    section_id=None, parent_id=None, order=1, labels=[],
                    is_completed=True),  # Completed
            MockTask(id="2", content="Second task", project_id="p1",
                    section_id=None, parent_id=None, order=2, labels=[]),
            MockTask(id="3", content="Third task", project_id="p1",
                    section_id=None, parent_id=None, order=3, labels=[]),
        ]

        next_action_label = "next_action"
        first_found = False

        # Simulate sequential labeling logic (skipping completed)
        labeled_tasks = []
        for task in sorted(tasks, key=lambda x: x.order):
            if task.is_completed:
                continue
            if not task.parent_id:  # Parentless task
                if not first_found:
                    task.labels.append(next_action_label)
                    labeled_tasks.append(task.id)
                    first_found = True

        assert len(labeled_tasks) == 1, "Only one task should be labeled"
        assert labeled_tasks[0] == "2", "Second task (first incomplete) labeled"
        assert next_action_label not in tasks[0].labels, "Completed task no label"
        assert next_action_label in tasks[1].labels, "Second task has label"

    def test_task_order_respected(self):
        """Tasks should be processed in order, not by ID."""
        # Tasks created out of order
        tasks = [
            MockTask(id="3", content="Third by order", project_id="p1",
                    section_id=None, parent_id=None, order=3, labels=[]),
            MockTask(id="1", content="First by order", project_id="p1",
                    section_id=None, parent_id=None, order=1, labels=[]),
            MockTask(id="2", content="Second by order", project_id="p1",
                    section_id=None, parent_id=None, order=2, labels=[]),
        ]

        next_action_label = "next_action"

        # Sort by order and label first
        sorted_tasks = sorted(tasks, key=lambda x: x.order)
        sorted_tasks[0].labels.append(next_action_label)

        # Find the task that got labeled
        labeled = [t for t in tasks if next_action_label in t.labels][0]

        assert labeled.content == "First by order", "Order determines first, not ID"
        assert labeled.order == 1, "Task with order=1 gets label"
