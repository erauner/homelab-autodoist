from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from autodoist.config import Config
from autodoist.labeling import LabelingEngine


def test_config_rejects_inbox_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TODOIST_API_KEY", "test-token")

    with pytest.raises(SystemExit):
        Config.from_env_and_cli(["--inbox", "parallel"])


@dataclass
class MockProject:
    id: str
    name: str
    is_inbox_project: bool = False


class MockClient:
    def get_all_projects(self) -> list[MockProject]:
        return [
            MockProject(id="inbox", name="Inbox", is_inbox_project=True),
            MockProject(id="work", name="Work -", is_inbox_project=False),
        ]

    def get_all_sections(self) -> list[Any]:
        return []

    def get_all_tasks(self) -> list[Any]:
        return []

    def queue_label_update(self, task_id: str, labels: list[str]) -> None:
        return None


class MockDB:
    def commit(self) -> None:
        return None


def test_labeling_engine_skips_inbox_projects(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config(api_key="test-token", label="next_action")
    engine = LabelingEngine(client=MockClient(), db=MockDB(), config=config)

    processed: list[str] = []

    def record_project(
        project: MockProject,
        all_sections: list[Any],
        all_tasks: list[Any],
        label: str,
    ) -> None:
        processed.append(project.id)

    monkeypatch.setattr(engine, "_process_project", record_project)

    changes = engine.run()
    assert changes == 0
    assert processed == ["work"]
