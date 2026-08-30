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

# 应用内部使用 done/doing，豆瓣接口使用 collect/do。
DOUBAN_INTEREST_MAP = {
    "do": "do",
    "doing": "do",
    "done": "collect",
}

CHINESE_NUM_MAP = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
    "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20,
    "廿": 20, "廿一": 21, "廿二": 22, "廿三": 23, "廿四": 24,
    "三十": 30, "四十": 40, "五十": 50,
}

SEASON_REGEXES = [
    re.compile(r"第\s*([0-9一二两三四五六七八九十]+)\s*季", re.IGNORECASE),
    re.compile(r"\bSeason\s*([0-9一二两三四五六七八九十]+)\b", re.IGNORECASE),
    re.compile(r"(?:^|[\s._\-\[(])S(\d{1,2})(?:[\s._\-\])]|E\d+|$)", re.IGNORECASE),
]


def parse_season_number(val: str | int | None) -> int | None:
    if val is None:
        return None
    if isinstance(val, int):
        return val if val > 0 else None
    val_str = str(val).strip()
    if not val_str:
        return None
    if val_str.isdigit():
        num = int(val_str)
        return num if num > 0 else None
    if val_str in CHINESE_NUM_MAP:
        return CHINESE_NUM_MAP[val_str]
    if val_str.startswith("二十") and len(val_str) == 3 and val_str[2] in CHINESE_NUM_MAP:
        return 20 + CHINESE_NUM_MAP[val_str[2]]
    if val_str.startswith("三十") and len(val_str) == 3 and val_str[2] in CHINESE_NUM_MAP:
        return 30 + CHINESE_NUM_MAP[val_str[2]]
    return None


def extract_season_info(title: str) -> tuple[str, int | None]:
    """从标题中提取干净主标题和季度号"""
    if not title:
        return "", None
    title = title.strip()
    for reg in SEASON_REGEXES:
        match = reg.search(title)
        if match:
            num = parse_season_number(match.group(1))
            if num:
                clean = (title[:match.start()] + " " + title[match.end():]).strip()
                clean = re.sub(r"\s+", " ", clean)
                clean = re.sub(r"[\(\[\{（【]\s*[\)\]\}）】]", "", clean).strip()
                return clean or title, num
    return title, None


def match_season_in_title(title: str, target_season: int | None) -> bool:
    """判断给定的标题是否匹配目标季度"""
    if not title:
        return False
    if target_season is None:
        return True

    _, extracted_season = extract_season_info(title)

    if target_season > 1:
        if extracted_season is not None:
            return extracted_season == target_season
        aliases = [
            f"第{target_season}季",
            f"Season {target_season}",
            f"season {target_season}",
            f"S{target_season:02d}",
            f"S{target_season}",
        ]
        return any(re.search(r"\b" + re.escape(alias) + r"\b" if alias.isalnum() else re.escape(alias),
                             title, re.IGNORECASE) for alias in aliases)

    if target_season == 1:
        if extracted_season == 1:
            return True
        if extracted_season is not None and extracted_season > 1:
            return False
        for s in range(2, 25):
            aliases = [f"第{s}季", f"Season {s}", f"season {s}", f"S{s:02d}", f"S{s}"]
            if any(re.search(r"\b" + re.escape(a) + r"\b" if a.isalnum() else re.escape(a),
                             title, re.IGNORECASE) for a in aliases):
                return False
        return True

    return False


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

    def search_subject(self, title: str, season_number: int | None = None) -> tuple[str | None, str | None]:
        """搜索豆瓣条目，返回 (subject_name, subject_id)"""
        clean_search_title, title_season = extract_season_info(title)
        target_season = season_number or title_season

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
            candidates = self._parse_search_results(resp.text)
            if not candidates:
                logger.debug("搜索无结果，响应前200字符: %s", resp.text[:200].strip())
                return None, None

            return self._select_best_candidate(candidates, clean_search_title, target_season)
        except Exception as e:
            logger.error("豆瓣搜索异常: %s", e)
            return None, None

    @classmethod
    def _select_best_candidate(cls, candidates: list[tuple[str, str]],
                               clean_search_title: str,
                               target_season: int | None) -> tuple[str | None, str | None]:
        if not candidates:
            return None, None

        clean_target = clean_search_title.lower().strip()

        # 1) 如果有明确目标季度（第 1 季或第 2+ 季）
        if target_season is not None:
            season_matched = [
                (name, sid) for (name, sid) in candidates
                if match_season_in_title(name, target_season)
            ]

            if season_matched:
                for name, sid in season_matched:
                    cand_clean, _ = extract_season_info(name)
                    cand_clean_lower = cand_clean.lower().strip()
                    if clean_target == cand_clean_lower or clean_target in cand_clean_lower or cand_clean_lower in clean_target:
                        return name, sid
                return season_matched[0]

            # 目标是第 2 季及以上且无匹配项时，绝不随意回退到第 1 季
            if target_season > 1:
                logger.warning("豆瓣搜索结果中未找到目标第 %d 季条目: search=%s 候选=%s",
                               target_season, clean_search_title, [c[0] for c in candidates[:3]])
                return None, None

        # 2) 电影或未指定季度的条目，优先匹配标题高度一致且非第 2+ 季的条目
        for name, sid in candidates:
            cand_clean, cand_season = extract_season_info(name)
            if target_season is None and cand_season and cand_season > 1:
                continue
            cand_clean_lower = cand_clean.lower().strip()
            if clean_target == cand_clean_lower or clean_target in cand_clean_lower or cand_clean_lower in clean_target:
                return name, sid

        return candidates[0]

    @staticmethod
    def _parse_search_results(html: str) -> list[tuple[str, str]]:
        from bs4 import BeautifulSoup
        from urllib.parse import urlparse, parse_qs, unquote
        soup = BeautifulSoup(html, "lxml")
        results = []
        for div in soup.find_all("div", class_="title"):
            a_tag = div.find("a")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            name = a_tag.get_text(strip=True)
            sid = None

            # 格式 A：直接链接 subject/ID/
            m = re.search(r"subject/(\d+)/", href)
            if m:
                sid = m.group(1)

            # 格式 B：跟踪链接 link2/?url=...subject%2FID%2F...
            elif "link2" in href or "url=" in href:
                try:
                    params = parse_qs(urlparse(href).query)
                    url_param = params.get("url", [None])[0]
                    if url_param:
                        decoded = unquote(url_param)
                        m = re.search(r"subject/(\d+)/", decoded)
                        if m:
                            sid = m.group(1)
                except Exception:
                    pass

            # 格式 C：onclick 属性中内嵌 sid
            elif "sid:" in a_tag.get("onclick", ""):
                m = re.search(r"sid:\s*(\d+)", a_tag.get("onclick", ""))
                if m:
                    sid = m.group(1)

            if sid and (name, sid) not in results:
                results.append((name, sid))

        return results

    @classmethod
    def _parse_search_result(cls, html: str) -> tuple[str | None, str | None]:
        results = cls._parse_search_results(html)
        return results[0] if results else (None, None)

    # ── 标记状态 ─────────────────────────────────────

    def _subject_headers(self, subject_id: str) -> dict:
        return {
            **BASE_HEADERS,
            "Referer": f"https://movie.douban.com/subject/{subject_id}/",
            "Origin": "https://movie.douban.com",
            "Host": "movie.douban.com",
            "Cookie": self._make_cookie_header(),
        }

    def mark_interest(self, subject_id: str, interest: str, private: bool = True) -> bool:
        """标记豆瓣条目观看状态，并核对豆瓣实际保存的状态"""
        url = f"https://movie.douban.com/j/subject/{subject_id}/interest"
        douban_interest = DOUBAN_INTEREST_MAP.get(interest)
        if not douban_interest:
            logger.error("不支持的豆瓣观看状态: %s", interest)
            return False
        data = {
            "ck": self._ck,
            "interest": douban_interest,
            "rating": "",
            "foldcollect": "U",
            "tags": "",
            "comment": "",
        }
        if private:
            data["private"] = "on"
        if not self._do_post(url, data, self._subject_headers(subject_id)):
            return False

        actual_interest = self.get_interest_status(subject_id)
        if actual_interest != douban_interest:
            logger.error("豆瓣状态未按预期保存 sid=%s 请求=%s 实际=%s",
                         subject_id, douban_interest, actual_interest or "未知")
            return False
        return True

    def get_interest_status(self, subject_id: str) -> str | None:
        """读取豆瓣当前状态，返回 wish/do/collect；读取失败返回 None"""
        url = f"https://movie.douban.com/j/subject/{subject_id}/interest"
        headers = self._subject_headers(subject_id)
        for attempt in range(2):
            try:
                resp = requests.get(url, headers=headers, timeout=10)
            except Exception as e:
                logger.error("读取豆瓣状态异常: %s", e)
                return None
            if resp.status_code == 403 and attempt == 0:
                logger.warning("读取豆瓣状态返回403，刷新 ck 后重试")
                self._refresh_ck()
                headers["Cookie"] = self._make_cookie_header()
                continue
            if resp.status_code != 200:
                logger.error("读取豆瓣状态失败 [%d]", resp.status_code)
                return None
            try:
                data = resp.json()
            except ValueError:
                logger.error("读取豆瓣状态响应不是 JSON")
                return None

            status = data.get("interest_status")
            if status:
                return status

            # 兼容未直接返回 interest_status 的旧响应格式。
            html = data.get("html", "")
            if html:
                from bs4 import BeautifulSoup
                checked = BeautifulSoup(html, "lxml").select_one(
                    'input[name="interest"]:checked'
                )
                return checked.get("value") if checked else None
            return None
        return None

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
