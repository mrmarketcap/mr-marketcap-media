"""Backtest the strategy on historical candles, including fees and slippage.

  python backtest.py --symbol BTC/USDT --days 7
Conservative assumptions: stop is checked before target within the same candle.
"""
import argparse
import os
import ccxt
from strategy import Params, entry_signal
from risk import RiskManager


def fetch(ex, symbol, tf, days):
    ms = ex.parse_timeframe(tf) * 1000
    since = ex.milliseconds() - days * 86400_000
    out = []
    while since < ex.milliseconds():
        chunk = ex.fetch_ohlcv(symbol, tf, since=since, limit=1000)
        if not chunk:
            break
        out += chunk
        since = chunk[-1][0] + ms
        if len(chunk) < 1000:
            break
    return out


def run(candles, budget=100.0, fee=0.001, slip=0.0002, risk=0.005, p=Params()):
    rm = RiskManager(budget=budget, risk_per_trade=risk, cooldown_sec=0,
                     max_trades_per_day=10**9, max_daily_loss=10.0)
    equity, trades, peak, mdd, i = budget, [], budget, 0.0, 0
    warm = 130
    while i < len(candles) - 1:
        if i < warm:
            i += 1
            continue
        sig = entry_signal(candles[max(0, i - 400): i + 1], p)
        if not sig:
            i += 1
            continue
        entry = candles[i + 1][1] * (1 + slip)       # fill at next open
        stop, target = sig.stop - (sig.entry - entry), sig.target - (sig.entry - entry)
        qty = rm.size(entry, stop)
        exit_px, j = None, i + 1
        while j < len(candles):
            lo, hi = candles[j][3], candles[j][2]
            if lo <= stop:
                exit_px = stop * (1 - slip); break
            if hi >= target:
                exit_px = target * (1 - slip); break
            j += 1
        if exit_px is None:
            break
        pnl = qty * (exit_px - entry) - fee * qty * (entry + exit_px)
        equity += pnl
        peak = max(peak, equity); mdd = max(mdd, (peak - equity) / peak)
        trades.append(pnl)
        i = j + 1
    wins = [t for t in trades if t > 0]
    return dict(trades=len(trades), win_rate=len(wins) / len(trades) if trades else 0,
                net_pnl=equity - budget, return_pct=(equity / budget - 1) * 100,
                max_drawdown_pct=mdd * 100,
                profit_factor=(sum(wins) / -sum(t for t in trades if t < 0))
                if any(t < 0 for t in trades) and wins else float("inf") if wins else 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--exchange", default=os.getenv("EXCHANGE", "binance"))
    ap.add_argument("--symbol", default=os.getenv("SYMBOL", "BTC/USDT"))
    ap.add_argument("--timeframe", default="1m")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--fee", type=float, default=0.001)
    a = ap.parse_args()
    ex = getattr(ccxt, a.exchange)({"enableRateLimit": True})
    c = fetch(ex, a.symbol, a.timeframe, a.days)
    print(f"{len(c)} candles")
    for k, v in run(c, fee=a.fee).items():
        print(f"{k:>18}: {v:.4f}" if isinstance(v, float) else f"{k:>18}: {v}")
