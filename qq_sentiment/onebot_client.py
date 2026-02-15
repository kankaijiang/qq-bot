"""OneBot v11 HTTP API client for fetching QQ group messages."""

import logging
import time
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class GroupMessage:
    """A single message from a QQ group."""
    message_id: int
    group_id: int
    user_id: int
    nickname: str
    text: str
    timestamp: int


class OneBotClient:
    """Minimal OneBot v11 HTTP client focused on reading group messages."""

    def __init__(self, base_url: str, access_token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if access_token:
            self.session.headers["Authorization"] = f"Bearer {access_token}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_group_list(self) -> list[dict]:
        """Return the list of groups the bot has joined."""
        return self._call("get_group_list")

    def get_group_member_list(self, group_id: int) -> list[dict]:
        """Return member list for a group."""
        return self._call("get_group_member_list", group_id=group_id)

    def get_group_msg_history(
        self, group_id: int, message_seq: int | None = None, count: int = 50
    ) -> list[GroupMessage]:
        """Fetch recent messages from a group.

        Args:
            group_id: Target group.
            message_seq: Start from this sequence number. ``None`` fetches
                the most recent messages.
            count: Maximum number of messages to retrieve.

        Returns:
            List of ``GroupMessage`` objects sorted by timestamp ascending.
        """
        params: dict = {"group_id": group_id, "count": count}
        if message_seq is not None:
            params["message_seq"] = message_seq

        data = self._call("get_group_msg_history", **params)
        if not data:
            return []

        # API returns {"messages": [...]} or directly a list
        if isinstance(data, dict):
            raw_messages = data.get("messages", [])
        elif isinstance(data, list):
            raw_messages = data
        else:
            return []

        if not raw_messages:
            return []

        results: list[GroupMessage] = []
        for msg in raw_messages:
            text = self._extract_text(msg)
            if not text.strip():
                continue
            results.append(
                GroupMessage(
                    message_id=msg.get("message_id", 0),
                    group_id=group_id,
                    user_id=msg.get("user_id", 0),
                    nickname=msg.get("sender", {}).get("nickname", ""),
                    text=text,
                    timestamp=msg.get("time", int(time.time())),
                )
            )
        results.sort(key=lambda m: m.timestamp)
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call(self, action: str, **params):
        """Call an OneBot action and return the ``data`` field."""
        url = f"{self.base_url}/{action}"
        try:
            resp = self.session.post(url, json=params, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("OneBot API request failed for %s: %s", action, exc)
            return []

        body = resp.json()
        if body.get("retcode") != 0:
            logger.warning(
                "OneBot action %s returned retcode=%s msg=%s",
                action,
                body.get("retcode"),
                body.get("msg"),
            )
            return []
        return body.get("data", [])

    @staticmethod
    def _extract_text(msg: dict) -> str:
        """Extract plain-text content from an OneBot message object.

        OneBot messages consist of CQ-code segments. We only care about
        ``type=text`` segments for sentiment analysis.
        """
        message_field = msg.get("message", [])

        # Some implementations return a plain string instead of segments
        if isinstance(message_field, str):
            return message_field

        parts: list[str] = []
        for seg in message_field:
            if seg.get("type") == "text":
                parts.append(seg.get("data", {}).get("text", ""))
        return "".join(parts)
