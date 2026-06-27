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


if __name__ == "__main__":
    unittest.main()
