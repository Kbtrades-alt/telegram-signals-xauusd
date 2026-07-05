"""
Shared enumerations used across the signal engine, risk engine, and Telegram layer.
Centralising these avoids magic strings drifting out of sync between modules.
"""

from enum import Enum


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class MarketRegime(str, Enum):
    TRENDING = "Trending"
    RANGING = "Ranging"
    VOLATILE_BREAKOUT = "Volatile Breakout"
    ILLIQUID = "Illiquid / Low Quality"


class SessionWindow(str, Enum):
    ASIA = "Asia"
    LONDON_OPEN = "London Open"
    LONDON_NY_OVERLAP = "London/NY Overlap"
    NY_AFTERNOON = "NY Afternoon"
    OFF_HOURS = "Off Hours"


class Instrument(str, Enum):
    XAUUSD = "XAUUSD"
    NAS100 = "NAS100"
    US30 = "US30"
    EURUSD = "EURUSD"
    GBPUSD = "GBPUSD"
