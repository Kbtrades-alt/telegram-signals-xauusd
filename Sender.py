"""
Telegram delivery layer. Takes a fully-formed, already-validated Signal
(core.models.Signal) and posts it to the configured chat using the raw
Bot API - no wrapper library, one HTTP call, trivial to run inside a
GitHub Actions job with no persistent process behind it.
"""

from __future__ import annotations

import time

import requests

from config.settings import TelegramConfig
from core.models import Signal
from utils.logger import get_logger

logger = get_logger(__name__)

API_BASE = "https://api.telegram.org"

DIRECTION_EMOJI = {"BUY": "🚀", "SELL": "🔻"}


class TelegramDeliveryError(RuntimeError):
    """Raised when a message can't be delivered after all retries are exhausted."""


class TelegramSender:
    def __init__(self, config: TelegramConfig, max_retries: int = 3, retry_backoff_seconds: float = 3.0):
        self._token = config.bot_token
        self._chat_id = config.chat_id
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff_seconds
        self._session = requests.Session()

    def send_signal(self, signal: Signal) -> None:
        """The main entry point once Module 4 is producing real signals."""
        signal.validate()  # never publish a malformed signal, even if upstream forgot to check
        self._send_text(self._format_signal(signal))

    def send_text(self, text: str) -> None:
        """For heartbeats / operational alerts - bypasses Signal formatting entirely."""
        self._send_text(text)

    def _send_text(self, text: str) -> None:
        url = f"{API_BASE}/bot{self._token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        last_error = None
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = self._session.post(url, json=payload, timeout=10)
                body = resp.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = str(exc)
                logger.warning(
                    "Telegram send failed (attempt %d/%d): %s", attempt, self._max_retries, last_error
                )
                time.sleep(self._retry_backoff * attempt)
                continue

            if body.get("ok"):
                logger.info("Telegram message delivered (message_id=%s)", body["result"]["message_id"])
                return

            last_error = body.get("description", "unknown Telegram API error")
            if resp.status_code == 429:
                retry_after = body.get("parameters", {}).get("retry_after", self._retry_backoff * attempt)
                logger.warning("Telegram rate limited - retrying after %ss", retry_after)
                time.sleep(retry_after)
                continue

            # Bad token, chat not found, malformed request - won't fix itself on retry
            raise TelegramDeliveryError(f"Telegram API rejected message: {last_error}")

        raise TelegramDeliveryError(f"Telegram send failed after {self._max_retries} attempts: {last_error}")

    @staticmethod
    def _format_signal(signal: Signal) -> str:
        emoji = DIRECTION_EMOJI.get(signal.direction.value, "")
        ts = signal.generated_at.strftime("%Y-%m-%d %H:%M UTC")
        return (
            f"{emoji} <b>{signal.direction.value} {signal.instrument.value}</b>\n\n"
            f"Entry: {signal.entry:.2f}\n"
            f"Stop Loss: {signal.stop_loss:.2f}\n"
            f"Take Profit: {signal.take_profit:.2f}\n"
            f"Risk Reward: 1:{signal.risk_reward:.1f}\n"
            f"Confidence: {signal.confidence:.0f}%\n\n"
            f"Market Regime:\n{signal.regime.value}\n\n"
            f"Reason:\n{signal.reason}\n\n"
            f"Invalidation:\n{signal.invalidation}\n\n"
            f"<i>{ts}</i>"
        )
