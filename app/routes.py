"""Web 路由"""

import json
import logging

from flask import Blueprint, jsonify, render_template, request, Response, stream_with_context

from app.sync_store import SyncStore
from app.fntv_db import FntvDb
from app.sync_engine import SyncEngine
from app.douban_client import DoubanClient
from app.config import Config

logger = logging.getLogger(__name__)

bp = Blueprint("web", __name__)


def _get_deps():
    """从 Flask 全局获取依赖（通过 app 扩展注入）"""
    from flask import current_app
    return (current_app.extensions["store"],
            current_app.extensions["fntv"],
            current_app.extensions["engine"],
            current_app.extensions["config"],
            current_app.extensions["event_bus"])


# ── 页面 ──────────────────────────────────────────────

@bp.route("/")
def dashboard():
    store, fntv, engine, cfg, _ = _get_deps()
    user_guid = cfg.selected_user
    stats = {"total": 0, "done": 0, "failed": 0}
    last_sync = ""
    db_connected = False

    if user_guid:
        stats = store.get_stats(user_guid)
    last_sync_ts = store.get_config("last_sync_time", "0")
    if last_sync_ts != "0":
        from datetime import datetime
        last_sync = datetime.fromtimestamp(int(last_sync_ts) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    try:
        db_connected = fntv.validate()[0]
    except Exception:
        pass

    return render_template("dashboard.html",
                           stats=stats,
                           last_sync=last_sync,
                           db_connected=db_connected,
                           cookie_set=bool(cfg.douban_cookie),
                           user_set=bool(user_guid),
                           engine_running=engine.is_running,
                           config=cfg.to_dict())


@bp.route("/config", methods=["GET", "POST"])
def config_page():
    store, fntv, engine, cfg, _ = _get_deps()
    message = ""
    error = ""

    if request.method == "POST":
        cfg.fntv_db_path = request.form.get("fntv_db_path", "")
        cfg.douban_cookie = request.form.get("douban_cookie", "")
        cfg.selected_user = request.form.get("selected_user", "")
        cfg.sync_mode = request.form.get("sync_mode", "interval")
        cfg.sync_cron = request.form.get("sync_cron", "0 3 * * *")
        try:
            hours = int(request.form.get("sync_interval_hours", 24))
            cfg.sync_interval_hours = max(1, min(168, hours))
        except ValueError:
            pass
        try:
            pct = int(request.form.get("watch_threshold_percent", 90))
            cfg.watch_threshold_percent = max(0, min(100, pct))
        except ValueError:
            pass
        cfg.private = request.form.get("private") == "on"
        cfg.bark_key = request.form.get("bark_key", "")
        message = "配置已保存"
        # 重排定时任务
        try:
            from app import reschedule_sync_job
            from flask import current_app
            reschedule_sync_job(current_app._get_current_object())
        except Exception as e:
            logger.warning("重排定时任务失败: %s", e)

    # 尝试连接获取用户列表
    users = []
    db_ok = False
    db_error = ""
    db_path = cfg.fntv_db_path
    if db_path:
        try:
            test_db = FntvDb(db_path)
            ok, msg = test_db.validate()
            if ok:
                db_ok = True
                users = test_db.get_users()
            else:
                db_error = msg
        except Exception as e:
            db_error = str(e)

    return render_template("config.html",
                           config=cfg.to_dict(),
                           users=users,
                           db_ok=db_ok,
                           db_error=db_error,
                           message=message,
                           error=error)


@bp.route("/history")
def history_page():
    store = _get_deps()[0]
    page = request.args.get("page", 1, type=int)
    per_page = 50
    logs = store.get_logs(per_page, (page - 1) * per_page)
    return render_template("history.html", logs=logs, page=page)


@bp.route("/cookie-guide")
def cookie_guide():
    return render_template("cookie_guide.html")


# ── SSE 实时事件流 ──────────────────────────────────────

@bp.route("/api/sync/stream")
def sync_stream():
    bus = _get_deps()[4]  # event_bus
    sid, q = bus.subscribe()

    def generate():
        try:
            # 发送初始连接确认
            yield f"data: {json.dumps({'type': 'connected'}, ensure_ascii=False)}\n\n"
            while True:
                payload = q.get()  # 阻塞等待事件
                yield f"data: {payload}\n\n"
        except GeneratorExit:
            bus.unsubscribe(sid)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── API ───────────────────────────────────────────────

@bp.route("/api/sync/run", methods=["POST"])
def api_sync_run():
    store, fntv, engine, cfg, _ = _get_deps()
    user_guid = cfg.selected_user
    if not user_guid:
        return jsonify({"error": "未选择同步用户"}), 400
    if engine.is_running:
        return jsonify({"error": "同步正在进行中"}), 409
    engine._cookie = cfg.douban_cookie
    run_id = engine.run(user_guid)
    return jsonify({"run_id": run_id})


@bp.route("/api/sync/status")
def api_sync_status():
    _, _, engine, _, _ = _get_deps()
    return jsonify({"running": engine.is_running})


@bp.route("/api/fntv/users")
def api_fntv_users():
    store, fntv, _, cfg, _ = _get_deps()
    db_path = request.args.get("db_path", "") or cfg.fntv_db_path
    if not db_path:
        return jsonify({"error": "未配置数据库路径"}), 400
    try:
        test_db = FntvDb(db_path)
        ok, msg = test_db.validate()
        if not ok:
            return jsonify({"error": msg}), 400
        users = test_db.get_users()
        return jsonify({"users": users})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/fntv/test-db", methods=["POST"])
def api_test_db():
    path = request.json.get("db_path", "")
    if not path:
        return jsonify({"ok": False, "error": "未提供路径"})
    try:
        test_db = FntvDb(path)
        ok, msg = test_db.validate()
        return jsonify({"ok": ok, "error": "" if ok else msg})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@bp.route("/api/douban/check-cookie", methods=["POST"])
def api_check_cookie():
    cookie = request.json.get("cookie", "")
    client = DoubanClient(cookie)
    detail = client.check_auth_detail()
    return jsonify(detail)


@bp.route("/api/config")
def api_config():
    """返回当前配置（JSON），供前端刷新用"""
    _, _, _, cfg, _ = _get_deps()
    return jsonify(cfg.to_dict())


@bp.route("/api/stats")
def api_stats():
    store, _, _, cfg, _ = _get_deps()
    user_guid = cfg.selected_user
    if not user_guid:
        return jsonify({"error": "未选择用户"}), 400
    return jsonify(store.get_stats(user_guid))


@bp.route("/api/bark/test", methods=["POST"])
def api_bark_test():
    from flask import current_app
    key = request.json.get("device_key", "")
    if not key:
        return jsonify({"ok": False, "message": "请填写 Bark Key"})

    notifier = current_app.extensions.get("notifier")
    if not notifier:
        return jsonify({"ok": False, "message": "通知器未初始化"})

    saved_key = notifier._device_key
    notifier._device_key = key
    ok = notifier.send("测试通知", "Bark 推送已生效 🎉", group="DouBanSync-测试")
    notifier._device_key = saved_key

    if ok:
        return jsonify({"ok": True, "message": "测试通知已发送，请查看手机"})
    return jsonify({"ok": False, "message": "推送失败，请检查 Bark Key"})
