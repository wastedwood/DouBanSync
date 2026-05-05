"""CookieCloud 客户端——从 CookieCloud 服务器拉取并解密豆瓣 Cookie

CookieCloud 加密方案：
  1. MD5(api_key) → 32 字符十六进制
  2. 前 16 字节 → AES 密钥, 后 16 字节 → AES IV
  3. AES-CBC 解密 + PKCS7 去填充
"""

import json
import logging
import hashlib
import base64

import requests

logger = logging.getLogger(__name__)

DOUBAN_DOMAINS = (".douban.com", "douban.com", "www.douban.com", "movie.douban.com")


def fetch_cookie(server_url: str, uuid: str, key: str) -> str:
    """从 CookieCloud 拉取并解密，返回拼接后的 cookie 字符串

    Returns:
        "; key=value" 格式的 cookie 字符串，供 DoubanClient 使用
        未找到豆瓣 cookie 时返回空字符串
    """
    url = f"{server_url.rstrip('/')}/get/{uuid}"
    resp = requests.get(url, params={"password": key}, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    encrypted_b64 = data.get("encrypted") or data.get("encrypted_data")
    if not encrypted_b64:
        raise ValueError("CookieCloud 响应中缺少 encrypted 字段")

    decrypted = _decrypt(encrypted_b64, key)
    cookie_data = json.loads(decrypted)
    return _extract_douban_cookies(cookie_data)


def _decrypt(encrypted_b64: str, key: str) -> str:
    """AES-CBC 解密"""
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad

    md5_hash = hashlib.md5(key.encode("utf-8")).hexdigest()
    aes_key = md5_hash[:16].encode("utf-8")
    aes_iv = md5_hash[16:32].encode("utf-8")

    encrypted = base64.b64decode(encrypted_b64)
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_iv)
    decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
    return decrypted.decode("utf-8")


def _extract_douban_cookies(cookie_data) -> str:
    """从 CookieCloud 数据中提取豆瓣 cookie"""
    cookies_list = []
    if isinstance(cookie_data, list):
        cookies_list = cookie_data
    elif isinstance(cookie_data, dict):
        cookies_list = cookie_data.get("cookie_data", [])

    if not cookies_list:
        logger.warning("CookieCloud 数据中未找到 cookie 列表")
        return ""

    douban_cookies = {}
    for c in cookies_list:
        domain = c.get("domain", "")
        name = c.get("name", "")
        value = c.get("value", "")
        if any(d in domain for d in DOUBAN_DOMAINS) and name and value:
            douban_cookies[name] = value

    if not douban_cookies:
        logger.warning("未找到豆瓣相关 cookie")
        return ""

    return "; ".join(f"{k}={v}" for k, v in sorted(douban_cookies.items()))
