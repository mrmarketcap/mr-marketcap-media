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
FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
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


def text_for(row, ev, last, pct, now):
    t = row["ticker"]
    days = (dt.datetime.utcfromtimestamp(now).date() - dt.datetime.strptime(row["date"], "%Y-%m-%d").date()).days
    p0 = fa(row["price_at_post"])
    n = fa(abs(round(pct)))
    kind = last if ("bull" in ev or "bear" in ev) else ("bull_move" if "up20" in ev else "bear_move")
    if kind == "bull":
        body = (f"🎯 آپدیت {t}\nاز تحلیل {fa(days)} روز پیش (قیمت اون موقع {p0}) تا الان حدود {n}٪ "
                f"{'رشد' if pct >= 0 else 'تغییر'} داشته و کندل روزانه بالای {fa(row['bull_trigger'])} بسته شده، "
                f"یعنی سناریوی صعودی فعال شد.\nنوسان هنوز بالاست و ممکنه وضعیت سریع عوض بشه.")
    elif kind == "bear":
        body = (f"⚠️ آپدیت {t}\nاز تحلیل {fa(days)} روز پیش (قیمت اون موقع {p0}) تا الان حدود {n}٪ "
                f"{'ریزش' if pct <= 0 else 'تغییر'} داشته و کندل روزانه زیر {fa(row['bear_trigger'])} بسته شده، "
                f"یعنی سناریوی نزولی فعال شد.\nنوسان هنوز بالاست و ممکنه وضعیت سریع عوض بشه.")
    elif kind == "bull_move":
        body = (f"🎯 آپدیت {t}\nاز تحلیل {fa(days)} روز پیش (قیمت اون موقع {p0}) تا الان حدود {n}٪ رشد کرده، "
                f"ولی هنوز کندل روزانه‌ای بالای {fa(row['bull_trigger'])} بسته نشده و سطح کلیدی تأیید نشده.")
    else:
        body = (f"⚠️ آپدیت {t}\nاز تحلیل {fa(days)} روز پیش (قیمت اون موقع {p0}) تا الان حدود {n}٪ ریزش داشته، "
                f"ولی هنوز کندل روزانه‌ای زیر {fa(row['bear_trigger'])} بسته نشده و سطح کلیدی تأیید نشده.")
    return body + "\n@Mr_marketcap"


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
    import requests
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                      json={"chat_id": CHAT, "text": text, "reply_to_message_id": int(reply_to),
                            "disable_notification": True}, timeout=30)
    if r.status_code == 400 and "not found" in r.text.lower():
        return "gone"
    r.raise_for_status()
    print("sent reply", r.json()["result"]["message_id"])
    return "ok"


if __name__ == "__main__":
    run()
