"""Weekly economic calendar (US high-impact events only), times in Tehran time (UTC+3:30), one silent text post on Mondays for @Mr_marketcap.
Source: ForexFactory public weekly JSON. Env: TELEGRAM_BOT_TOKEN (not needed with DRY_RUN=1). State: calendar-state.json
"""
import datetime as dt, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tgfmt import bold_first
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "calendar-state.json")
CHAT = "@Mr_marketcap"
DRY = os.environ.get("DRY_RUN") == "1"
URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
TEHRAN = dt.timezone(dt.timedelta(hours=3, minutes=30))
DIG = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
WEEKDAY = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
MONTH = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]

# English event title (lowercase, substring) -> Persian label. Events not listed are skipped.
LABELS = [
    ("core cpi", "تورم مصرف‌کننده آمریکا (CPI)"), ("cpi", "تورم مصرف‌کننده آمریکا (CPI)"),
    ("core pce", "تورم PCE آمریکا"), ("pce", "تورم PCE آمریکا"),
    ("ppi", "تورم تولیدکننده آمریکا (PPI)"),
    ("federal funds rate", "تصمیم نرخ بهره فدرال رزرو"), ("fomc statement", "تصمیم نرخ بهره فدرال رزرو"),
    ("fomc meeting minutes", "صورت‌جلسهٔ فدرال رزرو"), ("fomc press conference", "نشست خبری رئیس فدرال رزرو"),
    ("fed chair", "سخنرانی رئیس فدرال رزرو"),
    ("non-farm", "گزارش اشتغال آمریکا (NFP)"), ("unemployment rate", "گزارش اشتغال آمریکا (NFP)"),
    ("average hourly earnings", "گزارش اشتغال آمریکا (NFP)"),
    ("gdp", "رشد اقتصادی آمریکا (GDP)"), ("retail sales", "فروش خرده‌فروشی آمریکا"),
    ("ism manufacturing", "شاخص تولید ISM آمریکا"), ("ism services", "شاخص خدمات ISM آمریکا"),
]


def pd(x):
    return str(x).translate(DIG)


def to_jalali(gy, gm, gd):
    g_d = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + g_d[gm - 1]
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


def label(title):
    t = title.lower()
    for key, fa in LABELS:
        if key in t:
            return fa
    return None


def fetch():
    import requests
    return requests.get(URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"}).json()


def build(data):
    seen, by_day = set(), {}
    for e in data:
        if e.get("country") != "USD" or e.get("impact") != "High":
            continue
        fa = label(e.get("title", ""))
        if not fa:
            continue
        t = dt.datetime.fromisoformat(e["date"]).astimezone(TEHRAN)
        if (t, fa) in seen:
            continue
        seen.add((t, fa))
        by_day.setdefault(t.date(), []).append((t, fa))
    if not by_day:
        return None
    out = ["🗓 رویدادهای مهم اقتصادی این هفته", ""]
    for day in sorted(by_day):
        jy, jm, jd = to_jalali(day.year, day.month, day.day)
        out.append(f"{WEEKDAY[day.weekday()]} {pd(jd)} {MONTH[jm - 1]}")
        for t, fa in sorted(by_day[day]):
            out.append(f"🇺🇸 {fa} | ساعت {pd(t.strftime('%H:%M'))}")
        out.append("")
    out.append("⏰ همهٔ ساعت‌ها به وقت تهران")
    out.append("💡 روزهایی که این گزارش‌ها میان، نوسان بازار معمولاً بیشتر می‌شه.")
    out.append("@Mr_marketcap")
    return "\n".join(out)


def run(now=None, data=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    wk = now.strftime("%G-W%V")
    try:
        s = json.load(open(STATE))
    except FileNotFoundError:
        s = {}
    if s.get("week") == wk:
        print("already posted for", wk)
        return None
    text = build(data if data is not None else fetch())
    if not text:
        print("no major events this week; nothing posted")
        return None
    print(text)
    if DRY:
        return text
    import requests
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                      data={"chat_id": CHAT, "text": bold_first(text), "parse_mode": "HTML", "disable_notification": "true"}, timeout=60)
    r.raise_for_status()
    print("sent", r.json()["result"]["message_id"])
    json.dump({"week": wk}, open(STATE, "w"))
    return text


if __name__ == "__main__":
    run()
