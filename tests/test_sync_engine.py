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


class SeasonSubjectRepairTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = SyncStore(self._tmp.name)
        rows = [
            # (item, series, season, title, status, sid)
            ("bcs-1", "bcs", 1, "风骚律师", "done", "25726259"),
            ("bcs-2", "bcs", 2, "风骚律师", "done", "25726259"),
            ("aot-2", "aot", 2, "进击的巨人", "done", "23748525"),
            ("mds-2", "mds", 2, "马大帅", "doing", "2997297"),
            ("bng-2", "bng", 2, "百年孤独", "done", "30482958"),
        ]
        for item, series, season, title, status, sid in rows:
            self.store.upsert_state("u", item, media_type="episode", series_guid=series,
                                    season_number=season, series_title=title,
                                    status=status, douban_subject_id=sid)
        self.client = MagicMock()
        self.client.search_subject.side_effect = lambda title, season_number=None: {
            "风骚律师 第二季": ("风骚律师 第二季", "26647117"),
            "进击的巨人 第二季": ("进击的巨人 第二季", "26816519"),
            "马大帅 第二季": ("马大帅 第二季", "1966880"),
        }.get(title, (None, None))
        self.client.mark_interest.return_value = True
        self.engine = SyncEngine(MagicMock(), self.store, "ck=x")

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
        self.assertEqual(self.client.mark_interest.call_count, 3)

    def test_runs_once(self):
        self.engine._repair_season_subjects("run", self.client, "u")
        self.client.search_subject.reset_mock()
        self.engine._repair_season_subjects("run", self.client, "u")
        self.client.search_subject.assert_not_called()

    def test_mark_failure_retries_next_run(self):
        self.client.mark_interest.return_value = False
        self.engine._repair_season_subjects("run", self.client, "u")
        self.assertEqual(self._sid("bcs-2"), "25726259")
        self.assertNotEqual(self.store.get_config("season_subject_repair_v1:u"), "1")


if __name__ == "__main__":
    unittest.main()
