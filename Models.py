"""
Shared data models passed between modules:
data collection -> feature engine -> signal engine -> risk engine -> telegram layer.

Keeping these as typed dataclasses (rather than raw dicts) is what lets every
downstream module fail loudly and early if an upstream module's contract changes,
instead of silently propagating a KeyError or a wrong sign three modules downstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.enums import Instrument, MarketRegime, SessionWindow, SignalDirection


@dataclass(frozen=True)
class Bar:
    """One OHLCV candle, as pulled from MT5."""
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int


@dataclass
class ScoreBreakdown:
    """
    Component scores (0-100 each) that make up the composite confidence score.
    Weights are applied in the signal engine (Module 4) - this class is just the
    raw, auditable evidence, kept separately so every published signal can show
    its work rather than a single opaque number.
    """
    regime_score: float
    trend_score: float
    momentum_score: float
    volatility_score: float
    structure_score: float
    session_score: float
    risk_reward_score: float

    def as_dict(self) -> dict:
        return {
            "regime": self.regime_score,
            "trend": self.trend_score,
            "momentum": self.momentum_score,
            "volatility": self.volatility_score,
            "structure": self.structure_score,
            "session": self.session_score,
            "risk_reward": self.risk_reward_score,
        }


@dataclass
class Signal:
    """
    A fully-formed, ready-to-publish trade signal. This is the single object
    that crosses from the signal/risk engines into the Telegram layer - nothing
    downstream of this class should need to touch raw indicator data.
    """
    instrument: Instrument
    direction: SignalDirection
    entry: float
    stop_loss: float
    take_profit: float
    confidence: float                  # 0-100, final composite score
    regime: MarketRegime
    session: SessionWindow
    reason: str
    invalidation: str
    score_breakdown: ScoreBreakdown
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def risk_reward(self) -> float:
        risk = abs(self.entry - self.stop_loss)
        reward = abs(self.take_profit - self.entry)
        return round(reward / risk, 2) if risk > 0 else 0.0

    def validate(self) -> None:
        """Fail loudly rather than publish a malformed signal to Telegram."""
        if self.direction == SignalDirection.BUY:
            if not (self.stop_loss < self.entry < self.take_profit):
                raise ValueError(
                    f"Invalid BUY levels: SL {self.stop_loss} / Entry {self.entry} / "
                    f"TP {self.take_profit}"
                )
        else:
            if not (self.take_profit < self.entry < self.stop_loss):
                raise ValueError(
                    f"Invalid SELL levels: TP {self.take_profit} / Entry {self.entry} / "
                    f"SL {self.stop_loss}"
                )
        if not (0.0 <= self.confidence <= 100.0):
            raise ValueError(f"Confidence out of bounds: {self.confidence}")
        if self.risk_reward <= 0:
            raise ValueError("Risk:Reward computed as non-positive - check SL/TP/entry.")
