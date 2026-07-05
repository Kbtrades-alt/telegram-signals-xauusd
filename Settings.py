"""
Central configuration for the XAUUSD signal bot.

Design principle: every numeric threshold below is a STARTING DEFAULT, not a
finding. None of them are backtested yet - that happens in Module 7 (walk-forward
/ Monte Carlo / sensitivity validation). Nothing here should be read as "the edge" -
it's the scaffolding the edge gets measured against. Values get overwritten with
validated numbers once that suite runs against real historical data.

Fails fast and loud on missing credentials (MT5 / Telegram) rather than letting
a half-configured bot run silently on a VPS and drop signals later.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from core.enums import Instrument

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _require_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Missing required environment variable: {key}. "
            f"Copy .env.example to .env in {BASE_DIR} and fill it in."
        )
    return value


@dataclass(frozen=True)
class MT5Config:
    login: int = field(default_factory=lambda: int(_require_env("MT5_LOGIN")))
    password: str = field(default_factory=lambda: _require_env("MT5_PASSWORD"))
    server: str = field(default_factory=lambda: _require_env("MT5_SERVER"))
    # Optional - only needed if the terminal isn't already running under this user session
    terminal_path: str = field(default_factory=lambda: os.getenv("MT5_TERMINAL_PATH", ""))


@dataclass(frozen=True)
class TwelveDataConfig:
    """Free-tier REST data source - no VPS, no broker terminal required."""
    api_key: str = field(default_factory=lambda: _require_env("TWELVEDATA_API_KEY"))


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str = field(default_factory=lambda: _require_env("TELEGRAM_BOT_TOKEN"))
    chat_id: str = field(default_factory=lambda: _require_env("TELEGRAM_CHAT_ID"))


@dataclass(frozen=True)
class SessionWindows:
    """
    UTC hour boundaries [start, end). These are the commonly cited institutional
    session windows - treat as a prior, not ground truth. Module 7 recomputes
    actual realized-volatility-by-hour from your broker's own tick timestamps,
    and these get replaced with instrument-specific numbers at that point.
    """
    asia_start: int = 0
    asia_end: int = 7
    london_open_start: int = 7
    london_open_end: int = 12
    overlap_start: int = 12
    overlap_end: int = 16
    ny_afternoon_start: int = 16
    ny_afternoon_end: int = 21
    # 21:00-24:00 UTC falls through to Off Hours in the session classifier


@dataclass(frozen=True)
class RegimeThresholds:
    adx_trend_floor: float = 22.0          # ADX(H1) above this -> trend sub-models eligible
    atr_percentile_floor: float = 30.0     # below this percentile -> breakout signals suppressed (chop)
    atr_percentile_ceiling: float = 95.0   # above this -> likely news-spike/illiquid, suppress new entries
    # Bar count, not time - scale this when primary_timeframe changes. 300 M5
    # bars = ~25h, matching what 100 M15 bars covered. Keeping bar count fixed
    # across a timeframe change would quietly shrink the lookback window to a
    # third of its intended real-time span, which changes what "30th
    # percentile" even means. adx_trend_floor itself still needs independent
    # M5 validation in Module 7 - M5 ADX is inherently noisier than M15 ADX,
    # and nothing here assumes 22.0 is equally selective at both resolutions.
    atr_lookback_bars: int = 300


@dataclass(frozen=True)
class RiskDefaults:
    min_risk_reward: float = 1.5           # signals below this R:R are discarded outright, no exceptions
    atr_period: int = 14
    atr_stop_multiplier: float = 1.2       # initial SL distance = ATR(14) * this, before structure adjustment


@dataclass(frozen=True)
class ConfidenceThresholds:
    """
    Governs the "3 quality signals/day, never forced" requirement.
    publish_floor is an absolute hard floor validated in Module 7 - the taper
    mechanism (Module 4) is never allowed to cross it, regardless of how far
    behind the daily signal count falls.
    """
    publish_floor: float = 78.0
    target_floor: float = 82.0             # normal operating floor
    taper_step: float = 1.0                # points shaved off target_floor per adjustment cycle
    max_taper: float = 4.0                 # floor can never taper below (target_floor - max_taper)
    target_signals_per_day: float = 3.0    # monitored KPI, not a quota


@dataclass(frozen=True)
class Settings:
    instruments: List[Instrument] = field(
        # Start with XAUUSD only. Add NAS100/US30/EURUSD/GBPUSD after the
        # scoring weights are validated per-instrument in Module 7 - a weight
        # set tuned on gold is not assumed to transfer to indices or majors.
        default_factory=lambda: [Instrument.XAUUSD]
    )
    # "mt5" (live VPS + broker terminal) or "twelvedata" (free REST API,
    # zero infrastructure - GitHub Actions can run the whole loop). The two
    # data clients implement the same MarketDataClient interface (data/base.py)
    # so nothing downstream of the data layer cares which one is active.
    data_source: str = field(default_factory=lambda: os.getenv("DATA_SOURCE", "mt5").lower())
    # Explicit broker symbol overrides, e.g. {"XAUUSD": "XAUUSD-ECN"}.
    # VT Markets suffixes by account type (-STD/-ECN/-VIP), and more than one
    # variant can be visible in Market Watch at once - fuzzy-matching in
    # MT5Client.resolve_symbol() is a fallback, not a substitute for setting
    # this once you've confirmed the exact tradable symbol for your account.
    symbol_overrides: dict = field(default_factory=dict)
    primary_timeframe: str = "M5"
    # H1, not H4 - M15->H4 was a 16x zoom gap for HTF bias. Keeping H4 against
    # an M5 primary would stretch that to 48x, which weakens H4's relevance
    # as an immediate bias filter for entries this short. H1 keeps the ratio
    # (12x) close to what it was, so the HTF filter still means roughly the
    # same thing it did before the timeframe change.
    htf_timeframe: str = "H1"
    poll_interval_seconds: int = 60
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    environment: str = os.getenv("ENVIRONMENT", "development")

    # Telegram is required regardless of data source - the whole point of the
    # bot is delivering there. MT5/TwelveData credentials are deliberately
    # NOT loaded here - only whichever one data_source actually selects gets
    # required, via the factory methods below, so importing settings never
    # demands credentials for infrastructure you're not using.
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    sessions: SessionWindows = field(default_factory=SessionWindows)
    regime: RegimeThresholds = field(default_factory=RegimeThresholds)
    risk: RiskDefaults = field(default_factory=RiskDefaults)
    confidence: ConfidenceThresholds = field(default_factory=ConfidenceThresholds)

    @staticmethod
    def mt5_config() -> MT5Config:
        return MT5Config()

    @staticmethod
    def twelvedata_config() -> TwelveDataConfig:
        return TwelveDataConfig()


settings = Settings()
