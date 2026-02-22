"""
Autodoist local debug dashboard + JSON API.

Run with:
    python -m autodoist.webui --api-key <TOKEN>
or:
    autodoist-webui --api-key <TOKEN>
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, jsonify, render_template_string, request
from .db import MetadataDB
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
      --panel-soft: #f6f3ed;
      --ink: #1f2a33;
      --muted: #667784;
      --accent: #0d6d66;
      --warn: #b85c00;
      --danger: #b42318;
      --border: #d8d2c5;
      --border-strong: #c8bfad;
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
      border-radius: 14px;
      padding: 16px;
      box-shadow: 0 8px 22px rgba(31, 42, 51, 0.06);
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
      transition: background-color 120ms ease, border-color 120ms ease, transform 120ms ease;
    }

    button:hover {
      background: #f8f6f1;
      border-color: var(--border-strong);
    }

    button:active {
      transform: translateY(1px);
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

    #reconcilePreview, #focusHistory {
      margin-bottom: 12px;
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
    .actions button { padding: 5px 9px; font-size: 0.78rem; }
    .view-controls { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 14px 0; }
    .view-controls button.active { background: var(--accent); color: white; border-color: var(--accent); }
    .inline-controls { display: flex; gap: 10px; align-items: center; margin: 8px 0; font-size: 0.9rem; color: var(--muted); }
    .inline-controls label { display: inline-flex; align-items: center; gap: 6px; background: var(--panel-soft); border: 1px solid var(--border); border-radius: 10px; padding: 6px 10px; }
    .inline-controls select { border: 1px solid var(--border-strong); border-radius: 8px; background: white; padding: 4px 6px; }
    .history-list { margin: 10px 0 0 0; padding: 0; list-style: none; display: grid; gap: 10px; }
    .history-item { border: 1px solid var(--border); background: var(--panel-soft); border-radius: 12px; padding: 10px 12px; }
    .history-item-head { display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; margin-bottom: 4px; }
    .history-item-title { font-weight: 600; color: var(--ink); }
    .history-item-meta { color: var(--muted); font-size: 0.9rem; }
    .history-item-actions { display: flex; gap: 8px; margin-top: 8px; align-items: center; }
    .history-link { color: #0f4cbf; text-decoration: none; font-weight: 600; }
    .history-link:hover { text-decoration: underline; }
    .history-count { font-weight: 700; color: var(--ink); margin-bottom: 8px; }

    @media (max-width: 800px) {
      .hide-mobile { display: none; }
      h1 { font-size: 1.45rem; }
      .inline-controls { flex-direction: column; align-items: flex-start; }
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
    <div class="view-controls" id="viewControls">
      <button data-view="all" onclick="setTaskView('all')">All</button>
      <button data-view="next_action" onclick="setTaskView('next_action')">Only next_action</button>
      <button data-view="focus" onclick="setTaskView('focus')">Only focus</button>
      <button data-view="conflicts" onclick="setTaskView('conflicts')">Conflicts only</button>
      <button data-view="no_labels" onclick="setTaskView('no_labels')">No labels</button>
    </div>

    <div id="status" class="status">Loading...</div>
    <div class="card" id="reconcilePreview">
      <div class="k">Reconcile Preview</div>
      <div id="previewBody" class="preview-meta">Loading preview...</div>
    </div>
    <div class="card" id="focusHistory">
      <div class="k">Focus History</div>
      <div class="inline-controls">
        <label><input type="checkbox" id="focusHistoryOpenOnly" checked onchange="loadFocusHistory()"> Open tasks only</label>
        <label><input type="checkbox" id="focusHistoryLatestPerTask" checked onchange="loadFocusHistory()"> Latest per task</label>
        <label>Show
          <select id="focusHistoryLimit" onchange="loadFocusHistory()">
            <option value="5" selected>5</option>
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="50">50</option>
          </select>
        </label>
        <button onclick="loadFocusHistory()">Refresh history</button>
      </div>
      <div id="focusHistoryBody" class="preview-meta">Loading focus history...</div>
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
    const VIEW_KEY = 'autodoist_saved_view';
    let currentTaskView = localStorage.getItem(VIEW_KEY) || 'all';
    let currentState = null;

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

    function filterTasksByView(tasks, view) {
      if (view === 'next_action') return tasks.filter((t) => t.has_next_action);
      if (view === 'focus') return tasks.filter((t) => t.has_focus);
      if (view === 'conflicts') return tasks.filter((t) => t.is_focus_conflict);
      if (view === 'no_labels') return tasks.filter((t) => !Array.isArray(t.labels) || t.labels.length === 0);
      return tasks;
    }

    function updateTaskViewButtons() {
      const buttons = document.querySelectorAll('#viewControls button[data-view]');
      buttons.forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.view === currentTaskView);
      });
    }

    function renderCurrentView() {
      if (!currentState) return;
      const filtered = filterTasksByView(currentState.tasks || [], currentTaskView);
      renderTasks(filtered, currentState.labels);
      const label = currentTaskView === 'all' ? 'all' : currentTaskView;
      setStatus(`Loaded ${filtered.length} task(s) in '${label}' view at ${currentState.generated_at}`, 'ok');
    }

    function setTaskView(view) {
      currentTaskView = view;
      localStorage.setItem(VIEW_KEY, view);
      updateTaskViewButtons();
      renderCurrentView();
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

    function renderFocusHistory(payload) {
      const el = document.getElementById('focusHistoryBody');
      if (!payload || payload.ok !== true) {
        el.textContent = 'Focus history unavailable.';
        return;
      }
      const sessions = payload.sessions || [];
      if (!sessions.length) {
        el.textContent = 'No focus history found for current filter.';
        return;
      }
      const rows = sessions.map((s) => {
        const assigned = new Date(s.assigned_at).toLocaleString();
        const cleared = s.cleared_at ? new Date(s.cleared_at).toLocaleString() : 'active';
        const content = s.content || '(task not currently open)';
        const todoistUrl = `https://todoist.com/showTask?id=${encodeURIComponent(s.task_id)}`;
        const focusBtn = s.still_open
          ? `<button onclick="setFocusFromHistory('${esc(s.task_id)}')">Set as focus</button>`
          : '';
        return `
          <li class="history-item">
            <div class="history-item-head">
              <span class="mono">${esc(s.task_id)}</span>
              <span class="history-item-title">${esc(content)}</span>
            </div>
            <div class="history-item-meta"><span class="mono">assigned:</span> ${esc(assigned)} · <span class="mono">cleared:</span> ${esc(cleared)}</div>
            <div class="history-item-actions">
              <a class="history-link" href="${todoistUrl}" target="_blank" rel="noopener noreferrer">Open in Todoist</a>
              ${focusBtn}
            </div>
          </li>
        `;
      }).join('');
      el.innerHTML = `<div class="history-count">${esc(sessions.length)} session(s)</div><ul class="history-list">${rows}</ul>`;
    }

    async function loadFocusHistory() {
      try {
        const openOnly = document.getElementById('focusHistoryOpenOnly').checked;
        const latestPerTask = document.getElementById('focusHistoryLatestPerTask').checked;
        const limit = document.getElementById('focusHistoryLimit').value || '5';
        const params = new URLSearchParams({
          open_only: openOnly ? 'true' : 'false',
          latest_per_task: latestPerTask ? 'true' : 'false',
          limit
        });
        const res = await fetch(`${apiBase}/focus/history?${params.toString()}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        renderFocusHistory(data);
      } catch (err) {
        setStatus(`Focus history error: ${err.message}`, 'err');
      }
    }

    async function setFocusFromHistory(taskId) {
      try {
        setStatus(`Setting focus to ${taskId}...`);
        let res = await fetch(`${apiBase}/tasks/${taskId}/labels`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'set_focus' })
        });
        let data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

        res = await fetch(`${apiBase}/focus/reconcile`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ apply: true, winner_task_id: taskId })
        });
        data = await res.json();
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

        setStatus(`Focus switched to ${taskId}.`, 'ok');
        await refreshState();
      } catch (err) {
        setStatus(`Focus switch error: ${err.message}`, 'err');
      }
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
        currentState = state;
        updateTaskViewButtons();
        renderSummary(state.summary);
        renderCurrentView();
        await loadReconcilePreview();
        await loadFocusHistory();
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


def _apply_task_view(tasks: List[Dict[str, Any]], view: str) -> List[Dict[str, Any]]:
    if view == "all":
        return tasks
    if view == "next_action":
        return [t for t in tasks if bool(t.get("has_next_action"))]
    if view == "focus":
        return [t for t in tasks if bool(t.get("has_focus"))]
    if view == "conflicts":
        return [t for t in tasks if bool(t.get("is_focus_conflict"))]
    if view == "no_labels":
        return [t for t in tasks if not (t.get("labels") or [])]
    raise ValueError(f"Unsupported view '{view}'")


def create_app(
    api_token: str,
    next_action_label: str = "next_action",
    focus_label: str = "focus",
    db_path: Optional[str] = None,
) -> Flask:
    app = Flask(__name__)
    resolved_db_path = db_path or os.environ.get("AUTODOIST_DB_PATH", "metadata.sqlite")
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

    def _now_ms() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    def _open_db() -> MetadataDB:
        db = MetadataDB(resolved_db_path, auto_commit=True)
        db.connect()
        return db

    def _mark_focus_active(
        task_id: str,
        *,
        source: str,
        reason: str,
        assigned_at: Optional[int] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> None:
        ts = assigned_at if assigned_at is not None else _now_ms()
        db = _open_db()
        try:
            db.set_singleton_state(focus_label, str(task_id), is_active=True, assigned_at=ts)
            db.start_singleton_session(
                focus_label,
                str(task_id),
                assigned_at=ts,
                source=source,
                reason=reason,
                meta=meta,
            )
        finally:
            db.close()

    def _mark_focus_inactive(
        task_id: str,
        *,
        source: str,
        reason: str,
        cleared_at: Optional[int] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> None:
        ts = cleared_at if cleared_at is not None else _now_ms()
        db = _open_db()
        try:
            db.set_singleton_state(focus_label, str(task_id), is_active=False)
            db.end_singleton_session(
                focus_label,
                str(task_id),
                cleared_at=ts,
                source=source,
                reason=reason,
                meta=meta,
            )
        finally:
            db.close()

    def _to_bool(value: Optional[str], default: bool = False) -> bool:
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}

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
        task_ids = [str(t["id"]) for t in focus_tasks]
        assigned_at_by_task_id: dict[str, Optional[int]] = {}
        if task_ids:
            db = _open_db()
            try:
                assigned_at_by_task_id = db.get_singleton_assigned_at_map(focus_label, task_ids)
            finally:
                db.close()
        winner = choose_singleton_winner(focus_tasks, assigned_at_by_task_id=assigned_at_by_task_id)
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
        view = request.args.get("view", "all")

        try:
            state = fetch_state()
            tasks = state["tasks"]

            if label:
                tasks = [t for t in tasks if label in (t.get("labels") or [])]
            if contains:
                c = contains.lower()
                tasks = [t for t in tasks if c in (t.get("content") or "").lower()]
            tasks = _apply_task_view(tasks, view)

            return jsonify({
                "generated_at": state["generated_at"],
                "count": len(tasks),
                "view": view,
                "tasks": tasks,
            })
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
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

    @app.get("/api/focus/history")
    def focus_history():
        open_only = _to_bool(request.args.get("open_only"), default=False)
        latest_per_task = _to_bool(request.args.get("latest_per_task"), default=True)
        limit = int(request.args.get("limit", "50"))
        try:
            db = _open_db()
            try:
                sessions = db.list_singleton_history(focus_label, limit=limit)
            finally:
                db.close()

            state = fetch_state()
            task_map = {str(t["id"]): t for t in state["tasks"]}
            if open_only:
                sessions = [s for s in sessions if s["task_id"] in task_map]
            if latest_per_task:
                deduped: list[dict[str, Any]] = []
                seen_task_ids: set[str] = set()
                for session_item in sessions:
                    task_id = session_item["task_id"]
                    if task_id in seen_task_ids:
                        continue
                    seen_task_ids.add(task_id)
                    deduped.append(session_item)
                sessions = deduped

            enriched = []
            for session_item in sessions:
                task = task_map.get(session_item["task_id"])
                enriched.append(
                    {
                        **session_item,
                        "still_open": task is not None,
                        "content": task.get("content") if task else None,
                        "project_name": task.get("project_name") if task else None,
                        "section_name": task.get("section_name") if task else None,
                    }
                )

            return jsonify(
                {
                    "ok": True,
                    "generated_at": state["generated_at"],
                    "label": focus_label,
                    "open_only": open_only,
                    "latest_per_task": latest_per_task,
                    "count": len(enriched),
                    "sessions": enriched,
                }
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except requests.HTTPError as exc:
            return jsonify({"error": f"Todoist API HTTP error: {exc}"}), 502
        except requests.RequestException as exc:
            return jsonify({"error": f"Todoist API request error: {exc}"}), 502

    @app.get("/api/focus/history/<task_id>")
    def focus_history_for_task(task_id: str):
        limit = int(request.args.get("limit", "50"))
        try:
            db = _open_db()
            try:
                sessions = db.list_singleton_history(focus_label, task_id=str(task_id), limit=limit)
            finally:
                db.close()
            state = fetch_state()
            task = next((t for t in state["tasks"] if t["id"] == str(task_id)), None)
            return jsonify(
                {
                    "ok": True,
                    "generated_at": state["generated_at"],
                    "label": focus_label,
                    "task_id": str(task_id),
                    "task_missing": task is None,
                    "still_open": task is not None,
                    "content": task.get("content") if task else None,
                    "count": len(sessions),
                    "sessions": sessions,
                }
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
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
                _mark_focus_active(
                    str(task_id),
                    source="webui",
                    reason="action_set_focus",
                )
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
                _mark_focus_inactive(
                    str(task_id),
                    source="webui",
                    reason="action_clear_focus",
                )
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
            _mark_focus_active(
                str(task_id),
                source="webui",
                reason="action_make_winner",
            )

            # Remove focus from all losers using the same diff source as preview/apply.
            for upd in preview["updates"]:
                _set_labels(upd["task_id"], upd["to_labels"])
                _mark_focus_inactive(
                    upd["task_id"],
                    source="webui",
                    reason="reconcile_loser",
                    meta={"winner_task_id": str(task_id)},
                )

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
                    _mark_focus_inactive(
                        upd["task_id"],
                        source="webui",
                        reason="reconcile_loser",
                        meta={"winner_task_id": preview["winner_task_id"]},
                    )
                if preview["winner_task_id"] is not None:
                    _mark_focus_active(
                        preview["winner_task_id"],
                        source="webui",
                        reason="reconcile_winner",
                    )

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
    parser.add_argument(
        "--db-path",
        default=os.environ.get("AUTODOIST_DB_PATH", "metadata.sqlite"),
        help="Path to metadata SQLite database used for focus history (default from AUTODOIST_DB_PATH)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    app = create_app(
        api_token=args.api_key,
        next_action_label=args.next_action_label,
        focus_label=args.focus_label,
        db_path=args.db_path,
    )
    app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
