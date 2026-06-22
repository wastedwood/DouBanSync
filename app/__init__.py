"""Flask 应用工厂 + APScheduler 集成"""

import logging
import os
from datetime import datetime

from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

from app.routes import bp
from app.sync_store import SyncStore
from app.fntv_db import FntvDb
from app.sync_engine import SyncEngine
from app.config import Config
from app.event_bus import EventBus
from app.notifier import BarkNotifier

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

SYNC_STATE_DIR = os.environ.get("SYNC_STATE_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "sync_state"))


def create_app() -> Flask:
    app = Flask(__name__)

    # 初始化各层
    store = SyncStore(SYNC_STATE_DIR)
    cfg = Config(store)
    fntv = FntvDb(cfg.fntv_db_path) if cfg.fntv_db_path else None
    bus = EventBus()
    notifier = BarkNotifier(cfg.bark_key)
    engine = SyncEngine(fntv, store, cfg.douban_cookie, cfg.private, bus, notifier) if fntv else None

    # 注册到 app 扩展
    app.extensions["store"] = store
    app.extensions["fntv"] = fntv
    app.extensions["engine"] = engine
    app.extensions["config"] = cfg
    app.extensions["event_bus"] = bus
    app.extensions["notifier"] = notifier

    # 注册蓝图
    app.register_blueprint(bp)

    # 模板过滤器：Unix 时间戳 → 可读时间
    @app.template_filter("timestamp_to_dt")
    def _filter(ts: int):
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

    # 启动定时调度
    _start_scheduler(app, cfg, store, engine)

    return app


def _schedule_sync_job(scheduler: BackgroundScheduler, sync_job, cfg: Config):
    """根据当前配置（interval / cron）添加或更新同步任务"""
    if scheduler.get_job("douban_sync"):
        scheduler.remove_job("douban_sync")

    if cfg.sync_mode == "cron" and cfg.sync_cron:
        parts = cfg.sync_cron.strip().split()
        if len(parts) == 5:
            scheduler.add_job(
                sync_job, "cron",
                minute=parts[0], hour=parts[1],
                day=parts[2], month=parts[3], day_of_week=parts[4],
                id="douban_sync", replace_existing=True,
            )
            logger.info("定时同步已启动 (cron): %s", cfg.sync_cron)
            return

    # 兜底：interval 模式
    interval = max(1, cfg.sync_interval_hours)
    scheduler.add_job(
        sync_job, "interval",
        hours=interval,
        id="douban_sync", replace_existing=True,
    )
    logger.info("定时同步已启动，间隔 %d 小时", interval)


def reschedule_sync_job(app: Flask):
    """外部调用（路由保存配置后）重置定时器"""
    scheduler = app.extensions.get("scheduler")
    sync_job = app.extensions.get("sync_job")
    cfg = app.extensions["config"]
    if scheduler and sync_job and cfg:
        _schedule_sync_job(scheduler, sync_job, cfg)
        logger.info("定时同步已重排")


def _start_scheduler(app: Flask, cfg: Config, store: SyncStore, engine: SyncEngine):
    """启动 APScheduler 定时同步"""

    def sync_job():
        with app.app_context():
            user_guid = cfg.selected_user
            cookie = cfg.douban_cookie
            if not user_guid or not cookie or not engine:
                logger.info("定时同步跳过：配置不完整")
                return
            if engine.is_running:
                logger.info("定时同步跳过：上一轮未完成")
                return
            engine._cookie = cookie  # 更新 cookie（可能已在 Web UI 修改）
            engine._private = cfg.private
            engine.run(user_guid)

    scheduler = BackgroundScheduler(daemon=True)
    app.extensions["sync_job"] = sync_job  # 让 reschedule 函数能找到它
    _schedule_sync_job(scheduler, sync_job, cfg)
    scheduler.start()
    app.extensions["scheduler"] = scheduler
