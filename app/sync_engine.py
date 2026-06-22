"""同步主编排引擎——集成智能跨季、播放阈值、SSE 事件推送"""

import hashlib
import logging
import uuid
import threading
from datetime import datetime

from app.fntv_db import FntvDb, ItemCategory
from app.douban_client import DoubanClient
from app.sync_store import SyncStore

logger = logging.getLogger(__name__)

SEASON_LABELS = {1: "第一季", 2: "第二季", 3: "第三季", 4: "第四季",
                 5: "第五季", 6: "第六季", 7: "第七季", 8: "第八季",
                 9: "第九季", 10: "第十季"}


class SyncEngine:
    """FNTV → 豆瓣 同步引擎"""

    def __init__(self, fntv: FntvDb, store: SyncStore, cookie: str,
                 private: bool = True, event_bus=None, notifier=None):
        self._fntv = fntv
        self._store = store
        self._cookie = cookie
        self._private = private
        self._event_bus = event_bus
        self._notifier = notifier
        self._lock = threading.Lock()
        self._running = False
        self._stats = {}

    @property
    def is_running(self) -> bool:
        return self._running

    # ── 事件帮助方法 ─────────────────────────────────

    def _log(self, run_id: str, action: str, item_guid: str = "",
             series_title: str = "", detail: str = ""):
        """写日志到 store 并广播到事件总线"""
        self._store.log_action(run_id, action, item_guid, series_title, detail)
        if self._event_bus:
            self._event_bus.publish({
                "type": "log",
                "run_id": run_id,
                "action": action,
                "series_title": series_title,
                "detail": detail,
            })

    def _emit(self, run_id: str, event_type: str, **extra):
        if self._event_bus:
            self._event_bus.publish({"type": event_type, "run_id": run_id, **extra})

    # ── 播放百分比过滤 ───────────────────────────────

    @staticmethod
    def _calc_watch_pct(play: dict) -> tuple[float, bool]:
        """计算播放百分比，返回 (百分比, 是否可判定)"""
        runtime = play.get("runtime_minutes") or 0
        if runtime <= 0:
            return 100.0, False  # 无法判定，默认通过
        pct = (play["position_seconds"] / (runtime * 60)) * 100
        return pct, True

    @staticmethod
    def _compute_fingerprint(plays: list[dict]) -> str:
        """对即将处理的播放记录计算确定性指纹"""
        sorted_plays = sorted(plays, key=lambda p: p["item_guid"])
        parts = [f"{p['item_guid']}:{p['position_seconds']}" for p in sorted_plays]
        return hashlib.md5("|".join(parts).encode()).hexdigest()

    # ── 季度搜索标签 ─────────────────────────────────

    @staticmethod
    def _season_label(season_number: int) -> str:
        return SEASON_LABELS.get(season_number, f"第{season_number}季")

    # ── 主同步流程 ───────────────────────────────────

    def run(self, user_guid: str) -> str:
        """执行一次同步，返回 run_id"""
        if not self._lock.acquire(blocking=False):
            logger.warning("同步正在执行中，跳过")
            return ""
        try:
            self._running = True
            return self._do_run(user_guid)
        finally:
            self._running = False
            self._lock.release()

    def _do_run(self, user_guid: str) -> str:
        run_id = uuid.uuid4().hex[:12]
        self._stats = {"done": 0, "doing": 0, "failed": 0, "skipped": 0}
        logger.info("[%s] 同步开始 user=%s", run_id, user_guid)
        self._emit(run_id, "sync_start")

        client = DoubanClient(self._cookie)
        if not client.check_auth():
            logger.error("[%s] 豆瓣认证失败，请检查 Cookie", run_id)
            self._log(run_id, "auth_failed", detail="豆瓣 Cookie 无效")
            self._emit(run_id, "sync_end", success=False)
            if self._notifier and self._notifier.enabled:
                self._notifier.send("⚠️ 豆瓣同步失败", "Cookie 已过期，请在 Web 端更新",
                                    group="DouBanSync-警报")
            return run_id

        last_sync = int(self._store.get_config("last_sync_time", "0"))
        plays = self._fntv.get_new_plays(user_guid, last_sync)
        if not plays:
            logger.info("[%s] 无新增播放记录", run_id)
            self._log(run_id, "no_new_records")
            self._store.set_config("last_sync_time", str(int(datetime.now().timestamp() * 1000)))
            self._emit(run_id, "sync_end", success=True)
            return run_id

        logger.info("[%s] 发现 %d 条新播放记录", run_id, len(plays))

        # 1) 播放百分比阈值过滤
        threshold = int(self._store.get_config("watch_threshold_percent", "90"))
        if threshold > 0:
            before = len(plays)
            kept = []
            for p in plays:
                pct, ok = self._calc_watch_pct(p)
                if ok:
                    p["_watch_pct"] = round(pct, 1)
                    if pct < threshold:
                        logger.info("[%s] 播放不足阈值 %.1f%% < %d%%: %s",
                                    run_id, pct, threshold, p.get("title", ""))
                        self._log(run_id, "skip_threshold", p["item_guid"],
                                  p.get("title", ""), f"播放 {pct:.1f}% < 阈值 {threshold}%")
                        continue
                kept.append(p)
            plays = kept
            filtered = before - len(plays)
            if filtered:
                logger.info("[%s] 播放阈值过滤: %d/%d 跳过", run_id, filtered, before)

        if not plays:
            logger.info("[%s] 过滤后无剩余播放记录", run_id)
            self._log(run_id, "all_filtered", detail=f"全部未达阈值 {threshold}%")
            self._emit(run_id, "sync_end", success=True)
            return run_id

        # 3) 指纹检查：播放记录较上次无变化则跳过豆瓣调用
        fp = self._compute_fingerprint(plays)
        last_fp = self._store.get_config("last_play_fingerprint", "")
        if fp == last_fp:
            logger.info("[%s] 播放记录较上次无变化，跳过豆瓣API调用", run_id)
            self._log(run_id, "no_change_skip", detail="播放记录无变化")
            self._emit(run_id, "sync_end", success=True)
            return run_id

        # 4) 分组：电影 和 电视剧单集（含智能跨季回退）
        movie_plays = []
        tv_groups = {}  # {(series_guid, season_number_or_0): {info, plays, is_inferred}}

        conn = self._fntv.get_conn()
        for play in plays:
            cat = self._fntv.classify_item(conn, play["item_guid"])

            if cat == ItemCategory.MOVIE:
                movie_plays.append(play)

            elif cat == ItemCategory.EPISODE:
                info = self._fntv.get_series_hierarchy(conn, play["item_guid"])

                if info:
                    # 标准层级成功
                    key = (info["series_guid"], info["season_number"] or 0)
                    tv_groups.setdefault(key, {"info": info, "plays": [], "is_inferred": False})
                    tv_groups[key]["plays"].append(play)

                else:
                    # 标准层级失败 → 尝试扁平结构回退
                    flat = self._fntv.get_series_for_episode_flat(conn, play["item_guid"])
                    if flat:
                        ep_num = play.get("episode_number")
                        inferred = None
                        if ep_num:
                            inferred = self._fntv.infer_episode_group(
                                conn, flat["series_guid"], ep_num)

                        # 构造模拟 info
                        info = {
                            "series_guid": flat["series_guid"],
                            "season_guid": "",  # 无真实 season
                            "season_number": inferred["season_number"] if inferred else None,
                            "series_title": flat["series_title"],
                            "_total_eps_override": inferred["total_eps"] if inferred else None,
                        }
                        key = (info["series_guid"], info["season_number"] or 0)
                        tv_groups.setdefault(key, {"info": info, "plays": [], "is_inferred": True})
                        tv_groups[key]["plays"].append(play)
                        logger.info("[%s] 智能跨季回退: %s ep=%s → 季%s",
                                    run_id, flat["series_title"], ep_num,
                                    info["season_number"] or "?")
                    else:
                        logger.warning("[%s] 无法获取条目层级: %s", run_id, play["item_guid"])
        conn.close()

        # 5) 处理电影
        for play in movie_plays:
            self._process_movie(run_id, client, user_guid, play)

        # 6) 处理电视剧分组
        for key, group in tv_groups.items():
            self._process_tv_group(run_id, client, user_guid,
                                   group["info"], group["plays"],
                                   is_inferred=group["is_inferred"])

        # 更新同步时间戳和指纹
        max_time = max(p["play_update_time"] for p in plays)
        self._store.set_config("last_sync_time", str(max_time))
        self._store.set_config("last_play_fingerprint", fp)

        logger.info("[%s] 同步完成", run_id)
        self._emit(run_id, "sync_end", success=True)
        self._send_summary()
        return run_id

    # ── 通知 ────────────────────────────────────────

    def _send_summary(self):
        if not self._notifier or not self._notifier.enabled:
            return
        parts = []
        if self._stats["done"]:
            parts.append(f"看过 {self._stats['done']}")
        if self._stats["doing"]:
            parts.append(f"在看 {self._stats['doing']}")
        if self._stats["failed"]:
            parts.append(f"失败 {self._stats['failed']}")
        if self._stats["skipped"]:
            parts.append(f"跳过 {self._stats['skipped']}")
        body = "、".join(parts) if parts else "无变更"
        self._notifier.send("同步完成", body)

    # ── 电影 ─────────────────────────────────────────

    def _process_movie(self, run_id: str, client: DoubanClient,
                       user_guid: str, play: dict):
        item_guid = play["item_guid"]
        title = play["title"] or play["original_title"] or "未知片名"

        state = self._store.get_state(user_guid, item_guid)
        if state and state["status"] == "done":
            self._log(run_id, "skip_done", item_guid, title, "电影已标记过")
            self._stats["skipped"] += 1
            return

        name, sid = client.search_subject(title)
        if not sid:
            logger.warning("[%s] 豆瓣搜索无结果: %s", run_id, title)
            self._store.upsert_state(user_guid, item_guid, media_type="movie",
                                     status="failed",
                                     play_update_time=play["play_update_time"])
            self._log(run_id, "error_search", item_guid, title, "豆瓣搜索无结果")
            self._stats["failed"] += 1
            return

        ok = client.mark_interest(sid, "done", self._private)
        if ok:
            self._store.upsert_state(user_guid, item_guid,
                                     media_type="movie", status="done",
                                     douban_subject_id=sid,
                                     play_update_time=play["play_update_time"])
            self._log(run_id, "mark_done", item_guid, title, f"豆瓣ID={sid}")
            logger.info("[%s] 电影标记看过: %s", run_id, title)
            self._stats["done"] += 1
        else:
            self._store.upsert_state(user_guid, item_guid,
                                     media_type="movie", status="failed",
                                     play_update_time=play["play_update_time"])
            self._log(run_id, "error_api", item_guid, title,
                      f"标记失败 sid={sid}")
            self._stats["failed"] += 1

    # ── 电视剧 ───────────────────────────────────────

    def _process_tv_group(self, run_id: str, client: DoubanClient,
                          user_guid: str, info: dict, plays: list,
                          is_inferred: bool = False):
        series_guid = info["series_guid"]
        season_number = info.get("season_number")
        season_guid = info.get("season_guid", "")
        series_title = info["series_title"] or "未知剧集"

        conn = self._fntv.get_conn()

        if is_inferred and info.get("_total_eps_override"):
            # 扁平回退场景：使用推断的 total_eps
            total_eps = info["_total_eps_override"]
            max_watched = max(p.get("episode_number") or 0 for p in plays)
        elif season_guid:
            total_eps = self._fntv.get_season_total_episodes(conn, season_guid)
            max_watched = self._fntv.get_season_max_watched(conn, user_guid, season_guid)
        else:
            # 最极端回退：没有 season_guid
            total_eps = 0
            max_watched = max(p.get("episode_number") or 0 for p in plays)
        conn.close()

        current_status = self._store.get_series_status(user_guid, series_guid,
                                                       season_number or 0)

        # 幂等：已完成则跳过
        if current_status == "done":
            self._log(run_id, "skip_done", series_guid, series_title, "已标记看过")
            self._stats["skipped"] += 1
            return

        # 搜索豆瓣
        subject_id = None
        for play in plays:
            st = self._store.get_state(user_guid, play["item_guid"])
            if st and st.get("douban_subject_id"):
                subject_id = st["douban_subject_id"]
                break

        if not subject_id:
            # 智能搜索：如有季度信息则附加季度标签
            search_title = series_title
            if is_inferred and season_number:
                search_title = f"{series_title} {self._season_label(season_number)}"

            name, subject_id = client.search_subject(search_title)
            if not subject_id:
                logger.warning("[%s] 豆瓣搜索无结果: %s", run_id, search_title)
                for play in plays:
                    self._store.upsert_state(user_guid, play["item_guid"],
                                             media_type="episode",
                                             status="failed",
                                             series_guid=series_guid,
                                             season_number=season_number,
                                             series_title=series_title,
                                             episode_number=play.get("episode_number"),
                                             play_update_time=play["play_update_time"])
                self._log(run_id, "error_search", series_guid, search_title,
                          "豆瓣搜索无结果")
                self._stats["failed"] += 1
                return

        # 决定跃迁
        if not is_inferred or not info.get("_total_eps_override"):
            max_watched = max(max_watched,
                              max(p.get("episode_number") or 0 for p in plays))

        is_complete = total_eps > 0 and max_watched >= total_eps

        if current_status in (None, "pending"):
            new_status = "done" if is_complete else "doing"
            interest = "done" if is_complete else "doing"
        elif current_status == "doing":
            if is_complete:
                new_status = "done"
                interest = "done"
            else:
                new_status = "doing"
                interest = None
        else:
            new_status = current_status
            interest = None

        if interest:
            ok = client.mark_interest(subject_id, interest, self._private)
            if not ok:
                for play in plays:
                    self._store.upsert_state(user_guid, play["item_guid"],
                                             media_type="episode",
                                             status="failed",
                                             series_guid=series_guid,
                                             season_number=season_number,
                                             series_title=series_title,
                                             douban_subject_id=subject_id,
                                             episode_number=play.get("episode_number"),
                                             max_ep_watched=max_watched,
                                             total_episodes=total_eps,
                                             play_update_time=play["play_update_time"])
                self._log(run_id, "error_api", series_guid, series_title,
                          f"标记{interest}失败 sid={subject_id}")
                logger.error("[%s] 豆瓣标记[%s]失败: %s", run_id, interest, series_title)
                self._stats["failed"] += 1
                return
            action = "mark_done" if interest == "done" else "mark_doing"
            self._log(run_id, action, series_guid, series_title,
                      f"豆瓣ID={subject_id} ep={max_watched}/{total_eps}")
            logger.info("[%s] %s: %s (%s)", run_id, action, series_title, interest)
            if interest == "done":
                self._stats["done"] += 1
            else:
                self._stats["doing"] += 1
        else:
            self._log(run_id, "skip_middle", series_guid, series_title,
                      f"中间集跳过 ep={max_watched}/{total_eps}")
            self._stats["skipped"] += 1

        # 更新所有本批播放记录的状态
        for play in plays:
            self._store.upsert_state(user_guid, play["item_guid"],
                                     media_type="episode",
                                     status=new_status,
                                     series_guid=series_guid,
                                     season_number=season_number,
                                     series_title=series_title,
                                     douban_subject_id=subject_id,
                                     episode_number=play.get("episode_number"),
                                     max_ep_watched=max_watched,
                                     total_episodes=total_eps,
                                     play_update_time=play["play_update_time"])
