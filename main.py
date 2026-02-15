#!/usr/bin/env python3
"""QQ 群舆情自动监控与分析脚本

Usage:
    python main.py                  # 使用环境变量 / 默认配置
    python main.py --groups 123,456 # 指定群号
    python main.py --once           # 单次拉取分析，不循环
"""

import argparse
import logging
import sys

from qq_sentiment.config import Config
from qq_sentiment.onebot_client import OneBotClient
from qq_sentiment.sentiment import SentimentAnalyzer
from qq_sentiment.report import generate_text_report, save_report
from qq_sentiment.monitor import run


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _run_once(config: Config) -> None:
    """Single-shot: fetch messages from all groups, analyze, and exit."""
    client = OneBotClient(config.onebot_http_url, config.onebot_access_token)
    analyzer = SentimentAnalyzer(
        negative_threshold=config.negative_threshold,
        positive_threshold=config.positive_threshold,
        alert_negative_ratio=config.alert_negative_ratio,
        alert_keywords=config.alert_keywords,
    )

    for gid in config.group_ids:
        messages = client.get_group_msg_history(gid, count=config.fetch_limit)
        if not messages:
            print(f"群 {gid}: 无消息")
            continue
        report = analyzer.analyze_batch(gid, messages)
        print(generate_text_report(report))
        save_report(report, config.report_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="QQ 群舆情自动监控与分析")
    parser.add_argument(
        "--groups",
        type=str,
        default="",
        help="Comma-separated group IDs (overrides GROUP_IDS env var)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once then exit (no polling loop)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="Polling interval in seconds (overrides POLL_INTERVAL env var)",
    )
    parser.add_argument(
        "--url",
        type=str,
        default="",
        help="OneBot HTTP URL (overrides ONEBOT_HTTP_URL env var)",
    )
    args = parser.parse_args()

    config = Config()

    # CLI overrides
    if args.groups:
        config.group_ids = [int(g.strip()) for g in args.groups.split(",") if g.strip()]
    if args.interval:
        config.poll_interval = args.interval
    if args.url:
        config.onebot_http_url = args.url

    _setup_logging(config.log_level)

    if not config.group_ids:
        print("错误: 请通过 --groups 或 GROUP_IDS 环境变量指定要监控的群号", file=sys.stderr)
        sys.exit(1)

    if args.once:
        _run_once(config)
    else:
        run(config)


if __name__ == "__main__":
    main()
