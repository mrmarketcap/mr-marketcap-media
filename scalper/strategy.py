"""Scalping strategy (long + short): EMA crossover + RSI filter + ATR-based stop/target.

Pure functions, no I/O, so the same code runs in backtest, paper and live.
Candle = [timestamp_ms, open, high, low, close, volume]  (ccxt format)
"""
from dataclasses import dataclass
from typing import List, Optional


def ema(values: List[float], period: int) -> List[float]:
    k = 2 / (period + 1)
    out, prev = [], None
    for v in values:
        prev = v if prev is None else v * k + prev * (1 - k)
        out.append(prev)
    return out


def rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    ag, al = gains / period, losses / period
    out[period] = 100 - 100 / (1 + ag / al) if al else 100.0
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (period - 1) + max(d, 0)) / period
        al = (al * (period - 1) + max(-d, 0)) / period
        out[i] = 100 - 100 / (1 + ag / al) if al else 100.0
    return out


def atr(candles: List[list], period: int = 14) -> List[Optional[float]]:
    trs = []
    for i, c in enumerate(candles):
        if i == 0:
            trs.append(c[2] - c[3])
        else:
            pc = candles[i - 1][4]
            trs.append(max(c[2] - c[3], abs(c[2] - pc), abs(c[3] - pc)))
    out: List[Optional[float]] = [None] * len(candles)
    if len(candles) < period:
        return out
    a = sum(trs[:period]) / period
    out[period - 1] = a
    for i in range(period, len(candles)):
        a = (a * (period - 1) + trs[i]) / period
        out[i] = a
    return out


@dataclass
class Params:
    fast: int = 9
    slow: int = 21
    trend: int = 100          # فقط در جهت روند بزرگتر وارد شو
    rsi_period: int = 14
    rsi_min: float = 50.0     # مومنتوم صعودی
    rsi_max: float = 72.0     # وارد اوج اشباع نشو
    atr_period: int = 14
    sl_atr: float = 1.0
    tp_atr: float = 1.6
    min_atr_pct: float = 0.0008  # اگر نوسان خیلی کم باشد کارمزد سود را می‌خورد


@dataclass
class Signal:
    side: str  # "long" | "short"
    entry: float
    stop: float
    target: float


def entry_signal(candles: List[list], p: Params = Params()) -> Optional[Signal]:
    """Long/short signal evaluated on the last CLOSED candle (candles[-1])."""
    n = len(candles)
    if n < max(p.trend, p.slow, p.rsi_period, p.atr_period) + 3:
        return None
    closes = [c[4] for c in candles]
    f, s, t = ema(closes, p.fast), ema(closes, p.slow), ema(closes, p.trend)
    r, a = rsi(closes, p.rsi_period)[-1], atr(candles, p.atr_period)[-1]
    if r is None or a is None:
        return None
    price = closes[-1]
    if a / price < p.min_atr_pct:
        return None
    if f[-2] <= s[-2] and f[-1] > s[-1] and price > t[-1] and p.rsi_min <= r <= p.rsi_max:
        return Signal("long", price, price - p.sl_atr * a, price + p.tp_atr * a)
    if f[-2] >= s[-2] and f[-1] < s[-1] and price < t[-1] and 100 - p.rsi_max <= r <= 100 - p.rsi_min:
        return Signal("short", price, price + p.sl_atr * a, price - p.tp_atr * a)
    return None
