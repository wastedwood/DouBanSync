import sqlite3
import unittest
from unittest.mock import MagicMock

from app.fntv_db import FntvDb, ItemCategory


class ItemClassificationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """CREATE TABLE item (
                guid TEXT PRIMARY KEY,
                parent_guid TEXT,
                season_number INTEGER,
                episode_number INTEGER,
                title TEXT
            )"""
        )

    def tearDown(self):
        self.conn.close()

    def test_zero_season_episode_and_empty_parent_is_movie(self):
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?, ?)",
            ("movie-1", "", 0, 0, "电影1"),
        )

        self.assertEqual(
            FntvDb.classify_item(self.conn, "movie-1"),
            ItemCategory.MOVIE,
        )

    def test_positive_episode_number_is_episode(self):
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?, ?)",
            ("episode-1", "season-1", 1, 1, "第1集"),
        )

        self.assertEqual(
            FntvDb.classify_item(self.conn, "episode-1"),
            ItemCategory.EPISODE,
        )

    def test_series_hierarchy_extracts_season_from_episode_when_season_null(self):
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?, ?)",
            ("series-1", None, None, None, "曼达洛人"),
        )
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?, ?)",
            ("season-1", "series-1", None, None, "Season 2"),
        )
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?, ?)",
            ("episode-1", "season-1", 2, 1, "第1集"),
        )

        fntv = FntvDb.__new__(FntvDb)
        info = fntv.get_series_hierarchy(self.conn, "episode-1")
        self.assertIsNotNone(info)
        self.assertEqual(info["season_number"], 2)
        self.assertEqual(info["series_title"], "曼达洛人")

    def test_flat_structure_preserves_season_number(self):
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?, ?)",
            ("series-2", None, None, None, "怪奇物语 第二季"),
        )
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?, ?)",
            ("episode-2", "series-2", 2, 1, "第1集"),
        )

        fntv = FntvDb.__new__(FntvDb)
        flat = fntv.get_series_for_episode_flat(self.conn, "episode-2")
        self.assertIsNotNone(flat)
        self.assertEqual(flat["season_number"], 2)


if __name__ == "__main__":
    unittest.main()
