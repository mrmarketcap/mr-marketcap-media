"""Free market posts for @Mr_marketcap (GitHub Actions). Modes:
  fng     daily Fear & Greed banner (once per UTC day)
  movers  1-hour big moves of major coins (cooldown per coin)
Env: TELEGRAM_BOT_TOKEN (not needed with DRY_RUN=1). State: market-state.json
"""
import datetime as dt, json, os, subprocess, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "market-state.json")
CHAT = "@Mr_marketcap"
# Large, established projects only (no meme coins, no stablecoins)
MAJORS = ["BNB", "XRP", "SOL", "ADA", "TRX", "LINK", "AVAX", "DOT", "TON", "LTC", "BCH", "ATOM", "BTC", "ETH"]
MOVE_PCT = {"BTC": 3.0, "ETH": 4.0}      # others use DEFAULT_MOVE_PCT
DEFAULT_MOVE_PCT = 5.0
COOLDOWN = 4 * 3600
DRY = os.environ.get("DRY_RUN") == "1"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "mrmarketcap-alerts"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def load():
    try:
        return json.load(open(STATE))
    except FileNotFoundError:
        return {"fng_date": "", "movers": {}}


def save(s):
    json.dump(s, open(STATE, "w"), indent=1)


def post(pill, big, sub, tone, caption, name):
    out = os.path.join(ROOT, "alerts", "market", name + ".jpg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "stat_banner.py"), pill, big, sub, tone, out], check=True)
    import requests
    with open(out, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendPhoto",
                          data={"chat_id": CHAT, "caption": caption, "disable_notification": "true"},
                          files={"photo": f}, timeout=60)
    r.raise_for_status()
    print("sent", caption, r.json()["result"]["message_id"])


def fng(fetch=get):
    s = load()
    d = fetch("https://api.alternative.me/fng/?limit=2")["data"]
    today = dt.datetime.utcfromtimestamp(int(d[0]["timestamp"])).strftime("%Y-%m-%d")
    if s.get("fng_date") == today:
        print("fng already posted for", today)
        return None
    val, label = int(d[0]["value"]), d[0]["value_classification"]
    prev = int(d[1]["value"]) if len(d) > 1 else None
    sub = f"{label} · yesterday {prev}" if prev is not None else label
    tone = "up" if val >= 55 else "down" if val <= 45 else "flat"
    cap = f"{'🟢' if tone == 'up' else '🔴' if tone == 'down' else '🟠'} Fear & Greed Index: {val} ({label}) @Mr_marketcap"
    print(cap)
    if DRY:
        return cap
    post("FEAR & GREED", str(val), sub, tone, cap, f"fng-{today}")
    s["fng_date"] = today
    save(s)
    return cap


def movers(now=None, fetch=get):
    now = int(now or time.time())
    s = load()
    hits = []
    for c in MAJORS:
        last = s["movers"].get(c, 0)
        if now - last < COOLDOWN:
            continue
        try:
            rows = fetch(f"https://api.kucoin.com/api/v1/market/candles?type=1min&symbol={c}-USDT&startAt={now-3900}&endAt={now}")["data"]
        except Exception as e:  # one failing pair must not stop the others
            print(c, "error", e)
            continue
        rows = sorted(rows, key=lambda r: int(r[0]))
        if len(rows) < 30 or now - int(rows[-1][0]) > 300:
            continue
        start = [r for r in rows if int(r[0]) >= now - 3600]
        if not start:
            continue
        p0, p1 = float(start[0][1]), float(rows[-1][2])
        pct = (p1 / p0 - 1) * 100
        if abs(pct) >= MOVE_PCT.get(c, DEFAULT_MOVE_PCT):
            hits.append((abs(pct), c, pct, p1))
    hits.sort(reverse=True)
    out = []
    for _, c, pct, p1 in hits[:2]:
        up = pct > 0
        price = f"${p1:,.2f}" if p1 < 1000 else f"${p1:,.0f}"
        cap = f"{'🟢' if up else '🔴'} #{c} {pct:+.1f}% in 1h ({price}) @Mr_marketcap"
        print(cap)
        out.append(cap)
        if DRY:
            continue
        post(c, f"{pct:+.1f}%", f"last 1h · {price}", "up" if up else "down", cap,
             f"move-{c.lower()}-{dt.datetime.utcfromtimestamp(now).strftime('%Y%m%d-%H%M')}")
        s["movers"][c] = now
        save(s)
    if not hits:
        print("no big moves")
    return out


if __name__ == "__main__":
    {"fng": fng, "movers": movers}[sys.argv[1]]()
