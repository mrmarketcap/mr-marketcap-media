"""Parameter sweep with out-of-sample check.

  python sweep.py
Picks the best settings on the first 2/3 of history, then reports how those
same settings did on the last 1/3 (data they never saw). Only trust a setting
if BOTH parts are profitable.
"""
import itertools
import json
import os
import ccxt
from backtest import fetch, run
from strategy import Params

SYMBOL = os.getenv("SYMBOL", "BNB/USDT:USDT")
DAYS = {"5m": 60, "15m": 120}


def load(ex, tf):
    path = f"cache_{tf}.json"
    if os.path.exists(path):
        return json.load(open(path))
    print(f"downloading {tf} history ({DAYS[tf]} days)...", flush=True)
    c = fetch(ex, SYMBOL, tf, DAYS[tf])
    json.dump(c, open(path, "w"))
    return c


def main():
    ex = ccxt.okx({"enableRateLimit": True})
    rows = []
    for tf in DAYS:
        c = load(ex, tf)
        cut = len(c) * 2 // 3
        train, test = c[:cut], c[cut:]
        for atr_min, sl, tp in itertools.product([0.002, 0.003, 0.004], [1.0, 1.5], [1.5, 2.0, 3.0]):
            p = Params(min_atr_pct=atr_min, sl_atr=sl, tp_atr=tp)
            a, b = run(train, p=p), run(test, p=p)
            rows.append((tf, atr_min, sl, tp, a, b))
        print(f"{tf} done", flush=True)
    rows.sort(key=lambda r: r[4]["return_pct"], reverse=True)
    print("\nTop 8 by TRAIN result, with their TEST (unseen) result:")
    print(f"{'tf':>4} {'atr%':>6} {'sl':>4} {'tp':>4} | {'train%':>7} {'n':>4} {'win':>5} | {'test%':>7} {'n':>4} {'win':>5} {'dd%':>5}")
    for tf, am, sl, tp, a, b in rows[:8]:
        print(f"{tf:>4} {am*100:>6.2f} {sl:>4} {tp:>4} | {a['return_pct']:>7.1f} {a['trades']:>4} {a['win_rate']:>5.2f} | "
              f"{b['return_pct']:>7.1f} {b['trades']:>4} {b['win_rate']:>5.2f} {b['max_drawdown_pct']:>5.1f}")
    good = [r for r in rows if r[4]["return_pct"] > 0 and r[5]["return_pct"] > 0 and r[5]["trades"] >= 10]
    print(f"\nSettings profitable on BOTH train and test: {len(good)} of {len(rows)}")


if __name__ == "__main__":
    main()
