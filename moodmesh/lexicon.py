"""A small, offline, deterministic lexicon-based stress/sentiment scorer.

IMPORTANT: this is a coarse heuristic, NOT clinical sentiment analysis and
NOT a diagnostic tool. It counts occurrences of hand-picked stress-indicative
words/phrases versus a small set of neutral/positive markers in short text
(commit subject lines or PR review comment bodies) and returns a bounded
score. It exists only to help spot *trends* (is stress language increasing
over time for a contributor?) -- a single message's score means very little
on its own.

Score interpretation:
    score > 0   -> net "positive/calm" language
    score == 0  -> neutral / no signal
    score < 0   -> net "stress-indicative" language

The score is simply (positive_hits - stress_hits) normalized by word count,
clipped to [-1, 1]. Repeated stress words in one message (e.g. "fix fix fix")
count multiple times, which is intentional -- repetition/frustration is
itself part of the signal this tool is looking for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Hand-built, intentionally small and documented. Extend with care; every
# addition changes historical trend comparisons.
STRESS_WORDS = {
    "urgent",
    "asap",
    "hotfix",
    "revert",
    "reverted",
    "reverting",
    "sorry",
    "apologies",
    "oops",
    "ugh",
    "argh",
    "broken",
    "breaking",
    "critical",
    "emergency",
    "panic",
    "crash",
    "crashing",
    "outage",
    "down",
    "fail",
    "failing",
    "failed",
    "blocked",
    "blocker",
    "stuck",
    "frustrat",  # matches frustrated/frustrating via substring pass below
    "annoying",
    "nightmare",
    "mess",
    "hack",
    "hacky",
    "workaround",
    "temporary fix",
    "quick fix",
    "wtf",
    "damn",
    "ugh.",
}

# Neutral/positive markers -- deliberately conservative, everyday engineering
# vocabulary that signals calm, incremental, planned work.
POSITIVE_WORDS = {
    "add",
    "adds",
    "added",
    "improve",
    "improved",
    "improvement",
    "refactor",
    "refactored",
    "clean",
    "cleanup",
    "docs",
    "documentation",
    "test",
    "tests",
    "tested",
    "update",
    "updated",
    "upgrade",
    "upgraded",
    "feature",
    "implement",
    "implemented",
    "thanks",
    "thank you",
    "nice",
    "great",
    "lgtm",
    "polish",
    "polished",
}

_WORD_RE = re.compile(r"[a-zA-Z']+")


@dataclass(frozen=True)
class LexiconResult:
    stress_hits: int
    positive_hits: int
    word_count: int
    score: float  # in [-1, 1]

    @property
    def is_stress_indicative(self) -> bool:
        return self.score < 0


def _tokenize(text: str):
    return _WORD_RE.findall(text.lower())


def score_text(text: str) -> LexiconResult:
    """Score a single short text (e.g. one commit subject or comment body)."""
    if not text or not text.strip():
        return LexiconResult(stress_hits=0, positive_hits=0, word_count=0, score=0.0)

    lowered = text.lower()
    tokens = _tokenize(text)
    word_count = len(tokens) or 1

    stress_hits = 0
    for word in STRESS_WORDS:
        if " " in word:
            stress_hits += lowered.count(word)
        else:
            stress_hits += sum(1 for t in tokens if word in t)

    positive_hits = 0
    for word in POSITIVE_WORDS:
        if " " in word:
            positive_hits += lowered.count(word)
        else:
            positive_hits += sum(1 for t in tokens if t == word)

    raw = (positive_hits - stress_hits) / word_count
    score = max(-1.0, min(1.0, raw))
    return LexiconResult(
        stress_hits=stress_hits,
        positive_hits=positive_hits,
        word_count=word_count,
        score=score,
    )


def average_score(texts) -> float:
    """Mean lexicon score across a collection of texts. 0.0 if empty."""
    texts = list(texts)
    if not texts:
        return 0.0
    total = sum(score_text(t).score for t in texts)
    return total / len(texts)


def average_length(texts) -> float:
    """Mean character length across texts (terseness trend signal). 0.0 if empty."""
    texts = list(texts)
    if not texts:
        return 0.0
    return sum(len(t) for t in texts) / len(texts)
