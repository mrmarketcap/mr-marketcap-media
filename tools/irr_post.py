"""Free-market US dollar price in Iran (toman) for @Mr_marketcap. One silent post per day.
Source: TGJU public JSON, cross-checked against AlanChand (must agree within 2%) before posting.
Env: TELEGRAM_BOT_TOKEN (not needed with DRY_RUN=1). State: irr-state.json
"""
import datetime as dt, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "irr-state.json")
CHAT = "@Mr_marketcap"
DRY = os.environ.get("DRY_RUN") == "1"
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
DIG = str.maketrans("0123456789,.", "۰۱۲۳۴۵۶۷۸۹٬٫")
FROM = str.maketrans("۰۱۲۳۴۵۶۷۸۹٬", "0123456789,")


def pdig(x):
    return str(x).translate(DIG)


def sources():
    import requests
    d = requests.get("https://call2.tgju.org/ajax.json", headers=H, timeout=25).json()
    e = d["current"]["price_dollar_rl"]
    tgju = int(e["p"].replace(",", "")) // 10          # rial -> toman
    html = requests.get("https://alanchand.com/currencies-price/usd", headers=H, timeout=25).text
    m = re.search(r"[۰-۹]{3},[۰-۹]{3}", html)
    alan = int(m.group(0).translate(FROM).replace(",", "")) if m else None
    return tgju, alan, e.get("ts")


def run(fetch=sources, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    day = now.strftime("%Y-%m-%d")
    try:
        s = json.load(open(STATE))
    except FileNotFoundError:
        s = {}
    if s.get("date") == day:
        print("already posted for", day)
        return None
    tgju, alan, ts = fetch()
    print("tgju", tgju, ts, "alanchand", alan)
    if not alan or abs(tgju / alan - 1) > 0.02:
        print("sources missing or disagree; skipped")
        return None
    price = round((tgju + alan) / 2, -2)          # average of the two, nearest 100 toman
    prev = s.get("price")
    ch = (price / prev - 1) * 100 if prev else None
    tone = "flat" if ch is None or abs(ch) < 0.05 else ("up" if ch > 0 else "down")
    big = f"{int(price):,}"
    sub = "تومان" if ch is None else f"تومان · {ch:+.1f}% نسبت به دیروز" if tone != "flat" else "تومان · تقریباً بدون تغییر"
    emoji = {"up": "🟢", "down": "🔴", "flat": "🟠"}[tone]
    cap = f"{emoji} دلار آزاد: {pdig(big)} تومان @Mr_marketcap"
    print(cap, "|", sub)
    if DRY:
        return cap
    out = os.path.join(ROOT, "alerts", "irr", f"usd-{day}.jpg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "irr_banner.py"), "دلار آزاد", big, sub, tone, out], check=True)
    import requests
    with open(out, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendPhoto",
                          data={"chat_id": CHAT, "caption": cap, "disable_notification": "true"},
                          files={"photo": f}, timeout=60)
    r.raise_for_status()
    print("sent", r.json()["result"]["message_id"])
    json.dump({"date": day, "price": price}, open(STATE, "w"))
    return cap


if __name__ == "__main__":
    run()
