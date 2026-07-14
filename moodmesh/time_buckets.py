"""Time-of-day / weekend bucketing for commit timestamps.

Buckets (based on the *local* time the commit was authored, i.e. the
timezone offset recorded by git at commit time -- this is what
``git log``'s ``%ad``/``%ai`` with the author's own offset gives us):

- ``business_hours``: Mon-Fri, 09:00-18:00 (inclusive of 09:00, exclusive of 18:00)
- ``evening``: Mon-Fri, 18:00-23:00
- ``late_night``: any day, 23:00-05:00 (wraps past midnight)
- ``weekend``: Sat/Sun, 05:00-23:00 (daytime/evening weekend work)

Precedence: late_night is checked first (it can occur on a weekend too --
we still call it late_night, since "working at 2am on a Saturday" is a
stronger burnout signal than plain "weekend work"). Then weekend, then
business_hours vs evening on weekdays.

These thresholds are a deliberately simple, documented heuristic -- not a
labor-law or timezone-perfect model. Teams spanning many timezones should
interpret bucket ratios as relative trends per-contributor, not absolute
truths.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

BUCKETS = ("business_hours", "evening", "late_night", "weekend")

LATE_NIGHT_START_HOUR = 23
LATE_NIGHT_END_HOUR = 5  # exclusive upper bound, wraps past midnight
BUSINESS_START_HOUR = 9
BUSINESS_END_HOUR = 18


def classify_timestamp(dt: datetime) -> str:
    """Classify a single (timezone-aware or naive, but *local*) datetime.

    ``dt`` is expected to already be in the author's local time (i.e. the
    offset git recorded for that commit), not converted to UTC.
    """
    hour = dt.hour
    weekday = dt.weekday()  # Mon=0 .. Sun=6
    is_weekend = weekday >= 5

    if hour >= LATE_NIGHT_START_HOUR or hour < LATE_NIGHT_END_HOUR:
        return "late_night"
    if is_weekend:
        return "weekend"
    if BUSINESS_START_HOUR <= hour < BUSINESS_END_HOUR:
        return "business_hours"
    if BUSINESS_END_HOUR <= hour < LATE_NIGHT_START_HOUR:
        return "evening"
    # Early morning weekday before business hours (05:00-09:00): counts as
    # "evening"-adjacent off-hours work; grouped with evening as generic
    # off-hours-but-not-late-night weekday work.
    return "evening"


@dataclass(frozen=True)
class BucketCounts:
    business_hours: int = 0
    evening: int = 0
    late_night: int = 0
    weekend: int = 0

    @property
    def total(self) -> int:
        return self.business_hours + self.evening + self.late_night + self.weekend

    def ratio(self, bucket: str) -> float:
        total = self.total
        if total == 0:
            return 0.0
        return getattr(self, bucket) / total

    def as_dict(self) -> dict:
        return {
            "business_hours": self.business_hours,
            "evening": self.evening,
            "late_night": self.late_night,
            "weekend": self.weekend,
            "total": self.total,
        }


def bucket_commits(commits) -> BucketCounts:
    """``commits`` is an iterable of objects/dicts with a ``.timestamp``/["timestamp"]
    local datetime attribute (see git_ingest.Commit)."""
    counts = {b: 0 for b in BUCKETS}
    for c in commits:
        ts = c.timestamp if hasattr(c, "timestamp") else c["timestamp"]
        bucket = classify_timestamp(ts)
        counts[bucket] += 1
    return BucketCounts(**counts)
