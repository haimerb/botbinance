from collections import deque
from threading import Lock
from time import time


class AlertStore:
    def __init__(self, maxlen=100):
        self._items = deque(maxlen=maxlen)
        self._lock = Lock()

    def add(self, payload):
        entries = []
        for alert in payload.get("alerts") or []:
            labels = alert.get("labels") or {}
            annotations = alert.get("annotations") or {}
            entry = {
                "status": alert.get("status"),
                "alertname": labels.get("alertname"),
                "severity": labels.get("severity", "info"),
                "summary": annotations.get("summary"),
                "description": annotations.get("description"),
                "fingerprint": alert.get("fingerprint"),
                "starts_at": alert.get("startsAt"),
                "received_at": time(),
            }
            with self._lock:
                self._items.append(entry)
            entries.append(entry)
        return entries

    def list(self, limit=50):
        with self._lock:
            return list(reversed(self._items))[:limit]

    def clear(self):
        with self._lock:
            self._items.clear()
