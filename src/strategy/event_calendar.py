from dataclasses import dataclass
from datetime import datetime, timezone

MINUTO_MS = 60_000


@dataclass(frozen=True)
class EventWindow:
    start_ms: int
    end_ms: int
    label: str


_RAW_2026_EVENTS = [
    ("2026-01-13T13:30:00Z", "CPI"),
    ("2026-01-28T19:00:00Z", "FOMC"),
    ("2026-02-13T13:30:00Z", "CPI"),
    ("2026-03-11T12:30:00Z", "CPI"),
    ("2026-03-18T18:00:00Z", "FOMC"),
    ("2026-04-10T12:30:00Z", "CPI"),
    ("2026-04-29T18:00:00Z", "FOMC"),
    ("2026-05-12T12:30:00Z", "CPI"),
    ("2026-06-10T12:30:00Z", "CPI"),
    ("2026-06-17T18:00:00Z", "FOMC"),
    ("2026-07-14T12:30:00Z", "CPI"),
    ("2026-07-29T18:00:00Z", "FOMC"),
    ("2026-08-12T12:30:00Z", "CPI"),
    ("2026-09-11T12:30:00Z", "CPI"),
    ("2026-09-16T18:00:00Z", "FOMC"),
    ("2026-10-14T12:30:00Z", "CPI"),
    ("2026-10-28T18:00:00Z", "FOMC"),
    ("2026-11-10T13:30:00Z", "CPI"),
    ("2026-12-09T19:00:00Z", "FOMC"),
    ("2026-12-10T13:30:00Z", "CPI"),
]


def _to_ms(value):
    if isinstance(value, (int, float)):
        return int(value)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


class EconomicCalendar:
    """Ventanas de blackout alrededor de FOMC y CPI (horario ET → UTC)."""

    def __init__(self, events=None, blackout_minutes=120):
        raw = events if events is not None else _RAW_2026_EVENTS
        half = blackout_minutes * MINUTO_MS
        self.windows = []
        for item in raw:
            if len(item) == 2:
                ts, label = item
                start = end = _to_ms(ts)
            else:
                start, end, label = item
                start, end = _to_ms(start), _to_ms(end)
            self.windows.append(
                EventWindow(start - half, end + half, label)
            )
        self.windows.sort(key=lambda w: w.start_ms)

    def label_at(self, ts_ms):
        ts = _to_ms(ts_ms)
        for window in self.windows:
            if window.start_ms <= ts <= window.end_ms:
                return window.label
        return None

    def is_blackout(self, ts_ms) -> bool:
        return self.label_at(ts_ms) is not None
