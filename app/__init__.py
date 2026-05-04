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
    engine = SyncEngine(fntv, store, cfg.douban_cookie, cfg.private, bus) if fntv else None

    # 注册到 app 扩展
    app.extensions["store"] = store
    app.extensions["fntv"] = fntv
    app.extensions["engine"] = engine
    app.extensions["config"] = cfg
    app.extensions["event_bus"] = bus

    # 注册蓝图
    app.register_blueprint(bp)

    # 模板过滤器：Unix 时间戳 → 可读时间
    @app.template_filter("timestamp_to_dt")
    def _filter(ts: int):
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

    # 启动定时调度
    _start_scheduler(app, cfg, store, engine)

    return app


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
    interval = max(1, cfg.sync_interval_hours)
    scheduler.add_job(
        sync_job,
        "interval",
        hours=interval,
        id="douban_sync",
        replace_existing=True,
        next_run_time=None,  # 启动时不自动执行，等首次触发
    )
    scheduler.start()
    logger.info("定时同步已启动，间隔 %d 小时", interval)

    # 保存引用防止 GC
    app.extensions["scheduler"] = scheduler
