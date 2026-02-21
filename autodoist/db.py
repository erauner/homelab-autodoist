"""
SQLite metadata storage.

Stores type information for projects, sections, and tasks to detect
when types change between runs (triggering label cleanup).

Schema uses a single 'entities' table instead of separate tables
for projects, sections, and tasks.
"""

from __future__ import annotations
import json
import logging
import os
import sqlite3
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .types import EntityKind


# SQL statements
_CREATE_ENTITIES_TABLE = """
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_kind TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    type_str TEXT,
    parent_type TEXT,
    UNIQUE(entity_kind, entity_id)
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_entities_kind_id 
ON entities(entity_kind, entity_id);
"""

_MIGRATE_PROJECTS = """
INSERT OR IGNORE INTO entities (entity_kind, entity_id, type_str)
SELECT 'project', CAST(project_id AS TEXT), project_type FROM projects;
"""

_MIGRATE_SECTIONS = """
INSERT OR IGNORE INTO entities (entity_kind, entity_id, type_str)
SELECT 'section', CAST(section_id AS TEXT), section_type FROM sections;
"""

_MIGRATE_TASKS = """
INSERT OR IGNORE INTO entities (entity_kind, entity_id, type_str, parent_type)
SELECT 'task', CAST(task_id AS TEXT), task_type, parent_type FROM tasks;
"""

_CREATE_SINGLETON_LABEL_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS singleton_label_state (
    label_name TEXT NOT NULL,
    task_id TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    assigned_at INTEGER,
    PRIMARY KEY (label_name, task_id)
);
"""

_CREATE_SINGLETON_LABEL_STATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_singleton_label_state_active
ON singleton_label_state(label_name, is_active);
"""

_CREATE_FOCUS_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS focus_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label_name TEXT NOT NULL,
    task_id TEXT NOT NULL,
    assigned_at INTEGER NOT NULL,
    cleared_at INTEGER,
    assigned_source TEXT,
    cleared_source TEXT,
    assigned_reason TEXT,
    cleared_reason TEXT,
    meta_json TEXT
);
"""

_CREATE_FOCUS_HISTORY_LABEL_ASSIGNED_INDEX = """
CREATE INDEX IF NOT EXISTS idx_focus_history_label_assigned_at
ON focus_history(label_name, assigned_at DESC);
"""

_CREATE_FOCUS_HISTORY_TASK_INDEX = """
CREATE INDEX IF NOT EXISTS idx_focus_history_task
ON focus_history(task_id);
"""

_CREATE_FOCUS_HISTORY_OPEN_INDEX = """
CREATE INDEX IF NOT EXISTS idx_focus_history_open_sessions
ON focus_history(label_name, cleared_at);
"""


class MetadataDB:
    """
    SQLite database for storing entity metadata.

    Tracks type_str for projects/sections/tasks and parent_type for tasks.
    This allows detecting when a user changes the type suffix on an entity,
    triggering cleanup of stale labels.

    Supports batched writes: set auto_commit=False and call commit() manually
    to avoid per-operation commits (better performance for large accounts).
    """

    def __init__(self, db_path: str = "metadata.sqlite", auto_commit: bool = False) -> None:
        """
        Open or create the metadata database.

        Args:
            db_path: Path to SQLite database file
            auto_commit: If False, batch writes until commit() is called
        """
        self.db_path = db_path
        self.auto_commit = auto_commit
        self._conn: Optional[sqlite3.Connection] = None
    
    def connect(self) -> None:
        """Open database connection and initialize schema."""
        try:
            self._conn = sqlite3.connect(self.db_path, timeout=30)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA busy_timeout=30000")
            logging.debug("Connected to SQLite DB: %s", self.db_path)
            self._init_schema()
            self._migrate_legacy_tables()
        except Exception as e:
            logging.error("Could not connect to SQLite database: %s", e)
            raise
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            try:
                self._conn.close()
                self._conn = None
            except Exception as e:
                logging.error("Could not close SQLite database: %s", e)
    
    @property
    def conn(self) -> sqlite3.Connection:
        """Get the active connection, raising if not connected."""
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    def commit(self) -> None:
        """Commit pending changes to the database."""
        if self._conn:
            self._conn.commit()
    
    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        cursor = self.conn.cursor()
        cursor.execute(_CREATE_ENTITIES_TABLE)
        cursor.execute(_CREATE_INDEX)
        cursor.execute(_CREATE_SINGLETON_LABEL_STATE_TABLE)
        cursor.execute(_CREATE_SINGLETON_LABEL_STATE_INDEX)
        cursor.execute(_CREATE_FOCUS_HISTORY_TABLE)
        cursor.execute(_CREATE_FOCUS_HISTORY_LABEL_ASSIGNED_INDEX)
        cursor.execute(_CREATE_FOCUS_HISTORY_TASK_INDEX)
        cursor.execute(_CREATE_FOCUS_HISTORY_OPEN_INDEX)
        self.conn.commit()
        logging.debug("Database schema initialized")
    
    def _migrate_legacy_tables(self) -> None:
        """
        Migrate data from legacy separate tables if they exist.
        
        The old schema had separate tables: projects, sections, tasks.
        This migrates that data to the unified entities table.
        """
        cursor = self.conn.cursor()
        
        # Check if legacy tables exist
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('projects', 'sections', 'tasks')"
        )
        legacy_tables = [row[0] for row in cursor.fetchall()]
        
        if not legacy_tables:
            return  # No legacy tables to migrate
        
        # Check if entities table is empty (avoid duplicate migration)
        cursor.execute("SELECT COUNT(*) FROM entities")
        if cursor.fetchone()[0] > 0:
            logging.debug("Entities table not empty, skipping migration")
            return
        
        logging.info("Migrating data from legacy tables: %s", legacy_tables)
        
        try:
            if 'projects' in legacy_tables:
                cursor.execute(_MIGRATE_PROJECTS)
                logging.debug("Migrated projects table")
            
            if 'sections' in legacy_tables:
                cursor.execute(_MIGRATE_SECTIONS)
                logging.debug("Migrated sections table")
            
            if 'tasks' in legacy_tables:
                cursor.execute(_MIGRATE_TASKS)
                logging.debug("Migrated tasks table")
            
            self.conn.commit()
            logging.info("Legacy table migration complete")
            
        except Exception as e:
            logging.warning("Error during legacy migration: %s", e)
            self.conn.rollback()
    
    def ensure_entity(self, kind: "EntityKind", entity_id: str) -> None:
        """
        Ensure an entity exists in the database.

        Creates a new row if the entity doesn't exist.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO entities (entity_kind, entity_id) VALUES (?, ?)",
            (kind, str(entity_id))
        )
        if self.auto_commit:
            self.conn.commit()
    
    def get_type_str(self, kind: "EntityKind", entity_id: str) -> Optional[str]:
        """
        Get the stored type_str for an entity.
        
        Returns None if entity not found or type_str is NULL.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT type_str FROM entities WHERE entity_kind = ? AND entity_id = ?",
            (kind, str(entity_id))
        )
        row = cursor.fetchone()
        return row[0] if row else None
    
    def set_type_str(self, kind: "EntityKind", entity_id: str, type_str: Optional[str]) -> None:
        """
        Set the type_str for an entity.

        Creates the entity if it doesn't exist.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO entities (entity_kind, entity_id, type_str)
            VALUES (?, ?, ?)
            ON CONFLICT(entity_kind, entity_id) DO UPDATE SET type_str = ?
            """,
            (kind, str(entity_id), type_str, type_str)
        )
        if self.auto_commit:
            self.conn.commit()
    
    def get_parent_type(self, task_id: str) -> Optional[str]:
        """
        Get the stored parent_type for a task.
        
        parent_type is the dominant type inherited from the task's parent,
        used to determine subtask labeling behavior.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT parent_type FROM entities WHERE entity_kind = 'task' AND entity_id = ?",
            (str(task_id),)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    
    def set_parent_type(self, task_id: str, parent_type: Optional[str]) -> None:
        """
        Set the parent_type for a task.

        Creates the entity if it doesn't exist.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO entities (entity_kind, entity_id, parent_type)
            VALUES ('task', ?, ?)
            ON CONFLICT(entity_kind, entity_id) DO UPDATE SET parent_type = ?
            """,
            (str(task_id), parent_type, parent_type)
        )
        if self.auto_commit:
            self.conn.commit()
    
    def clear_task_types(self, task_id: str) -> None:
        """Clear both type_str and parent_type for a task."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE entities
            SET type_str = NULL, parent_type = NULL
            WHERE entity_kind = 'task' AND entity_id = ?
            """,
            (str(task_id),)
        )
        if self.auto_commit:
            self.conn.commit()

    def get_active_singleton_tasks(self, label_name: str) -> list[str]:
        """Return task IDs currently active for a singleton label."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT task_id
            FROM singleton_label_state
            WHERE label_name = ? AND is_active = 1
            """,
            (label_name,),
        )
        return [str(row[0]) for row in cursor.fetchall()]

    def get_singleton_assigned_at(self, label_name: str, task_id: str) -> Optional[int]:
        """Return stored assigned-at epoch milliseconds for a singleton label task."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT assigned_at
            FROM singleton_label_state
            WHERE label_name = ? AND task_id = ?
            """,
            (label_name, str(task_id)),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return int(row[0]) if row[0] is not None else None

    def set_singleton_state(
        self,
        label_name: str,
        task_id: str,
        *,
        is_active: bool,
        assigned_at: Optional[int] = None,
    ) -> None:
        """Upsert singleton label state for a task."""
        if assigned_at is None:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO singleton_label_state (label_name, task_id, is_active)
                VALUES (?, ?, ?)
                ON CONFLICT(label_name, task_id) DO UPDATE
                SET is_active = excluded.is_active
                """,
                (label_name, str(task_id), 1 if is_active else 0),
            )
        else:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO singleton_label_state (label_name, task_id, is_active, assigned_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(label_name, task_id) DO UPDATE
                SET is_active = excluded.is_active,
                    assigned_at = excluded.assigned_at
                """,
                (label_name, str(task_id), 1 if is_active else 0, int(assigned_at)),
            )
        if self.auto_commit:
            self.conn.commit()

    def get_singleton_assigned_at_map(self, label_name: str, task_ids: list[str]) -> dict[str, Optional[int]]:
        """Bulk fetch assigned-at values for a label/task set."""
        if not task_ids:
            return {}
        placeholders = ",".join(["?"] * len(task_ids))
        cursor = self.conn.cursor()
        cursor.execute(
            f"""
            SELECT task_id, assigned_at
            FROM singleton_label_state
            WHERE label_name = ? AND task_id IN ({placeholders})
            """,
            [label_name, *[str(tid) for tid in task_ids]],
        )
        result: dict[str, Optional[int]] = {}
        for task_id, assigned_at in cursor.fetchall():
            result[str(task_id)] = int(assigned_at) if assigned_at is not None else None
        return result

    def start_singleton_session(
        self,
        label_name: str,
        task_id: str,
        *,
        assigned_at: int,
        source: str,
        reason: Optional[str] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> None:
        """Open a focus session if none is currently open for this label/task."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id
            FROM focus_history
            WHERE label_name = ? AND task_id = ? AND cleared_at IS NULL
            ORDER BY assigned_at DESC, id DESC
            LIMIT 1
            """,
            (label_name, str(task_id)),
        )
        if cursor.fetchone():
            return
        meta_json = json.dumps(meta, sort_keys=True) if meta is not None else None
        cursor.execute(
            """
            INSERT INTO focus_history (
                label_name,
                task_id,
                assigned_at,
                assigned_source,
                assigned_reason,
                meta_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (label_name, str(task_id), int(assigned_at), source, reason, meta_json),
        )
        if self.auto_commit:
            self.conn.commit()

    def end_singleton_session(
        self,
        label_name: str,
        task_id: str,
        *,
        cleared_at: int,
        source: str,
        reason: Optional[str] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> None:
        """Close the latest open focus session for this label/task, if any."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id
            FROM focus_history
            WHERE label_name = ? AND task_id = ? AND cleared_at IS NULL
            ORDER BY assigned_at DESC, id DESC
            LIMIT 1
            """,
            (label_name, str(task_id)),
        )
        row = cursor.fetchone()
        if not row:
            return
        session_id = int(row[0])
        meta_json = json.dumps(meta, sort_keys=True) if meta is not None else None
        cursor.execute(
            """
            UPDATE focus_history
            SET cleared_at = ?,
                cleared_source = ?,
                cleared_reason = ?,
                meta_json = COALESCE(?, meta_json)
            WHERE id = ?
            """,
            (int(cleared_at), source, reason, meta_json, session_id),
        )
        if self.auto_commit:
            self.conn.commit()

    def list_singleton_history(
        self,
        label_name: str,
        *,
        task_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return focus sessions ordered by most recent assignment time."""
        safe_limit = max(1, int(limit))
        cursor = self.conn.cursor()
        if task_id is None:
            cursor.execute(
                """
                SELECT
                    id,
                    label_name,
                    task_id,
                    assigned_at,
                    cleared_at,
                    assigned_source,
                    cleared_source,
                    assigned_reason,
                    cleared_reason,
                    meta_json
                FROM focus_history
                WHERE label_name = ?
                ORDER BY assigned_at DESC, id DESC
                LIMIT ?
                """,
                (label_name, safe_limit),
            )
        else:
            cursor.execute(
                """
                SELECT
                    id,
                    label_name,
                    task_id,
                    assigned_at,
                    cleared_at,
                    assigned_source,
                    cleared_source,
                    assigned_reason,
                    cleared_reason,
                    meta_json
                FROM focus_history
                WHERE label_name = ? AND task_id = ?
                ORDER BY assigned_at DESC, id DESC
                LIMIT ?
                """,
                (label_name, str(task_id), safe_limit),
            )

        rows = []
        for row in cursor.fetchall():
            rows.append(
                {
                    "id": int(row[0]),
                    "label_name": str(row[1]),
                    "task_id": str(row[2]),
                    "assigned_at": int(row[3]),
                    "cleared_at": int(row[4]) if row[4] is not None else None,
                    "assigned_source": row[5],
                    "cleared_source": row[6],
                    "assigned_reason": row[7],
                    "cleared_reason": row[8],
                    "meta": json.loads(row[9]) if row[9] else None,
                }
            )
        return rows


def open_db(db_path: str = "metadata.sqlite") -> MetadataDB:
    """
    Open the metadata database.
    
    Convenience function that creates a MetadataDB instance and connects it.
    """
    db = MetadataDB(db_path)
    db.connect()
    return db
