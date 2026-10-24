"""Follow-up replies to past analyses (free replacement for the Claude task).

Reads posts-log.csv, checks KuCoin daily candles + live price, and replies silently
under the original post when a trigger was hit or the price moved +-20%.
Env: TELEGRAM_BOT_TOKEN (not needed with DRY_RUN=1).
"""
import csv, datetime as dt, json, os, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "posts-log.csv")
CHAT = "@Mr_marketcap"
MAX_REPLIES = 2
MAX_AGE_DAYS = 14
DRY = os.environ.get("DRY_RUN") == "1"
FA = str.maketrans("0123456789.", "۰۱۲۳۴۵۶۷۸۹٫")
FIELDS = ["date", "ticker", "message_id", "price_at_post", "bull_trigger", "bear_trigger",
          "post_type", "reported", "status"]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "mrmarketcap-alerts"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def fa(s):
    return str(s).translate(FA)


def events_for(row, now, fetch):
    """Returns (events, last_event_kind, pct_now, price_now) or None when data is unavailable."""
    sym = f"{row['ticker']}-USDT"
    post_day = dt.datetime.strptime(row["date"], "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    start = int(post_day.timestamp())
    today0 = now - now % 86400
    cs = fetch(f"https://api.kucoin.com/api/v1/market/candles?type=1day&symbol={sym}&startAt={start}&endAt={now}")["data"]
    p = fetch(f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={sym}")["data"]
    if not p or abs(now - p["time"] / 1000) > 300:
        return None
    price = float(p["price"])
    p0 = float(row["price_at_post"])
    bull, bear = float(row["bull_trigger"]), float(row["bear_trigger"])
    done = sorted([c for c in cs if int(c[0]) < today0 and int(c[0]) >= start + 86400], key=lambda c: int(c[0]))
    reported = set(filter(None, row["reported"].split("|")))
    ev, last = [], None
    for c in done:                                   # c = [time, open, close, high, low, ...]
        close = float(c[2])
        if close > bull and "bull" not in reported and "bull" not in ev:
            ev.append("bull"); last = ("bull", int(c[0]))
        if close < bear and "bear" not in reported and "bear" not in ev:
            ev.append("bear"); last = ("bear", int(c[0])) if not last or int(c[0]) > last[1] else last
    pct = (price / p0 - 1) * 100
    if pct >= 20 and "up20" not in reported:
        ev.append("up20")
    if pct <= -20 and "down20" not in reported:
        ev.append("down20")
    return ev, (last[0] if last else None), pct, price


def _ago(days, p0):
    """Spoken reference to the original post; varies with the age of the post."""
    if days <= 0:
        return f"از موقع تحلیل امروز ({p0})"
    if days == 1:
        return f"از تحلیل دیروز ({p0})"
    return f"از تحلیل {fa(days)} روز پیش ({p0})"


def text_for(row, ev, last, pct, now):
    """Update reply. Wording is picked from several natural variants (seeded by the post, so a
    re-run gives the same text) so the channel does not get the same sentences every time."""
    import random
    t = row["ticker"]
    days = (dt.datetime.utcfromtimestamp(now).date() - dt.datetime.strptime(row["date"], "%Y-%m-%d").date()).days
    p0 = fa(row["price_at_post"])
    n = fa(abs(round(pct)))
    kind = last if ("bull" in ev or "bear" in ev) else ("bull_move" if "up20" in ev else "bear_move")
    rnd = random.Random(f"{row['message_id']}-{kind}-{days}")
    ago = _ago(days, p0)
    up = rnd.choice(["رشد کرده", "بالا رفته"]) if pct >= 0 else "تغییر کرده"
    down = rnd.choice(["ریزش کرده", "پایین اومده", "افت کرده"]) if pct <= 0 else "تغییر کرده"
    bull, bear = fa(row["bull_trigger"]), fa(row["bear_trigger"])
    if kind == "bull":
        head = rnd.choice([f"🎯 آپدیت {t}", f"🎯 خبر تازه از {t}", f"🎯 {t} سطحش رو فعال کرد"])
        body = rnd.choice([
            f"{ago} تا الان حدود {n}٪ {up} و کندل روزانه بالای {bull} بسته شد؛ یعنی سناریوی صعودی فعال شده.",
            f"کندل روزانه بالای {bull} بسته شد و سناریوی صعودی فعال شد. قیمت {ago} حدود {n}٪ {up}.",
            f"قیمت {ago.replace('از ', 'نسبت به ', 1)} حدود {n}٪ {up} و بالای {bull} کندل روزانه بسته شده. سناریوی صعودی فعال شد.",
        ])
        tail = rnd.choice(["", "", "فعلاً نوسان بالاست و برگشت‌های ناگهانی هم ممکنه.", "باید دید بالای این سطح می‌مونه یا نه.",
                           "هنوز زوده که بشه گفت ادامه‌دار می‌شه."])
    elif kind == "bear":
        head = rnd.choice([f"⚠️ آپدیت {t}", f"⚠️ خبر تازه از {t}", f"⚠️ {t} زیر سطحش بسته شد"])
        body = rnd.choice([
            f"{ago} تا الان حدود {n}٪ {down} و کندل روزانه زیر {bear} بسته شد؛ یعنی سناریوی نزولی فعال شده.",
            f"کندل روزانه زیر {bear} بسته شد و سناریوی نزولی فعال شد. قیمت {ago} حدود {n}٪ {down}.",
            f"قیمت {ago.replace('از ', 'نسبت به ', 1)} حدود {n}٪ {down} و زیر {bear} کندل روزانه بسته شده. سناریوی نزولی فعال شد.",
        ])
        tail = rnd.choice(["", "", "فعلاً نوسان بالاست و برگشت‌های ناگهانی هم ممکنه.", "باید دید پایین این سطح می‌مونه یا نه.",
                           "هنوز زوده که بشه گفت ادامه‌دار می‌شه."])
    elif kind == "bull_move":
        head = rnd.choice([f"🎯 آپدیت {t}", f"🎯 خبر تازه از {t}"])
        body = rnd.choice([
            f"{ago} تا الان حدود {n}٪ {up}، ولی هنوز کندل روزانه‌ای بالای {bull} بسته نشده و سطح کلیدی تأیید نشده.",
            f"قیمت {ago.replace('از ', 'نسبت به ', 1)} حدود {n}٪ {up}. فقط هنوز کندل روزانه بالای {bull} نبسته، پس تأییدی در کار نیست.",
        ])
        tail = ""
    else:
        head = rnd.choice([f"⚠️ آپدیت {t}", f"⚠️ خبر تازه از {t}"])
        body = rnd.choice([
            f"{ago} تا الان حدود {n}٪ {down}، ولی هنوز کندل روزانه‌ای زیر {bear} بسته نشده و سطح کلیدی تأیید نشده.",
            f"قیمت {ago.replace('از ', 'نسبت به ', 1)} حدود {n}٪ {down}. فقط هنوز کندل روزانه زیر {bear} نبسته، پس تأییدی در کار نیست.",
        ])
        tail = ""
    parts = [head, body] + ([tail] if tail else [])
    return "\n".join(parts) + "\nصرفاً تحلیل می‌باشد، سیگنال خرید و فروش نیست.\n@Mr_marketcap"


def run(now=None, fetch=get, send=None):
    now = int(now or time.time())
    rows = list(csv.DictReader(open(LOG, encoding="utf-8")))
    today = dt.datetime.utcfromtimestamp(now).date()
    cands = []
    for r in rows:
        if r["status"] != "open":
            continue
        if (today - dt.datetime.strptime(r["date"], "%Y-%m-%d").date()).days > MAX_AGE_DAYS:
            r["status"] = "closed"
            continue
        try:
            res = events_for(r, now, fetch)
        except Exception as e:
            print(r["ticker"], "skipped:", e)
            continue
        if res is None:
            print(r["ticker"], "price stale or missing; skipped")
            continue
        ev, last, pct, price = res
        print(r["ticker"], f"{pct:+.1f}%", ev or "no event")
        if ev:
            cands.append((abs(pct), r, ev, last, pct))
    cands.sort(key=lambda c: -c[0])
    out = []
    for _, r, ev, last, pct in cands[:MAX_REPLIES]:
        txt = text_for(r, ev, last, pct, now)
        print("--- reply to", r["message_id"], "\n" + txt)
        out.append((r["ticker"], txt))
        if DRY:
            continue
        sent = send(r["message_id"], txt) if send else tg_send(r["message_id"], txt)
        if sent == "gone":
            r["status"] = "closed"
            continue
        r["reported"] = "|".join(sorted(set(filter(None, r["reported"].split("|"))) | set(ev)))
        if {"bull", "bear"} <= set(r["reported"].split("|")):
            r["status"] = "closed"
    if not DRY:
        with open(LOG, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    return out


def tg_send(reply_to, text):
    import requests, html
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from tgfmt import bold_first
    htext = bold_first(text)      # first line bold + RTL mark on every line
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                      json={"chat_id": CHAT, "text": htext, "parse_mode": "HTML", "reply_to_message_id": int(reply_to),
                            "disable_notification": True}, timeout=30)
    if r.status_code == 400 and "not found" in r.text.lower():
        return "gone"
    r.raise_for_status()
    print("sent reply", r.json()["result"]["message_id"])
    return "ok"


if __name__ == "__main__":
    run()
