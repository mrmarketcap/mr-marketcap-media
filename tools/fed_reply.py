"""Reply under the weekly calendar post with the Fed rate decision as soon as the FOMC statement is out.
Source: federalreserve.gov monetary-policy RSS + the statement page. Env: TELEGRAM_BOT_TOKEN (not needed with DRY_RUN=1).
State: calendar-state.json (written by calendar_post.py: msg, fed_utc; this script adds fed_replied)
"""
import datetime as dt, email.utils, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tgfmt import bold_first

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "calendar-state.json")
CHAT = "@Mr_marketcap"
DRY = os.environ.get("DRY_RUN") == "1"
RSS = "https://www.federalreserve.gov/feeds/press_monetary.xml"
H = {"User-Agent": "Mozilla/5.0"}
DIG = str.maketrans("0123456789.", "۰۱۲۳۴۵۶۷۸۹٫")


def frac(s):
    """'3-1/2' -> 3.5, '4' -> 4.0, '3-3/4' -> 3.75, '1/4' -> 0.25"""
    m = re.fullmatch(r"(?:(\d+)-)?(?:(\d+)/(\d+))?", s.strip())
    if m and (m.group(1) or m.group(2)):
        return float(m.group(1) or 0) + (int(m.group(2)) / int(m.group(3)) if m.group(2) else 0)
    return float(s)


def parse(text):
    """Returns (action, low, high) from the FOMC statement text; action in maintain/lower/raise."""
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).replace("&#8209;", "-").replace("‑", "-").replace("‐", "-")
    m = re.search(r"decided to (maintain|lower|raise)[^.]*?target range for the federal funds rate(?: by [^.]*?)?(?: (?:at|to)) "
                  r"([\d\-/]+) to ([\d\-/]+) percent", t)
    if not m:
        return None
    return m.group(1), frac(m.group(2)), frac(m.group(3))


def fmt(x):
    return format(x, ".2f").translate(DIG)


def reply_text(action, low, high):
    rng = f"بین {fmt(low)} تا {fmt(high)} درصد"
    if action == "maintain":
        body = f"نرخ بهره بدون تغییر موند و همچنان {rng}ه."
    elif action == "lower":
        body = f"نرخ بهره کاهش پیدا کرد و الان {rng}ه."
    else:
        body = f"نرخ بهره افزایش پیدا کرد و الان {rng}ه."
    return f"🏛 نتیجهٔ تصمیم فدرال رزرو\n{body}\n@Mr_marketcap"


def get(url):
    import requests
    r = requests.get(url, headers=H, timeout=30)
    r.raise_for_status()
    return r.text


def find_statement(rss_xml, after):
    for item in re.findall(r"<item>(.*?)</item>", rss_xml, flags=re.S):
        title = re.search(r"<title>(.*?)</title>", item, flags=re.S).group(1)
        if "FOMC statement" not in title:
            continue
        link = re.search(r"<link><!\[CDATA\[(.*?)\]\]></link>", item).group(1)
        pub = email.utils.parsedate_to_datetime(re.search(r"<pubDate><!\[CDATA\[(.*?)\]\]></pubDate>", item).group(1))
        if pub >= after:
            return link
    return None


def run(now=None, fetch=get):
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        s = json.load(open(STATE))
    except FileNotFoundError:
        return None
    if not s.get("fed_utc") or not s.get("msg") or s.get("fed_replied"):
        return None
    t0 = dt.datetime.strptime(s["fed_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    if not (t0 - dt.timedelta(minutes=5) <= now <= t0 + dt.timedelta(hours=8)):
        return None
    link = find_statement(fetch(RSS), t0 - dt.timedelta(hours=2))
    if not link:
        print("FOMC statement not out yet")
        return None
    res = parse(fetch(link))
    if not res:
        print("could not parse statement", link)
        return None
    text = reply_text(*res)
    print(text)
    if DRY:
        return text
    import requests
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                      data={"chat_id": CHAT, "text": bold_first(text), "parse_mode": "HTML",
                            "reply_to_message_id": s["msg"], "disable_notification": "true"}, timeout=30)
    r.raise_for_status()
    print("sent", r.json()["result"]["message_id"])
    s["fed_replied"] = True
    json.dump(s, open(STATE, "w"))
    return text


if __name__ == "__main__":
    if os.environ.get("FED_SELFTEST"):
        res = parse(get("https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm"))
        print("selftest:", res, reply_text(*res) if res else None)
    else:
        run()
