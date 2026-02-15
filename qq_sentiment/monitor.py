"""Main monitoring loop — polls groups and produces reports on schedule."""

import logging
import signal
import sys
import time

from .config import Config
from .onebot_client import OneBotClient
from .sentiment import SentimentAnalyzer
from .report import generate_text_report, save_report

logger = logging.getLogger(__name__)

# Track the latest message_seq per group so we don't re-analyze old messages
_last_seq: dict[int, int] = {}

_running = True


def _handle_signal(signum, _frame):
    global _running
    logger.info("Received signal %s, shutting down…", signum)
    _running = False


def run(config: Config) -> None:
    """Entry-point: run the polling loop until interrupted."""
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if not config.group_ids:
        logger.error("No GROUP_IDS configured. Exiting.")
        sys.exit(1)

    client = OneBotClient(config.onebot_http_url, config.onebot_access_token)
    analyzer = SentimentAnalyzer(
        negative_threshold=config.negative_threshold,
        positive_threshold=config.positive_threshold,
        alert_negative_ratio=config.alert_negative_ratio,
        alert_keywords=config.alert_keywords,
    )

    logger.info(
        "Starting sentiment monitor — groups=%s  interval=%ds",
        config.group_ids,
        config.poll_interval,
    )

    while _running:
        for gid in config.group_ids:
            _poll_group(gid, client, analyzer, config)
        _sleep(config.poll_interval)

    logger.info("Monitor stopped.")


def _poll_group(
    group_id: int,
    client: OneBotClient,
    analyzer: SentimentAnalyzer,
    config: Config,
) -> None:
    """Fetch new messages for one group, analyze, and save report."""
    seq = _last_seq.get(group_id)
    messages = client.get_group_msg_history(
        group_id, message_seq=seq, count=config.fetch_limit
    )

    if not messages:
        logger.debug("Group %s: no new messages.", group_id)
        return

    # Update sequence bookmark
    _last_seq[group_id] = messages[-1].message_id

    logger.info("Group %s: fetched %d messages.", group_id, len(messages))

    report = analyzer.analyze_batch(group_id, messages)

    # Print summary to console
    print(generate_text_report(report))

    # Persist reports
    txt_path, html_path = save_report(report, config.report_dir)

    if report.alert:
        logger.warning(
            "⚠ ALERT for group %s — negative ratio %.1f%%, keyword hits: %s",
            group_id,
            report.negative_count / report.total_messages * 100
            if report.total_messages
            else 0,
            report.keyword_hits,
        )


def _sleep(seconds: int) -> None:
    """Interruptible sleep."""
    end = time.monotonic() + seconds
    while _running and time.monotonic() < end:
        time.sleep(1)
