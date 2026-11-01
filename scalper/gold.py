"""Gold: buy & hold vs simple trend filter, on daily data. Analysis only.

  pip install yfinance
  python gold.py                 # GLD (gold ETF, ~20 years)
  python gold.py --ticker GC=F   # gold futures (roll gaps possible)
  python gold.py --csv gold.csv  # own file with columns: date,close

Trend rule: hold gold when yesterday's close > its N-day average, else sit in cash
(cash earns 0% here, which UNDERSTATES the strategy a little). Cost: 0.1% per switch.
Signal uses yesterday's close, trade happens today -> no look-ahead.
"""
import argparse
import csv
import datetime as dt
import math
import statistics

COST = 0.001
LENGTHS = [50, 100, 150, 200, 250]


def load_yf(ticker):
    import yfinance as yf
    h = yf.Ticker(ticker).history(period="max", auto_adjust=True)["Close"].dropna()
    return [d.date() for d in h.index], [float(x) for x in h.values]


def load_csv(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    k = {c.lower(): c for c in rows[0]}
    return ([dt.date.fromisoformat(r[k["date"]][:10]) for r in rows], [float(r[k["close"]]) for r in rows])


def sma(c, n):
    out, s = [None] * len(c), 0.0
    for i, x in enumerate(c):
        s += x
        if i >= n:
            s -= c[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def positions(c, n):
    """pos[t] = position held DURING day t, decided at close of day t-1."""
    m = sma(c, n)
    return [0] + [1 if (m[t - 1] is not None and c[t - 1] > m[t - 1]) else 0 for t in range(1, len(c))]


def daily_returns(c, pos):
    out, prev = [0.0], 0
    for t in range(1, len(c)):
        r = pos[t] * (c[t] / c[t - 1] - 1)
        if pos[t] != prev:
            r -= COST
        prev = pos[t]
        out.append(r)
    return out


def metrics(rets, pos=None):
    eq, peak, dd = 1.0, 1.0, 0.0
    for r in rets:
        eq *= 1 + r
        peak = max(peak, eq)
        dd = max(dd, 1 - eq / peak)
    yrs = len(rets) / 252
    cagr = eq ** (1 / yrs) - 1 if yrs > 0 and eq > 0 else -1
    vol = statistics.pstdev(rets) * math.sqrt(252)
    trades = sum(1 for i in range(1, len(pos)) if pos[i] != pos[i - 1]) // 2 if pos else 0
    inmkt = sum(pos) / len(pos) if pos else 1.0
    return dict(cagr=cagr * 100, dd=dd * 100, vol=vol * 100, calmar=(cagr / dd if dd else 0),
                trades=trades, inmkt=inmkt * 100, total=(eq - 1) * 100)


def row(name, m):
    return (f"{name:<14}| {m['cagr']:>6.1f} {m['dd']:>6.1f} {m['vol']:>6.1f} {m['calmar']:>6.2f} "
            f"{m['inmkt']:>6.0f} {m['trades']:>6}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="GLD")
    ap.add_argument("--csv")
    a = ap.parse_args()
    dates, c = load_csv(a.csv) if a.csv else load_yf(a.ticker)
    n = len(c)
    print(f"{a.ticker if not a.csv else a.csv}: {n} days, {dates[0]} -> {dates[-1]} ({n/252:.1f} years)\n")
    bh_pos = [1] * n
    bh = daily_returns(c, [1] + [1] * (n - 1))
    head = f"{'':<14}| {'CAGR%':>6} {'maxDD%':>6} {'vol%':>6} {'Calmar':>6} {'inMkt%':>6} {'trades':>6}"
    print("Whole period:\n" + head)
    print(row("buy & hold", metrics(bh[1:], bh_pos[1:])))
    pos_by, ret_by = {}, {}
    for L in LENGTHS:
        pos_by[L] = positions(c, L)
        ret_by[L] = daily_returns(c, pos_by[L])
        print(row(f"trend SMA{L}", metrics(ret_by[L][1:], pos_by[L][1:])))

    print("\nBy 5-year block, total return % (is the result stable, or one lucky era?):")
    print(f"{'block':<12}| {'hold':>7} " + " ".join(f"{'SMA'+str(L):>7}" for L in LENGTHS))
    step, i = 252 * 5, 1
    while i + step // 2 < n:
        j = min(i + step, n)
        lab = f"{dates[i].year}-{dates[j-1].year}"
        vals = [metrics(bh[i:j], None)["total"]] + [metrics(ret_by[L][i:j], None)["total"] for L in LENGTHS]
        print(f"{lab:<12}| " + " ".join(f"{v:>7.1f}" for v in vals))
        i = j

    cut = int(n * 0.6)
    best = max(LENGTHS, key=lambda L: metrics(ret_by[L][1:cut], pos_by[L][1:cut])["calmar"])
    print(f"\nHonest test: pick SMA length on first 60% of days (best Calmar -> SMA{best}), then judge on last 40% "
          f"({dates[cut]} -> {dates[-1]}):")
    print(head)
    print(row("buy & hold", metrics(bh[cut:], bh_pos[cut:])))
    print(row(f"trend SMA{best}", metrics(ret_by[best][cut:], pos_by[best][cut:])))


if __name__ == "__main__":
    main()
