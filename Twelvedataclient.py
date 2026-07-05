"""
Twelve Data REST client - the free-tier, zero-infrastructure data source.
No VPS, no broker terminal, no Windows host - just an API key. Implements
the same MarketDataClient interface as data/mt5_client.py, so the feature
and signal engines don't change based on which one is active.

Trade-offs vs the MT5 path, stated plainly (see config.settings.data_source):
- Prices come from Twelve Data's aggregated feed, not your broker's own book.
  Expect small discrepancies vs your broker's live quote - fine for planning
  entries, not for tick-level execution.
- No true bid/ask spread from this endpoint - get_current_tick() returns the
  same value for both. Don't treat this feed's "spread" as real.
- This feed doesn't provide genuine tick volume either - zeroed rather than
  fabricated, so volume-weighted scoring components stay honest about not
  having real data to work with on this path.
- Free tier is rate-limited. This client backs off on errors/429s but a poll
  can still fail outright - the orchestrator (Module 8) has to tolerate a
  missed cycle without crashing.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, Optional

import pandas as pd
import requests

from config.settings import TwelveDataConfig
from data.base import MarketDataClient
from utils.logger import get_logger

logger = get_logger(__name__)

BASE_URL = "https://api.twelvedata.com"

INTERVAL_MAP = {
    "M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
    "H1": "1h", "H4": "4h", "D1": "1day",
}

# Base instrument -> Twelve Data symbol format. Verified for gold/silver/FX
# majors. NAS100/US30 need confirming against your plan's index coverage
# before they're added to config.instruments on this data source.
DEFAULT_SYMBOL_MAP = {
    "XAUUSD": "XAU/USD",
    "XAGUSD": "XAG/USD",
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
}


class TwelveDataError(RuntimeError):
    """Raised on any non-'ok' response, missing data, or exhausted retries."""


class TwelveDataClient(MarketDataClient):
    def __init__(
        self,
        config: TwelveDataConfig,
        symbol_map: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
        retry_backoff_seconds: float = 5.0,
    ):
        self._api_key = config.api_key
        self._symbol_map = {**DEFAULT_SYMBOL_MAP, **(symbol_map or {})}
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff_seconds
        self._session = requests.Session()

    def _resolve_symbol(self, base_symbol: str) -> str:
        try:
            return self._symbol_map[base_symbol]
        except KeyError:
            raise TwelveDataError(
                f"No Twelve Data symbol mapping for '{base_symbol}'. "
                f"Pass symbol_map={{'{base_symbol}': 'PROVIDER/FORMAT'}} to the constructor."
            )

    def _get(self, path: str, params: dict) -> dict:
        params = {**params, "apikey": self._api_key}
        last_error = None
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = self._session.get(f"{BASE_URL}/{path}", params=params, timeout=15)
                data = resp.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = str(exc)
                logger.warning(
                    "Twelve Data request failed (attempt %d/%d): %s",
                    attempt, self._max_retries, last_error,
                )
                time.sleep(self._retry_backoff * attempt)
                continue

            if isinstance(data, dict) and data.get("status") == "error":
                last_error = data.get("message", "unknown error")
                rate_limited = resp.status_code == 429 or "limit" in str(last_error).lower()
                if rate_limited and attempt < self._max_retries:
                    logger.warning(
                        "Twelve Data rate limited (attempt %d/%d): %s",
                        attempt, self._max_retries, last_error,
                    )
                    time.sleep(self._retry_backoff * attempt)
                    continue
                raise TwelveDataError(f"Twelve Data API error: {last_error}")

            return data

        raise TwelveDataError(f"Twelve Data request failed after {self._max_retries} attempts: {last_error}")

    def fetch_latest_bars(self, base_symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        symbol = self._resolve_symbol(base_symbol)
        interval = self._interval(timeframe)
        data = self._get("time_series", {
            "symbol": symbol, "interval": interval, "outputsize": count, "timezone": "UTC",
        })
        values = data.get("values")
        if not values:
            raise TwelveDataError(f"No bars returned for {symbol} {timeframe}: {data}")
        return self._values_to_df(values)

    def fetch_historical_range(
        self, base_symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> pd.DataFrame:
        symbol = self._resolve_symbol(base_symbol)
        interval = self._interval(timeframe)
        data = self._get("time_series", {
            "symbol": symbol, "interval": interval, "timezone": "UTC",
            "start_date": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end_date": end.strftime("%Y-%m-%d %H:%M:%S"),
            "outputsize": 5000,
        })
        values = data.get("values")
        if not values:
            raise TwelveDataError(
                f"No historical bars for {symbol} {timeframe} between {start} and {end}: {data}"
            )
        return self._values_to_df(values)

    def get_current_tick(self, base_symbol: str) -> dict:
        symbol = self._resolve_symbol(base_symbol)
        data = self._get("price", {"symbol": symbol})
        if "price" not in data:
            raise TwelveDataError(f"No price returned for {symbol}: {data}")
        price = float(data["price"])
        # No true bid/ask on this endpoint - both set to the same mid price.
        return {"bid": price, "ask": price, "time": datetime.now(timezone.utc)}

    @staticmethod
    def _interval(timeframe: str) -> str:
        try:
            return INTERVAL_MAP[timeframe]
        except KeyError:
            raise ValueError(f"Unsupported timeframe '{timeframe}'. Valid: {list(INTERVAL_MAP)}")

    @staticmethod
    def _values_to_df(values: list) -> pd.DataFrame:
        df = pd.DataFrame(values)
        df["time"] = pd.to_datetime(df["datetime"], utc=True)
        for col in ("open", "high", "low", "close"):
            df[col] = df[col].astype(float)
        df["tick_volume"] = df["volume"].astype(float) if "volume" in df.columns else 0.0
        df["spread"] = 0
        df = df.sort_values("time").reset_index(drop=True)
        return df[["time", "open", "high", "low", "close", "tick_volume", "spread"]]
