"""豆瓣 API 客户端——基于用户 Cookie 调用豆瓣内部接口"""

import logging
import re
import requests
from http.cookies import SimpleCookie

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4",
    "Connection": "keep-alive",
    "DNT": "1",
}


class DoubanClient:
    """豆瓣 API 封装：搜索条目 + 标记状态"""

    def __init__(self, cookie_str: str = ""):
        self._ck = ""
        self._cookies = {}
        if cookie_str:
            self._cookies = self._parse_cookie(cookie_str)
            self._ck = self._cookies.get("ck", "")
            if not self._ck:
                # 尝试从 cookie 字符串直接提取 ck
                self._ck = self._extract_ck(cookie_str)

    # ── Cookie 处理 ─────────────────────────────────

    @staticmethod
    def _parse_cookie(cookie_str: str) -> dict:
        cookies = {}
        try:
            sc = SimpleCookie(cookie_str)
            for key, morsel in sc.items():
                if key != "__utmz":
                    cookies[key] = morsel.value
        except Exception:
            pass
        return cookies

    @staticmethod
    def _extract_ck(cookie_str: str) -> str:
        m = re.search(r'\bck=([^;]+)', cookie_str)
        return m.group(1) if m else ""

    def _make_cookie_header(self) -> str:
        return ";".join(f"{k}={v}" for k, v in self._cookies.items())

    def _refresh_ck(self):
        """向豆瓣首页请求新的 ck"""
        old_ck = self._ck
        headers = {**BASE_HEADERS, "Cookie": self._make_cookie_header(), "Host": "www.douban.com"}
        try:
            resp = requests.get("https://www.douban.com/", headers=headers, timeout=10)
            sc = SimpleCookie(resp.headers.get("Set-Cookie", ""))
            for key, morsel in sc.items():
                if key == "ck" and morsel.value and morsel.value != '"deleted"':
                    self._ck = morsel.value
                    self._cookies["ck"] = morsel.value
                    return
        except Exception as e:
            logger.warning("ck 刷新失败: %s", e)
        self._ck = old_ck

    # ── 搜索 ─────────────────────────────────────────

    def search_subject(self, title: str) -> tuple[str | None, str | None]:
        """搜索豆瓣条目，返回 (subject_name, subject_id)"""
        url = f"https://www.douban.com/search?cat=1002&q={requests.utils.quote(title)}"
        headers = {**BASE_HEADERS, "Cookie": self._make_cookie_header(), "Host": "www.douban.com"}
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                logger.warning("豆瓣搜索失败 [%d]: %s", resp.status_code, title)
                return None, None
            return self._parse_search_result(resp.text)
        except Exception as e:
            logger.error("豆瓣搜索异常: %s", e)
            return None, None

    @staticmethod
    def _parse_search_result(html: str) -> tuple[str | None, str | None]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        for div in soup.find_all("div", class_="title"):
            a_tag = div.find("a")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            m = re.search(r"subject/(\d+)/", href)
            if m:
                name = a_tag.get_text(strip=True)
                sid = m.group(1)
                return name, sid
        return None, None

    # ── 标记状态 ─────────────────────────────────────

    def mark_interest(self, subject_id: str, interest: str, private: bool = True) -> bool:
        """标记豆瓣条目观看状态（interest: do/done/doing）"""
        url = f"https://movie.douban.com/j/subject/{subject_id}/interest"
        data = {
            "ck": self._ck,
            "interest": interest,
            "rating": "",
            "foldcollect": "U",
            "tags": "",
            "comment": "",
        }
        if private:
            data["private"] = "on"
        headers = {
            **BASE_HEADERS,
            "Referer": f"https://movie.douban.com/subject/{subject_id}/",
            "Origin": "https://movie.douban.com",
            "Host": "movie.douban.com",
            "Cookie": self._make_cookie_header(),
        }
        return self._do_post(url, data, headers)

    def _do_post(self, url: str, data: dict, headers: dict) -> bool:
        for attempt in range(2):
            try:
                resp = requests.post(url, data=data, headers=headers, timeout=10)
            except Exception as e:
                logger.error("请求异常: %s", e)
                return False
            if resp.status_code == 403 and attempt == 0:
                logger.warning("豆瓣 403，刷新 ck 后重试")
                self._refresh_ck()
                data["ck"] = self._ck
                headers["Cookie"] = self._make_cookie_header()
                continue
            if resp.status_code == 200:
                return self._parse_mark_response(resp.json())
            logger.error("豆瓣标记失败 [%d]: %s", resp.status_code, resp.text[:200])
            return False
        return False

    @staticmethod
    def _parse_mark_response(data: dict) -> bool:
        r = data.get("r")
        if r == 0:
            return True
        if r is False:
            logger.warning("豆瓣返回 false（影片可能未上映）")
        else:
            logger.warning("豆瓣返回异常: %s", data)
        return False

    def check_auth(self) -> bool:
        """验证 cookie 是否有效"""
        if not self._ck:
            return False
        _, sid = self.search_subject("黑客帝国")
        return sid is not None
