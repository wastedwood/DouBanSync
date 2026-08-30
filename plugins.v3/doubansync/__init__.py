"""MoviePilot V3 适配层：飞牛影视播放记录同步到豆瓣。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Lock, Thread
from typing import Any

from apscheduler.triggers.cron import CronTrigger

from app import schemas
from app.plugins import _PluginBase
from app.schemas.types import EventType
from app.sdk.events import Event, eventmanager
from app.sdk.logging import logger

from .core.douban_client import DoubanClient
from .core.fntv_db import FntvDb
from .core.notifier import BarkNotifier
from .core.sync_engine import SyncEngine
from .core.sync_store import SyncStore

DEFAULT_DB_PATH = "/fntv-db/trimmedia.db"
DEFAULT_CRON = "0 3 * * *"
PLUGIN_ICON = "https://raw.githubusercontent.com/wastedwood/DouBanSync/main/app/static/img/brand-mark.svg"


def _as_bool(value: Any, default: bool = False) -> bool:
    """把 MoviePilot 表单可能传入的多种布尔值统一为 bool。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    """把表单数字转换并限制在安全范围内。"""
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


class DouBanSync(_PluginBase):
    """将 FNTV 播放记录同步到豆瓣观看状态的 MoviePilot 插件。"""

    plugin_name = "飞牛影视同步豆瓣"
    plugin_desc = "将飞牛影视中的电影和剧集播放记录自动同步到豆瓣。"
    plugin_icon = PLUGIN_ICON
    plugin_version = "1.0.0"
    plugin_author = "wastedwood"
    author_url = "https://github.com/wastedwood/DouBanSync"
    plugin_config_prefix = "doubansync_"
    plugin_order = 50
    auth_level = 1

    _enabled = False
    _db_path = DEFAULT_DB_PATH
    _douban_cookie = ""
    _selected_user = ""
    _sync_mode = "interval"
    _sync_cron = DEFAULT_CRON
    _sync_interval_hours = 24
    _watch_threshold_percent = 90
    _private = True
    _bark_key = ""
    _store: SyncStore | None = None
    _fntv: FntvDb | None = None
    _engine: SyncEngine | None = None
    _notifier: BarkNotifier | None = None
    _run_thread: Thread | None = None
    _trigger_lock: Lock | None = None

    def init_plugin(self, config: dict | None = None) -> None:
        """读取配置、初始化状态库，并让 MoviePilot 接管定时调度。"""
        self.stop_service()
        raw = config or {}

        self._enabled = _as_bool(raw.get("enabled"), False)
        self._db_path = str(raw.get("fntv_db_path") or DEFAULT_DB_PATH).strip()
        self._douban_cookie = str(raw.get("douban_cookie") or "").strip()
        self._selected_user = str(raw.get("selected_user") or "").strip()
        self._sync_mode = str(raw.get("sync_mode") or "interval").strip().lower()
        self._sync_cron = str(raw.get("sync_cron") or DEFAULT_CRON).strip()
        self._sync_interval_hours = _as_int(
            raw.get("sync_interval_hours"), 24, minimum=1, maximum=168
        )
        self._watch_threshold_percent = _as_int(
            raw.get("watch_threshold_percent"), 90, minimum=0, maximum=100
        )
        self._private = _as_bool(raw.get("private"), True)
        self._bark_key = str(raw.get("bark_key") or "").strip()
        run_once = _as_bool(raw.get("run_once"), False)

        self._trigger_lock = Lock()
        self._notifier = BarkNotifier(self._bark_key)
        self._fntv = FntvDb(self._db_path) if self._db_path else None

        try:
            self._store = SyncStore(Path(self.get_data_path()))
            self._store.set_config(
                "watch_threshold_percent", str(self._watch_threshold_percent)
            )
            self._store.set_config("private", "true" if self._private else "false")
            self._engine = (
                SyncEngine(
                    self._fntv,
                    self._store,
                    self._douban_cookie,
                    private=self._private,
                    notifier=self._notifier,
                )
                if self._fntv
                else None
            )
        except Exception as exc:
            self._store = None
            self._engine = None
            logger.error("DouBanSync 初始化状态库失败：%s", exc)

        if run_once:
            self._save_config(run_once=False)
            started, message = self._start_background()
            if not started:
                logger.warning("DouBanSync 一次性运行未启动：%s", message)

    def get_state(self) -> bool:
        """返回插件是否启用。"""
        return self._enabled

    @staticmethod
    def get_command() -> list[dict[str, Any]]:
        """注册一个可由 MoviePilot 消息渠道触发的手动同步命令。"""
        return [
            {
                "cmd": "/doubansync_run",
                "event": EventType.PluginAction,
                "desc": "同步飞牛影视观看记录到豆瓣",
                "category": "插件",
                "data": {"action": "doubansync_run"},
            }
        ]

    def get_api(self) -> list[dict[str, Any]]:
        """注册插件详情页和外部调用使用的轻量 API。"""
        return [
            {
                "path": "/run",
                "endpoint": self.api_run,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "后台触发一次同步",
            },
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "查询同步状态",
            },
            {
                "path": "/test_db",
                "endpoint": self.api_test_db,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "验证飞牛数据库",
            },
            {
                "path": "/users",
                "endpoint": self.api_users,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "读取飞牛用户列表",
            },
            {
                "path": "/check_cookie",
                "endpoint": self.api_check_cookie,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "验证当前豆瓣 Cookie",
            },
            {
                "path": "/stats",
                "endpoint": self.api_stats,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "查询同步统计",
            },
            {
                "path": "/logs",
                "endpoint": self.api_logs,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "查询最近同步日志",
            },
        ]

    def get_service(self) -> list[dict[str, Any]]:
        """把周期任务注册给 MoviePilot 公共调度器。"""
        if not self._enabled:
            return []

        if self._sync_mode == "cron":
            try:
                trigger = CronTrigger.from_crontab(self._sync_cron)
                return [
                    {
                        "id": "DouBanSync.Sync",
                        "name": "飞牛影视豆瓣同步",
                        "trigger": trigger,
                        "func": self.sync,
                        "kwargs": {},
                    }
                ]
            except (TypeError, ValueError) as exc:
                logger.warning(
                    "DouBanSync Cron 表达式无效，将回退为间隔调度：%s (%s)",
                    self._sync_cron,
                    exc,
                )

        return [
            {
                "id": "DouBanSync.Sync",
                "name": "飞牛影视豆瓣同步",
                "trigger": "interval",
                "func": self.sync,
                "kwargs": {"hours": self._sync_interval_hours},
            }
        ]

    def get_form(self) -> tuple[list[dict], dict[str, Any]]:
        """生成 MoviePilot Vuetify 配置表单。"""
        users, db_error = self._load_users()
        user_items = [
            {
                "title": f"{item.get('username', '')} ({item.get('guid', '')})",
                "value": item.get("guid", ""),
            }
            for item in users
            if item.get("guid")
        ]

        content: list[dict[str, Any]] = [
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 6},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "enabled",
                                    "label": "启用插件",
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 6},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "run_once",
                                    "label": "保存后立即同步一次",
                                },
                            }
                        ],
                    },
                ],
            },
            {
                "component": "VTextField",
                "props": {
                    "model": "fntv_db_path",
                    "label": "飞牛影视数据库路径",
                    "hint": "MoviePilot 容器内的 trimmedia.db 路径；只读访问。",
                    "persistent-hint": True,
                },
            },
            {
                "component": "VCombobox",
                "props": {
                    "model": "selected_user",
                    "label": "同步用户",
                    "items": user_items,
                    "item-title": "title",
                    "item-value": "value",
                    "placeholder": "先填写数据库路径，再选择或输入用户 GUID",
                    "clearable": True,
                },
            },
            {
                "component": "VTextField",
                "props": {
                    "model": "douban_cookie",
                    "label": "豆瓣 Cookie",
                    "type": "password",
                    "autocomplete": "off",
                    "hint": "从已登录豆瓣的浏览器请求头复制完整 Cookie。",
                    "persistent-hint": True,
                },
            },
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSelect",
                                "props": {
                                    "model": "sync_mode",
                                    "label": "调度模式",
                                    "items": [
                                        {"title": "间隔执行", "value": "interval"},
                                        {"title": "Cron 定时", "value": "cron"},
                                    ],
                                    "item-title": "title",
                                    "item-value": "value",
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VTextField",
                                "props": {
                                    "model": "sync_interval_hours",
                                    "label": "间隔小时数",
                                    "type": "number",
                                    "min": 1,
                                    "max": 168,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VTextField",
                                "props": {
                                    "model": "sync_cron",
                                    "label": "Cron 表达式",
                                    "placeholder": "分 时 日 月 周，例如 0 3 * * *",
                                },
                            }
                        ],
                    },
                ],
            },
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 6},
                        "content": [
                            {
                                "component": "VTextField",
                                "props": {
                                    "model": "watch_threshold_percent",
                                    "label": "播放完成阈值（%）",
                                    "type": "number",
                                    "min": 0,
                                    "max": 100,
                                    "hint": "低于阈值跳过；0 表示不限制。",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 6},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {
                                    "model": "private",
                                    "label": "豆瓣标记仅自己可见",
                                },
                            }
                        ],
                    },
                ],
            },
            {
                "component": "VTextField",
                "props": {
                    "model": "bark_key",
                    "label": "Bark Key（可选）",
                    "type": "password",
                    "autocomplete": "off",
                    "hint": "填写后会推送同步摘要和 Cookie 失效提醒。",
                    "persistent-hint": True,
                },
            },
        ]

        if db_error:
            content.append(
                {
                    "component": "VAlert",
                    "props": {
                        "type": "warning",
                        "variant": "tonal",
                        "text": f"数据库状态：{db_error}",
                    },
                }
            )
        elif users:
            content.append(
                {
                    "component": "VAlert",
                    "props": {
                        "type": "success",
                        "variant": "tonal",
                        "text": f"已读取 {len(users)} 个可用 FNTV 用户；保存后调度器会自动重排。",
                    },
                }
            )

        defaults = {
            "enabled": self._enabled,
            "run_once": False,
            "fntv_db_path": self._db_path,
            "douban_cookie": self._douban_cookie,
            "selected_user": self._selected_user,
            "sync_mode": self._sync_mode,
            "sync_cron": self._sync_cron,
            "sync_interval_hours": self._sync_interval_hours,
            "watch_threshold_percent": self._watch_threshold_percent,
            "private": self._private,
            "bark_key": self._bark_key,
        }
        return [{"component": "VForm", "content": content}], defaults

    def get_page(self) -> list[dict]:
        """展示数据库、Cookie、运行状态、统计和最近日志。"""
        db_ok, db_message = self._validate_database()
        store = self._store
        user_guid = self._selected_user
        stats = {"total": 0, "done": 0, "failed": 0}
        logs: list[dict] = []
        last_sync = "从未同步"

        if store:
            if user_guid:
                stats = store.get_stats(user_guid)
            logs = store.get_logs(limit=10, offset=0)
            raw_last_sync = store.get_config("last_sync_time", "0")
            try:
                if int(raw_last_sync) > 0:
                    last_sync = datetime.fromtimestamp(
                        int(raw_last_sync) / 1000
                    ).strftime("%Y-%m-%d %H:%M:%S")
            except (TypeError, ValueError, OSError):
                pass

        running = bool(
            self._engine and self._engine.is_running
        ) or bool(self._run_thread and self._run_thread.is_alive())
        status_text = "运行中" if running else "空闲"
        cookie_text = "已配置" if self._douban_cookie else "未配置"
        db_text = "正常" if db_ok else db_message

        log_lines = []
        for item in logs:
            created = item.get("created_at", 0)
            try:
                created_text = datetime.fromtimestamp(int(created)).strftime(
                    "%m-%d %H:%M"
                )
            except (TypeError, ValueError, OSError):
                created_text = "--"
            title = item.get("series_title") or item.get("item_guid") or ""
            detail = item.get("detail") or ""
            log_lines.append(
                f"{created_text} | {item.get('action', '')} | {title} {detail}".strip()
            )

        def card(label: str, value: Any) -> dict:
            return {
                "component": "VCard",
                "content": [
                    {"component": "VCardTitle", "text": label},
                    {"component": "VCardText", "text": str(value)},
                ],
            }

        return [
            {
                "component": "VAlert",
                "props": {
                    "type": "success" if db_ok else "warning",
                    "variant": "tonal",
                    "text": (
                        f"数据库：{db_text}；Cookie：{cookie_text}；"
                        f"状态：{status_text}；上次同步：{last_sync}"
                    ),
                },
            },
            {
                "component": "VRow",
                "content": [
                    card("记录数", stats.get("total", 0)),
                    card("已同步", stats.get("done", 0)),
                    card("失败", stats.get("failed", 0)),
                ],
            },
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VBtn",
                        "props": {"color": "primary"},
                        "text": "立即同步",
                        "events": {
                            "click": {
                                "api": "plugin/DouBanSync/run",
                                "method": "post",
                            }
                        },
                    },
                    {
                        "component": "VBtn",
                        "props": {"variant": "outlined"},
                        "text": "验证 Cookie",
                        "events": {
                            "click": {
                                "api": "plugin/DouBanSync/check_cookie",
                                "method": "post",
                            }
                        },
                    },
                    {
                        "component": "VBtn",
                        "props": {"variant": "outlined"},
                        "text": "验证数据库",
                        "events": {
                            "click": {
                                "api": "plugin/DouBanSync/test_db",
                                "method": "get",
                            }
                        },
                    },
                ],
            },
            {
                "component": "VCard",
                "content": [
                    {"component": "VCardTitle", "text": "最近同步日志"},
                    {
                        "component": "VCardText",
                        "text": "\n".join(log_lines) if log_lines else "暂无日志",
                    },
                ],
            },
        ]

    def get_service_status(self) -> dict[str, Any]:
        """返回无需经过 HTTP 包装的内部状态，便于页面和 API 共用。"""
        store = self._store
        stats = {"total": 0, "done": 0, "failed": 0}
        if store and self._selected_user:
            stats = store.get_stats(self._selected_user)
        return {
            "enabled": self._enabled,
            "running": bool(
                (self._engine and self._engine.is_running)
                or (self._run_thread and self._run_thread.is_alive())
            ),
            "configured": not bool(self._configuration_error()),
            "selected_user": self._selected_user,
            "stats": stats,
        }

    def api_run(self):
        """以后台线程触发一次同步，避免阻塞 MoviePilot API 请求。"""
        started, message = self._start_background()
        if not started:
            return schemas.Response(success=False, message=message)
        return {"started": True, "message": message}

    def api_status(self):
        """查询当前运行状态。"""
        return self.get_service_status()

    def api_test_db(self):
        """验证当前配置的 FNTV 数据库是否可读。"""
        ok, message = self._validate_database()
        return {"ok": ok, "message": message}

    def api_users(self):
        """读取当前配置数据库中的活跃用户。"""
        users, error = self._load_users()
        if error:
            return schemas.Response(success=False, message=error)
        return {"users": users}

    def api_check_cookie(self):
        """验证配置中的 Cookie，不把 Cookie 放进 URL 或日志。"""
        return DoubanClient(self._douban_cookie).check_auth_detail()

    def api_stats(self):
        """查询当前用户的同步统计。"""
        if not self._selected_user:
            return schemas.Response(success=False, message="尚未选择同步用户")
        if not self._store:
            return schemas.Response(success=False, message="状态库尚未初始化")
        return self._store.get_stats(self._selected_user)

    def api_logs(self, limit: int = 50):
        """查询最近同步日志。"""
        if not self._store:
            return schemas.Response(success=False, message="状态库尚未初始化")
        try:
            safe_limit = max(1, min(200, int(limit)))
        except (TypeError, ValueError):
            safe_limit = 50
        return {"logs": self._store.get_logs(limit=safe_limit, offset=0)}

    def _configuration_error(self) -> str:
        if not self._store or not self._engine:
            return "插件状态库尚未初始化"
        if not self._fntv:
            return "未配置 FNTV 数据库路径"
        if not self._selected_user:
            return "尚未选择 FNTV 同步用户"
        if not self._douban_cookie:
            return "尚未配置豆瓣 Cookie"
        return ""

    def _validate_database(self) -> tuple[bool, str]:
        if not self._db_path:
            return False, "未配置数据库路径"
        try:
            db = FntvDb(self._db_path)
            return db.validate()
        except Exception as exc:
            return False, str(exc)

    def _load_users(self) -> tuple[list[dict], str]:
        ok, message = self._validate_database()
        if not ok:
            return [], message
        try:
            return FntvDb(self._db_path).get_users(), ""
        except Exception as exc:
            return [], str(exc)

    def _save_config(self, run_once: bool) -> None:
        """保存 MoviePilot 表单配置，避免一次性开关重复执行。"""
        self.update_config(
            {
                "enabled": self._enabled,
                "run_once": run_once,
                "fntv_db_path": self._db_path,
                "douban_cookie": self._douban_cookie,
                "selected_user": self._selected_user,
                "sync_mode": self._sync_mode,
                "sync_cron": self._sync_cron,
                "sync_interval_hours": self._sync_interval_hours,
                "watch_threshold_percent": self._watch_threshold_percent,
                "private": self._private,
                "bark_key": self._bark_key,
            }
        )

    def _start_background(self) -> tuple[bool, str]:
        """启动后台同步；同一时刻只允许一个手动任务。"""
        message = self._configuration_error()
        if message:
            return False, message

        lock = self._trigger_lock
        if lock is None:
            self._trigger_lock = Lock()
            lock = self._trigger_lock

        with lock:
            if self._run_thread and self._run_thread.is_alive():
                return False, "同步正在进行中"
            if self._engine and self._engine.is_running:
                return False, "同步正在进行中"

            engine = self._engine
            thread = Thread(
                target=self._run_sync,
                args=(engine,),
                name="DouBanSync",
                daemon=True,
            )
            self._run_thread = thread
            thread.start()
        return True, "同步任务已启动"

    def _run_sync(self, engine: SyncEngine | None) -> None:
        """在线程中执行同步，并将最新配置同步给引擎。"""
        if engine is None:
            return
        ok, message = self._validate_database()
        if not ok:
            logger.error("DouBanSync 数据库验证失败：%s", message)
            return
        engine._cookie = self._douban_cookie
        engine._private = self._private
        try:
            run_id = engine.run(self._selected_user)
            if run_id:
                logger.info("DouBanSync 同步任务完成：%s", run_id)
        except Exception as exc:
            logger.exception("DouBanSync 同步任务异常：%s", exc)

    def sync(self) -> None:
        """MoviePilot 公共调度器调用的同步入口。"""
        message = self._configuration_error()
        if message:
            logger.warning("DouBanSync 定时同步跳过：%s", message)
            return
        lock = self._trigger_lock
        if lock is None:
            self._trigger_lock = Lock()
            lock = self._trigger_lock
        with lock:
            if self._run_thread and self._run_thread.is_alive():
                logger.info("DouBanSync 定时同步跳过：已有任务运行中")
                return
            engine = self._engine
        self._run_sync(engine)

    @eventmanager.register(EventType.PluginAction)
    def remote_sync(self, event: Event) -> None:
        """处理消息渠道中的手动同步命令。"""
        event_data = event.event_data if event else {}
        if not event_data or event_data.get("action") != "doubansync_run":
            return

        channel = event_data.get("channel")
        user_id = event_data.get("user")
        try:
            self.post_message(
                channel=channel,
                title="DouBanSync 开始同步",
                userid=user_id,
            )
            self.sync()
            self.post_message(
                channel=channel,
                title="DouBanSync 同步完成",
                userid=user_id,
            )
        except Exception as exc:
            logger.exception("DouBanSync 命令执行异常：%s", exc)
            try:
                self.post_message(
                    channel=channel,
                    title=f"DouBanSync 同步失败：{exc}",
                    userid=user_id,
                )
            except Exception:
                pass

    def stop_service(self) -> None:
        """释放插件持有的对象；公共调度任务由 MoviePilot 统一撤销。"""
        self._enabled = False
        self._engine = None
        self._fntv = None
        self._store = None
        self._notifier = None
