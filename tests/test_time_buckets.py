from datetime import datetime, timezone, timedelta

from moodmesh.time_buckets import classify_timestamp, bucket_commits, BucketCounts


def _dt(y, m, d, h, minute=0, offset_hours=0):
    tz = timezone(timedelta(hours=offset_hours))
    return datetime(y, m, d, h, minute, tzinfo=tz)


def test_business_hours_weekday():
    # 2024-05-01 is a Wednesday
    dt = _dt(2024, 5, 1, 10, 0)
    assert classify_timestamp(dt) == "business_hours"


def test_evening_weekday():
    dt = _dt(2024, 5, 1, 20, 0)
    assert classify_timestamp(dt) == "evening"


def test_late_night_weekday():
    dt = _dt(2024, 5, 1, 23, 30)
    assert classify_timestamp(dt) == "late_night"


def test_late_night_wraps_past_midnight():
    dt = _dt(2024, 5, 2, 2, 0)
    assert classify_timestamp(dt) == "late_night"


def test_weekend_daytime():
    # 2024-05-04 is a Saturday
    dt = _dt(2024, 5, 4, 14, 0)
    assert classify_timestamp(dt) == "weekend"


def test_weekend_late_night_still_late_night():
    # Saturday at 1am should be late_night, not weekend -- late night takes
    # precedence since it's a stronger burnout signal.
    dt = _dt(2024, 5, 4, 1, 0)
    assert classify_timestamp(dt) == "late_night"


def test_early_morning_weekday_counts_as_evening_bucket():
    dt = _dt(2024, 5, 1, 6, 0)
    assert classify_timestamp(dt) == "evening"


class _FakeCommit:
    def __init__(self, timestamp):
        self.timestamp = timestamp


def test_bucket_commits_counts_and_ratios():
    commits = [
        _FakeCommit(_dt(2024, 5, 1, 10, 0)),  # business_hours
        _FakeCommit(_dt(2024, 5, 1, 20, 0)),  # evening
        _FakeCommit(_dt(2024, 5, 1, 23, 30)),  # late_night
        _FakeCommit(_dt(2024, 5, 4, 14, 0)),  # weekend
    ]
    counts = bucket_commits(commits)
    assert counts.total == 4
    assert counts.business_hours == 1
    assert counts.evening == 1
    assert counts.late_night == 1
    assert counts.weekend == 1
    assert counts.ratio("late_night") == 0.25


def test_bucket_counts_empty():
    counts = BucketCounts()
    assert counts.total == 0
    assert counts.ratio("late_night") == 0.0
