from copy import deepcopy

from autodoist.webui import create_app


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.content = b"" if payload is None else b"{}"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, tasks, projects, sections, wrapped=False):
        self.tasks = tasks
        self.projects = projects
        self.sections = sections
        self.wrapped = wrapped
        self.headers = {}
        self.post_calls = []

    def get(self, url, params=None, timeout=20):
        if url.endswith("/tasks"):
            payload = deepcopy(self.tasks)
            return FakeResponse({"results": payload} if self.wrapped else payload)
        if url.endswith("/projects"):
            payload = deepcopy(self.projects)
            return FakeResponse({"results": payload} if self.wrapped else payload)
        if url.endswith("/sections"):
            payload = deepcopy(self.sections)
            return FakeResponse({"results": payload} if self.wrapped else payload)
        return FakeResponse({}, status_code=404)

    def post(self, url, json=None, timeout=20):
        self.post_calls.append({"url": url, "json": deepcopy(json)})
        if "/tasks/" in url:
            task_id = str(url.rsplit("/", 1)[-1])
            for task in self.tasks:
                if str(task["id"]) == task_id and isinstance(json, dict):
                    if "labels" in json:
                        task["labels"] = list(json["labels"])
            return FakeResponse(None, status_code=204)
        return FakeResponse({}, status_code=404)


def sample_data():
    tasks = [
        {
            "id": 1001,
            "content": "Task A",
            "description": "",
            "labels": ["doing_now", "next_action"],
            "priority": 1,
            "due": None,
            "added_at": "2026-01-01T10:00:00Z",
            "updated_at": "2026-02-20T10:00:00Z",
            "project_id": "1",
            "section_id": "10",
        },
        {
            "id": 1002,
            "content": "Task B",
            "description": "",
            "labels": ["doing_now"],
            "priority": 1,
            "due": None,
            "added_at": "2026-01-01T11:00:00Z",
            "updated_at": "2026-02-20T12:00:00Z",
            "project_id": "1",
            "section_id": "10",
        },
        {
            "id": 1003,
            "content": "Task C",
            "description": "",
            "labels": ["next_action"],
            "priority": 1,
            "due": None,
            "added_at": "2026-01-01T12:00:00Z",
            "updated_at": "2026-02-20T09:00:00Z",
            "project_id": "1",
            "section_id": "10",
        },
    ]
    projects = [{"id": "1", "name": "Project One"}]
    sections = [{"id": "10", "name": "Section A"}]
    return tasks, projects, sections


def build_client(monkeypatch, wrapped=False):
    tasks, projects, sections = sample_data()
    fake_session = FakeSession(tasks, projects, sections, wrapped=wrapped)
    monkeypatch.setattr("autodoist.webui.requests.Session", lambda: fake_session)
    app = create_app(
        api_token="test-token",
        next_action_label="next_action",
        doing_now_label="doing_now",
    )
    return app.test_client(), fake_session


def test_health_endpoint(monkeypatch):
    client, _ = build_client(monkeypatch)
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert "generated_at" in payload


def test_state_endpoint_includes_conflict_counts(monkeypatch):
    client, _ = build_client(monkeypatch)
    response = client.get("/api/state")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["summary"]["open_tasks"] == 3
    assert payload["summary"]["next_action_count"] == 2
    assert payload["summary"]["doing_now_count"] == 2
    assert payload["summary"]["doing_now_conflicts"] == 1
    by_id = {t["id"]: t for t in payload["tasks"]}
    assert by_id["1002"]["explain"]["doing_now"]["reason_code"] == "singleton_conflict_winner"
    assert by_id["1001"]["explain"]["doing_now"]["reason_code"] == "singleton_conflict_loser"
    assert by_id["1003"]["explain"]["next_action"]["reason_code"] == "label_present_on_active_task"
    assert by_id["1003"]["explain"]["doing_now"]["reason_code"] == "singleton_assigned_to_other_task"


def test_reconcile_dry_run_picks_most_recent_without_writing(monkeypatch):
    client, fake_session = build_client(monkeypatch)
    response = client.post("/api/doing-now/reconcile", json={"apply": False})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["applied"] is False
    assert payload["winner_task_id"] == "1002"
    assert payload["removed_count"] == 1
    write_calls = [c for c in fake_session.post_calls if "/tasks/" in c["url"]]
    assert len(write_calls) == 0
    assert payload["preview"]["winner_task_id"] == "1002"
    assert payload["preview"]["conflict_detected"] is True


def test_reconcile_preview_returns_winner_losers_and_diffs(monkeypatch):
    client, _ = build_client(monkeypatch)
    response = client.get("/api/doing-now/reconcile-preview")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["conflict_detected"] is True
    assert payload["winner_task_id"] == "1002"
    assert payload["loser_count"] == 1
    assert payload["losers"][0]["id"] == "1001"
    assert payload["updates"][0]["task_id"] == "1001"
    assert payload["updates"][0]["from_labels"] == ["doing_now", "next_action"]
    assert payload["updates"][0]["to_labels"] == ["next_action"]


def test_reconcile_preview_honors_explicit_winner_override(monkeypatch):
    client, _ = build_client(monkeypatch)
    response = client.get("/api/doing-now/reconcile-preview?winner_task_id=1001")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["winner_task_id"] == "1001"
    assert payload["updates"][0]["task_id"] == "1002"


def test_reconcile_apply_updates_losing_tasks(monkeypatch):
    client, fake_session = build_client(monkeypatch)
    response = client.post("/api/doing-now/reconcile", json={"apply": True})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["applied"] is True
    assert payload["winner_task_id"] == "1002"
    assert payload["removed_count"] == 1

    write_calls = [c for c in fake_session.post_calls if "/tasks/" in c["url"]]
    assert len(write_calls) == 1
    assert write_calls[0]["url"].endswith("/tasks/1001")
    assert write_calls[0]["json"]["labels"] == ["next_action"]


def test_reconcile_apply_honors_explicit_winner_override(monkeypatch):
    client, fake_session = build_client(monkeypatch)
    response = client.post(
        "/api/doing-now/reconcile",
        json={"apply": True, "winner_task_id": "1001"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["applied"] is True
    assert payload["winner_task_id"] == "1001"
    assert payload["removed_count"] == 1

    write_calls = [c for c in fake_session.post_calls if "/tasks/" in c["url"]]
    assert len(write_calls) == 1
    assert write_calls[0]["url"].endswith("/tasks/1002")
    assert write_calls[0]["json"]["labels"] == []


def test_state_endpoint_accepts_results_wrapped_payloads(monkeypatch):
    client, _ = build_client(monkeypatch, wrapped=True)
    response = client.get("/api/state")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["summary"]["open_tasks"] == 3
    assert payload["summary"]["doing_now_count"] == 2


def test_explain_endpoint_returns_task_reasons(monkeypatch):
    client, _ = build_client(monkeypatch)
    response = client.get("/api/explain")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 3

    by_id = {t["id"]: t for t in payload["tasks"]}
    assert by_id["1002"]["explain"]["doing_now"]["reason_code"] == "singleton_conflict_winner"
    assert by_id["1001"]["explain"]["doing_now"]["reason_code"] == "singleton_conflict_loser"
    assert by_id["1003"]["explain"]["next_action"]["has_label"] is True


def test_explain_endpoint_supports_task_id_filter(monkeypatch):
    client, _ = build_client(monkeypatch)
    response = client.get("/api/explain?task_id=1001")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    assert payload["tasks"][0]["id"] == "1001"
