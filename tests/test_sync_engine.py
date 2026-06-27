import unittest

from app.sync_engine import SyncEngine


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


if __name__ == "__main__":
    unittest.main()
