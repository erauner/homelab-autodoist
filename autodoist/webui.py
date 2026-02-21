"""
Autodoist local debug dashboard + JSON API.

Run with:
    python -m autodoist.webui --api-key <TOKEN>
or:
    autodoist-webui --api-key <TOKEN>
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, jsonify, render_template_string, request
from .singleton import choose_singleton_winner

TODOIST_API_V1_BASE = "https://api.todoist.com/api/v1"

DASHBOARD_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Autodoist Debug Dashboard</title>
  <style>
    :root {
      --bg: #f7f6f2;
      --panel: #fffdf8;
      --ink: #1f2a33;
      --muted: #667784;
      --accent: #0d6d66;
      --warn: #b85c00;
      --danger: #b42318;
      --border: #d8d2c5;
      --ok: #0f8f4e;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "IBM Plex Sans", "Avenir Next", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 20% 0%, #efe7da 0%, transparent 35%),
        radial-gradient(circle at 100% 30%, #dbe9e7 0%, transparent 40%),
        var(--bg);
      min-height: 100vh;
    }

    .wrap {
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
    }

    h1 {
      margin: 0 0 8px 0;
      font-size: 1.8rem;
      letter-spacing: 0.01em;
    }

    .sub {
      margin: 0 0 18px 0;
      color: var(--muted);
      font-size: 0.95rem;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }

    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px;
      box-shadow: 0 3px 10px rgba(0,0,0,0.04);
    }

    .k {
      color: var(--muted);
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .v {
      font-size: 1.4rem;
      margin-top: 4px;
      font-weight: 700;
    }

    .controls {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }

    button {
      border: 1px solid var(--border);
      background: white;
      color: var(--ink);
      padding: 8px 12px;
      border-radius: 8px;
      cursor: pointer;
      font-weight: 600;
    }

    button.primary {
      background: var(--accent);
      color: white;
      border-color: var(--accent);
    }

    button.warn {
      background: #fff2e0;
      color: var(--warn);
      border-color: #f0c899;
    }

    .status {
      margin-bottom: 12px;
      font-size: 0.92rem;
      color: var(--muted);
    }

    .status.ok { color: var(--ok); }
    .status.err { color: var(--danger); }
    .preview-meta {
      margin: 6px 0 0 0;
      color: var(--muted);
      font-size: 0.9rem;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
      font-size: 0.92rem;
    }

    thead th {
      text-align: left;
      padding: 10px;
      background: #f3eee5;
      border-bottom: 1px solid var(--border);
    }

    tbody td {
      padding: 9px 10px;
      border-top: 1px solid #eee7da;
      vertical-align: top;
    }

    .pill {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 0.78rem;
      border: 1px solid;
      margin-right: 6px;
      margin-bottom: 4px;
      white-space: nowrap;
    }

    .na { background: #edf7ff; border-color: #9ec9ef; color: #004b7a; }
    .dn { background: #eaf9f1; border-color: #9bd7b5; color: #0f5f35; }
    .conflict { background: #fff2f0; border-color: #f2a8a0; color: #8f1f14; }

    .mono { font-family: "SFMono-Regular", Menlo, Consolas, monospace; font-size: 0.82rem; color: var(--muted); }
    .actions { display: flex; gap: 6px; flex-wrap: wrap; }
    .actions button { padding: 4px 8px; font-size: 0.78rem; }

    @media (max-width: 800px) {
      .hide-mobile { display: none; }
      h1 { font-size: 1.45rem; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Autodoist Debug Dashboard</h1>
    <p class="sub">Visualize labels and conflict resolution without opening Todoist.</p>

    <div class="grid" id="summary"></div>

    <div class="controls">
      <button class="primary" onclick="refreshState()">Refresh</button>
      <button onclick="loadReconcilePreview()">Preview reconcile focus</button>
      <button class="warn" onclick="applyReconcile()">Apply reconcile focus</button>
    </div>

    <div id="status" class="status">Loading...</div>
    <div class="card" id="reconcilePreview">
      <div class="k">Reconcile Preview</div>
      <div id="previewBody" class="preview-meta">Loading preview...</div>
    </div>

    <table>
      <thead>
        <tr>
          <th>Task</th>
          <th class="hide-mobile">Project / Section</th>
          <th>Labels</th>
          <th>Actions</th>
          <th class="hide-mobile">Updated</th>
          <th class="hide-mobile">Task ID</th>
        </tr>
      </thead>
      <tbody id="tasks"></tbody>
    </table>
  </div>

  <script>
    const apiBase = '/api';

    function esc(v) {
      return String(v ?? '').replace(/[&<>\"]/g, (s) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[s]));
    }

    function setStatus(text, cls='') {
      const el = document.getElementById('status');
      el.className = 'status ' + cls;
      el.textContent = text;
    }

    function renderSummary(summary) {
      const cards = [
        ['Open Tasks', summary.open_tasks],
        ['next_action Count', summary.next_action_count],
        ['focus Count', summary.focus_count],
        ['focus Conflicts', summary.focus_conflicts]
      ];

      document.getElementById('summary').innerHTML = cards.map(([k, v]) =>
        `<div class="card"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`
      ).join('');
    }

    function renderTasks(tasks, labels) {
      const tbody = document.getElementById('tasks');
      if (!tasks.length) {
        tbody.innerHTML = '<tr><td colspan="6">No tasks returned.</td></tr>';
        return;
      }

      tbody.innerHTML = tasks.map((t) => {
        const pills = [];
        if (t.has_next_action) pills.push(`<span class="pill na">${esc(labels.next_action_label)}</span>`);
        if (t.has_focus) pills.push(`<span class="pill dn">${esc(labels.focus_label)}</span>`);
        if (t.is_focus_conflict) pills.push('<span class="pill conflict">conflict</span>');

        for (const l of t.labels) {
          if (l !== labels.next_action_label && l !== labels.focus_label) {
            pills.push(`<span class="pill">${esc(l)}</span>`);
          }
        }

        const actions = [];
        if (t.has_focus) {
          actions.push(`<button onclick="taskAction('${esc(t.id)}','clear_focus')">Clear focus</button>`);
        } else {
          actions.push(`<button onclick="taskAction('${esc(t.id)}','set_focus')">Set focus</button>`);
        }
        if (t.has_next_action) {
          actions.push(`<button onclick="taskAction('${esc(t.id)}','remove_next_action')">Remove next_action</button>`);
        }
        if (t.is_focus_conflict) {
          actions.push(`<button class="warn" onclick="taskAction('${esc(t.id)}','make_winner')">Make winner</button>`);
        }

        return `
          <tr>
            <td>${esc(t.content)}</td>
            <td class="hide-mobile">${esc(t.project_name || '-')} / ${esc(t.section_name || '-')}</td>
            <td>${pills.join(' ') || '-'}</td>
            <td><div class="actions">${actions.join(' ') || '-'}</div></td>
            <td class="hide-mobile mono">${esc(t.updated_at || 'n/a')}</td>
            <td class="hide-mobile mono">${esc(t.id)}</td>
          </tr>
        `;
      }).join('');
    }

    function renderReconcilePreview(preview) {
      const el = document.getElementById('previewBody');
      if (!preview.ok) {
        el.textContent = 'Preview unavailable.';
        return;
      }
      if (!preview.conflict_detected) {
        el.innerHTML = `No conflict detected. Winner: <span class="mono">${esc(preview.winner_task_id || 'none')}</span>`;
        return;
      }

      const updates = (preview.updates || []).map((u) => {
        const fromLabels = (u.from_labels || []).join(', ') || '-';
        const toLabels = (u.to_labels || []).join(', ') || '-';
        return `<li><span class="mono">${esc(u.task_id)}</span> (${esc(u.content || '')}): [${esc(fromLabels)}] → [${esc(toLabels)}]</li>`;
      }).join('');

      el.innerHTML = `
        <div>Winner: <span class="mono">${esc(preview.winner_task_id)}</span> (${esc(preview.winner_content || '')})</div>
        <div class="preview-meta">Losers: ${esc(preview.loser_count)} task(s)</div>
        <ul>${updates}</ul>
      `;
    }

    async function loadReconcilePreview() {
      try {
        const res = await fetch(`${apiBase}/focus/reconcile-preview`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        renderReconcilePreview(data);
      } catch (err) {
        setStatus(`Preview error: ${err.message}`, 'err');
      }
    }

    async function refreshState() {
      try {
        setStatus('Loading state...');
        const res = await fetch(`${apiBase}/state`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const state = await res.json();
        renderSummary(state.summary);
        renderTasks(state.tasks, state.labels);
        await loadReconcilePreview();
        setStatus(`Loaded ${state.summary.open_tasks} tasks at ${state.generated_at}`, 'ok');
      } catch (err) {
        setStatus(`Error loading state: ${err.message}`, 'err');
      }
    }

    async function dryRunReconcile() {
      await loadReconcilePreview();
      setStatus('Loaded reconcile preview.', 'ok');
    }

    async function applyReconcile() {
      await doReconcile(true);
      await refreshState();
    }

    async function doReconcile(apply) {
      try {
        setStatus(`${apply ? 'Applying' : 'Running dry-run'} reconcile...`);
        const res = await fetch(`${apiBase}/focus/reconcile`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ apply })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        const msg = apply
          ? `Applied. Winner: ${data.winner_task_id || 'none'}. Removed from ${data.removed_count} task(s).`
          : `Dry-run. Winner: ${data.winner_task_id || 'none'}. Would remove from ${data.removed_count} task(s).`;
        setStatus(msg, 'ok');
      } catch (err) {
        setStatus(`Reconcile error: ${err.message}`, 'err');
      }
    }

    async function taskAction(taskId, action) {
      try {
        setStatus(`Applying action ${action} on ${taskId}...`);
        const res = await fetch(`${apiBase}/tasks/${taskId}/labels`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        setStatus(data.message || `Action ${action} applied to ${taskId}.`, 'ok');
        await refreshState();
      } catch (err) {
        setStatus(`Task action error: ${err.message}`, 'err');
      }
    }

    refreshState();
    setInterval(refreshState, 10000);
  </script>
</body>
</html>
"""


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_list(payload: Any) -> List[Dict[str, Any]]:
    """
    Normalize Todoist API payloads into a list of objects.

    Some endpoints return plain lists, while others may return wrapper
    objects (e.g. {"results": [...]}).
    """
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            return [item for item in payload["results"] if isinstance(item, dict)]
        if isinstance(payload.get("items"), list):
            return [item for item in payload["items"] if isinstance(item, dict)]
        return []
    return []


def _parse_default_type_suffix(name: Optional[str], width: int) -> Optional[str]:
    if not name:
        return None
    suffix = ""
    for ch in reversed(name):
        if ch not in ("-", "="):
            break
        suffix = ch + suffix
        if len(suffix) == width:
            break
    if not suffix:
        return None
    if len(suffix) < width:
        suffix += suffix[-1] * (width - len(suffix))
    return "".join("s" if ch == "-" else "p" for ch in suffix)


def create_app(
    api_token: str,
    next_action_label: str = "next_action",
    focus_label: str = "focus",
) -> Flask:
    app = Flask(__name__)
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {api_token}"})

    def todoist_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        response = session.get(f"{TODOIST_API_V1_BASE}{path}", params=params, timeout=20)
        response.raise_for_status()
        return response.json()

    def todoist_post(path: str, payload: Dict[str, Any]) -> Any:
        response = session.post(f"{TODOIST_API_V1_BASE}{path}", json=payload, timeout=20)
        response.raise_for_status()
        if response.content:
            return response.json()
        return {"ok": True}

    def fetch_state() -> Dict[str, Any]:
        tasks = _as_list(todoist_get("/tasks"))
        projects = _as_list(todoist_get("/projects"))
        sections = _as_list(todoist_get("/sections"))

        project_by_id = {str(p["id"]): p.get("name") for p in projects}
        section_by_id = {str(s["id"]): s.get("name") for s in sections}

        open_tasks: List[Dict[str, Any]] = []
        focus_tasks: List[Dict[str, Any]] = []

        for task in tasks:
            task_labels = task.get("labels") or []
            item = {
                "id": str(task["id"]),
                "content": task.get("content"),
                "description": task.get("description"),
                "project_id": str(task.get("project_id")) if task.get("project_id") is not None else None,
                "project_name": project_by_id.get(str(task.get("project_id"))),
                "section_id": str(task.get("section_id")) if task.get("section_id") is not None else None,
                "section_name": section_by_id.get(str(task.get("section_id"))) if task.get("section_id") else None,
                "labels": task_labels,
                "priority": task.get("priority"),
                "due": task.get("due"),
                "added_at": task.get("added_at"),
                "updated_at": task.get("updated_at"),
                "has_next_action": next_action_label in task_labels,
                "has_focus": focus_label in task_labels,
                "is_focus_conflict": False,
            }
            open_tasks.append(item)
            if item["has_focus"]:
                focus_tasks.append(item)

        if len(focus_tasks) > 1:
            for item in focus_tasks:
                item["is_focus_conflict"] = True
        winner = choose_singleton_winner(focus_tasks)
        winner_task_id = str(winner["id"]) if isinstance(winner, dict) and winner.get("id") is not None else None

        for item in open_tasks:
            is_header = (item.get("content") or "").startswith("*")
            section_name = item.get("section_name")
            section_disabled = bool(section_name) and (section_name.startswith("*") or section_name.endswith("*"))
            project_type = _parse_default_type_suffix(item.get("project_name"), 3)
            section_type = _parse_default_type_suffix(section_name, 2)
            task_type = _parse_default_type_suffix(item.get("content"), 1)
            dominant_type = task_type or section_type or project_type

            if item["has_next_action"]:
                na_code = "label_present_on_active_task"
                na_message = "Task currently has next_action label."
            elif is_header:
                na_code = "header_task_not_actionable"
                na_message = "Task is a header (`*`) and is treated as non-actionable."
            elif section_disabled:
                na_code = "section_labeling_disabled"
                na_message = "Task section is disabled for automatic labeling."
            elif dominant_type is None:
                na_code = "no_type_suffix_detected"
                na_message = "No sequential/parallel type suffix detected in project/section/task."
            else:
                na_code = "not_selected_by_ordering_or_rules"
                na_message = "Task is currently not selected by sequential/parallel labeling rules."

            if item["has_focus"] and item["is_focus_conflict"] and winner_task_id == item["id"]:
                dn_code = "singleton_conflict_winner"
                dn_message = "Task is the chosen singleton winner among conflicting focus labels."
            elif item["has_focus"] and item["is_focus_conflict"]:
                dn_code = "singleton_conflict_loser"
                dn_message = "Task currently has focus but is a losing task in singleton conflict."
            elif item["has_focus"]:
                dn_code = "singleton_holder"
                dn_message = "Task currently holds focus and no conflict is detected."
            elif winner_task_id is not None:
                dn_code = "singleton_assigned_to_other_task"
                dn_message = f"Another task ({winner_task_id}) currently holds focus."
            else:
                dn_code = "not_labeled"
                dn_message = "Task does not have focus label."

            item["explain"] = {
                "next_action": {
                    "has_label": item["has_next_action"],
                    "reason_code": na_code,
                    "reason": na_message,
                },
                "focus": {
                    "has_label": item["has_focus"],
                    "reason_code": dn_code,
                    "reason": dn_message,
                    "winner_task_id": winner_task_id,
                },
                "signals": {
                    "is_header_task": is_header,
                    "section_disabled": section_disabled,
                    "task_type": task_type,
                    "section_type": section_type,
                    "project_type": project_type,
                    "dominant_type": dominant_type,
                    "is_focus_conflict": item["is_focus_conflict"],
                },
            }

        summary = {
            "open_tasks": len(open_tasks),
            "next_action_count": sum(1 for t in open_tasks if t["has_next_action"]),
            "focus_count": len(focus_tasks),
            "focus_conflicts": max(0, len(focus_tasks) - 1),
        }

        return {
            "generated_at": _iso_now(),
            "labels": {
                "next_action_label": next_action_label,
                "focus_label": focus_label,
            },
            "summary": summary,
            "conflicts": {
                "focus": [
                    {"id": t["id"], "content": t["content"], "updated_at": t["updated_at"]}
                    for t in focus_tasks
                ],
            },
            "tasks": open_tasks,
        }

    def pick_winner(
        focus_tasks: List[Dict[str, Any]],
        preferred_task_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        winner = choose_singleton_winner(
            focus_tasks,
            preferred_task_id=preferred_task_id,
        )
        if winner is None:
            return None
        return winner if isinstance(winner, dict) else None

    def build_reconcile_preview(
        state: Dict[str, Any],
        preferred_task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        focus_tasks = [t for t in state["tasks"] if t["has_focus"]]
        if len(focus_tasks) <= 1:
            winner = focus_tasks[0] if focus_tasks else None
            return {
                "ok": True,
                "generated_at": state["generated_at"],
                "conflict_detected": False,
                "winner_task_id": winner["id"] if winner else None,
                "winner_content": winner["content"] if winner else None,
                "winner_updated_at": winner["updated_at"] if winner else None,
                "loser_count": 0,
                "losers": [],
                "updates": [],
                "message": "No conflict detected.",
            }

        winner = pick_winner(focus_tasks, preferred_task_id)
        assert winner is not None
        losers = [t for t in focus_tasks if t["id"] != winner["id"]]

        updates = []
        for task in losers:
            new_labels = [l for l in task["labels"] if l != focus_label]
            updates.append(
                {
                    "task_id": task["id"],
                    "content": task.get("content"),
                    "from_labels": task["labels"],
                    "to_labels": new_labels,
                }
            )

        return {
            "ok": True,
            "generated_at": state["generated_at"],
            "conflict_detected": True,
            "winner_task_id": winner["id"],
            "winner_content": winner.get("content"),
            "winner_updated_at": winner.get("updated_at"),
            "loser_count": len(losers),
            "losers": [
                {
                    "id": t["id"],
                    "content": t.get("content"),
                    "updated_at": t.get("updated_at"),
                }
                for t in losers
            ],
            "updates": updates,
        }

    @app.get("/")
    def index() -> str:
        return render_template_string(DASHBOARD_HTML)

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "generated_at": _iso_now()})

    @app.get("/api/state")
    def api_state():
        try:
            return jsonify(fetch_state())
        except requests.HTTPError as exc:
            return jsonify({"error": f"Todoist API HTTP error: {exc}"}), 502
        except requests.RequestException as exc:
            return jsonify({"error": f"Todoist API request error: {exc}"}), 502

    @app.get("/api/tasks")
    def api_tasks():
        label = request.args.get("label")
        contains = request.args.get("contains")

        try:
            state = fetch_state()
            tasks = state["tasks"]

            if label:
                tasks = [t for t in tasks if label in (t.get("labels") or [])]
            if contains:
                c = contains.lower()
                tasks = [t for t in tasks if c in (t.get("content") or "").lower()]

            return jsonify({
                "generated_at": state["generated_at"],
                "count": len(tasks),
                "tasks": tasks,
            })
        except requests.HTTPError as exc:
            return jsonify({"error": f"Todoist API HTTP error: {exc}"}), 502
        except requests.RequestException as exc:
            return jsonify({"error": f"Todoist API request error: {exc}"}), 502

    @app.get("/api/explain")
    def api_explain():
        task_id = request.args.get("task_id")
        try:
            state = fetch_state()
            tasks = state["tasks"]
            if task_id:
                tasks = [t for t in tasks if str(t.get("id")) == str(task_id)]

            explained = [
                {
                    "id": t["id"],
                    "content": t["content"],
                    "project_name": t["project_name"],
                    "section_name": t["section_name"],
                    "labels": t["labels"],
                    "explain": t.get("explain", {}),
                }
                for t in tasks
            ]
            return jsonify(
                {
                    "generated_at": state["generated_at"],
                    "labels": state["labels"],
                    "summary": state["summary"],
                    "count": len(explained),
                    "tasks": explained,
                }
            )
        except requests.HTTPError as exc:
            return jsonify({"error": f"Todoist API HTTP error: {exc}"}), 502
        except requests.RequestException as exc:
            return jsonify({"error": f"Todoist API request error: {exc}"}), 502

    @app.post("/api/tasks/<task_id>/labels")
    def task_label_action(task_id: str):
        try:
            body = request.get_json(silent=True) or {}
            action = str(body.get("action", "")).strip()
            allowed_actions = {"set_focus", "clear_focus", "remove_next_action", "make_winner"}
            if action not in allowed_actions:
                return jsonify({"error": f"Unsupported action '{action}'"}), 400

            state = fetch_state()
            task = next((t for t in state["tasks"] if t["id"] == str(task_id)), None)
            if task is None:
                return jsonify({"error": f"Task '{task_id}' not found"}), 404

            def _set_labels(target_task_id: str, labels: list[str]) -> None:
                todoist_post(f"/tasks/{target_task_id}", {"labels": labels})

            labels = list(task["labels"])
            if action == "set_focus":
                if focus_label not in labels:
                    labels.append(focus_label)
                    _set_labels(task_id, labels)
                return jsonify(
                    {
                        "ok": True,
                        "action": action,
                        "task_id": task_id,
                        "labels": labels,
                        "message": f"Set @{focus_label} on task {task_id}.",
                    }
                )

            if action == "clear_focus":
                labels = [l for l in labels if l != focus_label]
                _set_labels(task_id, labels)
                return jsonify(
                    {
                        "ok": True,
                        "action": action,
                        "task_id": task_id,
                        "labels": labels,
                        "message": f"Cleared @{focus_label} on task {task_id}.",
                    }
                )

            if action == "remove_next_action":
                labels = [l for l in labels if l != next_action_label]
                _set_labels(task_id, labels)
                return jsonify(
                    {
                        "ok": True,
                        "action": action,
                        "task_id": task_id,
                        "labels": labels,
                        "message": f"Removed @{next_action_label} on task {task_id}.",
                    }
                )

            # action == make_winner
            preview = build_reconcile_preview(state, preferred_task_id=str(task_id))
            if not preview["conflict_detected"]:
                return jsonify(
                    {
                        "error": "No focus conflict detected. 'make_winner' is only valid during conflicts.",
                        "preview": preview,
                    }
                ), 400

            # Ensure selected winner has focus
            if focus_label not in labels:
                labels.append(focus_label)
                _set_labels(task_id, labels)

            # Remove focus from all losers using the same diff source as preview/apply.
            for upd in preview["updates"]:
                _set_labels(upd["task_id"], upd["to_labels"])

            return jsonify(
                {
                    "ok": True,
                    "action": action,
                    "task_id": task_id,
                    "winner_task_id": preview["winner_task_id"],
                    "updated_task_ids": [task_id] + [u["task_id"] for u in preview["updates"]],
                    "message": f"Task {task_id} selected as @{focus_label} winner.",
                }
            )
        except requests.HTTPError as exc:
            return jsonify({"error": f"Todoist API HTTP error: {exc}"}), 502
        except requests.RequestException as exc:
            return jsonify({"error": f"Todoist API request error: {exc}"}), 502

    @app.get("/api/focus/reconcile-preview")
    def reconcile_focus_preview():
        winner_task_id = request.args.get("winner_task_id")
        try:
            state = fetch_state()
            preview = build_reconcile_preview(state, winner_task_id)
            return jsonify(preview)
        except requests.HTTPError as exc:
            return jsonify({"error": f"Todoist API HTTP error: {exc}"}), 502
        except requests.RequestException as exc:
            return jsonify({"error": f"Todoist API request error: {exc}"}), 502

    @app.post("/api/focus/reconcile")
    def reconcile_focus():
        try:
            body = request.get_json(silent=True) or {}
            apply_changes = bool(body.get("apply", False))
            winner_task_id = body.get("winner_task_id")

            state = fetch_state()
            preview = build_reconcile_preview(state, winner_task_id)
            updates = preview["updates"]

            if not preview["conflict_detected"]:
                return jsonify({
                    "ok": True,
                    "applied": apply_changes,
                    "winner_task_id": preview["winner_task_id"],
                    "removed_count": 0,
                    "updated_task_ids": [],
                    "message": preview["message"],
                    "preview": preview,
                })

            if apply_changes:
                for upd in updates:
                    todoist_post(f"/tasks/{upd['task_id']}", {"labels": upd["to_labels"]})

            return jsonify({
                "ok": True,
                "applied": apply_changes,
                "winner_task_id": preview["winner_task_id"],
                "winner_updated_at": preview["winner_updated_at"],
                "removed_count": len(updates),
                "updated_task_ids": [u["task_id"] for u in updates],
                "updates": updates,
                "preview": preview,
            })
        except requests.HTTPError as exc:
            return jsonify({"error": f"Todoist API HTTP error: {exc}"}), 502
        except requests.RequestException as exc:
            return jsonify({"error": f"Todoist API request error: {exc}"}), 502

    return app


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autodoist debug dashboard and API")
    parser.add_argument(
        "-a",
        "--api-key",
        required=True,
        help="Todoist API token",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", default=8080, type=int, help="Bind port")
    parser.add_argument(
        "--next-action-label",
        default="next_action",
        help="Label name treated as next-action",
    )
    parser.add_argument(
        "--focus-label",
        default="focus",
        help="Label name treated as singleton focus label",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    app = create_app(
        api_token=args.api_key,
        next_action_label=args.next_action_label,
        focus_label=args.focus_label,
    )
    app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
