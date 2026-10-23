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

    def test_season_skips_empty_season_nodes(self):
        rows = [
            ("aot", None, None, None, "进击的巨人"),
            ("s4-old", "aot", 4, None, "第 4 季"),  # 重新刮削遗留，下面没有单集
            ("s4", "aot", 4, None, "最终季"),
            ("ep-1", "s4", 4, 1, "第1集"),
        ]
        self.conn.executemany("INSERT INTO item VALUES (?, ?, ?, ?, ?)", rows)

        fntv = FntvDb.__new__(FntvDb)
        self.assertEqual(fntv.get_season(self.conn, "aot", 4), {"guid": "s4", "title": "最终季"})
        self.assertIsNone(fntv.get_season(self.conn, "aot", 5))

    def test_library_titles_list_movies_and_series_with_seasons(self):
        self.conn.execute("ALTER TABLE item ADD COLUMN original_title TEXT")
        self.conn.execute("ALTER TABLE item ADD COLUMN imdb_id TEXT")
        rows = [
            ("movie", None, None, None, "赴汤蹈火", "Hell or High Water", "tt2582782"),
            ("tv", "", None, None, "信号", "시그널", None),
            ("tv-s1", "tv", 1, 16, "第 1 季", None, None),
            ("tv-s1-e1", "tv-s1", 1, 1, "", None, None),
            ("tv-s2", "tv", 2, 16, "第 2 季", None, None),  # 没有单集，不算在库
        ]
        self.conn.executemany("INSERT INTO item VALUES (?, ?, ?, ?, ?, ?, ?)", rows)

        fntv = FntvDb.__new__(FntvDb)
        library = {e["title"]: e for e in fntv.get_library_titles(self.conn)}
        self.assertEqual(set(library), {"赴汤蹈火", "信号"})
        self.assertEqual(library["赴汤蹈火"]["imdb_id"], "tt2582782")
        self.assertEqual(library["信号"]["seasons"], {1})
        self.assertEqual(library["信号"]["imdb_id"], "")

    def test_season_total_uses_planned_episodes_for_ongoing_season(self):
        # 季节点的 episode_number 是刮削到的计划集数
        rows = [
            ("jojo-6", "jojo", 6, 12, "飙马野郎篇"),
            ("ep-1", "jojo-6", 6, 1, "第1集"),
            ("ep-2", "jojo-6", 6, 2, "第2集"),
            ("mds-1", "mds", 1, 27, "第 1 季"),
        ] + [(f"mds-ep-{i}", "mds-1", 1, i, "") for i in range(1, 30)]
        self.conn.executemany("INSERT INTO item VALUES (?, ?, ?, ?, ?)", rows)

        fntv = FntvDb.__new__(FntvDb)
        self.assertEqual(fntv.get_season_total_episodes(self.conn, "jojo-6"), 12)
        # 本地集数多于计划集数时以本地为准
        self.assertEqual(fntv.get_season_total_episodes(self.conn, "mds-1"), 29)


if __name__ == "__main__":
    unittest.main()
