"""飞牛影视(FNTV) SQLite 数据库只读访问层"""

import os
import sqlite3
import time
import logging
import shutil
import tempfile
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

DB_CACHE_SECONDS = 60  # 临时副本过期秒数


class ItemCategory(Enum):
    MOVIE = "movie"
    EPISODE = "episode"
    SEASON = "season"
    SERIES = "series"
    UNKNOWN = "unknown"


class FntvDb:
    """FNTV 数据库只读访问，使用临时副本避免锁竞争"""

    def __init__(self, db_path: str):
        self._src_path = Path(db_path)
        tmp_dir = Path(tempfile.gettempdir())
        tmp_name = f"{self._src_path.stem}_tmp.db"
        self._tmp_path = tmp_dir / tmp_name
        self._lock = time.monotonic
        self._last_copy = 0.0

    def _copy_db(self):
        """原子级复制数据库到临时文件（60s 缓存）"""
        now = time.monotonic()
        if now - self._last_copy < DB_CACHE_SECONDS and self._tmp_path.exists():
            return
        try:
            shutil.copy2(str(self._src_path), str(self._tmp_path))
            self._last_copy = now
            logger.debug("数据库副本已刷新: %s", self._tmp_path)
        except Exception as e:
            logger.error("复制数据库失败: %s", e)
            raise

    def get_conn(self):
        """获取只读数据库连接（自动刷新副本）"""
        if not self._src_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {self._src_path}")
        if not self._src_path.is_file():
            raise IsADirectoryError(f"路径不是文件: {self._src_path}")
        self._copy_db()
        uri = f"file:{self._tmp_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    # ── 条目分类 ──────────────────────────────────────────

    @staticmethod
    def classify_item(conn, item_guid: str) -> ItemCategory:
        """根据结构特征分类条目（不依赖 item.type 字段）"""
        row = conn.execute(
            "SELECT parent_guid, season_number, episode_number FROM item WHERE guid = ?",
            (item_guid,)
        ).fetchone()
        if not row:
            return ItemCategory.UNKNOWN
        if row["episode_number"] is not None:
            return ItemCategory.EPISODE
        if row["season_number"] is not None:
            return ItemCategory.SEASON
        if row["parent_guid"] is None:
            cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM item WHERE parent_guid = ?",
                (item_guid,)
            ).fetchone()["c"]
            return ItemCategory.SERIES if cnt > 0 else ItemCategory.MOVIE
        return ItemCategory.UNKNOWN

    # ── 查询接口 ──────────────────────────────────────────

    def get_users(self):
        """获取所有活跃用户列表"""
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT guid, username FROM user WHERE status = 1 AND guid != 'default-user-template' ORDER BY username"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_new_plays(self, user_guid: str, last_sync: int = 0):
        """获取用户自 last_sync 以来的新增播放记录（含条目信息）"""
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT ip.item_guid, ip.user_guid, ip.ts AS position_seconds,
                          ip.watched, ip.update_time AS play_update_time,
                          i.title, i.original_title, i.parent_guid AS item_parent_guid,
                          i.season_number, i.episode_number, i.runtime AS runtime_minutes
                   FROM item_user_play ip
                   JOIN item i ON ip.item_guid = i.guid
                   WHERE ip.user_guid = ? AND ip.visible = 1
                     AND ip.update_time > ?
                   ORDER BY ip.update_time ASC""",
                (user_guid, last_sync)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_series_hierarchy(self, conn, episode_guid: str):
        """从单集 guid 反查 Series/Season 信息"""
        row = conn.execute(
            """SELECT season.guid AS season_guid, season.parent_guid AS series_guid,
                      season.season_number, series.title AS series_title
               FROM item AS episode
               JOIN item AS season ON episode.parent_guid = season.guid
               JOIN item AS series ON season.parent_guid = series.guid
               WHERE episode.guid = ?""",
            (episode_guid,)
        ).fetchone()
        return dict(row) if row else None

    # ── 智能跨季推断 ────────────────────────────────────

    def get_series_for_episode_flat(self, conn, episode_guid: str) -> dict | None:
        """扁平结构回退：当 episode→season→series 层级缺失时，尝试 episode→series 直连"""
        row = conn.execute(
            """SELECT episode.parent_guid AS series_guid,
                      series.title AS series_title,
                      episode.episode_number
               FROM item AS episode
               JOIN item AS series ON episode.parent_guid = series.guid
               WHERE episode.guid = ? AND series.parent_guid IS NULL""",
            (episode_guid,)
        ).fetchone()
        return dict(row) if row else None

    def get_all_series_episodes(self, conn, series_guid: str) -> list[dict]:
        """获取某系列所有剧集的 episode_number（用于模式检测）"""
        rows = conn.execute(
            "SELECT guid, episode_number FROM item WHERE parent_guid = ? AND episode_number IS NOT NULL ORDER BY episode_number",
            (series_guid,)
        ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def detect_season_groups(episodes: list[dict]) -> list[dict]:
        """从剧集号分布中检测季度边界

        检测策略：如果 episode_number 出现回退（如 24→1），判定为新季度。
        返回 [{season_number, min_ep, max_ep, total_eps}, ...]
        """
        eps = [e["episode_number"] for e in episodes]
        if not eps:
            return []

        groups = []
        current = [eps[0]]
        for i in range(1, len(eps)):
            if eps[i] <= current[-1]:
                groups.append(current)
                current = [eps[i]]
            else:
                current.append(eps[i])
        if current:
            groups.append(current)

        result = []
        for i, g in enumerate(groups):
            result.append({
                "season_number": i + 1,
                "min_ep": min(g),
                "max_ep": max(g),
                "total_eps": len(g),
            })
        return result

    def infer_episode_group(self, conn, series_guid: str, episode_number: int) -> dict | None:
        """推断某集的所属季度分组

        对扁平结构（无 season 层）的系列，从全量 episode_number
        分布推断季度边界。返回 {season_number, total_eps} 或 None（单组）
        """
        all_eps = self.get_all_series_episodes(conn, series_guid)
        groups = self.detect_season_groups(all_eps)
        if len(groups) <= 1:
            return None  # 单组，无明确季度边界

        for g in groups:
            if g["min_ep"] <= episode_number <= g["max_ep"]:
                return {"season_number": g["season_number"], "total_eps": g["total_eps"]}
        return None

    # ── 季度查询 ──────────────────────────────────────────

    def get_season_total_episodes(self, conn, season_guid: str) -> int:
        """获取某季的总集数"""
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM item WHERE parent_guid = ? AND episode_number IS NOT NULL",
            (season_guid,)
        ).fetchone()
        return row["c"] if row else 0

    def get_season_max_watched(self, conn, user_guid: str, season_guid: str) -> int:
        """获取用户在某季已看过的最大集号"""
        row = conn.execute(
            """SELECT MAX(i.episode_number) AS max_ep
               FROM item_user_play ip
               JOIN item i ON ip.item_guid = i.guid
               WHERE ip.user_guid = ? AND ip.visible = 1 AND ip.watched = 1
                 AND i.parent_guid = ?""",
            (user_guid, season_guid)
        ).fetchone()
        return row["max_ep"] if row and row["max_ep"] else 0

    def validate(self) -> tuple[bool, str]:
        """验证数据库可读且是有效的 FNTV SQLite 库"""
        if not self._src_path.exists():
            return False, f"文件不存在: {self._src_path}"
        if self._src_path.is_dir():
            return False, (
                f"路径是目录而非文件: {self._src_path}\n"
                "Docker volume 挂载时，若宿主机源文件不存在，Docker 会自动创建同名目录。"
                "请检查宿主机路径是否正确，确保文件存在。"
            )
        if not os.access(str(self._src_path), os.R_OK):
            return False, "文件不可读（权限问题）"
        try:
            conn = self.get_conn()
            conn.execute("SELECT COUNT(*) FROM item").fetchone()
            conn.close()
            return True, "OK"
        except Exception as e:
            return False, str(e)
