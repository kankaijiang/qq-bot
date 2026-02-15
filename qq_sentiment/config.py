"""Configuration for QQ group sentiment monitoring."""

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    # OneBot HTTP API settings
    onebot_http_url: str = os.getenv("ONEBOT_HTTP_URL", "http://127.0.0.1:5700")
    onebot_access_token: str = os.getenv("ONEBOT_ACCESS_TOKEN", "")

    # QQ group IDs to monitor (comma-separated in env var)
    group_ids: list[int] = field(default_factory=list)

    # Monitoring interval in seconds
    poll_interval: int = int(os.getenv("POLL_INTERVAL", "60"))

    # How many messages to fetch per poll (OneBot get_group_msg_history limit)
    fetch_limit: int = int(os.getenv("FETCH_LIMIT", "50"))

    # Sentiment thresholds
    negative_threshold: float = float(os.getenv("NEGATIVE_THRESHOLD", "0.3"))
    positive_threshold: float = float(os.getenv("POSITIVE_THRESHOLD", "0.7"))

    # Alert settings: trigger alert if negative ratio exceeds this
    alert_negative_ratio: float = float(os.getenv("ALERT_NEGATIVE_RATIO", "0.4"))

    # Report output directory
    report_dir: str = os.getenv("REPORT_DIR", "reports")

    # Keyword watchlist (comma-separated in env var)
    alert_keywords: list[str] = field(default_factory=list)

    # Log level
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def __post_init__(self):
        if not self.group_ids:
            raw = os.getenv("GROUP_IDS", "")
            self.group_ids = [int(g.strip()) for g in raw.split(",") if g.strip()]

        if not self.alert_keywords:
            raw = os.getenv("ALERT_KEYWORDS", "")
            self.alert_keywords = [k.strip() for k in raw.split(",") if k.strip()]
