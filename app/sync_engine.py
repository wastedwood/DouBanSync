"""同步主编排引擎——集成智能跨季、播放阈值、SSE 事件推送"""

import hashlib
import logging
import re
import uuid
import threading
from datetime import datetime

from app.fntv_db import FntvDb, ItemCategory
from app.douban_client import DoubanClient, extract_season_info
from app.sync_store import SyncStore

logger = logging.getLogger(__name__)

SEASON_LABELS = {1: "第一季", 2: "第二季", 3: "第三季", 4: "第四季",
                 5: "第五季", 6: "第六季", 7: "第七季", 8: "第八季",
                 9: "第九季", 10: "第十季"}

SUMMARY_ACTIONS = {
    "mark_done": ("done", ""),
    "mark_doing": ("doing", ""),
    "error_search": ("failed", "豆瓣搜索无结果"),
    "error_api": ("failed", "豆瓣标记失败"),
    "skip_done": ("skipped", "此前已同步"),
    "skip_middle": ("skipped", "中间集，无需更新豆瓣"),
}

SUMMARY_SECTIONS = (
    ("done", "✅ 已看完"),
    ("doing", "▶️ 在看"),
    ("failed", "❌ 失败"),
    ("skipped", "⏭️ 跳过"),
)

MAX_SUMMARY_ITEMS = 3

MAX_SEASON_CANDIDATES = 8  # 按季标题匹配时最多核对的豆瓣条目数

# 飞牛季标题只是「Ⅱ」「III」这类序号时，按季号搜索
ROMAN_NUMERAL_REGEX = re.compile(r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+|[IVX]+")


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
        self._summary_items = {}

    @property
    def is_running(self) -> bool:
        return self._running

    # ── 事件帮助方法 ─────────────────────────────────

    def _log(self, run_id: str, action: str, item_guid: str = "",
             series_title: str = "", detail: str = ""):
        """写日志到 store 并广播到事件总线"""
        self._store.log_action(run_id, action, item_guid, series_title, detail)
        summary = SUMMARY_ACTIONS.get(action)
        if summary and series_title:
            category, reason = summary
            self._summary_items.setdefault(category, []).append((series_title, reason))
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
        if play.get("watched"):
            return 100.0, True
        runtime = play.get("runtime_minutes") or 0
        if runtime <= 0:
            return 100.0, False  # 无法判定，默认通过
        pct = (play["position_seconds"] / (runtime * 60)) * 100
        return pct, True

    @staticmethod
    def _compute_fingerprint(plays: list[dict]) -> str:
        """对即将处理的播放记录计算确定性指纹"""
        sorted_plays = sorted(plays, key=lambda p: p["item_guid"])
        parts = [
            f"{p['item_guid']}:{p['position_seconds']}:{int(bool(p.get('watched')))}"
            for p in sorted_plays
        ]
        return hashlib.md5("|".join(parts).encode()).hexdigest()

    # ── 季度搜索标签 ─────────────────────────────────

    @staticmethod
    def _season_label(season_number: int) -> str:
        return SEASON_LABELS.get(season_number, f"第{season_number}季")

    @staticmethod
    def _resolve_season(series_title: str, season_number: int | None) -> tuple[str, int | None]:
        """返回 (去季度剧名, 实际季度)"""
        clean_title, title_season = extract_season_info(series_title)
        # 续作常作为独立剧集入库（如「庆余年 第二季」下只有第 1 季），此时以剧名中的季度为准
        if title_season and season_number in (None, 1):
            return clean_title, title_season
        return clean_title, season_number

    @classmethod
    def _build_tv_search_title(cls, series_title: str, season_number: int | None,
                               is_inferred: bool = False) -> str:
        """构造电视剧搜索词，避免多季剧集始终命中第一季"""
        clean_title, effective_season = cls._resolve_season(series_title, season_number)
        # 标准层级的第一季沿用总剧名搜索；第二季及以后必须带季度标签。
        # 扁平结构的季度号是推断得到的，第一季也保留原有的带标签搜索策略。
        if effective_season and (is_inferred or effective_season > 1):
            return f"{clean_title} {cls._season_label(effective_season)}"
        return clean_title

    @staticmethod
    def _season_tag(clean_title: str, season_title: str | None) -> str:
        """飞牛季标题不是「第 N 季」这类通用写法时（如「最终季」「飙马野郎篇」），返回它作为豆瓣搜索的季标签"""
        tag = (season_title or "").strip()
        if clean_title and tag.startswith(clean_title):
            tag = tag[len(clean_title):].strip()
        if not tag or extract_season_info(tag)[1] or tag.isdigit() or ROMAN_NUMERAL_REGEX.fullmatch(tag):
            return ""
        return tag

    def _season_parts(self, client: DoubanClient, series_title: str, season_number: int | None,
                      season_title: str | None, total_eps: int) -> list[tuple[str, int]]:
        """第 2 季及以后按季标题找出该季在豆瓣上的条目，返回 [(条目 ID, 集数)]，按上线先后

        豆瓣常把一季拆成多个条目（Part.1/Part.2、诀别谭/相克谭），按集数累计对齐飞牛该季总集数：
        非剧集条目（剧场版、完结篇）跳过，累计达到总集数即止，之后的新篇不算该季。
        """
        clean_title, season = self._resolve_season(series_title, season_number)
        tag = self._season_tag(clean_title, season_title) if season and season > 1 else ""
        if not tag:
            return []
        parts, covered = [], 0
        for _, sid in client.search_season_parts(clean_title, tag)[:MAX_SEASON_CANDIDATES]:
            abstract = client.get_subject_abstract(sid)
            if abstract is None:
                return []  # 读不到集数就无法对齐，宁可放弃也不误标
            if not abstract.get("is_tv"):
                continue
            count = str(abstract.get("episodes_count") or "")
            eps = int(count) if count.isdigit() else 0
            parts.append((sid, eps))
            covered += eps
            if not eps or not total_eps or covered >= total_eps:
                break
        return parts

    def _search_tv_subjects(self, client: DoubanClient, series_title: str,
                            season_number: int | None, season_title: str | None = "",
                            total_eps: int = 0, is_inferred: bool = False) -> list[tuple[str, int]]:
        """搜索某季对应的豆瓣条目 [(条目 ID, 集数)]，首个为主条目；季标题匹配不到时按季号搜索"""
        parts = self._season_parts(client, series_title, season_number, season_title, total_eps)
        if parts:
            return parts
        _, season = self._resolve_season(series_title, season_number)
        search_title = self._build_tv_search_title(series_title, season_number, is_inferred)
        _, sid = client.search_subject(search_title, season_number=season)
        return [(sid, 0)] if sid else []

    @staticmethod
    def _part_interests(parts: list[tuple[str, int]], interest: str,
                        max_watched: int) -> list[tuple[str, str]]:
        """把一季的进度映射到豆瓣各分部：看完的分部标看过，正在看的分部标在看"""
        if interest == "done":
            return [(sid, "done") for sid, _ in parts]
        result, watched_before = [], 0
        for sid, eps in parts:
            if eps and watched_before + eps <= max_watched:
                result.append((sid, "done"))
                watched_before += eps
            else:
                result.append((sid, "doing"))
                break
        return result

    def _mark_season(self, client: DoubanClient, parts: list[tuple[str, int]],
                     interest: str, max_watched: int) -> list[str]:
        """按进度标记该季的豆瓣条目，返回「ID(状态)」列表，任一失败返回空列表"""
        targets = self._part_interests(parts, interest, max_watched)
        if all(client.mark_interest(sid, status, self._private) for sid, status in targets):
            return [f"{sid}({status})" for sid, status in targets]
        return []

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
        self._summary_items = {key: [] for key, _ in SUMMARY_SECTIONS}
        logger.info("[%s] 同步开始 user=%s", run_id, user_guid)
        self._emit(run_id, "sync_start")

        client = DoubanClient(self._cookie)
        if not client.check_auth():
            logger.error("[%s] 豆瓣认证失败，请检查 Cookie", run_id)
            self._log(run_id, "auth_failed", detail="豆瓣 Cookie 无效")
            self._emit(run_id, "sync_end", success=False)
            if self._notifier and self._notifier.enabled:
                self._notifier.send("DouBanSync", "⚠️ Cookie 过期，请在 Web 端更新",
                                    group="DouBanSync-警报")
            return run_id

        # 旧版本把 done 原样发送给豆瓣，可能只返回成功但仍停留在 wish。
        # 首次升级后检查本地已完成条目，修复实际状态不一致的历史记录。
        self._repair_legacy_done(run_id, client, user_guid)
        self._repair_season_subjects(run_id, client, user_guid)
        self._clean_wish_list(run_id, client)

        last_sync = int(self._store.get_config("last_sync_time", "0"))
        plays = self._fntv.get_new_plays(user_guid, last_sync)
        if not plays:
            logger.info("[%s] 无新增播放记录", run_id)
            self._log(run_id, "no_new_records")
            self._store.set_config("last_sync_time", str(int(datetime.now().timestamp() * 1000)))
            self._emit(run_id, "sync_end", success=True)
            return run_id

        logger.info("[%s] 发现 %d 条新播放记录", run_id, len(plays))

        # 1) 播放进度判定：达到阈值（或飞牛标记已看）算看完，未达阈值算在看，没有进度的忽略
        threshold = int(self._store.get_config("watch_threshold_percent", "90"))
        kept = []
        for p in plays:
            pct, ok = self._calc_watch_pct(p)
            if ok:
                p["_watch_pct"] = round(pct, 1)
                if pct <= 0:
                    continue
            p["_complete"] = not ok or pct >= threshold
            if not p["_complete"]:
                logger.info("[%s] 播放未达阈值 %.1f%% < %d%%，按在看处理: %s",
                            run_id, pct, threshold, p.get("title", ""))
            kept.append(p)
        plays = kept

        if not plays:
            logger.info("[%s] 过滤后无剩余播放记录", run_id)
            self._log(run_id, "all_filtered", detail="播放进度均为 0")
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
                    # 标准层级成功；第 0 季是特别篇，豆瓣通常无对应条目，搜索会误中第一季
                    if info["season_number"] == 0:
                        self._log(run_id, "skip_special", play["item_guid"],
                                  info["series_title"] or "", "特别篇不同步")
                        continue
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

                        season_num = None
                        total_eps_override = None
                        if inferred:
                            season_num = inferred.get("season_number")
                            total_eps_override = inferred.get("total_eps")
                        if not season_num:
                            season_num = flat.get("season_number") or play.get("season_number")

                        # 构造模拟 info
                        info = {
                            "series_guid": flat["series_guid"],
                            "season_guid": "",  # 无真实 season
                            "season_number": season_num,
                            "series_title": flat["series_title"],
                            "_total_eps_override": total_eps_override,
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

    def _repair_legacy_done(self, run_id: str, client: DoubanClient,
                            user_guid: str):
        """一次性修复旧版本误记为 done、但豆瓣仍处于 wish 的条目"""
        marker = f"douban_interest_mapping_v2:{user_guid}"
        if self._store.get_config(marker, "") == "1":
            return

        subjects = self._store.get_done_subjects(user_guid)
        checked = repaired = failed = 0
        for item in subjects:
            subject_id = item["douban_subject_id"]
            checked += 1
            actual = client.get_interest_status(subject_id)
            if actual == "collect":
                continue
            if actual is None or not client.mark_interest(subject_id, "done", self._private):
                failed += 1
                logger.warning("[%s] 历史豆瓣状态修复失败 sid=%s actual=%s",
                               run_id, subject_id, actual or "未知")
            else:
                repaired += 1

        if not failed:
            self._store.set_config(marker, "1")
        logger.info("[%s] 历史豆瓣状态检查完成: 检查=%d 修复=%d 失败=%d",
                    run_id, checked, repaired, failed)

    def _repair_season_subjects(self, run_id: str, client: DoubanClient,
                                user_guid: str):
        """一次性修复已同步电视剧季的豆瓣条目与状态

        第 2 季及以后误标到第一季或其他剧的条目：重新搜索（按季标题 / 季号），找到不同条目才改标，
        并按飞牛当前进度重算状态（最后一集看完才算看过）；找不到则保持原样。
        原先误标的条目不撤销，由用户自行核对。
        """
        marker = f"season_subject_repair_v3:{user_guid}"
        if self._store.get_config(marker, "") == "1":
            return

        checked = repaired = failed = 0
        conn = self._fntv.get_conn()
        try:
            for group in self._store.get_season_subjects(user_guid):
                series_title = group["series_title"]
                _, season = self._resolve_season(series_title, group["season_number"])
                if not season or season <= 1:
                    continue
                checked += 1
                old_sid = group["douban_subject_id"]
                watched = group["max_ep_watched"] or 0
                total = group["total_episodes"] or 0
                season_row = self._fntv.get_season(conn, group["series_guid"],
                                                   group["season_number"]) or {}
                if season_row:
                    watched = max(watched, self._fntv.get_season_max_watched(
                        conn, user_guid, season_row["guid"]))
                    total = max(total, self._fntv.get_season_total_episodes(conn, season_row["guid"]))

                search_title = self._build_tv_search_title(series_title, group["season_number"])
                parts = self._search_tv_subjects(client, series_title, group["season_number"],
                                                 season_row.get("title", ""), total)
                if not parts or parts[0][0] == old_sid:
                    continue
                status = ("done" if watched >= total else "doing") if total else group["status"]
                marked = self._mark_season(client, parts, status, watched)
                if not marked:
                    failed += 1
                    logger.warning("[%s] 电视剧季修复失败: %s sid=%s", run_id, search_title,
                                   ",".join(sid for sid, _ in parts))
                    continue
                self._store.update_season_subject(user_guid, group["series_guid"],
                                                  group["season_number"], old_sid, parts[0][0], status)
                self._log(run_id, "repair_subject", group["series_guid"], search_title,
                          f"豆瓣ID {old_sid} → {'、'.join(marked)} ep={watched}/{total}")
                repaired += 1
        finally:
            conn.close()

        if not failed:
            self._store.set_config(marker, "1")
        logger.info("[%s] 多季豆瓣条目检查完成: 检查=%d 修复=%d 失败=%d",
                    run_id, checked, repaired, failed)

    # ── 想看清理 ─────────────────────────────────────

    @staticmethod
    def _match_library(names: list[str], imdb_id: str, library: list[dict]) -> dict | None:
        """在飞牛库中找豆瓣条目对应的电影 / 剧集

        IMDb 一致优先；豆瓣没有 IMDb 或飞牛条目没有 IMDb 时按中文名 / 原名精确匹配。
        豆瓣条目带第 2 季及以后的季号时，飞牛里必须有这一季。
        """
        season = next((s for _, s in map(extract_season_info, names) if s), None)
        clean_names = {extract_season_info(n)[0].lower() for n in names}
        for entry in library:
            if imdb_id and entry["imdb_id"]:
                matched = entry["imdb_id"] == imdb_id
            else:
                matched = bool(clean_names & {entry["title"].lower(), entry["original_title"].lower()} - {""})
            if matched and (not season or season == 1 or season in entry["seasons"]):
                return entry
        return None

    def _clean_wish_list(self, run_id: str, client: DoubanClient):
        """豆瓣「想看」中已在飞牛库里的影片去掉想看标记（配置开关，默认关闭）

        只处理想看列表里的条目，在看 / 看过不动。
        """
        if self._store.get_config("clean_wish", "") != "true":
            return
        wishes = client.get_wish_list()
        if not wishes:
            return
        conn = self._fntv.get_conn()
        try:
            library = self._fntv.get_library_titles(conn)
        finally:
            conn.close()

        removed = 0
        for wish in wishes:
            entry = self._match_library(wish["names"], client.get_subject_imdb(wish["sid"]), library)
            if not entry:
                continue
            title = wish["names"][0]
            if client.remove_interest(wish["sid"]):
                self._log(run_id, "remove_wish", wish["sid"], title, f"飞牛库已有「{entry['title']}」")
                removed += 1
            else:
                self._log(run_id, "error_api", wish["sid"], title, "移出想看失败")
        logger.info("[%s] 想看清理完成: 想看=%d 移出=%d", run_id, len(wishes), removed)

    # ── 通知 ────────────────────────────────────────

    @staticmethod
    def _build_summary_body(stats: dict, summary_items: dict) -> str:
        lines = []
        for category, label in SUMMARY_SECTIONS:
            count = stats.get(category, 0)
            if not count:
                continue
            lines.append(f"{label}（{count}）")
            items = summary_items.get(category, [])
            for title, reason in items[:MAX_SUMMARY_ITEMS]:
                suffix = f"：{reason}" if reason else ""
                lines.append(f"• {title}{suffix}")
            if count > MAX_SUMMARY_ITEMS:
                lines.append(f"• 另有 {count - MAX_SUMMARY_ITEMS} 项")
            lines.append("")

        total = sum(stats.get(key, 0) for key, _ in SUMMARY_SECTIONS)
        lines.append(f"本次共处理 {total} 项" if total else "本次无状态变更")
        return "\n".join(lines).strip()

    def _send_summary(self):
        if not self._notifier or not self._notifier.enabled:
            return
        if self._stats["failed"]:
            title = "DouBanSync · 同步有异常"
        elif self._stats["done"] or self._stats["doing"]:
            title = "DouBanSync · 同步完成"
        else:
            title = "DouBanSync · 无需更新"
        body = self._build_summary_body(self._stats, self._summary_items)
        self._notifier.send(title, body)

    # ── 电影 ─────────────────────────────────────────

    def _process_movie(self, run_id: str, client: DoubanClient,
                       user_guid: str, play: dict):
        item_guid = play["item_guid"]
        title = play["title"] or play["original_title"] or "未知片名"

        # 达到阈值算看过，有进度但未达阈值算在看
        interest = "done" if play.get("_complete", True) else "doing"
        state = self._store.get_state(user_guid, item_guid)
        if state and state["status"] == "done":
            self._log(run_id, "skip_done", item_guid, title, "电影已标记过")
            self._stats["skipped"] += 1
            return
        if state and state["status"] == "doing" and interest == "doing":
            self._log(run_id, "skip_done", item_guid, title, "电影已标记在看")
            self._stats["skipped"] += 1
            return

        sid = state.get("douban_subject_id") if state else None
        if not sid:
            _, sid = client.search_subject(title)
        if not sid:
            logger.warning("[%s] 豆瓣搜索无结果: %s", run_id, title)
            self._store.upsert_state(user_guid, item_guid, media_type="movie",
                                     status="failed",
                                     play_update_time=play["play_update_time"])
            self._log(run_id, "error_search", item_guid, title, "豆瓣搜索无结果")
            self._stats["failed"] += 1
            return

        ok = client.mark_interest(sid, interest, self._private)
        if ok:
            self._store.upsert_state(user_guid, item_guid,
                                     media_type="movie", status=interest,
                                     douban_subject_id=sid,
                                     play_update_time=play["play_update_time"])
            self._log(run_id, f"mark_{interest}", item_guid, title, f"豆瓣ID={sid}")
            logger.info("[%s] 电影标记%s: %s", run_id, "看过" if interest == "done" else "在看", title)
            self._stats[interest] += 1
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
        # 未达阈值的单集只说明在看，不计入看到第几集
        played_max = max((p.get("episode_number") or 0 for p in plays
                          if p.get("_complete", True)), default=0)

        if is_inferred and info.get("_total_eps_override"):
            # 扁平回退场景：使用推断的 total_eps
            total_eps = info["_total_eps_override"]
            max_watched = played_max
        elif season_guid:
            total_eps = self._fntv.get_season_total_episodes(conn, season_guid)
            max_watched = self._fntv.get_season_max_watched(conn, user_guid, season_guid)
        else:
            # 最极端回退：没有 season_guid
            total_eps = 0
            max_watched = played_max
        conn.close()

        current_status = self._store.get_series_status(user_guid, series_guid,
                                                       season_number or 0)

        # 幂等：已完成则跳过
        if current_status == "done":
            self._log(run_id, "skip_done", series_guid, series_title, "已标记看过")
            self._stats["skipped"] += 1
            return

        # 搜索豆瓣
        season_title = info.get("season_title") or ""
        parts = []
        for play in plays:
            st = self._store.get_state(user_guid, play["item_guid"])
            if st and st.get("douban_subject_id"):
                parts = [(st["douban_subject_id"], 0)]
                break
        from_store = bool(parts)

        if not parts:
            # 智能搜索：优先按季标题，否则附加季度标签，避免豆瓣默认返回第一季
            search_title = self._build_tv_search_title(
                series_title, season_number, is_inferred
            )
            parts = self._search_tv_subjects(client, series_title, season_number,
                                             season_title, total_eps, is_inferred)
            if not parts:
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
        subject_id = parts[0][0]

        # 决定跃迁
        if not is_inferred or not info.get("_total_eps_override"):
            max_watched = max(max_watched, played_max)

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
            if from_store:
                # 本地只记了主条目，重新按季标题对齐豆瓣各分部
                parts = self._season_parts(client, series_title, season_number,
                                           season_title, total_eps) or parts
            subject_id = parts[0][0]
            marked = self._mark_season(client, parts, interest, max_watched)
            if not marked:
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
                      f"豆瓣ID={','.join(marked)} ep={max_watched}/{total_eps}")
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
