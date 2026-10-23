import unittest
from unittest.mock import Mock, patch

from app.douban_client import (
    DoubanClient,
    extract_season_info,
    parse_season_number,
)


class SeasonParsingTests(unittest.TestCase):
    def test_parse_season_numbers(self):
        self.assertEqual(parse_season_number("1"), 1)
        self.assertEqual(parse_season_number("一"), 1)
        self.assertEqual(parse_season_number("二"), 2)
        self.assertEqual(parse_season_number("两"), 2)
        self.assertEqual(parse_season_number("十"), 10)
        self.assertEqual(parse_season_number("十二"), 12)
        self.assertIsNone(parse_season_number("abc"))
        self.assertIsNone(parse_season_number(0))

    def test_extract_season_info_chinese(self):
        title, season = extract_season_info("怪奇物语 第二季")
        self.assertEqual(title, "怪奇物语")
        self.assertEqual(season, 2)

        title, season = extract_season_info("曼达洛人 第2季")
        self.assertEqual(title, "曼达洛人")
        self.assertEqual(season, 2)

    def test_extract_season_info_english(self):
        title, season = extract_season_info("Stranger Things Season 3")
        self.assertEqual(title, "Stranger Things")
        self.assertEqual(season, 3)

        title, season = extract_season_info("Dark S02")
        self.assertEqual(title, "Dark")
        self.assertEqual(season, 2)

    def test_extract_season_info_no_season(self):
        title, season = extract_season_info("肖申克的救赎")
        self.assertEqual(title, "肖申克的救赎")
        self.assertIsNone(season)


class CandidateSelectionTests(unittest.TestCase):
    def test_selects_correct_season_when_first_result_is_season_1(self):
        candidates = [
            ("怪奇物语 第一季 Stranger Things Season 1 (2016)", "111"),
            ("怪奇物语 第二季 Stranger Things Season 2 (2017)", "222"),
            ("怪奇物语 第三季 Stranger Things Season 3 (2019)", "333"),
        ]

        name, sid = DoubanClient._select_best_candidate(candidates, "怪奇物语", 2)
        self.assertEqual(sid, "222")
        self.assertIn("第二季", name)

    def test_returns_none_when_target_season_not_in_results(self):
        candidates = [
            ("怪奇物语 第一季 Stranger Things Season 1 (2016)", "111"),
            ("怪奇物语 第二季 Stranger Things Season 2 (2017)", "222"),
        ]

        name, sid = DoubanClient._select_best_candidate(candidates, "怪奇物语", 4)
        self.assertIsNone(sid)
        self.assertIsNone(name)

    def test_selects_season_1_without_season_suffix(self):
        candidates = [
            ("曼达洛人 The Mandalorian (2019)", "101"),
            ("曼达洛人 第二季 The Mandalorian Season 2 (2020)", "102"),
        ]

        name, sid = DoubanClient._select_best_candidate(candidates, "曼达洛人", 1)
        self.assertEqual(sid, "101")

    def test_does_not_fall_back_to_other_show_with_same_season(self):
        candidates = [
            ("鬼灭之刃", "1"),
            ("鬼灭之刃 游郭篇", "2"),
            ("咒术回战 第二季", "3"),
        ]

        self.assertEqual(DoubanClient._select_best_candidate(candidates, "鬼灭之刃", 2), (None, None))

    def test_matches_season_label_without_space(self):
        candidates = [("庆余年", "1"), ("庆余年第二季", "2")]

        name, sid = DoubanClient._select_best_candidate(candidates, "庆余年", 2)
        self.assertEqual(sid, "2")

    def test_first_season_never_picks_later_season_with_matching_title(self):
        candidates = [("其他剧", "1"), ("曼达洛人 第二季", "2")]

        name, sid = DoubanClient._select_best_candidate(candidates, "曼达洛人", 1)
        self.assertEqual(sid, "1")

    # 豆瓣实际搜索「马大帅 第二季」的结果
    MADASHUAI = [
        ("马大帅2", "4043850"),
        ("马大帅", "2997297"),
        ("马大帅3", "4044821"),
        ("华灯初上 第二季", "35550794"),
        ("寻找马大帅", "38365094"),
    ]

    def test_matches_sequel_named_with_trailing_number(self):
        self.assertEqual(DoubanClient._select_best_candidate(self.MADASHUAI, "马大帅", 2)[1], "4043850")
        self.assertEqual(DoubanClient._select_best_candidate(self.MADASHUAI, "马大帅", 3)[1], "4044821")

    def test_first_season_skips_sequel_named_with_trailing_number(self):
        self.assertEqual(DoubanClient._select_best_candidate(self.MADASHUAI, "马大帅", 1)[1], "2997297")


class MarkInterestTests(unittest.TestCase):
    @staticmethod
    def _response():
        response = Mock(status_code=200, text='{"r": 0}')
        response.json.return_value = {"r": 0}
        return response

    @patch("app.douban_client.requests.get")
    @patch("app.douban_client.requests.post")
    def test_done_uses_douban_collect_status(self, post, get):
        post.return_value = self._response()
        get.return_value = self._response()
        get.return_value.json.return_value = {"interest_status": "collect"}

        result = DoubanClient("ck=test; dbcl2=login").mark_interest("123", "done")

        self.assertTrue(result)
        self.assertEqual(post.call_args.kwargs["data"]["interest"], "collect")

    @patch("app.douban_client.requests.get")
    @patch("app.douban_client.requests.post")
    def test_doing_uses_douban_do_status(self, post, get):
        post.return_value = self._response()
        get.return_value = self._response()
        get.return_value.json.return_value = {"interest_status": "do"}

        result = DoubanClient("ck=test; dbcl2=login").mark_interest("123", "doing")

        self.assertTrue(result)
        self.assertEqual(post.call_args.kwargs["data"]["interest"], "do")

    @patch("app.douban_client.requests.get")
    @patch("app.douban_client.requests.post")
    def test_response_success_but_wrong_saved_status_is_failure(self, post, get):
        post.return_value = self._response()
        get.return_value = self._response()
        get.return_value.json.return_value = {"interest_status": "wish"}

        result = DoubanClient("ck=test; dbcl2=login").mark_interest("123", "done")

        self.assertFalse(result)

    @patch("app.douban_client.requests.post")
    def test_unknown_status_is_rejected_without_request(self, post):
        result = DoubanClient("ck=test; dbcl2=login").mark_interest("123", "unknown")

        self.assertFalse(result)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
