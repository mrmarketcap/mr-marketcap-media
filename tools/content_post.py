"""Daily educational post for @Mr_marketcap from data/content_bank.json (written once, zero tokens at run time).
One silent text post per UTC day. Dated 'history' items are posted on their day (again every year);
other items go in bank order, each used once. State: content-state.json
Env: TELEGRAM_BOT_TOKEN (not needed with DRY_RUN=1).
"""
import datetime as dt, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "data", "content_bank.json")
STATE = os.path.join(ROOT, "content-state.json")
CHAT = "@Mr_marketcap"
DRY = os.environ.get("DRY_RUN") == "1"
HEAD = {"term": "📘 اصطلاح امروز", "tip": "💡 نکتهٔ مالی امروز", "psych": "🧠 دام ذهنی امروز"}
DIG = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def persian_numbers(t):
    t = re.sub(r"(?<=\d),(?=\d)", "٬", t)
    t = re.sub(r"(?<=\d)\.(?=\d)", "٫", t)
    t = t.replace("%", "٪")
    return t.translate(DIG)


def render(item):
    if item["type"] == "history":
        text = f"📅 {item['title']}\n\n{item['body']}"
    else:
        text = f"{HEAD[item['type']]}: {item['title']}\n\n{item['body']}"
    return persian_numbers(text) + "\n@Mr_marketcap"


def pick(bank, state, now):
    md = now.strftime("%m-%d")
    year = now.strftime("%Y")
    used = set(state.get("used", []))
    for it in bank:
        if it["type"] == "history" and it["date"] == md and f"{it['id']}@{year}" not in used:
            return it, f"{it['id']}@{year}"
    for it in bank:
        if it["type"] != "history" and it["id"] not in used:
            return it, it["id"]
    return None, None


def remaining(bank, state):
    used = set(state.get("used", []))
    return sum(1 for it in bank if it["type"] != "history" and it["id"] not in used)


def run(now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    day = now.strftime("%Y-%m-%d")
    bank = json.load(open(BANK))
    try:
        state = json.load(open(STATE))
    except FileNotFoundError:
        state = {"used": [], "last_date": ""}
    if state.get("last_date") == day:
        print("already posted for", day)
        return None
    it, key = pick(bank, state, now)
    if not it:
        print("bank exhausted; nothing posted")
        return None
    text = render(it)
    print(text)
    print("remaining after this:", remaining(bank, state) - (0 if it["type"] == "history" else 1))
    if DRY:
        return text
    import requests
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                      data={"chat_id": CHAT, "text": text, "disable_notification": "true"}, timeout=30)
    r.raise_for_status()
    print("sent", r.json()["result"]["message_id"])
    state["used"] = state.get("used", []) + [key]
    state["last_date"] = day
    json.dump(state, open(STATE, "w"), indent=1)
    return text


if __name__ == "__main__":
    run()
