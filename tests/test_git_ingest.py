import os
import subprocess

import pytest

from moodmesh.git_ingest import load_commits, is_git_repo, window_commits, GitIngestError


def _run(cmd, cwd, env=None):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True, env=env)


@pytest.fixture
def sample_repo(tmp_path):
    repo_dir = tmp_path / "sample_repo"
    repo_dir.mkdir()
    repo_path = str(repo_dir)

    _run(["git", "init"], cwd=repo_path)
    _run(["git", "config", "user.name", "Test Author"], cwd=repo_path)
    _run(["git", "config", "user.email", "test.author@example.com"], cwd=repo_path)
    _run(["git", "config", "commit.gpgsign", "false"], cwd=repo_path)

    commits = [
        ("file1.txt", "Add initial feature", "2024-05-01T10:00:00+00:00"),
        ("file2.txt", "urgent hotfix: revert broken build", "2024-05-01T23:30:00+00:00"),
        ("file3.txt", "Improve tests and docs", "2024-05-04T14:00:00+00:00"),
    ]

    for filename, message, date in commits:
        fpath = repo_dir / filename
        fpath.write_text(f"content for {filename}\n")
        _run(["git", "add", filename], cwd=repo_path)
        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
        env["GIT_AUTHOR_NAME"] = "Test Author"
        env["GIT_AUTHOR_EMAIL"] = "test.author@example.com"
        env["GIT_COMMITTER_NAME"] = "Test Author"
        env["GIT_COMMITTER_EMAIL"] = "test.author@example.com"
        _run(["git", "commit", "-m", message], cwd=repo_path, env=env)

    return repo_path, commits


def test_is_git_repo_true(sample_repo):
    repo_path, _ = sample_repo
    assert is_git_repo(repo_path)


def test_is_git_repo_false(tmp_path):
    not_a_repo = tmp_path / "not_a_repo"
    not_a_repo.mkdir()
    assert not is_git_repo(str(not_a_repo))


def test_load_commits_reads_all_commits(sample_repo):
    repo_path, expected_commits = sample_repo
    commits = load_commits(repo_path)
    assert len(commits) == len(expected_commits)

    messages = {c.message for c in commits}
    for _, message, _ in expected_commits:
        assert message in messages


def test_load_commits_parses_author_and_timestamp(sample_repo):
    repo_path, _ = sample_repo
    commits = load_commits(repo_path)
    for c in commits:
        assert c.author_email == "test.author@example.com"
        assert c.author == "test.author@example.com"
        assert c.timestamp.year == 2024
        assert c.timestamp.month == 5


def test_load_commits_on_non_repo_raises(tmp_path):
    not_a_repo = tmp_path / "nope"
    not_a_repo.mkdir()
    with pytest.raises(GitIngestError):
        load_commits(str(not_a_repo))


def test_window_commits_filters_by_reference_date(sample_repo):
    repo_path, _ = sample_repo
    commits = load_commits(repo_path)
    from datetime import datetime, timezone

    reference = datetime(2024, 5, 4, 14, 0, tzinfo=timezone.utc)
    windowed = window_commits(commits, reference, days=1)
    # Only the commit exactly at 2024-05-04T14:00:00Z falls within a 1-day
    # window ending at that same instant.
    assert len(windowed) == 1
    assert windowed[0].message == "Improve tests and docs"


def test_window_commits_wider_window_includes_more(sample_repo):
    repo_path, _ = sample_repo
    commits = load_commits(repo_path)
    from datetime import datetime, timezone

    reference = datetime(2024, 5, 4, 14, 0, tzinfo=timezone.utc)
    windowed = window_commits(commits, reference, days=30)
    assert len(windowed) == 3
