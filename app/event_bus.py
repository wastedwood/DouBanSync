"""线程安全的事件总线——用于 SSE 实时日志推送"""

import json
import queue
import threading


class EventBus:
    """发布/订阅事件总线，支持多订阅者队列"""

    def __init__(self):
        self._queues: dict[int, queue.Queue] = {}
        self._lock = threading.Lock()

    def subscribe(self) -> tuple[int, queue.Queue]:
        """注册订阅者，返回 (sid, queue)"""
        q = queue.Queue(maxsize=1000)
        with self._lock:
            sid = id(q)
            self._queues[sid] = q
            return sid, q

    def unsubscribe(self, sid: int):
        """取消订阅"""
        with self._lock:
            self._queues.pop(sid, None)

    def publish(self, event: dict):
        """向所有订阅者广播事件"""
        payload = json.dumps(event, ensure_ascii=False)
        with self._lock:
            dead = []
            for sid, q in self._queues.items():
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    dead.append(sid)
            for sid in dead:
                self._queues.pop(sid, None)
