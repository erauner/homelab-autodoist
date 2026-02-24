from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any

from autodoist.config import Config
from autodoist.db import MetadataDB
from autodoist.labeling import LabelingEngine


@dataclass
class MockProject:
    id: str | int
    name: str
    is_inbox_project: bool = False


@dataclass
class MockTask:
    id: str | int
    content: str
    project_id: str | int
    section_id: Optional[str | int]
    parent_id: Optional[str | int]
    order: int
    labels: list[str]
    is_completed: bool = False
    due: Any = None


class MockClient:
    def __init__(self, projects: list[MockProject], tasks: list[MockTask]) -> None:
        self._projects = projects
        self._tasks = tasks
        self.queued_updates: dict[str, list[str]] = {}

    def get_all_projects(self) -> list[MockProject]:
        return self._projects

    def get_all_sections(self) -> list[Any]:
        return []

    def get_all_tasks(self) -> list[MockTask]:
        return self._tasks

    def queue_label_update(self, task_id: str, labels: list[str]) -> None:
        self.queued_updates[str(task_id)] = list(labels)

    def update_task_via_rest(self, task_id: str | int, **kwargs: Any) -> None:
        return None

    def update_section_via_rest(self, section_id: str | int, **kwargs: Any) -> None:
        return None

    def update_project_via_rest(self, project_id: str | int, **kwargs: Any) -> None:
        return None


def _open_test_db(tmp_path: Path) -> MetadataDB:
    db = MetadataDB(str(tmp_path / "metadata.sqlite"), auto_commit=False)
    db.connect()
    return db


def test_sectionless_parent_cascades_next_action_to_first_child_without_flipflop(tmp_path: Path) -> None:
    """
    Regression:
    - sectionless tasks must still be processed (NoSection id None handling)
    - parent->child cascade should use desired labels in-pass, not stale task.labels
    """
    project = MockProject(id=1, name="Work ---")
    parent = MockTask(
        id=100,
        content="Parent task",
        project_id="1",  # mixed type vs project.id
        section_id=None,
        parent_id=None,
        order=1,
        labels=[],
    )
    child1 = MockTask(
        id="200",
        content="First child",
        project_id="1",
        section_id=None,
        parent_id=100,  # mixed type vs parent.id
        order=1,
        labels=[],
    )
    child2 = MockTask(
        id="201",
        content="Second child",
        project_id="1",
        section_id=None,
        parent_id="100",
        order=2,
        labels=[],
    )

    client = MockClient([project], [parent, child1, child2])
    db = _open_test_db(tmp_path)
    try:
        engine = LabelingEngine(client=client, db=db, config=Config(api_key="x", label="next_action"))
        changes = engine.run()

        assert changes == 1
        assert client.queued_updates == {"200": ["next_action"]}
    finally:
        db.close()


def test_waiting_task_does_not_keep_next_action_and_next_task_is_labeled(tmp_path: Path) -> None:
    project = MockProject(id=1, name="Work ---")
    waiting_task = MockTask(
        id="100",
        content="Waiting on vendor",
        project_id="1",
        section_id=None,
        parent_id=None,
        order=1,
        labels=["waiting", "next_action"],
    )
    active_task = MockTask(
        id="101",
        content="Do work now",
        project_id="1",
        section_id=None,
        parent_id=None,
        order=2,
        labels=[],
    )

    client = MockClient([project], [waiting_task, active_task])
    db = _open_test_db(tmp_path)
    try:
        engine = LabelingEngine(
            client=client,
            db=db,
            config=Config(api_key="x", label="next_action", blocking_labels=("waiting",)),
        )
        changes = engine.run()

        assert changes == 2
        assert client.queued_updates == {
            "100": ["waiting"],
            "101": ["next_action"],
        }
    finally:
        db.close()
