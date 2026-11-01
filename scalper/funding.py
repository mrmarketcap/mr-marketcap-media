"""Funding-rate carry analysis (cash-and-carry): long spot + short perpetual.

  python funding.py                    # OKX (history may be short)
  python funding.py --exchange binance # longer history, if reachable from your network

The short perp RECEIVES funding when the rate is positive and PAYS when negative.
Price moves cancel out (spot gain = perp loss), so only funding, fees and risks matter.
This is an analysis, not a trading bot.
"""
import argparse
import statistics
import ccxt

ROUND_TRIP_COST = 0.0010 * 2 + 0.0005 * 2   # spot taker x2 + perp taker x2 = 0.30% of notional
PERP_LEVERAGE = 2.0                          # capital = 1 (spot) + 1/lev (perp margin)


def fetch_funding(ex, symbol, years):
    now = ex.milliseconds()
    since = now - int(years * 365 * 86400_000)
    out, seen = [], set()
    while since < now:
        chunk = ex.fetch_funding_rate_history(symbol, since=since, limit=100)
        new = [x for x in chunk if x.get("timestamp") and x["timestamp"] not in seen]
        if not new:
            break
        for x in new:
            seen.add(x["timestamp"])
        out += new
        since = max(x["timestamp"] for x in new) + 1
    out.sort(key=lambda x: x["timestamp"])
    return [(x["timestamp"], float(x["fundingRate"])) for x in out if x.get("fundingRate") is not None]


def analyse(data):
    ts, r = [t for t, _ in data], [x for _, x in data]
    n = len(r)
    hours = statistics.median((ts[i + 1] - ts[i]) for i in range(n - 1)) / 3_600_000
    ppy = 365 * 24 / hours
    years = n / ppy
    cap = 1 + 1 / PERP_LEVERAGE
    res = {"n": n, "hours": hours, "years": years}

    gross = sum(r)
    res["always_gross_apr"] = gross / years * 100
    res["always_net_apr"] = (gross - ROUND_TRIP_COST) / years * 100
    res["always_net_apr_on_capital"] = (gross - ROUND_TRIP_COST) / years / cap * 100
    res["pos_share"] = sum(1 for x in r if x > 0) / n * 100

    # filtered variant: only hold when last-7d average (annualised) > 10%, leave when < 0
    k = max(3, int(7 * 24 / hours))
    on, pnl, switches = False, 0.0, 0
    for i in range(k, n):
        avg_apr = statistics.fmean(r[i - k:i]) * ppy
        if not on and avg_apr > 0.10:
            on, switches = True, switches + 1
        elif on and avg_apr < 0:
            on = False
        if on:
            pnl += r[i]
    net = pnl - switches * ROUND_TRIP_COST
    res["filt_net_apr"] = net / years * 100
    res["filt_net_apr_on_capital"] = net / years / cap * 100
    res["filt_switches"] = switches

    # risk views
    block = int(90 * 24 / hours)
    blocks = [(ts[i], sum(r[i:i + block]) / (block / ppy) * 100) for i in range(0, n - block + 1, block)]
    res["blocks"] = blocks
    res["worst_block_apr"] = min(b for _, b in blocks) if blocks else 0.0
    eq = peak = dd = 0.0
    for x in r:
        eq += x; peak = max(peak, eq); dd = max(dd, peak - eq)
    res["max_funding_drawdown_pct"] = dd * 100
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exchange", default="okx")
    ap.add_argument("--symbol", default="BNB/USDT:USDT")
    ap.add_argument("--years", type=float, default=3)
    a = ap.parse_args()
    ex = getattr(ccxt, a.exchange)({"enableRateLimit": True})
    data = fetch_funding(ex, a.symbol, a.years)
    if len(data) < 100:
        raise SystemExit(f"only {len(data)} funding records - too little history. Try --exchange binance")
    s = analyse(data)
    print(f"{a.exchange} {a.symbol}: {s['n']} funding periods ({s['hours']:.0f}h each) = {s['years']:.2f} years")
    print(f"share of periods with positive funding: {s['pos_share']:.0f}%")
    print("\nYearly return, as % of the position size (before leverage effects):")
    print(f"  always on, before fees : {s['always_gross_apr']:>6.1f}%")
    print(f"  always on, after fees  : {s['always_net_apr']:>6.1f}%")
    print(f"  filtered, after fees   : {s['filt_net_apr']:>6.1f}%   ({s['filt_switches']} entries)")
    print(f"\nOn real capital needed (spot + perp margin at {PERP_LEVERAGE:g}x):")
    print(f"  always on : {s['always_net_apr_on_capital']:>6.1f}%/yr")
    print(f"  filtered  : {s['filt_net_apr_on_capital']:>6.1f}%/yr")
    print(f"\nWorst 90-day stretch (annualised): {s['worst_block_apr']:.1f}%")
    print(f"Biggest funding drawdown (peak to trough): {s['max_funding_drawdown_pct']:.1f}% of position")
    print("\n90-day blocks (annualised % of position):")
    import time
    for t, v in s["blocks"]:
        print(f"  {time.strftime('%Y-%m-%d', time.gmtime(t / 1000))}  {v:>6.1f}%")


if __name__ == "__main__":
    main()
