from src.strategy.event_calendar import EconomicCalendar, _to_ms


def test_calendar_labels_cpi_and_fomc():
    calendar = EconomicCalendar()
    assert calendar.label_at(_to_ms("2026-11-10T13:30:00Z")) == "CPI"
    assert calendar.label_at(_to_ms("2026-12-09T19:00:00Z")) == "FOMC"


def test_calendar_blackout_window():
    calendar = EconomicCalendar(blackout_minutes=120)
    event = _to_ms("2026-11-10T13:30:00Z")
    assert calendar.is_blackout(event - 119 * 60_000)
    assert calendar.is_blackout(event + 119 * 60_000)
    assert not calendar.is_blackout(event - 121 * 60_000)


def test_calendar_accepts_custom_events():
    calendar = EconomicCalendar(
        events=[("2026-11-27T12:00:00Z", "CUSTOM")],
        blackout_minutes=30,
    )
    assert calendar.label_at(_to_ms("2026-11-27T11:45:00Z")) == "CUSTOM"
    assert calendar.label_at(_to_ms("2026-11-27T12:45:00Z")) is None
