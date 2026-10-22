"""Replies under the weekly calendar post with the US CPI / jobs-report result as soon as BLS publishes it, plus a short market-impact note.
Source: BLS public API v1 (official, free, no key). State: calendar-state.json ("events" list written by calendar_post.py)
Env: TELEGRAM_BOT_TOKEN (not needed with DRY_RUN=1).
"""
import datetime as dt, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tgfmt import bold_first

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "calendar-state.json")
CHAT = "@Mr_marketcap"
DRY = os.environ.get("DRY_RUN") == "1"
DIG = str.maketrans("0123456789.", "۰۱۲۳۴۵۶۷۸۹٫")
SERIES = {"cpi_sa": "CUSR0000SA0", "cpi_nsa": "CUUR0000SA0", "jobs": "CES0000000001", "unemp": "LNS14000000"}


def pd(x):
    return str(x).translate(DIG)


def series(code, fetch=None):
    """Newest-first list of (period 'YYYY-Mxx', float value)."""
    import requests
    j = (fetch or (lambda u: requests.get(u, timeout=30).json()))(f"https://api.bls.gov/publicAPI/v1/timeseries/data/{code}")
    rows = j["Results"]["series"][0]["data"]
    return [(f"{r['year']}-{r['period']}", float(r["value"])) for r in rows if r["period"].startswith("M") and r["period"] != "M13"]


def latest_period(kind, fetch=None):
    code = SERIES["cpi_sa"] if kind == "cpi" else SERIES["jobs"]
    return series(code, fetch)[0][0]


def num(s):
    """'0.3%' -> 0.3 ; '150K' -> 150 ; '' -> None"""
    m = re.search(r"-?\d+(?:\.\d+)?", s or "")
    return float(m.group(0)) if m else None


def cmp(actual, forecast):
    if forecast is None:
        return "na"
    return "above" if actual > forecast else ("below" if actual < forecast else "inline")


CPI_IMPACT = {
    "above": "تورم بالاتر از انتظار بوده، یعنی فدرال رزرو برای کم‌کردن نرخ بهره کمتر جا داره. معمولاً به سهام و کریپتو و طلا فشار میاره و دلار رو قوی‌تر می‌کنه.",
    "below": "تورم پایین‌تر از انتظار بوده، یعنی فدرال رزرو برای کم‌کردن نرخ بهره راحت‌تره. معمولاً به نفع سهام و کریپتو و طلاست و دلار رو ضعیف‌تر می‌کنه.",
    "inline": "عدد هم‌راستا با انتظار بوده، پس شوک بزرگی نیست و واکنش بازار معمولاً کوچیک‌تره.",
    "na": "اثر روی بازارها بیشتر به فاصلهٔ عدد با انتظار بازار بستگی داره؛ تورم بالاتر معمولاً به دلار کمک می‌کنه و تورم پایین‌تر معمولاً به سهام و کریپتو و طلا.",
}
JOBS_IMPACT = {
    "above": "بازار کار قوی‌تر از انتظار بوده، یعنی احتمال کم‌کردن نرخ بهره کمتر می‌شه. معمولاً دلار قوی‌تر می‌شه و به طلا و کریپتو فشار میاد؛ سهام گاهی بالا می‌ره چون اقتصاد قویه و گاهی پایین چون نرخ بهره بالا می‌مونه.",
    "below": "بازار کار ضعیف‌تر از انتظار بوده، یعنی احتمال کم‌کردن نرخ بهره بیشتر می‌شه. معمولاً به نفع طلا و کریپتو و ضعیف‌تر شدن دلاره؛ فقط اگه خیلی ضعیف باشه، نگرانی از رکود به سهام فشار میاره.",
    "inline": "عدد هم‌راستا با انتظار بوده، پس شوک بزرگی نیست و واکنش بازار معمولاً کوچیک‌تره.",
    "na": "اثر روی بازارها بیشتر به فاصلهٔ عدد با انتظار بازار بستگی داره؛ بازار کار قوی معمولاً دلار رو قوی‌تر می‌کنه و بازار کار ضعیف معمولاً به نفع طلا و کریپتوئه.",
}


def cpi_text(ev, fetch=None):
    sa, nsa = series(SERIES["cpi_sa"], fetch), series(SERIES["cpi_nsa"], fetch)
    mm = round((sa[0][1] / sa[1][1] - 1) * 100, 1)
    yy = round((nsa[0][1] / nsa[12][1] - 1) * 100, 1)
    f = num(ev.get("forecast"))
    c = cmp(mm, f)
    head = f"تورم ماهانه {pd(mm)}٪ شد" + (f" (پیش‌بینی {pd(f)}٪)" if f is not None else "") + f" و تورم سالانه {pd(yy)}٪."
    return f"📈 نتیجهٔ تورم آمریکا (CPI)\n{head}\n\n📌 اثر روی بازارها\n{CPI_IMPACT[c]}\n@Mr_marketcap", sa[0][0]


def jobs_text(ev, fetch=None):
    j, u = series(SERIES["jobs"], fetch), series(SERIES["unemp"], fetch)
    ch = round(j[0][1] - j[1][1])
    f = num(ev.get("forecast"))
    c = cmp(ch, f)
    sign = "+" if ch >= 0 else "-"
    line1 = f"شاغلان غیرکشاورزی {sign}{pd(format(abs(ch), ','))} هزار نفر" + (f" (پیش‌بینی {pd(format(int(f), ','))} هزار)" if f is not None else "") + " و "
    uf = num(ev.get("u_forecast"))
    line1 += f"نرخ بیکاری {pd(u[0][1])}٪" + (f" (پیش‌بینی {pd(uf)}٪)" if uf is not None else "") + "."
    return f"👷 نتیجهٔ گزارش اشتغال آمریکا\n{line1}\n\n📌 اثر روی بازارها\n{JOBS_IMPACT[c]}\n@Mr_marketcap", j[0][0]


def run(now=None, fetch=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        s = json.load(open(STATE))
    except FileNotFoundError:
        return []
    out, changed = [], False
    for ev in s.get("events", []):
        if ev.get("replied") or not s.get("msg") or not ev.get("base"):
            continue
        t0 = dt.datetime.strptime(ev["utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        if not (t0 - dt.timedelta(minutes=5) <= now <= t0 + dt.timedelta(hours=8)):
            continue
        try:
            if latest_period(ev["kind"], fetch) == ev["base"]:
                print(ev["kind"], "not published yet")
                continue
            text, _ = (cpi_text if ev["kind"] == "cpi" else jobs_text)(ev, fetch)
        except Exception as e:
            print(ev["kind"], "failed:", e)
            continue
        print(text)
        out.append(text)
        if DRY:
            continue
        import requests
        r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                          data={"chat_id": CHAT, "text": bold_first(text), "parse_mode": "HTML",
                                "reply_to_message_id": s["msg"], "disable_notification": "true"}, timeout=30)
        r.raise_for_status()
        print("sent", r.json()["result"]["message_id"])
        ev["replied"] = True
        changed = True
    if changed:
        json.dump(s, open(STATE, "w"))
    return out


if __name__ == "__main__":
    if os.environ.get("ECON_SELFTEST"):
        print(cpi_text({"forecast": "0.3%"})[0])
        print(jobs_text({"forecast": "150K", "u_forecast": "4.2%"})[0])
    else:
        run()
