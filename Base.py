"""
Common interface every market data source implements. The feature engine
(Module 3) and everything after it consumes this interface, never a specific
client - so swapping MT5 for Twelve Data (or adding a third source later)
never requires touching the signal engine, risk engine, or Telegram layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd


class MarketDataClient(ABC):
    @abstractmethod
    def fetch_latest_bars(self, base_symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        """
        Most recent `count` bars, oldest first.
        Columns: time (UTC datetime), open, high, low, close, tick_volume, spread.
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_historical_range(
        self, base_symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Same columns as fetch_latest_bars - used by the Module 7 validation suite."""
        raise NotImplementedError

    @abstractmethod
    def get_current_tick(self, base_symbol: str) -> dict:
        """Returns {'bid': float, 'ask': float, 'time': datetime (UTC)}."""
        raise NotImplementedError
