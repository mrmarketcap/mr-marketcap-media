"""Weekly free-market dollar poll (toman) for @Mr_marketcap, same idea as the BTC poll.
Monday: stop last week's poll and reply under it with the outcome, then open a new poll.
Env: TELEGRAM_BOT_TOKEN (not needed with DRY_RUN=1). State: usd-poll-state.json
"""
import datetime as dt, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tgfmt import bold_first
import irr_post

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "usd-poll-state.json")
CHAT = "@Mr_marketcap"
DRY = os.environ.get("DRY_RUN") == "1"
pdig = irr_post.pdig


def tg(method, **data):
    import requests
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/{method}", data=data, timeout=60)
    r.raise_for_status()
    return r.json()["result"]


def usd_now(fetch=irr_post.sources):
    a, b = fetch()["usd"]
    if not b or abs(a / b - 1) > 0.03:
        return None
    return round(b / 1000) * 1000          # live AlanChand value, TGJU only sanity-checks it


def run(now=None, price_fn=usd_now):
    now = int(now or time.time())
    try:
        s = json.load(open(STATE))
    except FileNotFoundError:
        s = {}
    day = dt.datetime.utcfromtimestamp(now).strftime("%Y-%m-%d")
    if s.get("date") == day:
        print("already handled for", day)
        return None
    price = price_fn()
    if not price:
        print("dollar price missing or sources disagree; skipped")
        return None
    old = s.get("poll")
    lines = []
    if old and now - old["ts"] >= 5 * 86400:
        ch = (price / old["price"] - 1) * 100
        up = price > old["price"]
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
        text = ("📊 نتیجهٔ نظرسنجی دلار هفتهٔ پیش\n"
                f"قیمت دلار موقع نظرسنجی {pdig(format(old['price'], ','))} تومان بود و الان {pdig(format(price, ','))} تومانه "
                f"({pdig(format(abs(ch), '.1f'))}٪ {word})، پس جواب «{word}» درست بود.{share}\n@Mr_marketcap")
        lines.append(text)
        if not DRY:
            tg("sendMessage", chat_id=CHAT, text=bold_first(text), parse_mode="HTML",
               reply_to_message_id=old["msg"], disable_notification="true")
    question = f"تا دوشنبهٔ بعد، دلار بالاتر از {pdig(format(price, ','))} تومان هست؟"
    lines.append("new poll: " + question)
    print("\n".join(lines))
    if DRY:
        return lines
    res = tg("sendPoll", chat_id=CHAT, question=question,
             options=json.dumps(["آره، بالاتر", "نه، پایین‌تر"], ensure_ascii=False),
             is_anonymous="true", disable_notification="true")
    json.dump({"date": day, "poll": {"msg": res["message_id"], "price": price, "ts": now}}, open(STATE, "w"))
    return lines


if __name__ == "__main__":
    run()
