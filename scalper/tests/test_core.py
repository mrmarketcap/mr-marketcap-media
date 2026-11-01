import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from strategy import ema, rsi, atr, entry_signal
from risk import RiskManager
from backtest import run


def synth(n=600):
    import math
    c, p = [], 100.0
    for i in range(n):
        p *= 1 + 0.0004 * math.sin(i / 7) + 0.0001
        c.append([i * 60000, p, p * 1.001, p * 0.999, p * (1 + 0.0003 * math.sin(i / 3)), 1])
    return c


def test_indicators():
    assert ema([1, 1, 1], 3) == [1, 1, 1]
    assert rsi(list(range(1, 40)))[-1] == 100.0
    assert atr(synth(50))[-1] > 0


def test_sizing_caps_risk_and_budget():
    rm = RiskManager(budget=1000, risk_per_trade=0.01)
    q = rm.size(100, 99)          # risk 1 per unit -> 10 units, notional 1000 == budget
    assert abs(q - 10) < 1e-9
    assert rm.size(100, 100.0001) * 100 <= 1000 + 1e-6
    assert rm.size(100, 101) == 0


def test_daily_loss_halts():
    rm = RiskManager(budget=1000, max_daily_loss=0.02, cooldown_sec=0)
    rm.record(-21)
    assert rm.can_trade() == (False, "daily loss limit hit")


def test_backtest_runs():
    r = run(synth(), budget=100)
    assert r["trades"] >= 0 and r["max_drawdown_pct"] >= 0
