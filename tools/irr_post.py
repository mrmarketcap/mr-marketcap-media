"""Free-market US dollar, 18k gold gram and Emami coin in Iran (toman), one text post, no banner for @Mr_marketcap. One silent post per day.
Source: TGJU public JSON, cross-checked against AlanChand (must agree within 2%) before posting.
Env: TELEGRAM_BOT_TOKEN (not needed with DRY_RUN=1). State: irr-state.json
"""
import datetime as dt, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tgfmt import bold_first
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
        if not b or abs(a / b - 1) > 0.02:        # AlanChand is live; TGJU may lag
            print(k, "sources missing or disagree; skipped")
            continue
        price[k] = round(b / STEP[k]) * STEP[k]      # live AlanChand value; TGJU only sanity-checks it
        old = s.get("prices", {}).get(k)
        ch[k] = (price[k] / old - 1) * 100 if old else None
    if "usd" not in price:
        print("no dollar price; nothing posted")
        return None
    def line(emoji_name, k):
        c = ch.get(k)
        mark = "🟠" if c is None or abs(c) < 0.05 else ("🟢" if c > 0 else "🔴")
        tail = "" if c is None else (" (تقریباً بدون تغییر)" if abs(c) < 0.05 else f" ({pdig(format(abs(c), '.1f'))}٪ {'بالاتر' if c > 0 else 'پایین‌تر'} از دیروز)")
        return f"{mark} {emoji_name}: {pdig(format(price[k], ','))}{tail}"
    lines = ["💵 قیمت امروز بازار آزاد", line("دلار", "usd")]
    if "gold18" in price:
        lines.append(line("طلای ۱۸ عیار", "gold18"))
    if "coin" in price:
        lines.append(line("سکه امامی", "coin"))
    text = "\n".join(lines) + "\n@Mr_marketcap"
    print(text)
    if DRY:
        return text
    import requests
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                      data={"chat_id": CHAT, "text": bold_first(text), "parse_mode": "HTML", "disable_notification": "true"}, timeout=60)
    r.raise_for_status()
    print("sent", r.json()["result"]["message_id"])
    prices = dict(s.get("prices", {}))
    prices.update(price)
    json.dump({"date": day, "prices": prices}, open(STATE, "w"))
    return text


if __name__ == "__main__":
    run()
