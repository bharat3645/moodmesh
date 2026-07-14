from datetime import datetime

from moodmesh.risk import ContributorWindowStats, ContributorRiskFlag
from moodmesh.report import generate_digest, CONFIDENTIALITY_NOTICE
from moodmesh.narrate import narrate_digest


def test_generate_digest_contains_confidential_notice():
    recent = {"alice": ContributorWindowStats(author="alice", commit_count=10, late_night_ratio=0.4)}
    baseline = {"alice": ContributorWindowStats(author="alice", commit_count=10, late_night_ratio=0.1)}
    flags = [ContributorRiskFlag(author="alice", reasons=["late-night commit ratio up 30% vs prior window"])]

    digest = generate_digest(recent, baseline, flags, repo_path="/tmp/repo", generated_at=datetime(2024, 5, 1))

    assert "CONFIDENTIAL" in digest
    assert "manager eyes only" in digest
    assert "alice" in digest
    assert "RISING RISK" in digest
    assert "Team-Level Trends" in digest


def test_generate_digest_no_flags_shows_no_rising_risk():
    recent = {"bob": ContributorWindowStats(author="bob", commit_count=10)}
    baseline = {"bob": ContributorWindowStats(author="bob", commit_count=10)}
    flags = [ContributorRiskFlag(author="bob", reasons=[])]

    digest = generate_digest(recent, baseline, flags, repo_path="/tmp/repo")

    assert "no flags" in digest
    assert "0 of 1 contributors" in digest


def test_generate_digest_empty_data():
    digest = generate_digest({}, {}, [])
    assert "No contributor data available" in digest


def test_narrate_digest_offline_templated_no_risk():
    recent = {"bob": ContributorWindowStats(author="bob", commit_count=10)}
    baseline = {"bob": ContributorWindowStats(author="bob", commit_count=10)}
    flags = [ContributorRiskFlag(author="bob", reasons=[])]
    digest = generate_digest(recent, baseline, flags)

    narrative = narrate_digest(digest, llm_client=None)
    assert "no contributors" in narrative.lower()


def test_narrate_digest_offline_templated_with_risk():
    recent = {"alice": ContributorWindowStats(author="alice", commit_count=10)}
    baseline = {"alice": ContributorWindowStats(author="alice", commit_count=10)}
    flags = [ContributorRiskFlag(author="alice", reasons=["some reason"])]
    digest = generate_digest(recent, baseline, flags)

    narrative = narrate_digest(digest, llm_client=None)
    assert "1 of 1 contributors" in narrative
    assert "CONFIDENTIAL" in narrative or "confidential" in narrative.lower() or "private" in narrative.lower()
