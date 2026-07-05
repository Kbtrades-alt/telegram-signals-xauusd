"""
Connectivity check for the free (GitHub Actions + Twelve Data) deployment
path. Confirms the data feed and Telegram delivery both work end-to-end.

NOT a trading signal - Modules 3-4 (feature engine, scoring engine) aren't
wired in yet. This script exists so the infrastructure (secrets, workflow,
Telegram chat) can be verified working today, on your phone, before the
actual signal logic lands. Once Module 4 exists, main.py replaces this as
the workflow's entry point - nothing about the workflow YAML changes.

Run manually via the Actions tab -> this workflow -> "Run workflow", or
let the schedule fire it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import TelegramConfig, TwelveDataConfig, settings  # noqa: E402
from data.twelvedata_client import TwelveDataClient  # noqa: E402
from telegram_bot.sender import TelegramSender  # noqa: E402
from utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)


def main() -> None:
    data_client = TwelveDataClient(TwelveDataConfig())
    telegram = TelegramSender(TelegramConfig())

    instrument = settings.instruments[0].value
    tick = data_client.get_current_tick(instrument)

    message = (
        f"\u2705 <b>Bot online</b>\n\n"
        f"{instrument} latest: {tick['bid']:.2f}\n"
        f"Primary timeframe: {settings.primary_timeframe}\n"
        f"Checked: {tick['time'].strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        f"<i>Connectivity heartbeat only - the scoring engine isn't wired in "
        f"yet, so this is not a trade signal.</i>"
    )
    telegram.send_text(message)
    logger.info("Heartbeat sent: %s @ %s", instrument, tick["bid"])


if __name__ == "__main__":
    main()
