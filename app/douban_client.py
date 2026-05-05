"""豆瓣 API 客户端——基于用户 Cookie 调用豆瓣内部接口"""

import logging
import re
import requests
from http.cookies import SimpleCookie

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
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
        """向豆瓣首页请求新的 ck（含重定向链追踪）"""
        old_ck = self._ck
        headers = {**BASE_HEADERS, "Cookie": self._make_cookie_header(), "Host": "www.douban.com"}
        try:
            resp = requests.get("https://www.douban.com/", headers=headers, timeout=10)
            # 豆瓣可能在重定向（302）过程中设置新 ck，需检查整个跳转链
            for response in resp.history + [resp]:
                sc = SimpleCookie(response.headers.get("Set-Cookie", ""))
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
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                logger.warning("豆瓣搜索失败 [%d]: %s", resp.status_code, title)
                return None, None
            # 检查是否被重定向到登录页（精确匹配域名，避免误杀）
            if any(d in resp.url.lower() for d in ["accounts.douban.com", "passport.douban"]):
                logger.warning("搜索被重定向到登录页，Cookie 可能已过期: %s", title)
                return None, None
            # 验证码/空响应拦截
            if len(resp.text) < 500 or "captcha" in resp.text.lower():
                logger.warning("豆瓣搜索请求被拦截(status=%d, len=%d): %s",
                               resp.status_code, len(resp.text), title)
                return None, None
            result = self._parse_search_result(resp.text)
            if result == (None, None):
                logger.debug("搜索无结果，响应前200字符: %s", resp.text[:200].strip())
            return result
        except Exception as e:
            logger.error("豆瓣搜索异常: %s", e)
            return None, None

    @staticmethod
    def _parse_search_result(html: str) -> tuple[str | None, str | None]:
        from bs4 import BeautifulSoup
        from urllib.parse import urlparse, parse_qs, unquote
        soup = BeautifulSoup(html, "lxml")
        for div in soup.find_all("div", class_="title"):
            a_tag = div.find("a")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            name = a_tag.get_text(strip=True)

            # 格式 A：直接链接 subject/ID/
            m = re.search(r"subject/(\d+)/", href)
            if m:
                return name, m.group(1)

            # 格式 B：跟踪链接 link2/?url=...subject%2FID%2F...
            if "link2" in href or "url=" in href:
                try:
                    params = parse_qs(urlparse(href).query)
                    url_param = params.get("url", [None])[0]
                    if url_param:
                        decoded = unquote(url_param)
                        m = re.search(r"subject/(\d+)/", decoded)
                        if m:
                            return name, m.group(1)
                except Exception:
                    continue

            # 格式 C：onclick 属性中内嵌 sid
            onclick = a_tag.get("onclick", "")
            m = re.search(r"sid:\s*(\d+)", onclick)
            if m:
                return name, m.group(1)

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
        """验证 cookie 是否有效（返回布尔值）"""
        return self.check_auth_detail()["ok"]

    def check_auth_detail(self) -> dict:
        """验证 cookie 并返回详细诊断信息——访问豆瓣首页判断认证状态"""
        if not self._cookies:
            return {"ok": False, "reason": "cookie_format", "message": "Cookie 格式无效，请检查是否完整复制"}
        if not self._ck:
            return {"ok": False, "reason": "no_ck", "message": "Cookie 中缺少 ck 字段，请重新从浏览器导出"}
        if "dbcl2" not in self._cookies:
            return {"ok": False, "reason": "no_dbcl2", "message": "Cookie 中缺少 dbcl2（登录凭证），请确认已登录豆瓣"}

        cookie_val = self._cookies.get("dbcl2", "")
        if not cookie_val:
            return {"ok": False, "reason": "no_dbcl2",
                    "message": "dbcl2 值为空，请重新从浏览器导出 Cookie"}

        headers = {**BASE_HEADERS, "Cookie": self._make_cookie_header(), "Host": "www.douban.com"}
        try:
            resp = requests.get("https://www.douban.com/", headers=headers,
                                timeout=15, allow_redirects=True)
            logger.debug("豆瓣首页响应: status=%s url=%s body_len=%d",
                         resp.status_code, resp.url, len(resp.text))

            final_url = resp.url.lower()
            if any(p in final_url for p in ["login", "accounts", "passport", "signup"]):
                return {"ok": False, "reason": "cookie_expired",
                        "message": "Cookie 已过期，被重定向到登录页面，请重新从浏览器导出 Cookie"}

            if len(resp.text) < 500 or "captcha" in resp.text.lower():
                return {"ok": False, "reason": "captcha_or_blocked",
                        "message": "豆瓣返回了验证码或拦截页面，可能是服务器 IP 被限制"}

            # 从 Set-Cookie 刷新 ck
            for response in resp.history + [resp]:
                sc = SimpleCookie(response.headers.get("Set-Cookie", ""))
                for key, morsel in sc.items():
                    if key == "ck" and morsel.value and morsel.value != '"deleted"':
                        self._ck = morsel.value
                        self._cookies["ck"] = morsel.value
                        break

            return {"ok": True, "reason": "", "message": "Cookie 有效"}

        except requests.RequestException as e:
            logger.error("豆瓣首页请求异常: %s", e)
            return {"ok": False, "reason": "network_error",
                    "message": f"无法连接豆瓣: {e}"}
