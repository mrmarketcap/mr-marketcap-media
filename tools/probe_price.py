import json, time, urllib.request, datetime as dt
def get(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "x"}), timeout=20))
now = int(time.time())
for sym in ("BTC-USDT",):
    p = get(f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={sym}")["data"]
    print(sym, "price", p["price"], "age_s", now - p["time"] / 1000)
    rows = get(f"https://api.kucoin.com/api/v1/market/candles?type=15min&symbol={sym}&startAt={now-3600*8}&endAt={now}")["data"]
    for r in sorted(rows, key=lambda r: int(r[0])):
        t = dt.datetime.utcfromtimestamp(int(r[0])).strftime("%H:%M")
        print(t, "o", r[1], "h", r[3], "l", r[4], "c", r[2])
