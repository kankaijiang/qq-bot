"""Sentiment analysis engine combining SnowNLP scoring and keyword detection."""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum

from snownlp import SnowNLP

from .onebot_client import GroupMessage

logger = logging.getLogger(__name__)


class Sentiment(Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass
class AnalysisResult:
    """Analysis result for a single message."""
    message: GroupMessage
    score: float  # 0.0 (very negative) ~ 1.0 (very positive)
    sentiment: Sentiment
    matched_keywords: list[str] = field(default_factory=list)


@dataclass
class GroupReport:
    """Aggregated sentiment report for one group over a time window."""
    group_id: int
    start_ts: int
    end_ts: int
    total_messages: int
    positive_count: int
    neutral_count: int
    negative_count: int
    avg_score: float
    keyword_hits: dict[str, int]  # keyword -> occurrence count
    top_negative: list[AnalysisResult]  # most negative messages
    top_positive: list[AnalysisResult]  # most positive messages
    alert: bool  # True if negative ratio exceeds threshold


class SentimentAnalyzer:
    """Analyze sentiment of QQ group messages."""

    def __init__(
        self,
        negative_threshold: float = 0.3,
        positive_threshold: float = 0.7,
        alert_negative_ratio: float = 0.4,
        alert_keywords: list[str] | None = None,
    ):
        self.neg_thresh = negative_threshold
        self.pos_thresh = positive_threshold
        self.alert_ratio = alert_negative_ratio
        self.keywords = alert_keywords or []
        # Pre-compile keyword patterns for performance
        self._kw_patterns = {
            kw: re.compile(re.escape(kw), re.IGNORECASE) for kw in self.keywords
        }

    def analyze_message(self, msg: GroupMessage) -> AnalysisResult:
        """Score a single message and detect keyword hits."""
        text = msg.text.strip()
        if not text:
            return AnalysisResult(
                message=msg, score=0.5, sentiment=Sentiment.NEUTRAL
            )

        try:
            score = SnowNLP(text).sentiments
        except Exception:
            logger.debug("SnowNLP failed on: %s", text[:80])
            score = 0.5

        if score < self.neg_thresh:
            sentiment = Sentiment.NEGATIVE
        elif score > self.pos_thresh:
            sentiment = Sentiment.POSITIVE
        else:
            sentiment = Sentiment.NEUTRAL

        matched = [kw for kw, pat in self._kw_patterns.items() if pat.search(text)]

        return AnalysisResult(
            message=msg,
            score=score,
            sentiment=sentiment,
            matched_keywords=matched,
        )

    def analyze_batch(
        self, group_id: int, messages: list[GroupMessage]
    ) -> GroupReport:
        """Analyze a batch of messages and produce an aggregated report."""
        results = [self.analyze_message(m) for m in messages]

        positive = [r for r in results if r.sentiment == Sentiment.POSITIVE]
        neutral = [r for r in results if r.sentiment == Sentiment.NEUTRAL]
        negative = [r for r in results if r.sentiment == Sentiment.NEGATIVE]

        total = len(results)
        avg_score = sum(r.score for r in results) / total if total else 0.5

        # Keyword occurrence counter
        kw_hits: dict[str, int] = {}
        for r in results:
            for kw in r.matched_keywords:
                kw_hits[kw] = kw_hits.get(kw, 0) + 1

        # Determine alert status
        neg_ratio = len(negative) / total if total else 0.0
        alert = neg_ratio >= self.alert_ratio or bool(kw_hits)

        # Timestamps
        timestamps = [m.timestamp for m in messages]
        start_ts = min(timestamps) if timestamps else 0
        end_ts = max(timestamps) if timestamps else 0

        # Top negative / positive (up to 5)
        negative_sorted = sorted(negative, key=lambda r: r.score)
        positive_sorted = sorted(positive, key=lambda r: r.score, reverse=True)

        return GroupReport(
            group_id=group_id,
            start_ts=start_ts,
            end_ts=end_ts,
            total_messages=total,
            positive_count=len(positive),
            neutral_count=len(neutral),
            negative_count=len(negative),
            avg_score=round(avg_score, 4),
            keyword_hits=kw_hits,
            top_negative=negative_sorted[:5],
            top_positive=positive_sorted[:5],
            alert=alert,
        )
