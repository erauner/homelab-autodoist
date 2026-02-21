from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest

from autodoist.config import Config
from autodoist.db import MetadataDB
from autodoist.labeling import LabelingEngine


def test_config_reads_doing_now_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TODOIST_API_KEY", "test-token")
    monkeypatch.setenv("AUTODOIST_DOING_NOW_LABEL", "doing_now")
    config = Config.from_env_and_cli([])
    assert config.doing_now_label == "doing_now"


def test_config_cli_overrides_doing_now_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TODOIST_API_KEY", "test-token")
    monkeypatch.setenv("AUTODOIST_DOING_NOW_LABEL", "from_env")
    config = Config.from_env_and_cli(["--doing-now-label", "from_cli"])
    assert config.doing_now_label == "from_cli"


def test_db_singleton_state_roundtrip(tmp_path) -> None:
    db = MetadataDB(str(tmp_path / "metadata.sqlite"), auto_commit=True)
    db.connect()
    try:
        db.set_singleton_state("doing_now", "1", is_active=True, assigned_at=111)
        db.set_singleton_state("doing_now", "2", is_active=False)

        active = db.get_active_singleton_tasks("doing_now")
        assert active == ["1"]
        assert db.get_singleton_assigned_at("doing_now", "1") == 111
        assert db.get_singleton_assigned_at("doing_now", "2") is None
    finally:
        db.close()


@dataclass
class MockTask:
    id: str
    content: str
    project_id: str
    section_id: Optional[str]
    parent_id: Optional[str]
    order: int
    labels: list[str]
    is_completed: bool = False
    updated_at: Optional[str] = None


class MockClient:
    def __init__(self, tasks: list[MockTask]) -> None:
        self._tasks = tasks
        self.label_updates: list[tuple[str, list[str]]] = []

    def get_all_projects(self) -> list[object]:
        return []

    def get_all_sections(self) -> list[object]:
        return []

    def get_all_tasks(self) -> list[MockTask]:
        return self._tasks

    def queue_label_update(self, task_id: str, labels: list[str]) -> None:
        self.label_updates.append((str(task_id), list(labels)))


def test_doing_now_conflict_keeps_recent_and_removes_loser(tmp_path) -> None:
    tasks = [
        MockTask(
            id="1001",
            content="A",
            project_id="p",
            section_id=None,
            parent_id=None,
            order=1,
            labels=["doing_now", "next_action"],
            updated_at="2026-02-20T10:00:00Z",
        ),
        MockTask(
            id="1002",
            content="B",
            project_id="p",
            section_id=None,
            parent_id=None,
            order=2,
            labels=["doing_now"],
            updated_at="2026-02-20T12:00:00Z",
        ),
    ]
    client = MockClient(tasks)
    db = MetadataDB(str(tmp_path / "metadata.sqlite"))
    db.connect()
    try:
        config = Config(api_key="token", doing_now_label="doing_now")
        engine = LabelingEngine(client=client, db=db, config=config)
        changes = engine.run()

        assert changes == 1
        assert client.label_updates == [("1001", ["next_action"])]
        assert db.get_active_singleton_tasks("doing_now") == ["1002"]
    finally:
        db.close()


def test_main_allows_doing_now_only_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    import autodoist.__main__ as entry

    config = Config(api_key="token", doing_now_label="doing_now", onetime=True)

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.labels_ensured: list[str] = []

        def initial_sync(self) -> None:
            return None

        def ensure_label_exists(self, label_name: str) -> None:
            self.labels_ensured.append(label_name)

        @property
        def pending_changes(self) -> int:
            return 0

        def flush_queue(self) -> int:
            return 0

    class FakeDB:
        def close(self) -> None:
            return None

    fake_client = FakeClient("token")
    monkeypatch.setattr(entry.Config, "from_env_and_cli", lambda argv=None: config)
    monkeypatch.setattr(entry, "setup_logging", lambda debug: None)
    monkeypatch.setattr(entry, "TodoistClient", lambda api_key: fake_client)
    monkeypatch.setattr(entry, "open_db", lambda db_path: FakeDB())
    monkeypatch.setattr(entry, "run_labeling_pass", lambda client, db, cfg: 0)

    rc = entry.main([])
    assert rc == 0
    assert fake_client.labels_ensured == ["doing_now"]

