"""BTC/ETH round-price alerts (runs in GitHub Actions every ~5 minutes).

detect: reads live KuCoin data, writes pending.json with the alerts to send.
send:   renders banners, posts them silently to Telegram, updates the state file.
Needs env TELEGRAM_BOT_TOKEN for `send`. State: price-alerts-state.json
"""
import json, os, subprocess, sys, time, urllib.request, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "price-alerts-state.json")
PENDING = os.path.join(ROOT, "pending.json")
STEPS = {"BTC": 500, "ETH": 100}
CHAT = "@Mr_marketcap"
WINDOW = 1200      # look back at most 20 minutes
DAILY_CAP = 20
API = "https://api.kucoin.com"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "mrmarketcap-alerts"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def load_state():
    try:
        with open(STATE) as f:
            s = json.load(f)
    except FileNotFoundError:
        s = {}
    s.setdefault("day", "")
    s.setdefault("alerts_today", 0)
    for c in STEPS:
        s.setdefault(c, {})
        s[c].setdefault("alerts_today", 0)
        s[c].setdefault("last_alert_level", None)
        s[c].setdefault("last_alert_ts", 0)
    return s


def detect(now=None, fetch=get):
    now = int(now or time.time())
    s = load_state()
    today = dt.datetime.utcfromtimestamp(now).strftime("%Y-%m-%d")
    same_day = s["day"] == today
    out = []
    for coin, step in STEPS.items():
        if (s[coin]["alerts_today"] if same_day else 0) >= DAILY_CAP:
            print(f"{coin}: daily cap reached")
            continue
        sym = f"{coin}-USDT"
        st = s[coin]
        start = max(int(st["last_alert_ts"]), now - WINDOW)
        p = fetch(f"{API}/api/v1/market/orderbook/level1?symbol={sym}")["data"]
        if abs(now - p["time"] / 1000) > 180:
            print(f"{coin}: price stale, skipping")
            continue
        cur = float(p["price"])
        rows = fetch(f"{API}/api/v1/market/candles?type=1min&symbol={sym}&startAt={start}&endAt={now}")["data"]
        rows = sorted(rows, key=lambda r: int(r[0]))
        if rows:
            first = float(rows[0][1])
            hi = max([float(r[3]) for r in rows] + [cur])
            lo = min([float(r[4]) for r in rows] + [cur])
        else:
            first, hi, lo = cur, cur, cur
        cands = [l for l in range(int(lo // step + 1) * step if lo % step else int(lo), int(hi) + 1, step)
                 if lo <= l <= hi and l != st["last_alert_level"]]
        if not cands:
            print(f"{coin}: {cur} no new level")
            continue
        lvl = min(cands, key=lambda l: abs(l - cur))
        out.append({"coin": coin, "level": lvl, "up": first < lvl, "price": cur})
        print(f"{coin}: {cur} -> alert {lvl} {'up' if first < lvl else 'down'}")
    if out:
        json.dump({"now": now, "alerts": out}, open(PENDING, "w"))
    elif os.path.exists(PENDING):
        os.remove(PENDING)
    return out


def send():
    import requests  # noqa
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    p = json.load(open(PENDING))
    now = p["now"]
    s = load_state()
    today = dt.datetime.utcfromtimestamp(now).strftime("%Y-%m-%d")
    if s["day"] != today:
        s["day"], s["alerts_today"] = today, 0
        for c in STEPS:
            s[c]["alerts_today"] = 0
    stamp = dt.datetime.utcfromtimestamp(now).strftime("%Y%m%d-%H%M")
    os.makedirs(os.path.join(ROOT, "alerts", today[:7]), exist_ok=True)
    for a in p["alerts"]:
        png = os.path.join(ROOT, "alerts", today[:7], f"{a['coin'].lower()}-{a['level']}-{stamp}.jpg")
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "price_banner.py"), a["coin"],
                        str(a["level"]), "up" if a["up"] else "down", png], check=True)
        cap = f"{'🟢⬆️' if a['up'] else '🔴⬇️'} ${a['level']:,} #{a['coin']}\n@Mr_marketcap"
        with open(png, "rb") as f:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto",
                              data={"chat_id": CHAT, "caption": cap, "disable_notification": "true"},
                              files={"photo": f}, timeout=60)
        r.raise_for_status()
        mid = r.json()["result"]["message_id"]
        print("sent", cap, mid)
        s[a["coin"]]["last_alert_level"] = a["level"]
        s[a["coin"]]["last_alert_ts"] = now
        s["alerts_today"] += 1
        s[a["coin"]]["alerts_today"] += 1
        json.dump(s, open(STATE, "w"), indent=1)  # save after every successful post
    os.remove(PENDING)


def test():
    """Send a test banner to the channel (the user deletes it by hand)."""
    import requests
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    png = os.path.join(ROOT, "test-banner.jpg")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "price_banner.py"), "BTC", "84500", "up", png], check=True)
    with open(png, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto",
                          data={"chat_id": CHAT, "caption": "test", "disable_notification": "true"},
                          files={"photo": f}, timeout=60)
    r.raise_for_status()
    mid = r.json()["result"]["message_id"]
    print("test sent (not deleted):", mid)


if __name__ == "__main__":
    {"detect": detect, "send": send, "test": test}[sys.argv[1]]()
