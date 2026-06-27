import sqlite3
import unittest

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
                episode_number INTEGER
            )"""
        )

    def tearDown(self):
        self.conn.close()

    def test_zero_season_episode_and_empty_parent_is_movie(self):
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?)",
            ("movie-1", "", 0, 0),
        )

        self.assertEqual(
            FntvDb.classify_item(self.conn, "movie-1"),
            ItemCategory.MOVIE,
        )

    def test_positive_episode_number_is_episode(self):
        self.conn.execute(
            "INSERT INTO item VALUES (?, ?, ?, ?)",
            ("episode-1", "season-1", 1, 1),
        )

        self.assertEqual(
            FntvDb.classify_item(self.conn, "episode-1"),
            ItemCategory.EPISODE,
        )


if __name__ == "__main__":
    unittest.main()
