"""Fetch weekly + monthly candles (KuCoin 1week / 1month, UTC) into data/htf-candles.json.

Usage: python tools/htf_candles.py BTC ETH
Weekly candles open Monday 00:00 UTC, monthly on the 1st 00:00 UTC. The last candle of
each list has "live": true when it is still open (not yet closed).
"""
import json, sys, time, urllib.request, datetime as dt

API = "https://api.kucoin.com"

def get(path):
    req = urllib.request.Request(API + path, headers={"User-Agent": "mrmarketcap"})
    return json.load(urllib.request.urlopen(req, timeout=20))["data"]

def candles(sym, typ, span, now):
    rows = get(f"/api/v1/market/candles?type={typ}&symbol={sym}&startAt={now-span}&endAt={now}")
    out = []
    for r in sorted(rows, key=lambda r: int(r[0])):
        start = int(r[0])
        # KuCoin row: [time, open, close, high, low, volume, turnover]
        out.append({"start": dt.datetime.fromtimestamp(start, dt.timezone.utc).strftime("%Y-%m-%d"),
                    "open": float(r[1]), "high": float(r[3]), "low": float(r[4]), "close": float(r[2]),
                    "_t": start})
    return out

def mark_live(cs, typ, now):
    if not cs: return cs
    last = cs[-1]["_t"]
    length = 7*86400 if typ == "1week" else 31*86400
    if typ == "1month":
        d = dt.datetime.fromtimestamp(last, dt.timezone.utc)
        nxt = dt.datetime(d.year + (d.month == 12), d.month % 12 + 1, 1, tzinfo=dt.timezone.utc)
        end = int(nxt.timestamp())
    else:
        end = last + length
    if now < end: cs[-1]["live"] = True
    cs[-1]["closes_utc"] = dt.datetime.fromtimestamp(end, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    for c in cs: c.pop("_t", None)
    return cs

def main(coins):
    now = int(time.time())
    out = {"fetched_utc": dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(), "source": "KuCoin", "coins": {}}
    for c in coins:
        sym = f"{c}-USDT"
        lv = get(f"/api/v1/market/orderbook/level1?symbol={sym}")
        w = mark_live(candles(sym, "1week", 86400*7*60, now), "1week", now)
        m = mark_live(candles(sym, "1month", 86400*31*40, now), "1month", now)
        out["coins"][c] = {"price": float(lv["price"]), "weekly": w, "monthly": m}
    json.dump(out, open("data/htf-candles.json", "w"), indent=1)
    print({k: (v["price"], len(v["weekly"]), len(v["monthly"])) for k, v in out["coins"].items()})

if __name__ == "__main__":
    main(sys.argv[1:] or ["BTC", "ETH"])
