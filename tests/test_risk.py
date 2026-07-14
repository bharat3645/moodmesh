from moodmesh.risk import (
    ContributorWindowStats,
    compute_deltas,
    apply_review_load_flag,
    aggregate_risk,
    DEFAULT_THRESHOLDS,
)


def test_no_change_no_flag():
    baseline = ContributorWindowStats(
        author="alice",
        late_night_ratio=0.1,
        weekend_ratio=0.1,
        avg_sentiment=0.1,
        avg_message_length=40,
        commit_count=20,
    )
    recent = ContributorWindowStats(
        author="alice",
        late_night_ratio=0.1,
        weekend_ratio=0.1,
        avg_sentiment=0.1,
        avg_message_length=40,
        commit_count=20,
    )
    flag = compute_deltas(recent, baseline)
    assert not flag.is_rising_risk
    assert flag.reasons == []


def test_late_night_spike_flags():
    baseline = ContributorWindowStats(author="bob", late_night_ratio=0.05, commit_count=20)
    recent = ContributorWindowStats(author="bob", late_night_ratio=0.30, commit_count=20)
    flag = compute_deltas(recent, baseline)
    assert flag.is_rising_risk
    assert any("late-night" in r for r in flag.reasons)


def test_weekend_spike_flags():
    baseline = ContributorWindowStats(author="carol", weekend_ratio=0.0, commit_count=20)
    recent = ContributorWindowStats(author="carol", weekend_ratio=0.20, commit_count=20)
    flag = compute_deltas(recent, baseline)
    assert flag.is_rising_risk
    assert any("weekend" in r for r in flag.reasons)


def test_sentiment_drop_flags():
    baseline = ContributorWindowStats(author="dave", avg_sentiment=0.2, commit_count=20)
    recent = ContributorWindowStats(author="dave", avg_sentiment=-0.05, commit_count=20)
    flag = compute_deltas(recent, baseline)
    assert flag.is_rising_risk
    assert any("sentiment" in r for r in flag.reasons)


def test_terseness_drop_flags():
    baseline = ContributorWindowStats(author="erin", avg_message_length=60, commit_count=20)
    recent = ContributorWindowStats(author="erin", avg_message_length=20, commit_count=20)
    flag = compute_deltas(recent, baseline)
    assert flag.is_rising_risk
    assert any("terser" in r for r in flag.reasons)


def test_small_deltas_do_not_flag():
    baseline = ContributorWindowStats(
        author="frank", late_night_ratio=0.10, weekend_ratio=0.05, avg_sentiment=0.1,
        avg_message_length=40, commit_count=20,
    )
    recent = ContributorWindowStats(
        author="frank", late_night_ratio=0.15, weekend_ratio=0.08, avg_sentiment=0.05,
        avg_message_length=38, commit_count=20,
    )
    flag = compute_deltas(recent, baseline)
    assert not flag.is_rising_risk


def test_review_load_concentration_flags():
    baseline = ContributorWindowStats(author="grace", commit_count=10)
    recent = ContributorWindowStats(author="grace", commit_count=10)
    flag = compute_deltas(recent, baseline)
    apply_review_load_flag(flag, review_load_share=0.75)
    assert flag.is_rising_risk
    assert any("review load" in r for r in flag.reasons)
    assert flag.review_load_share == 0.75


def test_review_load_below_threshold_no_flag():
    baseline = ContributorWindowStats(author="heidi", commit_count=10)
    recent = ContributorWindowStats(author="heidi", commit_count=10)
    flag = compute_deltas(recent, baseline)
    apply_review_load_flag(flag, review_load_share=0.2)
    assert not flag.is_rising_risk


def test_aggregate_risk_missing_baseline_uses_zero_baseline():
    recent = {"ivan": ContributorWindowStats(author="ivan", late_night_ratio=0.5, commit_count=5)}
    flags = aggregate_risk(recent, baseline_stats={})
    assert len(flags) == 1
    assert flags[0].is_rising_risk


def test_custom_thresholds_are_respected():
    baseline = ContributorWindowStats(author="judy", late_night_ratio=0.0, commit_count=10)
    recent = ContributorWindowStats(author="judy", late_night_ratio=0.05, commit_count=10)
    # default threshold 0.15 would not flag a 0.05 delta
    default_flag = compute_deltas(recent, baseline)
    assert not default_flag.is_rising_risk
    # a stricter custom threshold should flag it
    strict_flag = compute_deltas(recent, baseline, thresholds={"late_night_ratio_delta": 0.03})
    assert strict_flag.is_rising_risk


def test_default_thresholds_immutable_across_calls():
    # ensure passing custom thresholds doesn't mutate the module default
    baseline = ContributorWindowStats(author="k", late_night_ratio=0.0, commit_count=10)
    recent = ContributorWindowStats(author="k", late_night_ratio=0.05, commit_count=10)
    compute_deltas(recent, baseline, thresholds={"late_night_ratio_delta": 0.01})
    assert DEFAULT_THRESHOLDS["late_night_ratio_delta"] == 0.15
