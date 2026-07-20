import unittest
from unittest.mock import Mock, patch

from app.douban_client import DoubanClient


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
