# moodmesh

**A private engineering team health & burnout early-warning trend detector.**

moodmesh reads your git commit history (and, optionally, an exported JSON
file of PR review comments) and produces a weekly Markdown digest that flags
*rising* risk trends per contributor -- e.g. an increasing share of
late-night/weekend commits, a drop in commit-message sentiment, or review
load piling up on one person. It is designed from the ground up as a
**private manager tool**, not a surveillance or ranking system.

---

## Ethics & Privacy -- read this first

moodmesh analyzes coarse, aggregate trends in metadata that already exists
in your git history and (optionally) PR review comments. It is built around
a few hard rules:

1. **This is a conversation-starter, not a verdict.** A "rising risk" flag
   means a metric moved in a worse direction relative to that same person's
   own recent baseline -- it does not mean that person is burned out, doing
   bad work, or in trouble. Treat every flag as a prompt to have a private,
   supportive conversation, not as evidence.
2. **Never use this for performance reviews, ranking, or public reporting.**
   The per-contributor section of every digest is explicitly marked
   CONFIDENTIAL and is meant for a manager's eyes only, to inform how *they*
   check in with someone -- not to be shared with the team, HR, or used in
   promotion/PIP decisions.
3. **Get team opt-in and be transparent.** If you run moodmesh against a
   team's repository, tell the team it exists, what it looks at, and how
   you'll use (and won't use) it. Analyzing people without their knowledge
   undermines the trust this tool is meant to protect.
4. **The heuristics are coarse on purpose, and can be wrong.** Off-hours
   commit timestamps can reflect timezones, caregiving schedules, personal
   preference, or a deliberate flexible-hours culture -- not distress. The
   sentiment lexicon is a hand-built word list, not a clinical or validated
   psychological instrument. See "Limitations" below.
5. **No data leaves your machine.** moodmesh runs entirely locally against a
   git repo you already have on disk, and an optional local JSON file. The
   only network call in the entire codebase is the *optional* LLM narration
   layer, which only activates if you explicitly provide an API key.

If you are not comfortable with the above, don't run this tool on other
people's data.

---

## Problem statement

Engineering managers usually find out about burnout, review bottlenecks, or
team friction only after someone quits or a crisis hits. But the leading
indicators are often already sitting in your git history and review
activity: a rising ratio of late-night/weekend commits, review turnaround
slowing down, commit messages getting terser or more stressed-sounding
("urgent hotfix", "sorry", "fix fix fix"), or review load quietly piling
onto one person. moodmesh turns that existing metadata into a private,
trend-focused weekly digest so a manager can notice and act *before* it
becomes a crisis -- through a conversation, not a spreadsheet.

## Install

Requires Python 3.9+ and `git` on your PATH.

```bash
git clone https://github.com/bharat3645/moodmesh.git
cd moodmesh
pip install -r requirements.txt   # pytest (required for tests); anthropic is optional
```

No build step, no package install required to run the CLI directly out of
the repo (see Usage below). If you want `pip install -e .` style usage,
just add a `pyproject.toml` -- not included by default to keep the surface
area small.

## Usage

```bash
python -m moodmesh analyze <repo_path> [--reviews reviews.json] [--weeks 4] [--narrate] [-o out.md]
```

- `repo_path`: path to a local git repository to analyze.
- `--reviews`: optional path to a JSON file of PR review comments (schema below).
- `--weeks`: size in weeks of the trailing window and the prior baseline
  window it's compared against (default 4).
- `--narrate`: also print a short narrative summary (deterministic template
  unless `ANTHROPIC_API_KEY` is set and the `anthropic` package is installed).
- `-o/--output`: write the digest to a file instead of stdout.

### Example

```bash
python -m moodmesh analyze /path/to/some/repo --weeks 4 --narrate
```

Sample output (trimmed, from this project's own test fixtures):

```markdown
# moodmesh Weekly Digest

- Repository: `/path/to/some/repo`
- Generated: 2026-07-14T11:30:13
- Window: trailing 4 weeks vs. the prior 4 weeks (see CLI `--weeks` for the exact window used)

## Team-Level Trends

- Commits analyzed (recent window): **5**
- Late-night commit ratio: **60%** (prior window: 0%)
- Weekend commit ratio: **20%** (prior window: 0%)
- Average commit-message sentiment score: **-0.23** (prior window: 0.47, ...)

**1 of 1 contributors** show a rising-risk trend this period (see confidential section below).

---

## Per-Contributor Detail

> **CONFIDENTIAL -- for manager eyes only.**
> ...

### alice@example.com -- RISING RISK

- Commits (recent window): 5
- Late-night ratio: 60%
- Weekend ratio: 20%
- Avg sentiment score: -0.23
- Reasons flagged:
  - late-night commit ratio up 60% vs prior window
  - weekend commit ratio up 20% vs prior window
  - commit-message sentiment down 0.70 vs prior window
  - review load concentrated: 75% of all review comments
```

### PR review JSON schema (optional, for `--reviews`)

A list of review-comment objects:

```json
[
  {
    "author": "alice@example.com",
    "created_at": "2024-04-02T10:00:00+00:00",
    "body": "lgtm, thanks!",
    "pr_number": 101,
    "pr_opened_at": "2024-04-01T09:00:00+00:00"
  }
]
```

`author`, `created_at`, and `body` are required; `pr_number` and
`pr_opened_at` are optional. If `pr_opened_at` is present for a PR's
comments, moodmesh computes per-reviewer first-review turnaround time. If
it's missing, moodmesh degrades gracefully to comment-volume-per-reviewer
and review-load-share only (no error).

## Architecture

```
moodmesh/
  git_ingest.py     git log ingester -> Commit objects (author, local ts, message)
  time_buckets.py   classifies timestamps: business_hours/evening/late_night/weekend
  lexicon.py        hand-built, documented word-list stress/sentiment scorer
  review_ingest.py  optional PR review-comment JSON loader + turnaround/volume/share
  risk.py           pure functions comparing recent vs baseline window per contributor
  report.py         renders the Markdown digest (team section + CONFIDENTIAL section)
  narrate.py        narrate_digest(report, llm_client=None): templated or real LLM
  cli.py, __main__.py  python -m moodmesh analyze ...
tests/              pytest suite incl. a real temp git repo fixture
```

Data flow: git_ingest -> group commits by author -> time_buckets + lexicon
compute per-author stats for a recent window and a baseline window ->
risk.aggregate_risk compares the two windows per author (plus optional
review_ingest review-load-share) -> report.generate_digest renders
Markdown -> optional narrate.narrate_digest for a short summary.

## Limitations of the heuristics

- Time bucketing uses git's recorded author timezone offset, not a
  verified real-world timezone.
- Off-hours work is not inherently bad; moodmesh flags *changes* relative
  to a person's own baseline specifically to reduce false positives.
- The sentiment/stress lexicon is a small hand-built word list, not a
  trained model or clinical instrument.
- Squash-merged/rebased history can distort authorship and timing.
- Small sample sizes are noisy -- use judgment on low commit counts.
- Review-load concentration is a snapshot by design and can also reflect
  legitimate code-ownership patterns.

moodmesh is meant to prompt a human conversation with context the tool
does not have -- not to replace that conversation with a number.

## Testing

```bash
pip install -r requirements.txt
pytest
```

The test suite covers time bucketing, the lexicon scorer, the risk
aggregator (synthetic before/after data with known expected flags), the
report generator, and the git-log ingester (a real temporary git repo
created in a pytest fixture with controlled GIT_AUTHOR_DATE/
GIT_COMMITTER_DATE commits -- fully local, no network required).

## License

MIT -- see [LICENSE](LICENSE).
