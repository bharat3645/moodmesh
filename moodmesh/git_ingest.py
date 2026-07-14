"""Git-log ingester.

Extracts per-commit author, local timestamp, and message from a local git
repository using ``git log`` via subprocess. No network access, no cloning --
operates purely on a repo path already present on disk.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

# Field separator unlikely to appear in commit data; record separator marks
# the boundary between commits (a commit message may contain the field sep
# only if it literally contains this exact byte sequence, which is
# extraordinarily unlikely for real commit messages).
_FIELD_SEP = "\x1f"
_RECORD_SEP = "\x1e"

_LOG_FORMAT = (
    f"%H{_FIELD_SEP}%an{_FIELD_SEP}%ae{_FIELD_SEP}%aI{_FIELD_SEP}%s{_RECORD_SEP}"
)


@dataclass(frozen=True)
class Commit:
    sha: str
    author_name: str
    author_email: str
    timestamp: datetime  # local time, tz-aware, using the author's own UTC offset
    message: str

    @property
    def author(self) -> str:
        """Stable per-contributor key: prefer email, fall back to name."""
        return self.author_email or self.author_name


class GitIngestError(RuntimeError):
    """Raised when the target path is not a usable git repository."""


def _parse_author_date(raw: str) -> datetime:
    # %aI = strict ISO 8601, e.g. 2024-05-01T13:45:00+05:30
    return datetime.fromisoformat(raw)


def load_commits(
    repo_path: str,
    since: Optional[str] = None,
    branch: Optional[str] = None,
) -> List[Commit]:
    """Run ``git log`` against ``repo_path`` and parse commits.

    Parameters
    ----------
    repo_path: path to a local git repository (must contain a .git dir/worktree)
    since: optional git-compatible date expression (e.g. "8 weeks ago") passed
        straight to ``git log --since``.
    branch: optional branch/ref to read instead of the current HEAD.
    """
    cmd = ["git", "-C", repo_path, "log", f"--pretty=format:{_LOG_FORMAT}"]
    if since:
        cmd.append(f"--since={since}")
    if branch:
        cmd.append(branch)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise GitIngestError("git executable not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise GitIngestError(
            f"git log failed for repo {repo_path!r}: {exc.stderr.strip()}"
        ) from exc

    commits: List[Commit] = []
    raw = result.stdout
    for record in raw.split(_RECORD_SEP):
        record = record.strip("\n")
        if not record.strip():
            continue
        parts = record.split(_FIELD_SEP)
        if len(parts) != 5:
            # Skip malformed records rather than blowing up the whole ingest.
            continue
        sha, author_name, author_email, date_raw, subject = parts
        try:
            ts = _parse_author_date(date_raw)
        except ValueError:
            continue
        commits.append(
            Commit(
                sha=sha,
                author_name=author_name,
                author_email=author_email,
                timestamp=ts,
                message=subject,
            )
        )
    return commits


def is_git_repo(repo_path: str) -> bool:
    try:
        subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def window_commits(
    commits: List[Commit], reference: datetime, days: int
) -> List[Commit]:
    """Return commits with timestamp in (reference - days, reference]."""
    start = reference - timedelta(days=days)
    out = []
    for c in commits:
        ts = c.timestamp
        ref = reference
        # Normalize both to UTC for comparison to avoid naive/aware mismatches.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        if ts.tzinfo != timezone.utc:
            ts = ts.astimezone(timezone.utc)
        if ref.tzinfo != timezone.utc:
            ref = ref.astimezone(timezone.utc)
        start_utc = start
        if start_utc.tzinfo is None:
            start_utc = start_utc.replace(tzinfo=timezone.utc)
        else:
            start_utc = start_utc.astimezone(timezone.utc)
        if start_utc < ts <= ref:
            out.append(c)
    return out
