"""CLI entrypoint: ``python -m moodmesh analyze <repo_path> [--reviews reviews.json] [--weeks 4]``"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List

from .git_ingest import Commit, GitIngestError, is_git_repo, load_commits, window_commits
from .lexicon import average_length, average_score
from .narrate import narrate_digest
from .report import generate_digest
from .review_ingest import (
    ReviewIngestError,
    load_reviews,
    review_load_share,
)
from .risk import ContributorWindowStats, aggregate_risk
from .time_buckets import bucket_commits


def _group_by_author(commits: List[Commit]) -> Dict[str, List[Commit]]:
    grouped: Dict[str, List[Commit]] = defaultdict(list)
    for c in commits:
        grouped[c.author].append(c)
    return grouped


def build_window_stats(commits: List[Commit]) -> Dict[str, ContributorWindowStats]:
    grouped = _group_by_author(commits)
    stats: Dict[str, ContributorWindowStats] = {}
    for author, author_commits in grouped.items():
        counts = bucket_commits(author_commits)
        messages = [c.message for c in author_commits]
        stats[author] = ContributorWindowStats(
            author=author,
            late_night_ratio=counts.ratio("late_night"),
            weekend_ratio=counts.ratio("weekend"),
            evening_ratio=counts.ratio("evening"),
            business_hours_ratio=counts.ratio("business_hours"),
            avg_sentiment=average_score(messages),
            avg_message_length=average_length(messages),
            commit_count=len(author_commits),
        )
    return stats


def run_analysis(repo_path: str, reviews_path: str = None, weeks: int = 4) -> str:
    if not is_git_repo(repo_path):
        raise GitIngestError(f"{repo_path!r} is not a git repository")

    commits = load_commits(repo_path)
    if not commits:
        reference = datetime.now(timezone.utc)
        recent_stats: Dict[str, ContributorWindowStats] = {}
        baseline_stats: Dict[str, ContributorWindowStats] = {}
    else:
        latest = max(c.timestamp for c in commits)
        reference = latest
        recent_window_days = weeks * 7
        baseline_window_days = weeks * 7

        recent_commits = window_commits(commits, reference, recent_window_days)
        baseline_reference = reference
        # baseline window = the window immediately before the recent window
        from datetime import timedelta

        baseline_reference = reference - timedelta(days=recent_window_days)
        baseline_commits = window_commits(commits, baseline_reference, baseline_window_days)

        recent_stats = build_window_stats(recent_commits)
        baseline_stats = build_window_stats(baseline_commits)

    load_share = {}
    if reviews_path:
        try:
            reviews = load_reviews(reviews_path)
            load_share = review_load_share(reviews)
        except ReviewIngestError as exc:
            print(f"warning: could not load reviews file: {exc}", file=sys.stderr)

    flags = aggregate_risk(recent_stats, baseline_stats, review_load=load_share)
    digest = generate_digest(
        recent_stats,
        baseline_stats,
        flags,
        repo_path=repo_path,
        generated_at=datetime.now(),
    )
    return digest


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="moodmesh",
        description=(
            "moodmesh -- private engineering team health & burnout "
            "early-warning trend detector. See README Ethics & Privacy "
            "section before use."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser(
        "analyze", help="Analyze a local git repo and print a weekly digest"
    )
    analyze.add_argument("repo_path", help="Path to a local git repository")
    analyze.add_argument(
        "--reviews",
        default=None,
        help="Optional path to a JSON file of PR review comments (see README schema)",
    )
    analyze.add_argument(
        "--weeks",
        type=int,
        default=4,
        help="Size of the trailing/baseline comparison windows in weeks (default: 4)",
    )
    analyze.add_argument(
        "--narrate",
        action="store_true",
        help="Also print a short narrative summary (templated unless ANTHROPIC_API_KEY is set)",
    )
    analyze.add_argument(
        "-o",
        "--output",
        default=None,
        help="Write the digest Markdown to this file instead of stdout",
    )

    args = parser.parse_args(argv)

    if args.command == "analyze":
        try:
            digest = run_analysis(args.repo_path, reviews_path=args.reviews, weeks=args.weeks)
        except GitIngestError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        if args.output:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(digest)
            print(f"Digest written to {args.output}")
        else:
            print(digest)

        if args.narrate:
            print("\n--- Narrative Summary ---\n")
            print(narrate_digest(digest))

        return 0

    return 1
