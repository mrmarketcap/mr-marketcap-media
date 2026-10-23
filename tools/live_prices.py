"""Fetch live prices + daily candles from KuCoin into data/live-prices.json.

Usage: python tools/live_prices.py BTC ETH SOL
Daily candles are UTC days (KuCoin 1day). Each symbol gets the live price with
its exchange timestamp, so the analysis task can quote a fresh price.
"""
import json, sys, time, urllib.request, datetime as dt

API = "https://api.kucoin.com"
TEHRAN = dt.timezone(dt.timedelta(hours=3, minutes=30))

def get(path):
    req = urllib.request.Request(API + path, headers={"User-Agent": "mrmarketcap"})
    return json.load(urllib.request.urlopen(req, timeout=20))["data"]

def main(coins):
    now = int(time.time())
    out = {"fetched_utc": dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
           "fetched_tehran": dt.datetime.fromtimestamp(now, TEHRAN).strftime("%Y-%m-%d %H:%M"),
           "source": "KuCoin", "coins": {}}
    for c in coins:
        sym = f"{c}-USDT"
        lv = get(f"/api/v1/market/orderbook/level1?symbol={sym}")
        t = lv["time"] / 1000
        rows = get(f"/api/v1/market/candles?type=1day&symbol={sym}&startAt={now-86400*36}&endAt={now}")
        candles = []
        for r in sorted(rows, key=lambda r: int(r[0])):
            d = dt.datetime.fromtimestamp(int(r[0]), dt.timezone.utc).strftime("%Y-%m-%d")
            # KuCoin row: [time, open, close, high, low, volume, turnover]
            candles.append({"date": d, "open": float(r[1]), "high": float(r[3]), "low": float(r[4]), "close": float(r[2])})
        if candles and candles[-1]["date"] == dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%d"):
            candles[-1]["live"] = True
        out["coins"][c] = {"price": float(lv["price"]),
                           "price_time_tehran": dt.datetime.fromtimestamp(t, TEHRAN).strftime("%Y-%m-%d %H:%M"),
                           "price_age_s": round(now - t), "candles": candles}
    json.dump(out, open("data/live-prices.json", "w"), indent=1)
    print(json.dumps({k: (v["price"], v["price_time_tehran"], v["price_age_s"], len(v["candles"])) for k, v in out["coins"].items()}))

if __name__ == "__main__":
    main(sys.argv[1:] or ["BTC", "ETH"])
