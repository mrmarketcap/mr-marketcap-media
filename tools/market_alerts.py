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


def post(cmd, caption, name):
    out = os.path.join(ROOT, "alerts", "market", name + ".jpg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", cmd[0])] + cmd[1:] + [out], check=True)
    import requests
    with open(out, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendPhoto",
                          data={"chat_id": CHAT, "caption": caption, "disable_notification": "true"},
                          files={"photo": f}, timeout=60)
    r.raise_for_status()
    print("sent", caption, r.json()["result"]["message_id"])


def alt_fng():
    """Alternative.me Fear & Greed (free, no key). Newest first: today, yesterday, ... 7 days ago."""
    return get("https://api.alternative.me/fng/?limit=8")["data"]


def fng(fetch=None):
    s = load()
    d = fetch("x")["data"] if fetch else alt_fng()
    if not d:
        return None
    today = dt.datetime.utcfromtimestamp(int(d[0]["timestamp"])).strftime("%Y-%m-%d")
    if s.get("fng_date") == today:
        print("fng already posted for", today)
        return None
    val, label = int(d[0]["value"]), d[0]["value_classification"]
    y = d[1] if len(d) > 1 else d[0]
    w = d[7] if len(d) > 7 else d[-1]
    tone = "up" if val >= 55 else "down" if val <= 45 else "flat"
    cap = f"{'🟢' if tone == 'up' else '🔴' if tone == 'down' else '🟠'} Fear & Greed Index: {val} ({label}) @Mr_marketcap"
    print(cap)
    if DRY:
        return cap
    post(["fng_banner.py", str(val), label, y["value"], y["value_classification"], w["value"],
          w["value_classification"]], cap, f"fng-{today}")
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
        post(["stat_banner.py", c, f"{pct:+.1f}%", f"last 1h · {price}", "up" if up else "down"], cap,
             f"move-{c.lower()}-{dt.datetime.utcfromtimestamp(now).strftime('%Y%m%d-%H%M')}")
        s["movers"][c] = now
        save(s)
    if not hits:
        print("no big moves")
    return out


def daily_candles(sym, now, fetch=get, pages=3):
    """Completed daily candles (oldest first) going back up to ~12 years, 1500 per KuCoin page."""
    rows, end = [], now
    for _ in range(pages):
        start = end - 1500 * 86400
        page = fetch(f"https://api.kucoin.com/api/v1/market/candles?type=1day&symbol={sym}&startAt={start}&endAt={end}")["data"]
        if not page:
            break
        rows += page
        end = start - 1
    today0 = now - now % 86400
    seen = {int(r[0]): r for r in rows if int(r[0]) < today0}
    return [seen[k] for k in sorted(seen)]


def records(now=None, fetch=get):
    """New 30-day / 52-week / all-time highs and 30-day / 52-week lows for BTC and ETH (once per kind per UTC day)."""
    now = int(now or time.time())
    s = load()
    s.setdefault("records", {})
    day = dt.datetime.utcfromtimestamp(now).strftime("%Y-%m-%d")
    out = []
    for coin in ("BTC", "ETH"):
        sym = f"{coin}-USDT"
        p = fetch(f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={sym}")["data"]
        if abs(now - p["time"] / 1000) > 180:
            print(coin, "price stale; skipped")
            continue
        price = float(p["price"])
        cs = daily_candles(sym, now, fetch)
        if len(cs) < 400:
            print(coin, "not enough history; skipped")
            continue
        def win(n):
            w = cs[-n:]
            return max(float(c[3]) for c in w), min(float(c[4]) for c in w)
        hi_all = max(float(c[3]) for c in cs)
        hi30, lo30 = win(30)
        hi365, lo365 = win(365)
        found = []   # strongest first
        if price > hi_all and len(cs) >= 1400:
            found.append(("ath", "new all-time high", "up"))
        if price > hi365:
            found.append(("hi365", "new 52-week high", "up"))
        if price > hi30:
            found.append(("hi30", "new 30-day high", "up"))
        if price < lo365:
            found.append(("lo365", "new 52-week low", "down"))
        if price < lo30:
            found.append(("lo30", "new 30-day low", "down"))
        for kind, label, tone in found:
            if s["records"].get(f"{coin}-{kind}") == day:
                continue
            val = f"${price:,.0f}"
            cap = f"{'🟢' if tone == 'up' else '🔴'} #{coin} {label}: {val} @Mr_marketcap"
            print(cap)
            out.append(cap)
            if not DRY:
                post(["stat_banner.py", coin, val, label[4:].capitalize() if label.startswith("new ") else label, tone],
                     cap, f"record-{coin.lower()}-{kind}-{dt.datetime.utcfromtimestamp(now).strftime('%Y%m%d-%H%M')}")
                s["records"][f"{coin}-{kind}"] = day
                save(s)
            break   # one banner per coin per run (the strongest)
        if not found:
            print(coin, f"{price:,.0f} no record")
    return out


SUMMARY_COINS = ["BTC", "ETH", "BNB", "XRP", "SOL", "ADA", "TRX", "LINK", "AVAX", "DOT", "TON", "LTC", "BCH",
                 "ATOM", "UNI", "AAVE", "NEAR", "ETC", "XLM", "HBAR"]


def summary(now=None, fetch=get):
    now = int(now or time.time())
    s = load()
    day = dt.datetime.utcfromtimestamp(now).strftime("%Y-%m-%d")
    if s.get("summary_date") == day:
        print("summary already posted for", day)
        return None
    tick = {t["symbol"]: t for t in fetch("https://api.kucoin.com/api/v1/market/allTickers")["data"]["ticker"]}
    data = {}
    for c in SUMMARY_COINS:
        t = tick.get(f"{c}-USDT")
        if t and t.get("changeRate") is not None and t.get("last"):
            data[c] = (float(t["changeRate"]) * 100, float(t["last"]))
    if len(data) < 10:
        print("not enough tickers; skipped")
        return None
    rank = sorted(((c, v[0]) for c, v in data.items()), key=lambda x: -x[1])
    gain = [[c, round(p, 1)] for c, p in rank[:5]]
    lose = [[c, round(p, 1)] for c, p in rank[::-1][:5]]
    head = " · ".join(f"{c} ${data[c][1]:,.0f} {data[c][0]:+.1f}%" for c in ("BTC", "ETH") if c in data)
    cap = (f"📊 Market summary, last 24h: #{gain[0][0]} {gain[0][1]:+.1f}% on top, "
           f"#{lose[0][0]} {lose[0][1]:+.1f}% at the bottom @Mr_marketcap")
    print(cap, "|", head)
    if DRY:
        return cap
    out = os.path.join(ROOT, "alerts", "market", f"summary-{day}.jpg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "summary_banner.py"),
                    json.dumps({"head": head, "gain": gain, "lose": lose}), out], check=True)
    import requests
    with open(out, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendPhoto",
                          data={"chat_id": CHAT, "caption": cap, "disable_notification": "true"},
                          files={"photo": f}, timeout=60)
    r.raise_for_status()
    print("sent", r.json()["result"]["message_id"])
    s["summary_date"] = day
    save(s)
    return cap


def pdig(x):
    return str(x).translate(str.maketrans("0123456789,.-", "۰۱۲۳۴۵۶۷۸۹٬٫-"))


def tg(method, **data):
    import requests
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{method}", data=data, timeout=60)
    r.raise_for_status()
    return r.json()["result"]


def weekly(now=None, fetch=get):
    """Friday: best and worst of the week (7 days) among established coins."""
    now = int(now or time.time())
    s = load()
    wk = dt.datetime.utcfromtimestamp(now).strftime("%G-W%V")
    if s.get("weekly_week") == wk:
        print("weekly already posted for", wk)
        return None
    data = {}
    for c in SUMMARY_COINS:
        try:
            cs = daily_candles(f"{c}-USDT", now, fetch, pages=1)
            last = float(fetch(f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={c}-USDT")["data"]["price"])
        except Exception as e:
            print(c, "skipped", e)
            continue
        if len(cs) >= 8:
            base = float(cs[-7][2])        # close of the day 7 days ago
            data[c] = ((last / base - 1) * 100, last)
    if len(data) < 10:
        print("not enough data; skipped")
        return None
    rank = sorted(((c, v[0]) for c, v in data.items()), key=lambda x: -x[1])
    gain = [[c, round(p, 1)] for c, p in rank[:5]]
    lose = [[c, round(p, 1)] for c, p in rank[::-1][:5]]
    head = " · ".join(f"{c} ${data[c][1]:,.0f} {data[c][0]:+.1f}%" for c in ("BTC", "ETH") if c in data)
    cap = (f"📅 Weekly recap: #{gain[0][0]} {gain[0][1]:+.1f}% led the week, "
           f"#{lose[0][0]} {lose[0][1]:+.1f}% lagged @Mr_marketcap")
    print(cap, "|", head)
    if DRY:
        return cap
    out = os.path.join(ROOT, "alerts", "market", f"weekly-{wk}.jpg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "summary_banner.py"),
                    json.dumps({"head": head, "gain": gain, "lose": lose, "title": "خلاصهٔ بازار هفتهٔ گذشته"}), out], check=True)
    import requests
    with open(out, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendPhoto",
                          data={"chat_id": CHAT, "caption": cap, "disable_notification": "true"},
                          files={"photo": f}, timeout=60)
    r.raise_for_status()
    print("sent", r.json()["result"]["message_id"])
    s["weekly_week"] = wk
    save(s)
    return cap


def poll(now=None, fetch=get):
    """Monday: close last week's BTC poll (reply with the outcome), then open a new one."""
    now = int(now or time.time())
    s = load()
    day = dt.datetime.utcfromtimestamp(now).strftime("%Y-%m-%d")
    if s.get("poll_date") == day:
        print("poll already handled for", day)
        return None
    q = fetch("https://api.kucoin.com/api/v1/market/orderbook/level1?symbol=BTC-USDT")["data"]
    if abs(now - q["time"] / 1000) > 180:
        print("BTC price stale; skipped")
        return None
    price = float(q["price"])
    old = s.get("poll")
    lines = []
    if old and now - old["ts"] >= 5 * 86400:
        ch = (price / old["price"] - 1) * 100
        up = price > old["price"]
        lines.append(f"close poll {old['msg']}: BTC {old['price']:,.0f} -> {price:,.0f} ({ch:+.1f}%)")
        share = ""
        if not DRY:
            try:
                res = tg("stopPoll", chat_id=CHAT, message_id=old["msg"])
                v = [o["voter_count"] for o in res["options"]]
                if sum(v):
                    share = f"\n{pdig(round(100 * v[0] / sum(v)))}٪ از رأی‌دهنده‌ها «بالاتر» گفته بودن."
            except Exception as e:
                print("stopPoll failed", e)
        word = "بالاتر" if up else "پایین‌تر"
        text = (f"📊 نتیجهٔ نظرسنجی هفتهٔ پیش\n"
                f"قیمت BTC موقع نظرسنجی {pdig(format(round(old['price']), ','))} دلار بود و الان {pdig(format(round(price), ','))} دلاره "
                f"({pdig(format(abs(ch), '.1f'))}٪ {'بالاتر' if up else 'پایین‌تر'})، پس جواب «{word}» درست بود.{share}\n"
                f"این فقط یه بازی آموزشیه، نه پیش‌بینی یا توصیه‌ی خرید و فروش.\n@Mr_marketcap")
        lines.append(text)
        if not DRY:
            tg("sendMessage", chat_id=CHAT, text=text, reply_to_message_id=old["msg"], disable_notification="true")
    ref = round(price, -2)
    question = f"تا دوشنبهٔ بعد، BTC بالاتر از {pdig(format(int(ref), ','))} دلار هست؟"
    lines.append("new poll: " + question)
    print("\n".join(lines) + "\n@Mr_marketcap")
    if DRY:
        return lines
    res = tg("sendPoll", chat_id=CHAT, question=question,
             options=json.dumps(["آره، بالاتر", "نه، پایین‌تر"], ensure_ascii=False),
             is_anonymous="true", disable_notification="true")
    s["poll"] = {"msg": res["message_id"], "price": ref, "ts": now}
    s["poll_date"] = day
    save(s)
    return lines


if __name__ == "__main__":
    {"fng": fng, "movers": movers, "records": records, "summary": summary, "weekly": weekly, "poll": poll}[sys.argv[1]]()
