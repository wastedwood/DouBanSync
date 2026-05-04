"""同步状态持久化层——基于 SQLite 的去重、状态追踪、日志"""

import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

STORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_guid TEXT NOT NULL,
    item_guid TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK(media_type IN ('movie','episode')),
    series_guid TEXT,
    season_number INTEGER,
    series_title TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','doing','done','failed')),
    douban_subject_id TEXT,
    episode_number INTEGER,
    max_ep_watched INTEGER,
    total_episodes INTEGER,
    play_update_time INTEGER,
    last_synced_at INTEGER DEFAULT (unixepoch()),
    UNIQUE(user_guid, item_guid)
);

CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    action TEXT NOT NULL,
    item_guid TEXT,
    series_title TEXT,
    detail TEXT,
    created_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS runtime_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_sync_state_series ON sync_state(user_guid, series_guid, season_number);
CREATE INDEX IF NOT EXISTS idx_sync_log_run ON sync_log(run_id);
CREATE INDEX IF NOT EXISTS idx_sync_state_status ON sync_state(status);
"""


class SyncStore:
    """同步状态管理"""

    def __init__(self, db_dir: str):
        self._db_path = Path(db_dir) / "sync_state.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(STORE_SCHEMA)

    # ── Sync State ──────────────────────────────────

    def upsert_state(self, user_guid: str, item_guid: str, **kwargs):
        """插入或更新同步状态"""
        fields = ["user_guid", "item_guid", "media_type", "series_guid",
                   "season_number", "series_title", "status", "douban_subject_id",
                   "episode_number", "max_ep_watched", "total_episodes", "play_update_time"]
        data = {k: kwargs.get(k) for k in fields if k in kwargs}
        data["user_guid"] = user_guid
        data["item_guid"] = item_guid
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        updates = ", ".join(f"{k}=excluded.{k}" for k in data)
        sql = (f"INSERT INTO sync_state ({cols}) VALUES ({placeholders}) "
               f"ON CONFLICT(user_guid, item_guid) DO UPDATE SET {updates}, last_synced_at=unixepoch()")
        with self._connect() as conn:
            conn.execute(sql, list(data.values()))

    def get_state(self, user_guid: str, item_guid: str) -> dict | None:
        """获取单条同步状态"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sync_state WHERE user_guid=? AND item_guid=?",
                (user_guid, item_guid)
            ).fetchone()
            return dict(row) if row else None

    def get_series_status(self, user_guid: str, series_guid: str, season_number: int) -> str | None:
        """获取某剧某季的当前最高状态"""
        with self._connect() as conn:
            for st in ("done", "doing", "pending"):
                exists = conn.execute(
                    "SELECT 1 FROM sync_state WHERE user_guid=? AND series_guid=? AND season_number=? AND status=? LIMIT 1",
                    (user_guid, series_guid, season_number, st)
                ).fetchone()
                if exists:
                    return st
            return None

    def get_stats(self, user_guid: str) -> dict:
        """获取同步统计"""
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS c FROM sync_state WHERE user_guid=?", (user_guid,)
            ).fetchone()["c"]
            done = conn.execute(
                "SELECT COUNT(*) AS c FROM sync_state WHERE user_guid=? AND status='done'", (user_guid,)
            ).fetchone()["c"]
            failed = conn.execute(
                "SELECT COUNT(*) AS c FROM sync_state WHERE user_guid=? AND status='failed'", (user_guid,)
            ).fetchone()["c"]
            return {"total": total, "done": done, "failed": failed}

    # ── 同步日志 ─────────────────────────────────────

    def log_action(self, run_id: str, action: str, item_guid: str = "",
                   series_title: str = "", detail: str = ""):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sync_log (run_id, action, item_guid, series_title, detail) VALUES (?, ?, ?, ?, ?)",
                (run_id, action, item_guid, series_title, detail)
            )

    def get_logs(self, limit: int = 100, offset: int = 0) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sync_log ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── 运行时配置 ───────────────────────────────────

    def get_config(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM runtime_config WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default

    def set_config(self, key: str, value: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO runtime_config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=unixepoch()",
                (key, value)
            )

    def get_all_config(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM runtime_config").fetchall()
            return {r["key"]: r["value"] for r in rows}
