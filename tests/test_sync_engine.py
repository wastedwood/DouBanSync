import tempfile
import unittest
from unittest.mock import ANY, MagicMock, patch

from app.fntv_db import ItemCategory
from app.sync_engine import SyncEngine
from app.sync_store import SyncStore


class WatchPercentageTests(unittest.TestCase):
    def test_watched_flag_takes_priority_over_zero_position(self):
        pct, determinable = SyncEngine._calc_watch_pct({
            "watched": 1,
            "position_seconds": 0,
            "runtime_minutes": 120,
        })

        self.assertEqual(pct, 100.0)
        self.assertTrue(determinable)

    def test_unwatched_item_still_uses_play_position(self):
        pct, determinable = SyncEngine._calc_watch_pct({
            "watched": 0,
            "position_seconds": 60 * 60,
            "runtime_minutes": 120,
        })

        self.assertEqual(pct, 50.0)
        self.assertTrue(determinable)

    def test_watched_change_alters_fingerprint(self):
        base_play = {
            "item_guid": "movie-1",
            "position_seconds": 0,
            "watched": 0,
        }
        watched_play = {**base_play, "watched": 1}

        self.assertNotEqual(
            SyncEngine._compute_fingerprint([base_play]),
            SyncEngine._compute_fingerprint([watched_play]),
        )


class TvSearchTitleTests(unittest.TestCase):
    def test_standard_second_season_includes_season_label(self):
        self.assertEqual(
            SyncEngine._build_tv_search_title("三体", 2),
            "三体 第二季",
        )

    def test_standard_first_season_keeps_generic_search(self):
        self.assertEqual(
            SyncEngine._build_tv_search_title("三体", 1),
            "三体",
        )

    def test_inferred_first_season_keeps_season_label(self):
        self.assertEqual(
            SyncEngine._build_tv_search_title("三体", 1, is_inferred=True),
            "三体 第一季",
        )

    def test_series_title_already_with_season_is_not_duplicated(self):
        self.assertEqual(
            SyncEngine._build_tv_search_title("怪奇物语 第二季", 2),
            "怪奇物语 第二季",
        )
        self.assertEqual(
            SyncEngine._build_tv_search_title("Dark S03", None),
            "Dark 第三季",
        )

    def test_sequel_stored_as_separate_series_keeps_title_season(self):
        # 续作独立入库：剧名带「第二季」，FNTV 季号为 1
        self.assertEqual(
            SyncEngine._build_tv_search_title("庆余年 第二季", 1),
            "庆余年 第二季",
        )
        self.assertEqual(SyncEngine._resolve_season("庆余年 第二季", 1), ("庆余年", 2))

    def test_explicit_later_season_overrides_title(self):
        self.assertEqual(SyncEngine._resolve_season("怪奇物语 第二季", 3), ("怪奇物语", 3))


class SummaryNotificationTests(unittest.TestCase):
    def test_summary_contains_title_and_result_sections(self):
        body = SyncEngine._build_summary_body(
            {"done": 1, "doing": 1, "failed": 1, "skipped": 0},
            {
                "done": [("真人快打2", "")],
                "doing": [("三体", "")],
                "failed": [("未知影片", "豆瓣搜索无结果")],
                "skipped": [],
            },
        )

        self.assertIn("✅ 已看完（1）\n• 真人快打2", body)
        self.assertIn("▶️ 在看（1）\n• 三体", body)
        self.assertIn("❌ 失败（1）\n• 未知影片：豆瓣搜索无结果", body)
        self.assertTrue(body.endswith("本次共处理 3 项"))

    def test_summary_limits_each_section_to_three_titles(self):
        body = SyncEngine._build_summary_body(
            {"done": 5, "doing": 0, "failed": 0, "skipped": 0},
            {
                "done": [(f"影片{i}", "") for i in range(1, 6)],
                "doing": [],
                "failed": [],
                "skipped": [],
            },
        )

        self.assertIn("• 影片1", body)
        self.assertIn("• 影片3", body)
        self.assertNotIn("• 影片4", body)
        self.assertIn("• 另有 2 项", body)


class SpecialSeasonTests(unittest.TestCase):
    @patch("app.sync_engine.DoubanClient")
    def test_season_zero_specials_are_not_synced(self, client_cls):
        client_cls.return_value.check_auth.return_value = True
        store = MagicMock()
        store.get_config.side_effect = lambda key, default="": "1" if key.startswith("douban_interest") else default
        fntv = MagicMock()
        fntv.get_new_plays.return_value = [{
            "item_guid": "ep-36", "title": "最终季 完结篇（前篇）", "position_seconds": 0,
            "watched": 1, "play_update_time": 1, "episode_number": 36, "runtime_minutes": 60,
        }]
        fntv.classify_item.return_value = ItemCategory.EPISODE
        fntv.get_series_hierarchy.return_value = {
            "series_guid": "tv-1", "season_guid": "s-0", "season_number": 0, "series_title": "进击的巨人",
        }

        SyncEngine(fntv, store, "ck=x").run("user-1")

        client_cls.return_value.search_subject.assert_not_called()
        client_cls.return_value.mark_interest.assert_not_called()
        store.log_action.assert_any_call(ANY, "skip_special", "ep-36", "进击的巨人", "特别篇不同步")


@patch("app.sync_engine.DoubanClient")
class PlayProgressTests(unittest.TestCase):
    """有进度但未达阈值算在看；剧集最后一集看完才算看过"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = SyncStore(self._tmp.name)
        for marker in ("douban_interest_mapping_v2:u", "season_subject_repair_v3:u"):
            self.store.set_config(marker, "1")
        self.fntv = MagicMock()
        self.engine = SyncEngine(self.fntv, self.store, "ck=x")

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, client_cls, minutes, watched=0, item="movie-1", episode=None):
        client = client_cls.return_value
        client.check_auth.return_value = True
        client.search_subject.return_value = ("片名", "100")
        client.mark_interest.reset_mock()
        client.mark_interest.return_value = True
        self.fntv.get_new_plays.return_value = [{
            "item_guid": item, "title": "片名", "original_title": "", "position_seconds": minutes * 60,
            "watched": watched, "play_update_time": minutes + 1, "episode_number": episode,
            "runtime_minutes": 100,
        }]
        self.engine.run("u")
        return [c.args[:2] for c in client.mark_interest.call_args_list]

    def test_movie_partial_is_doing_then_done(self, client_cls):
        self.fntv.classify_item.return_value = ItemCategory.MOVIE
        self.assertEqual(self._run(client_cls, 30), [("100", "doing")])
        self.assertEqual(self.store.get_state("u", "movie-1")["status"], "doing")
        # 仍未看完：不重复调用豆瓣
        self.assertEqual(self._run(client_cls, 50), [])
        self.assertEqual(self._run(client_cls, 95), [("100", "done")])
        self.assertEqual(self.store.get_state("u", "movie-1")["status"], "done")

    def test_zero_progress_is_ignored(self, client_cls):
        self.fntv.classify_item.return_value = ItemCategory.MOVIE
        self.assertEqual(self._run(client_cls, 0), [])
        self.assertIsNone(self.store.get_state("u", "movie-1"))

    def test_final_episode_not_finished_is_doing(self, client_cls):
        self.fntv.classify_item.return_value = ItemCategory.EPISODE
        self.fntv.get_series_hierarchy.return_value = {
            "series_guid": "tv", "season_guid": "s1", "season_number": 1,
            "season_title": "第 1 季", "series_title": "某剧"}
        self.fntv.get_season_total_episodes.return_value = 12
        self.fntv.get_season_max_watched.return_value = 11
        marks = self._run(client_cls, 40, item="ep-12", episode=12)
        self.assertEqual(marks, [("100", "doing")])
        self.assertEqual(self.store.get_state("u", "ep-12")["max_ep_watched"], 11)


# 豆瓣实测数据：搜索「剧名 季标题」的候选，以及各条目摘要
DOUBAN_SEARCH = {
    ("进击的巨人", "最终季"): [
        ("进击的巨人 最终季 完结篇 后篇", "36283000"),
        ("进击的巨人 最终季 完结篇 前篇", "35853587"),
        ("进击的巨人 最终季 Part.1", "33440021"),
        ("进击的巨人 最终季 Part.2", "35290710"),
    ],
    ("死神", "千年血战篇"): [
        ("死神 千年血战篇", "35001432"),
        ("死神 千年血战篇 -祸进谭-", "36189165"),
        ("死神 千年血战篇 -相克谭-", "36189164"),
        ("死神 千年血战篇 -诀别谭-", "36189163"),
    ],
    ("JOJO的奇妙冒险", "飙马野郎篇"): [("JOJO的奇妙冒险 飙马野郎", "36449242")],
}
DOUBAN_ABSTRACT = {
    "33440021": {"is_tv": True, "episodes_count": "16"},
    "35290710": {"is_tv": True, "episodes_count": "12"},
    "35853587": {"is_tv": False, "episodes_count": ""},
    "36283000": {"is_tv": False, "episodes_count": ""},
    "35001432": {"is_tv": True, "episodes_count": "13"},
    "36189163": {"is_tv": True, "episodes_count": "13"},
    "36189164": {"is_tv": True, "episodes_count": "14"},
    "36189165": {"is_tv": True, "episodes_count": "13"},
    "36449242": {"is_tv": True, "episodes_count": ""},
}


def douban_client_mock():
    client = MagicMock()
    client.search_season_parts.side_effect = lambda series, tag: sorted(
        DOUBAN_SEARCH.get((series, tag), []), key=lambda c: int(c[1]))
    client.get_subject_abstract.side_effect = DOUBAN_ABSTRACT.get
    client.mark_interest.return_value = True
    return client


class SeasonSubjectRepairTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = SyncStore(self._tmp.name)
        rows = [
            # (item, series, season, title, status, sid, 已看到, 总集数)
            ("bcs-1", "bcs", 1, "风骚律师", "done", "25726259", 10, 10),
            ("bcs-2", "bcs", 2, "风骚律师", "done", "25726259", 10, 10),
            ("aot-2", "aot", 2, "进击的巨人", "done", "23748525", 12, 12),
            ("mds-2", "mds", 2, "马大帅", "doing", "2997297", 3, 30),
            ("bng-2", "bng", 2, "百年孤独", "done", "30482958", 8, 8),
            ("aot-4", "aot", 4, "进击的巨人", "done", "23748525", 28, 28),
            ("bleach-2", "bleach", 2, "死神", "doing", "35605985", 30, 40),
            # 连载中：同步时本地只有已播出的集，被判为看完
            ("jojo-6", "jojo", 6, "JOJO的奇妙冒险", "done", "11498785", 1, 1),
            ("qs-1", "qs", 1, "棋士", "done", "37000001", 11, 11),
        ]
        for item, series, season, title, status, sid, watched, total in rows:
            self.store.upsert_state("u", item, media_type="episode", series_guid=series,
                                    season_number=season, series_title=title,
                                    status=status, douban_subject_id=sid,
                                    max_ep_watched=watched, total_episodes=total)
        self.client = douban_client_mock()
        self.client.search_subject.side_effect = lambda title, season_number=None: {
            "风骚律师 第二季": ("风骚律师 第二季", "26647117"),
            "进击的巨人 第二季": ("进击的巨人 第二季", "26816519"),
            "马大帅 第二季": ("马大帅 第二季", "1966880"),
        }.get(title, (None, None))
        season_titles = {("aot", 4): "最终季", ("bleach", 2): "千年血战篇", ("mds", 2): "Ⅱ",
                         ("jojo", 6): "飙马野郎篇"}
        planned_episodes = {"jojo-6": 12, "qs-1": 22}
        live_watched = {"jojo-6": 5}  # 飞牛当前已看到的集数（同步记录之后又看了几集）
        fntv = MagicMock()
        fntv.get_season.side_effect = lambda conn, series, season: {
            "guid": f"{series}-{season}",
            "title": season_titles.get((series, season), f"第 {season} 季")}
        fntv.get_season_total_episodes.side_effect = lambda conn, guid: planned_episodes.get(guid, 0)
        fntv.get_season_max_watched.side_effect = lambda conn, user, guid: live_watched.get(guid, 0)
        self.engine = SyncEngine(fntv, self.store, "ck=x")

    def tearDown(self):
        self._tmp.cleanup()

    def _sid(self, item):
        return self.store.get_state("u", item)["douban_subject_id"]

    def test_repairs_later_seasons_and_keeps_unmatched(self):
        self.engine._repair_season_subjects("run", self.client, "u")

        self.assertEqual(self._sid("bcs-1"), "25726259")
        self.assertEqual(self._sid("bcs-2"), "26647117")
        self.assertEqual(self._sid("aot-2"), "26816519")
        self.assertEqual(self._sid("mds-2"), "1966880")
        # 豆瓣找不到独立第二季条目时保持原样
        self.assertEqual(self._sid("bng-2"), "30482958")
        self.client.mark_interest.assert_any_call("26647117", "done", True)
        self.client.mark_interest.assert_any_call("1966880", "doing", True)

    def test_split_season_marks_parts_by_episode_count(self):
        self.engine._repair_season_subjects("run", self.client, "u")
        marks = [c.args[:2] for c in self.client.mark_interest.call_args_list]

        # 最终季 28 集 = Part.1(16) + Part.2(12)，完结篇不是剧集，不标
        self.assertEqual(self._sid("aot-4"), "33440021")
        self.assertIn(("33440021", "done"), marks)
        self.assertIn(("35290710", "done"), marks)
        self.assertNotIn("35853587", [m[0] for m in marks])
        # 千年血战篇看到第 30 集：前两部（26 集）看过，相克谭在看，祸进谭不属于该季
        self.assertEqual(self._sid("bleach-2"), "35001432")
        self.assertIn(("35001432", "done"), marks)
        self.assertIn(("36189163", "done"), marks)
        self.assertIn(("36189164", "doing"), marks)
        self.assertNotIn("36189165", [m[0] for m in marks])

    def test_rematched_season_status_follows_final_episode(self):
        self.engine._repair_season_subjects("run", self.client, "u")
        marks = [c.args[:2] for c in self.client.mark_interest.call_args_list]

        # 飙马野郎篇计划 12 集、飞牛当前看到第 5 集：改配到正确条目，最后一集没看完是在看
        state = self.store.get_state("u", "jojo-6")
        self.assertEqual((state["douban_subject_id"], state["status"]), ("36449242", "doing"))
        self.assertIn(("36449242", "doing"), marks)
        # 条目没变的季不动原有状态（本地删片导致记录不全时不误改）
        state = self.store.get_state("u", "qs-1")
        self.assertEqual((state["douban_subject_id"], state["status"]), ("37000001", "done"))
        self.assertNotIn("37000001", [m[0] for m in marks])
        self.assertEqual(self.store.get_state("u", "bng-2")["status"], "done")

    def test_runs_once(self):
        self.engine._repair_season_subjects("run", self.client, "u")
        self.client.search_subject.reset_mock()
        self.engine._repair_season_subjects("run", self.client, "u")
        self.client.search_subject.assert_not_called()

    def test_mark_failure_retries_next_run(self):
        self.client.mark_interest.return_value = False
        self.engine._repair_season_subjects("run", self.client, "u")
        self.assertEqual(self._sid("bcs-2"), "25726259")
        self.assertNotEqual(self.store.get_config("season_subject_repair_v3:u"), "1")


class SeasonTitleSearchTests(unittest.TestCase):
    def setUp(self):
        self.engine = SyncEngine(MagicMock(), MagicMock(), "ck=x")
        self.client = douban_client_mock()
        self.client.search_subject.return_value = ("X 第二季", "111")

    def test_season_tag_ignores_generic_titles(self):
        self.assertEqual(SyncEngine._season_tag("进击的巨人", "最终季"), "最终季")
        self.assertEqual(SyncEngine._season_tag("进击的巨人", "进击的巨人 最终季"), "最终季")
        for generic in ("第 2 季", "第二季", "Season 3", "Ⅱ", "III", "2", "", None):
            self.assertEqual(SyncEngine._season_tag("进击的巨人", generic), "")

    def test_parts_stop_at_season_episode_total(self):
        parts = self.engine._season_parts(self.client, "死神", 2, "千年血战篇", 40)
        self.assertEqual(parts, [("35001432", 13), ("36189163", 13), ("36189164", 14)])
        parts = self.engine._season_parts(self.client, "进击的巨人", 4, "最终季", 16)
        self.assertEqual(parts, [("33440021", 16)])

    def test_unknown_episode_count_takes_single_subject(self):
        parts = self.engine._season_parts(self.client, "JOJO的奇妙冒险", 6, "飙马野郎篇", 5)
        self.assertEqual(parts, [("36449242", 0)])

    def test_abstract_failure_gives_up_title_match(self):
        self.client.get_subject_abstract.side_effect = None
        self.client.get_subject_abstract.return_value = None
        self.assertEqual(self.engine._season_parts(self.client, "死神", 2, "千年血战篇", 40), [])

    def test_falls_back_to_season_number_when_title_unmatched(self):
        parts = self.engine._search_tv_subjects(self.client, "X", 2, "无名篇", 10)
        self.assertEqual(parts, [("111", 0)])
        self.client.search_subject.assert_called_once_with("X 第二季", season_number=2)

    def test_first_season_never_uses_season_title(self):
        self.engine._search_tv_subjects(self.client, "JOJO的奇妙冒险", 1, "幻影之血", 26)
        self.client.search_season_parts.assert_not_called()

    def test_progress_maps_to_parts(self):
        parts = [("p1", 16), ("p2", 12)]
        self.assertEqual(SyncEngine._part_interests(parts, "doing", 3), [("p1", "doing")])
        self.assertEqual(SyncEngine._part_interests(parts, "doing", 20),
                         [("p1", "done"), ("p2", "doing")])
        self.assertEqual(SyncEngine._part_interests(parts, "done", 28),
                         [("p1", "done"), ("p2", "done")])
        self.assertEqual(SyncEngine._part_interests([("x", 0)], "doing", 5), [("x", "doing")])

    def test_mark_failure_returns_empty(self):
        self.client.mark_interest.return_value = False
        self.assertEqual(self.engine._mark_season(self.client, [("p1", 16)], "done", 16), [])


class SeasonPartsCompletionTests(unittest.TestCase):
    """本地只记了主条目，看完时按集数补齐其余分部"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = SyncStore(self._tmp.name)
        self.store.upsert_state("u", "aot-4-20", media_type="episode", series_guid="aot",
                                season_number=4, series_title="进击的巨人",
                                status="doing", douban_subject_id="33440021")
        self.fntv = MagicMock()
        self.fntv.get_season_total_episodes.return_value = 28
        self.fntv.get_season_max_watched.return_value = 28
        self.client = douban_client_mock()
        self.engine = SyncEngine(self.fntv, self.store, "ck=x")
        self.engine._stats = {"done": 0, "doing": 0, "failed": 0, "skipped": 0}
        self.engine._summary_items = {}

    def tearDown(self):
        self._tmp.cleanup()

    def test_completion_marks_remaining_parts(self):
        info = {"series_guid": "aot", "season_guid": "s4", "season_number": 4,
                "season_title": "最终季", "series_title": "进击的巨人"}
        play = {"item_guid": "aot-4-28", "episode_number": 28, "play_update_time": 1}
        self.engine._process_tv_group("run", self.client, "u", info, [play])

        marks = [c.args[:2] for c in self.client.mark_interest.call_args_list]
        self.assertEqual(marks, [("33440021", "done"), ("35290710", "done")])
        state = self.store.get_state("u", "aot-4-28")
        self.assertEqual((state["douban_subject_id"], state["status"]), ("33440021", "done"))


class WishCleanupTests(unittest.TestCase):
    # 飞牛库（实测数据节选）
    LIBRARY = [
        {"title": "赴汤蹈火", "original_title": "Hell or High Water", "imdb_id": "tt2582782", "seasons": set()},
        {"title": "大理石厅谋杀案", "original_title": "Marble Hall Murders", "imdb_id": "", "seasons": {1}},
        {"title": "信号", "original_title": "시그널", "imdb_id": "tt5332206", "seasons": {1}},
        {"title": "无依之地", "original_title": "Nomadland", "imdb_id": "tt9770150", "seasons": set()},
    ]

    def test_match_by_imdb_or_title(self):
        match = SyncEngine._match_library
        self.assertEqual(match(["赴汤蹈火", "Hell or High Water"], "tt2582782", self.LIBRARY)["title"], "赴汤蹈火")
        # 中文名不同，按原名匹配
        self.assertEqual(match(["翠鸟谋杀案", "Marble Hall Murders"], "", self.LIBRARY)["title"],
                         "大理石厅谋杀案")
        # 同名但 IMDb 不同：不是同一部
        self.assertIsNone(match(["无依之地", "Nomadland"], "tt0000001", self.LIBRARY))
        self.assertIsNone(match(["野兽之心", "Heart of the Beast"], "tt1", self.LIBRARY))

    def test_later_season_must_exist_in_library(self):
        self.assertIsNone(SyncEngine._match_library(["信号 第二季", "시그널 시즌 2"], "tt5332206", self.LIBRARY))
        self.assertIsNotNone(SyncEngine._match_library(["信号 第一季"], "tt5332206", self.LIBRARY))

    def _engine(self, enabled):
        store = MagicMock()
        store.get_config.side_effect = lambda key, default="": "true" if enabled and key == "clean_wish" else default
        fntv = MagicMock()
        fntv.get_library_titles.return_value = self.LIBRARY
        return SyncEngine(fntv, store, "ck=x"), store

    def test_disabled_by_default(self):
        engine, _ = self._engine(enabled=False)
        client = MagicMock()
        engine._clean_wish_list("run", client)
        client.get_wish_list.assert_not_called()

    def test_removes_only_wishes_in_library(self):
        engine, store = self._engine(enabled=True)
        client = MagicMock()
        client.get_wish_list.return_value = [
            {"sid": "26389148", "names": ["赴汤蹈火", "Hell or High Water"]},
            {"sid": "36828393", "names": ["野兽之心", "Heart of the Beast"]},
        ]
        client.get_subject_imdb.side_effect = {"26389148": "tt2582782", "36828393": "tt99"}.get
        client.remove_interest.return_value = True
        engine._clean_wish_list("run", client)

        client.remove_interest.assert_called_once_with("26389148")
        store.log_action.assert_called_once_with("run", "remove_wish", "26389148", "赴汤蹈火",
                                                 "飞牛库已有「赴汤蹈火」")


if __name__ == "__main__":
    unittest.main()
