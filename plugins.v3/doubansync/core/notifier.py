"""Bark 推送通知"""

import logging

import requests

logger = logging.getLogger(__name__)

BARK_API_BASE = "https://api.day.app"


class BarkNotifier:
    """Bark iOS 推送通知客户端"""

    def __init__(self, device_key: str = ""):
        self._device_key = device_key

    @property
    def enabled(self) -> bool:
        return bool(self._device_key)

    @property
    def device_key(self) -> str:
        return self._device_key

    def send(self, title: str, body: str, group: str = "DouBanSync") -> bool:
        if not self._device_key:
            return False
        try:
            url = f"{BARK_API_BASE}/{self._device_key}"
            resp = requests.post(url, json={
                "title": title,
                "body": body,
                "group": group,
            }, timeout=5)
            if resp.status_code != 200:
                logger.warning("Bark API 返回异常: %s", resp.text[:200])
                return False
            return True
        except requests.RequestException as e:
            logger.warning("Bark 通知发送失败: %s", e)
            return False
