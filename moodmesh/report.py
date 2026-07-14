"""Markdown weekly digest generator.

Layout, aggregate-first:
  1. Team-level summary (trend direction, headline numbers)
  2. Private, per-contributor "rising risk" section, clearly labeled
     CONFIDENTIAL, intended for a manager's eyes only and as a prompt for a
     supportive 1:1 conversation -- never for ranking, public shaming, or
     unilateral performance decisions.

This module contains no I/O beyond returning a string; callers decide
whether/where to write it to disk.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from .risk import ContributorRiskFlag, ContributorWindowStats

CONFIDENTIALITY_NOTICE = (
    "> **CONFIDENTIAL -- for manager eyes only.**\n"
    "> This section flags *trends*, not facts about a person's wellbeing.\n"
    "> Discuss with the individual, in private and with empathy, before acting on\n"
    "> anything here. Do not use this section in performance reviews, do not\n"
    "> share it with the team, and do not use it to rank or compare people.\n"
)


def _team_totals(recent_stats: Dict[str, ContributorWindowStats]) -> dict:
    total_commits = sum(s.commit_count for s in recent_stats.values())
    if total_commits == 0:
        return {
            "total_commits": 0,
            "late_night_ratio": 0.0,
            "weekend_ratio": 0.0,
            "avg_sentiment": 0.0,
        }
    late_night = sum(s.late_night_ratio * s.commit_count for s in recent_stats.values())
    weekend = sum(s.weekend_ratio * s.commit_count for s in recent_stats.values())
    sentiment = sum(s.avg_sentiment * s.commit_count for s in recent_stats.values())
    return {
        "total_commits": total_commits,
        "late_night_ratio": late_night / total_commits,
        "weekend_ratio": weekend / total_commits,
        "avg_sentiment": sentiment / total_commits,
    }


def generate_digest(
    recent_stats: Dict[str, ContributorWindowStats],
    baseline_stats: Dict[str, ContributorWindowStats],
    flags: List[ContributorRiskFlag],
    repo_path: str = "",
    generated_at: Optional[datetime] = None,
) -> str:
    generated_at = generated_at or datetime.now()
    recent_totals = _team_totals(recent_stats)
    baseline_totals = _team_totals(baseline_stats)

    lines: List[str] = []
    lines.append("# moodmesh Weekly Digest")
    lines.append("")
    lines.append(f"- Repository: `{repo_path or 'unknown'}`")
    lines.append(f"- Generated: {generated_at.isoformat(timespec='seconds')}")
    lines.append(
        "- Window: trailing 4 weeks vs. the prior 4 weeks "
        "(see CLI `--weeks` for the exact window used)"
    )
    lines.append("")
    lines.append(
        "This is a private, aggregate-first digest of trend signals derived "
        "from git commit metadata. It is **not** a performance evaluation "
        "tool -- see the Ethics & Privacy section of the README before "
        "using it."
    )
    lines.append("")

    lines.append("## Team-Level Trends")
    lines.append("")
    lines.append(f"- Commits analyzed (recent window): **{recent_totals['total_commits']}**")
    lines.append(
        f"- Late-night commit ratio: **{recent_totals['late_night_ratio']:.0%}** "
        f"(prior window: {baseline_totals['late_night_ratio']:.0%})"
    )
    lines.append(
        f"- Weekend commit ratio: **{recent_totals['weekend_ratio']:.0%}** "
        f"(prior window: {baseline_totals['weekend_ratio']:.0%})"
    )
    lines.append(
        f"- Average commit-message sentiment score: **{recent_totals['avg_sentiment']:.2f}** "
        f"(prior window: {baseline_totals['avg_sentiment']:.2f}, range -1..1, "
        "see README for what this heuristic does and does not measure)"
    )
    lines.append("")

    rising = [f for f in flags if f.is_rising_risk]
    lines.append(
        f"**{len(rising)} of {len(flags)} contributors** show a rising-risk "
        "trend this period (see confidential section below for names and "
        "reasons)."
    )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Per-Contributor Detail")
    lines.append("")
    lines.append(CONFIDENTIALITY_NOTICE)
    lines.append("")

    if not flags:
        lines.append("_No contributor data available for this window._")
    else:
        for flag in sorted(flags, key=lambda f: f.author):
            marker = "RISING RISK" if flag.is_rising_risk else "no flags"
            lines.append(f"### {flag.author} -- {marker}")
            lines.append("")
            recent = recent_stats.get(flag.author)
            if recent:
                lines.append(f"- Commits (recent window): {recent.commit_count}")
                lines.append(f"- Late-night ratio: {recent.late_night_ratio:.0%}")
                lines.append(f"- Weekend ratio: {recent.weekend_ratio:.0%}")
                lines.append(f"- Avg sentiment score: {recent.avg_sentiment:.2f}")
            if flag.reasons:
                lines.append("- Reasons flagged:")
                for r in flag.reasons:
                    lines.append(f"  - {r}")
            else:
                lines.append("- No worsening trend detected this period.")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "_Generated by moodmesh, a coarse trend-detection heuristic. "
        "See README `Limitations` before making any decisions based on this "
        "report._"
    )
    return "\n".join(lines) + "\n"
