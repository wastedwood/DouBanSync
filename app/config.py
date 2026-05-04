"""配置管理"""

import os

import yaml

from app.sync_store import SyncStore

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")


class Config:
    def __init__(self, store: SyncStore):
        self._store = store
        self._defaults = self._load_defaults()

    @staticmethod
    def _load_defaults() -> dict:
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    @property
    def fntv_db_path(self) -> str:
        return (os.environ.get("FNTV_DB_PATH")
                or self._store.get_config("fntv_db_path")
                or self._defaults.get("fntv_db_path", ""))

    @fntv_db_path.setter
    def fntv_db_path(self, value: str):
        self._store.set_config("fntv_db_path", value)

    @property
    def douban_cookie(self) -> str:
        return self._store.get_config("douban_cookie", "")

    @douban_cookie.setter
    def douban_cookie(self, value: str):
        self._store.set_config("douban_cookie", value)

    @property
    def selected_user(self) -> str:
        return self._store.get_config("selected_user_guid", "")

    @selected_user.setter
    def selected_user(self, value: str):
        self._store.set_config("selected_user_guid", value)

    @property
    def sync_interval_hours(self) -> int:
        val = self._store.get_config("sync_interval_hours", "")
        if val:
            return int(val)
        return self._defaults.get("sync_interval_hours", 24)

    @sync_interval_hours.setter
    def sync_interval_hours(self, value: int):
        self._store.set_config("sync_interval_hours", str(value))

    @property
    def watch_threshold_percent(self) -> int:
        val = self._store.get_config("watch_threshold_percent", "")
        if val:
            return int(val)
        return self._defaults.get("watch_threshold_percent", 90)

    @watch_threshold_percent.setter
    def watch_threshold_percent(self, value: int):
        self._store.set_config("watch_threshold_percent", str(max(0, min(100, value))))

    @property
    def private(self) -> bool:
        val = self._store.get_config("private", "")
        if val:
            return val == "true"
        return self._defaults.get("private", True)

    @private.setter
    def private(self, value: bool):
        self._store.set_config("private", "true" if value else "false")

    def to_dict(self) -> dict:
        return {
            "fntv_db_path": self.fntv_db_path,
            "douban_cookie": self.douban_cookie,
            "selected_user": self.selected_user,
            "sync_interval_hours": self.sync_interval_hours,
            "watch_threshold_percent": self.watch_threshold_percent,
            "private": self.private,
        }
