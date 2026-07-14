"""Optional LLM narrative layer.

``narrate_digest(report, llm_client=None)`` produces a short human-readable
narrative summary of an already-generated Markdown digest.

- With no ``llm_client`` and no ANTHROPIC_API_KEY configured, this returns a
  deterministic, templated narrative (no network calls, fully offline,
  reproducible -- good for CI/tests).
- If an ``llm_client`` is supplied (an anthropic.Anthropic()-like client) or
  ANTHROPIC_API_KEY is set in the environment and the ``anthropic`` package
  is installed, a real Claude call is attempted for a richer narrative. This
  code path is not exercised by the test suite (no network in CI); it is
  provided as a real, working integration for users who want it.
"""

from __future__ import annotations

import os
import re
from typing import Optional


def _extract_summary_facts(report: str) -> dict:
    facts = {"rising_count": None, "total_count": None}
    m = re.search(r"\*\*(\d+) of (\d+) contributors\*\*", report)
    if m:
        facts["rising_count"] = int(m.group(1))
        facts["total_count"] = int(m.group(2))
    return facts


def _templated_narrative(report: str) -> str:
    facts = _extract_summary_facts(report)
    rising = facts.get("rising_count")
    total = facts.get("total_count")

    if rising is None or total is None:
        return (
            "moodmesh digest summary: report generated, but no contributor "
            "summary line was found to narrate. Review the full digest for "
            "details."
        )

    if rising == 0:
        return (
            f"Summary: no contributors ({total} analyzed) show a rising-risk "
            "trend this period. Team-level off-hours and sentiment metrics "
            "are stable relative to the prior window. No action needed beyond "
            "routine check-ins."
        )

    return (
        f"Summary: {rising} of {total} contributors show a rising-risk trend "
        "this period (worsening late-night/weekend ratios, sentiment, or "
        "review-load concentration versus their own prior-window baseline). "
        "This is a private, manager-facing signal only -- review the "
        "CONFIDENTIAL per-contributor section and consider a supportive, "
        "private conversation before taking any action."
    )


def narrate_digest(report: str, llm_client: Optional[object] = None) -> str:
    """Return a short narrative summary of ``report``.

    If ``llm_client`` is given, or ``ANTHROPIC_API_KEY`` is set in the
    environment and the ``anthropic`` package is importable, attempt a real
    LLM call. Otherwise (the default, offline path) return a deterministic
    templated narrative.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    client = llm_client
    if client is None and api_key:
        try:
            import anthropic  # type: ignore

            client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            client = None

    if client is None:
        return _templated_narrative(report)

    prompt = (
        "You are summarizing a private, confidential engineering-team "
        "health digest for an engineering manager. Be concise (3-5 "
        "sentences), empathetic, and explicitly avoid ranking or shaming "
        "individuals. Recommend supportive private conversations, not "
        "performance actions. Here is the digest:\n\n" + report
    )
    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        # anthropic SDK returns content blocks; concatenate text blocks.
        parts = []
        for block in getattr(response, "content", []):
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        narrative = "".join(parts).strip()
        return narrative or _templated_narrative(report)
    except Exception:
        # Never let a narrative-layer failure break the core digest.
        return _templated_narrative(report)
