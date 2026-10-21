"""Free-market US dollar, 18k gold gram and Emami coin in Iran (toman), one banner for @Mr_marketcap. One silent post per day.
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


def num(m):
    return int(m.group(1).translate(FROM).replace(",", ""))


def sources():
    """Returns {name: (tgju_toman, alanchand_toman)} for usd, gold18 (gram), coin (Emami)."""
    import requests
    d = requests.get("https://call2.tgju.org/ajax.json", headers=H, timeout=25).json()["current"]
    tg = {"usd": int(d["price_dollar_rl"]["p"].replace(",", "")) // 10,
          "gold18": int(d["geram18"]["p"].replace(",", "")) // 10,
          "coin": int(d["sekee"]["p"].replace(",", "")) // 10}
    out = {}
    html = requests.get("https://alanchand.com/currencies-price/usd", headers=H, timeout=25).text
    m = re.search(r"([۰-۹]{3},[۰-۹]{3})", html)
    out["usd"] = (tg["usd"], num(m) if m else None)
    g = requests.get("https://alanchand.com/gold-price", headers=H, timeout=25).text
    g = re.sub(r"<script.*?</script>|<style.*?</style>", "", g, flags=re.S)
    g = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", g))
    m = re.search(r"گرم طلای 18 عیار ([۰-۹]{2},[۰-۹]{3},[۰-۹]{3})", g)
    out["gold18"] = (tg["gold18"], num(m) if m else None)
    m = re.search(r"سکه امامی \(طرح جدید\) ([۰-۹]{3},[۰-۹]{3},[۰-۹]{3})", g)
    out["coin"] = (tg["coin"], num(m) if m else None)
    return out


STEP = {"usd": 100, "gold18": 1000, "coin": 100000}
LABEL = {"gold18": "طلای ۱۸ عیار (گرم)", "coin": "سکه امامی"}


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
    src = fetch()
    price, ch = {}, {}
    for k, (a, b) in src.items():
        print(k, "tgju", a, "alanchand", b)
        if not b or abs(a / b - 1) > 0.03:        # AlanChand is live; TGJU may lag
            print(k, "sources missing or disagree; skipped")
            continue
        price[k] = round((a + b) / 2 / STEP[k]) * STEP[k]
        old = s.get("prices", {}).get(k)
        ch[k] = (price[k] / old - 1) * 100 if old else None
    if "usd" not in price:
        print("no dollar price; nothing posted")
        return None
    c = ch["usd"]
    tone = "flat" if c is None or abs(c) < 0.05 else ("up" if c > 0 else "down")
    sub = "تومان" if c is None else (f"تومان · {c:+.1f}% نسبت به دیروز" if tone != "flat" else "تومان · تقریباً بدون تغییر")
    rows = [{"label": LABEL[k], "value": f"{price[k]:,}", "ch": ch[k]} for k in ("gold18", "coin") if k in price]
    emoji = {"up": "🟢", "down": "🔴", "flat": "🟠"}[tone]
    cap = f"{emoji} دلار آزاد: {pdig(format(price['usd'], ','))} تومان @Mr_marketcap"
    print(cap, "|", sub, "|", rows)
    if DRY:
        return cap
    out = os.path.join(ROOT, "alerts", "irr", f"usd-{day}.jpg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    data = {"big": f"{price['usd']:,}", "sub": sub, "tone": tone, "rows": rows}
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "irr_banner.py"), json.dumps(data, ensure_ascii=False), out], check=True)
    import requests
    with open(out, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendPhoto",
                          data={"chat_id": CHAT, "caption": cap, "disable_notification": "true"},
                          files={"photo": f}, timeout=60)
    r.raise_for_status()
    print("sent", r.json()["result"]["message_id"])
    prices = dict(s.get("prices", {}))
    prices.update(price)
    json.dump({"date": day, "prices": prices}, open(STATE, "w"))
    return cap


if __name__ == "__main__":
    run()
