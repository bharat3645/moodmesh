"""Optional PR review-comment ingester.

Expected JSON schema (a list of review-comment objects)::

    [
      {
        "author": "alice@example.com",
        "created_at": "2024-05-01T13:45:00+00:00",   # ISO 8601
        "body": "lgtm, thanks!",
        "pr_number": 42,
        "pr_opened_at": "2024-04-30T09:00:00+00:00"   # optional
      },
      ...
    ]

Only ``author``, ``created_at``, and ``body`` are required. ``pr_number`` and
``pr_opened_at`` are optional and enable turnaround-time computation (time
from PR open to first review comment on that PR, per reviewer). If
``pr_opened_at`` is missing for a PR's comments, we degrade gracefully:
turnaround for that PR is skipped and only comment-volume-per-reviewer /
sentiment are computed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ReviewComment:
    author: str
    timestamp: datetime
    body: str
    pr_number: Optional[int] = None
    pr_opened_at: Optional[datetime] = None


class ReviewIngestError(RuntimeError):
    pass


def _parse_dt(raw) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def load_reviews(path: str) -> List[ReviewComment]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:
        raise ReviewIngestError(f"reviews file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReviewIngestError(f"invalid JSON in reviews file {path}: {exc}") from exc

    if not isinstance(data, list):
        raise ReviewIngestError("reviews JSON must be a list of comment objects")

    comments: List[ReviewComment] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        author = item.get("author")
        created_at = _parse_dt(item.get("created_at"))
        body = item.get("body", "")
        if not author or created_at is None:
            # Skip malformed entries rather than aborting the whole file.
            continue
        pr_number = item.get("pr_number")
        pr_opened_at = _parse_dt(item.get("pr_opened_at"))
        comments.append(
            ReviewComment(
                author=author,
                timestamp=created_at,
                body=body or "",
                pr_number=pr_number,
                pr_opened_at=pr_opened_at,
            )
        )
    return comments


def comment_volume_per_reviewer(comments: List[ReviewComment]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for c in comments:
        counts[c.author] = counts.get(c.author, 0) + 1
    return counts


def turnaround_hours_per_reviewer(
    comments: List[ReviewComment],
) -> Dict[str, List[float]]:
    """First-review turnaround (hours from pr_opened_at to first comment by
    that reviewer on that PR), grouped by reviewer. PRs/comments lacking
    ``pr_opened_at`` are skipped for this computation (graceful degradation).
    """
    first_seen: Dict[tuple, ReviewComment] = {}
    for c in comments:
        if c.pr_number is None or c.pr_opened_at is None:
            continue
        key = (c.pr_number, c.author)
        existing = first_seen.get(key)
        if existing is None or c.timestamp < existing.timestamp:
            first_seen[key] = c

    out: Dict[str, List[float]] = {}
    for (_, author), c in first_seen.items():
        delta = c.timestamp - c.pr_opened_at
        hours = delta.total_seconds() / 3600.0
        if hours < 0:
            continue
        out.setdefault(author, []).append(hours)
    return out


def review_load_share(comments: List[ReviewComment]) -> Dict[str, float]:
    """Each reviewer's share of total review comment volume (0..1)."""
    counts = comment_volume_per_reviewer(comments)
    total = sum(counts.values())
    if total == 0:
        return {}
    return {author: n / total for author, n in counts.items()}
