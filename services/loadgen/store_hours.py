"""Store hours in each location's IANA time zone, including DST changes."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


STORE_TIME_ZONES = {
    "boston": "America/New_York",
    "chicago": "America/Chicago",
    "london": "Europe/London",
}
OPEN_HOUR = 10
CLOSE_HOUR = 20


def is_open(store: str, when: datetime | None = None) -> bool:
    instant = when or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("store hour checks require a timezone-aware timestamp")
    hour = instant.astimezone(ZoneInfo(STORE_TIME_ZONES[store])).hour
    return OPEN_HOUR <= hour < CLOSE_HOUR


def open_stores(when: datetime | None = None) -> list[str]:
    return [store for store in STORE_TIME_ZONES if is_open(store, when)]
