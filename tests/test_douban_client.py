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


class SeasonPartsSelectionTests(unittest.TestCase):
    # 豆瓣搜索「进击的巨人 最终季」的实际返回顺序
    AOT_FINAL = [
        ("进击的巨人 最终季 完结篇 后篇", "36283000"),
        ("进击的巨人 最终季 完结篇 前篇", "35853587"),
        ("进击的巨人 最终季 Part.1", "33440021"),
        ("进击的巨人 最终季 Part.2", "35290710"),
        ("进击的巨人", "2154069"),
    ]
    JOJO = [
        ("JOJO的奇妙冒险 飙马野郎", "36449242"),
        ("JOJO的奇妙冒险 星尘斗士 埃及篇", "25984031"),
        ("JOJO的奇妙冒险 石之海", "34605404"),
    ]

    def test_keeps_titles_with_season_tag_in_release_order(self):
        parts = DoubanClient._select_season_parts(self.AOT_FINAL, "进击的巨人", "最终季")
        self.assertEqual([sid for _, sid in parts],
                         ["33440021", "35290710", "35853587", "36283000"])

    def test_season_title_suffix_pian_is_optional(self):
        parts = DoubanClient._select_season_parts(self.JOJO, "JOJO的奇妙冒险", "飙马野郎篇")
        self.assertEqual(parts, [("JOJO的奇妙冒险 飙马野郎", "36449242")])

    def test_other_show_with_same_season_title_is_not_matched(self):
        self.assertEqual(DoubanClient._select_season_parts(self.AOT_FINAL, "海贼王", "最终季"), [])
        self.assertEqual(DoubanClient._select_season_parts(self.AOT_FINAL, "进击的巨人", "巨人"), [])

    def test_later_season_requires_same_series_title(self):
        cands = [("死神少爷与黑女仆 第二季", "35605985"), ("死神", "1460932")]
        self.assertEqual(DoubanClient._select_best_candidate(cands, "死神", 2), (None, None))


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


class WishListTests(unittest.TestCase):
    # 豆瓣「想看」列表页（mode=list）的实际结构
    PAGE = """<ul class="list-view">
    <li class="item" id="list37214286"><div class="item-show"><div class="title">
      <a href="https://movie.douban.com/subject/37214286/">
        中头奖还是要上班 / 로또 1등도 출근합니다
      </a></div></div></li>
    <li class="item last" id="list34607563"><div class="item-show"><div class="title">
      <a href="https://movie.douban.com/subject/34607563/">信号 第二季 / 시그널 시즌 2</a>
    </div></div></li></ul>"""

    def test_parse_wish_list(self):
        self.assertEqual(DoubanClient._parse_wish_list(self.PAGE), [
            {"sid": "37214286", "names": ["中头奖还是要上班", "로또 1등도 출근합니다"]},
            {"sid": "34607563", "names": ["信号 第二季", "시그널 시즌 2"]},
        ])

    def test_user_id_from_dbcl2(self):
        self.assertEqual(DoubanClient('ck=x; dbcl2="12345:abc"').user_id, "12345")

    @patch("app.douban_client.requests.get")
    def test_wish_list_stops_when_last_page_repeats(self, get):
        # 翻过最后一页时豆瓣重复返回末页
        get.return_value = Mock(status_code=200, text=self.PAGE)
        items = DoubanClient('ck=x; dbcl2="12345:abc"').get_wish_list()
        self.assertEqual([i["sid"] for i in items], ["37214286", "34607563"])
        self.assertEqual(get.call_count, 2)
        self.assertIn("start=2", get.call_args.args[0])

    @patch("app.douban_client.requests.get")
    def test_subject_imdb(self, get):
        get.return_value = Mock(status_code=200, text='<span class="pl">IMDb:</span> tt2582782<br>')
        self.assertEqual(DoubanClient("ck=x").get_subject_imdb("26389148"), "tt2582782")
        get.return_value = Mock(status_code=200, text="<div></div>")
        self.assertEqual(DoubanClient("ck=x").get_subject_imdb("26389148"), "")

    @patch("app.douban_client.requests.get")
    @patch("app.douban_client.requests.post")
    def test_remove_interest_verifies_wish_is_gone(self, post, get):
        post.return_value = Mock(status_code=302)
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {"interest_status": "wish"}
        client = DoubanClient("ck=test; dbcl2=login")
        self.assertFalse(client.remove_interest("123"))
        self.assertEqual(post.call_args.args[0], "https://movie.douban.com/subject/123/remove")
        self.assertEqual(post.call_args.kwargs["data"], {"ck": "test"})

        get.return_value.json.return_value = {}
        self.assertTrue(client.remove_interest("123"))


if __name__ == "__main__":
    unittest.main()
