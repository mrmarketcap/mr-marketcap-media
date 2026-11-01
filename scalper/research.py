"""Compare 3 low-frequency strategy families on 1h / 4h candles, honestly.

  python research.py

Families: Donchian breakout (trend), EMA-cross trend, Bollinger mean-reversion.
Rules of the game (set BEFORE looking at results):
  * settings are chosen on the first 60% of history (TRAIN)
  * a setting only counts if the last 40% (TEST, never used for choosing) is
    ALSO profitable: profit factor > 1.2 and at least 30 test trades
  * costs: taker fee 0.05%/side, slippage 0.02%/side, and funding of
    0.01% per 8h paid on the position (conservative: never received)
"""
import itertools
import json
import os
import statistics
import ccxt
from backtest import fetch
from strategy import ema, rsi, atr

SYMBOL = os.getenv("SYMBOL", "BNB/USDT:USDT")
DAYS = {"1h": 730, "4h": 1460}
FEE, SLIP, FUND_8H = 0.0005, 0.0002, 0.0001
BUDGET, RISK, LEV = 100.0, 0.01, 3
WARM = 250


class Data:
    def __init__(self, candles):
        self.t = [c[0] for c in candles]
        self.o = [c[1] for c in candles]
        self.h = [c[2] for c in candles]
        self.l = [c[3] for c in candles]
        self.c = [c[4] for c in candles]
        self.n = len(candles)
        self._candles, self._cache = candles, {}

    def memo(self, key, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def ema(self, p):
        return self.memo(("ema", p), lambda: ema(self.c, p))

    def atr(self, p=14):
        return self.memo(("atr", p), lambda: atr(self._candles, p))

    def hhv(self, N):   # highest high of the N bars BEFORE i
        return self.memo(("hhv", N), lambda: [None] * N + [max(self.h[i - N:i]) for i in range(N, self.n)])

    def llv(self, N):
        return self.memo(("llv", N), lambda: [None] * N + [min(self.l[i - N:i]) for i in range(N, self.n)])

    def bb(self, p, k):
        def f():
            mid, lo, up = [None] * self.n, [None] * self.n, [None] * self.n
            for i in range(p - 1, self.n):
                w = self.c[i - p + 1:i + 1]
                m, s = sum(w) / p, statistics.pstdev(w)
                mid[i], lo[i], up[i] = m, m - k * s, m + k * s
            return mid, lo, up
        return self.memo(("bb", p, k), f)


# each strategy -> (entry(i)->(side, stop_dist)|None, exit(i, side)->bool, trail_mult|None, max_hold_bars)
def donchian(d, N, m):
    hh, ll, a = d.hhv(N), d.llv(N), d.atr()

    def entry(i):
        if hh[i] is None or a[i] is None:
            return None
        if d.c[i] > hh[i]:
            return 1, m * a[i]
        if d.c[i] < ll[i]:
            return -1, m * a[i]
        return None
    return entry, (lambda i, s: False), m, 10**9


def ema_trend(d, f, s_, m):
    ef, es, a = d.ema(f), d.ema(s_), d.atr()

    def entry(i):
        if a[i] is None or i < s_:
            return None
        if ef[i - 1] <= es[i - 1] and ef[i] > es[i]:
            return 1, m * a[i]
        if ef[i - 1] >= es[i - 1] and ef[i] < es[i]:
            return -1, m * a[i]
        return None

    def exit_(i, side):
        return (ef[i] < es[i]) if side == 1 else (ef[i] > es[i])
    return entry, exit_, m, 10**9


def mean_rev(d, k, trend_p, m):
    mid, lo, up = d.bb(20, k)
    et, a = d.ema(trend_p), d.atr()

    def entry(i):
        if lo[i] is None or a[i] is None or i < trend_p:
            return None
        if d.c[i] < lo[i] and d.c[i] > et[i]:
            return 1, m * a[i]
        if d.c[i] > up[i] and d.c[i] < et[i]:
            return -1, m * a[i]
        return None

    def exit_(i, side):
        return (d.c[i] >= mid[i]) if side == 1 else (d.c[i] <= mid[i])
    return entry, exit_, None, 48


def simulate(d, strat, lo, hi):
    entry_f, exit_f, trail, max_hold = strat
    trades, i = [], max(lo, WARM)
    while i < hi - 2:
        sig = entry_f(i)
        if not sig or sig[1] <= 0:
            i += 1
            continue
        side, sd = sig
        ep = d.o[i + 1] * (1 + side * SLIP)
        stop = ep - side * sd
        qty = min(BUDGET * RISK / sd, BUDGET * LEV * 0.95 / ep)
        best, j, xp, k = d.c[i], i + 1, None, None
        while j < hi:
            o, h, l, c = d.o[j], d.h[j], d.l[j], d.c[j]
            if side == 1 and l <= stop:
                xp, k = min(o, stop) * (1 - SLIP), j; break
            if side == -1 and h >= stop:
                xp, k = max(o, stop) * (1 + SLIP), j; break
            if trail:
                best = max(best, c) if side == 1 else min(best, c)
                a = d.atr()[j]
                if a:
                    ns = best - side * trail * a
                    stop = max(stop, ns) if side == 1 else min(stop, ns)
            if exit_f(j, side) or (j - i) >= max_hold:
                if j + 1 < hi:
                    xp, k = d.o[j + 1] * (1 - side * SLIP), j + 1
                else:
                    xp, k = c, j
                break
            j += 1
        if xp is None:
            break
        hours = (d.t[k] - d.t[i + 1]) / 3_600_000
        pnl = (side * qty * (xp - ep) - FEE * qty * (ep + xp)
               - FUND_8H * qty * ep * hours / 8)
        trades.append(pnl)
        i = k
    return trades


def stats(tr):
    if not tr:
        return dict(n=0, ret=0.0, pf=0.0, win=0.0, dd=0.0)
    wins, loss = sum(t for t in tr if t > 0), -sum(t for t in tr if t < 0)
    eq = peak = dd = 0.0
    for t in tr:
        eq += t; peak = max(peak, eq); dd = max(dd, peak - eq)
    return dict(n=len(tr), ret=sum(tr) / BUDGET * 100, pf=(wins / loss if loss else 99.0),
                win=sum(1 for t in tr if t > 0) / len(tr), dd=dd / BUDGET * 100)


def grid(d):
    for N, m in itertools.product([20, 50, 100], [2.0, 3.0]):
        yield f"donchian N={N} stop={m}ATR", donchian(d, N, m)
    for (f, s), m in itertools.product([(20, 50), (50, 200)], [2.0, 3.0]):
        yield f"ema-cross {f}/{s} stop={m}ATR", ema_trend(d, f, s, m)
    for k, tp, m in itertools.product([2.0, 2.5], [100, 200], [2.0, 3.0]):
        yield f"meanrev bb{k} ema{tp} stop={m}ATR", mean_rev(d, k, tp, m)


def load(ex, tf):
    path = f"cache_research_{tf}.json"
    if os.path.exists(path):
        return json.load(open(path))
    print(f"downloading {tf} history ({DAYS[tf]} days), a few minutes...", flush=True)
    c = fetch(ex, SYMBOL, tf, DAYS[tf])
    json.dump(c, open(path, "w"))
    return c


def evaluate(candles, tf):
    d = Data(candles)
    cut = int(d.n * 0.6)
    bh = (d.c[-1] / d.c[cut] - 1) * 100
    rows = []
    for name, strat in grid(d):
        a = stats(simulate(d, strat, 0, cut))
        te = simulate(d, strat, cut, d.n)
        b = stats(te)
        half = len(te) // 2
        stable = len(te) >= 2 and sum(te[:half]) > 0 and sum(te[half:]) > 0
        rows.append((tf, name, a, b, stable))
    return rows, bh, d.n


def main():
    ex = ccxt.okx({"enableRateLimit": True})
    allrows = []
    for tf in DAYS:
        rows, bh, n = evaluate(load(ex, tf), tf)
        allrows += rows
        print(f"\n[{tf}] {n} candles. Buy&hold over the TEST period: {bh:+.1f}%")
        print(f"{'strategy':<34}| {'tr_ret%':>7} {'n':>4} {'pf':>5} | {'te_ret%':>7} {'n':>4} {'pf':>5} {'dd%':>5} stable")
        for _, name, a, b, st in sorted(rows, key=lambda r: -r[2]["pf"])[:6]:
            print(f"{name:<34}| {a['ret']:>7.1f} {a['n']:>4} {a['pf']:>5.2f} | {b['ret']:>7.1f} {b['n']:>4} {b['pf']:>5.2f} {b['dd']:>5.1f} {'yes' if st else 'no'}")
    ok = [r for r in allrows if r[2]["pf"] > 1.2 and r[3]["pf"] > 1.2 and r[3]["n"] >= 30]
    print(f"\nSettings passing the rules (train PF>1.2, test PF>1.2, >=30 test trades): {len(ok)} of {len(allrows)}")
    for tf, name, a, b, st in ok:
        print(f"  PASS [{tf}] {name}  test: {b['ret']:+.1f}% pf={b['pf']:.2f} n={b['n']} stable={st}")


if __name__ == "__main__":
    main()
