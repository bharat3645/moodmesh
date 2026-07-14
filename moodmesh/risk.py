"""Risk aggregator: turns trend deltas into per-contributor "rising risk" flags.

Design principle: this module deliberately does NOT produce an absolute
"burnout score" for a person. It only flags WORSENING trends (deltas between
a recent window and a prior baseline window), because a single snapshot
(e.g. "40% late-night commits") could simply reflect someone's normal
schedule or timezone. A rising trend relative to that same person's own
baseline is a much weaker but more defensible signal.

All functions here are pure (no I/O, no globals) so they are easy to unit
test with synthetic before/after data.

Documented thresholds (tunable, see DEFAULT_THRESHOLDS):
    late_night_ratio_delta   >= 0.15   (15 percentage points) -> flag
    weekend_ratio_delta      >= 0.15   (15 percentage points) -> flag
    sentiment_score_delta    <= -0.10  (drop of 0.10 on the -1..1 scale) -> flag
    message_length_delta_pct <= -0.30  (messages got 30%+ terser) -> flag
    review_load_share        >= 0.50   (one reviewer carries >=50% of load) -> flag
        (this one is an absolute concentration threshold, not a delta,
        since review-load concentration is meaningful even as a snapshot)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

DEFAULT_THRESHOLDS = {
    "late_night_ratio_delta": 0.15,
    "weekend_ratio_delta": 0.15,
    "sentiment_score_delta": -0.10,
    "message_length_delta_pct": -0.30,
    "review_load_share": 0.50,
}


@dataclass
class ContributorWindowStats:
    """Stats for one contributor over one time window (recent or baseline)."""

    author: str
    late_night_ratio: float = 0.0
    weekend_ratio: float = 0.0
    evening_ratio: float = 0.0
    business_hours_ratio: float = 0.0
    avg_sentiment: float = 0.0
    avg_message_length: float = 0.0
    commit_count: int = 0


@dataclass
class ContributorRiskFlag:
    author: str
    reasons: List[str] = field(default_factory=list)
    late_night_ratio_delta: float = 0.0
    weekend_ratio_delta: float = 0.0
    sentiment_score_delta: float = 0.0
    message_length_delta_pct: Optional[float] = None
    review_load_share: Optional[float] = None

    @property
    def is_rising_risk(self) -> bool:
        return len(self.reasons) > 0


def compute_deltas(
    recent: ContributorWindowStats,
    baseline: ContributorWindowStats,
    thresholds: Dict[str, float] = None,
) -> ContributorRiskFlag:
    """Compare a recent window to a prior baseline window for one contributor
    and flag any thresholds crossed in the "worsening" direction."""
    t = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        t.update(thresholds)

    reasons: List[str] = []

    late_night_delta = recent.late_night_ratio - baseline.late_night_ratio
    if late_night_delta >= t["late_night_ratio_delta"]:
        reasons.append(
            f"late-night commit ratio up {late_night_delta:.0%} vs prior window"
        )

    weekend_delta = recent.weekend_ratio - baseline.weekend_ratio
    if weekend_delta >= t["weekend_ratio_delta"]:
        reasons.append(
            f"weekend commit ratio up {weekend_delta:.0%} vs prior window"
        )

    sentiment_delta = recent.avg_sentiment - baseline.avg_sentiment
    if sentiment_delta <= t["sentiment_score_delta"]:
        reasons.append(
            f"commit-message sentiment down {abs(sentiment_delta):.2f} vs prior window"
        )

    length_delta_pct: Optional[float] = None
    if baseline.avg_message_length > 0:
        length_delta_pct = (
            recent.avg_message_length - baseline.avg_message_length
        ) / baseline.avg_message_length
        if length_delta_pct <= t["message_length_delta_pct"]:
            reasons.append(
                f"commit messages {abs(length_delta_pct):.0%} terser vs prior window"
            )

    return ContributorRiskFlag(
        author=recent.author,
        reasons=reasons,
        late_night_ratio_delta=late_night_delta,
        weekend_ratio_delta=weekend_delta,
        sentiment_score_delta=sentiment_delta,
        message_length_delta_pct=length_delta_pct,
    )


def apply_review_load_flag(
    flag: ContributorRiskFlag,
    review_load_share: float,
    thresholds: Dict[str, float] = None,
) -> ContributorRiskFlag:
    """Add a review-load-concentration reason if this contributor carries an
    outsized share of total review comments. Mutates and returns ``flag``."""
    t = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        t.update(thresholds)

    flag.review_load_share = review_load_share
    if review_load_share >= t["review_load_share"]:
        flag.reasons.append(
            f"review load concentrated: {review_load_share:.0%} of all review comments"
        )
    return flag


def aggregate_risk(
    recent_stats: Dict[str, ContributorWindowStats],
    baseline_stats: Dict[str, ContributorWindowStats],
    review_load: Optional[Dict[str, float]] = None,
    thresholds: Dict[str, float] = None,
) -> List[ContributorRiskFlag]:
    """Compute a ContributorRiskFlag for every contributor present in
    ``recent_stats`` (contributors with no baseline data get an all-zero
    baseline, so any recent activity delta is measured against zero)."""
    flags = []
    for author, recent in recent_stats.items():
        baseline = baseline_stats.get(author) or ContributorWindowStats(author=author)
        flag = compute_deltas(recent, baseline, thresholds)
        if review_load and author in review_load:
            apply_review_load_flag(flag, review_load[author], thresholds)
        flags.append(flag)
    return flags
