"""Watchdog for the free automations: sends the owner a PRIVATE Telegram message when something is broken.
Env: GITHUB_TOKEN, GITHUB_REPOSITORY, TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID (owner's own chat with the bot).
DRY_RUN=1 prints only. State: watchdog-state.json (problem key -> last alert time).
"""
import datetime as dt, json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "watchdog-state.json")
DRY = os.environ.get("DRY_RUN") == "1"
NAMES = {"price-alerts.yml": "هشدار قیمت BTC/ETH", "market-alerts.yml": "پست‌های بازار (ترس و طمع، جابه‌جایی، خلاصه، رکورد، نظرسنجی)",
         "channel-tasks.yml": "پاسخ تحلیل‌ها و یوتیوب", "irr-post.yml": "قیمت دلار، طلا و سکه"}
REPEAT_H = 6
PAT_EXPIRES = dt.date(2027, 1, 20)


def jload(name, default):
    try:
        return json.load(open(os.path.join(ROOT, name)))
    except Exception:
        return default


def gh_runs(wf):
    import requests
    r = requests.get(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/{wf}/runs?per_page=10",
                     headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"}, timeout=30)
    r.raise_for_status()
    return r.json()["workflow_runs"]


def problems(now, runs_for=gh_runs):
    """Returns {key: message}. now is an aware UTC datetime."""
    out = {}
    today = now.strftime("%Y-%m-%d")
    for wf, name in NAMES.items():
        try:
            runs = runs_for(wf)
        except Exception as e:
            out[f"api-{wf}"] = f"⚠️ نگهبان نتونست وضعیت «{name}» رو از گیت‌هاب بخونه ({str(e)[:80]})."
            continue
        done = [r for r in runs if r["status"] == "completed"][:3]
        if len(done) == 3 and all(r["conclusion"] != "success" for r in done):
            out[f"fail-{wf}"] = f"⚠️ «{name}» سه بار پشت‌سرهم خطا داده.\n{done[0]['html_url']}"
        if wf == "price-alerts.yml" and runs:
            last = dt.datetime.fromisoformat(runs[0]["created_at"].replace("Z", "+00:00"))
            mins = (now - last).total_seconds() / 60
            if mins > 25:
                out["stale-price"] = (f"⚠️ هشدار قیمت BTC/ETH حدود {int(mins)} دقیقه است اجرا نشده. "
                                      "احتمالاً سرور کلودفلر یا توکن گیت‌هاب مشکل داره.")
    ms, irr = jload("market-state.json", {}), jload("irr-state.json", {})
    h = now.hour + now.minute / 60
    if h >= 10.5 and ms.get("fng_date") != today:
        out["daily-fng"] = "⚠️ پست ترس و طمع امروز هنوز نرفته."
    if h >= 15.5 and ms.get("summary_date") != today:
        out["daily-summary"] = "⚠️ خلاصهٔ روزانهٔ بازار امروز هنوز نرفته."
    if h >= 10.5 and irr.get("date") != today:
        out["daily-irr"] = "⚠️ قیمت دلار، طلا و سکهٔ امروز هنوز نرفته (شاید دو منبع قیمت با هم نخونن)."
    if (PAT_EXPIRES - now.date()).days <= 14:
        out["pat"] = f"⏰ توکن گیت‌هاب (برای سرور کلودفلر) تا {PAT_EXPIRES} تموم می‌شه. قبلش یکی جدید بساز و جایگزین کن."
    return out


def send(text):
    import requests
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                      data={"chat_id": os.environ["TELEGRAM_OWNER_CHAT_ID"], "text": text}, timeout=30)
    r.raise_for_status()


def run(now=None, runs_for=gh_runs):
    now = now or dt.datetime.now(dt.timezone.utc)
    st = jload("watchdog-state.json", {})
    cur = problems(now, runs_for)
    lines = []
    for k, msg in cur.items():
        last = st.get(k)
        age = (now - dt.datetime.fromisoformat(last)).total_seconds() / 3600 if last else None
        gap = 24 if k == "pat" else REPEAT_H
        if age is None or age >= gap:
            lines.append(msg)
            st[k] = now.isoformat()
    fixed = [k for k in list(st) if k not in cur]
    for k in fixed:
        del st[k]
    if fixed and not cur:
        lines.append("✅ نگهبان: همهٔ مشکل‌های قبلی برطرف شد.")
    print("problems:", list(cur) or "none")
    if lines:
        text = "\n\n".join(lines)
        print(text)
        if not DRY and os.environ.get("TELEGRAM_OWNER_CHAT_ID"):
            send(text)
        elif not DRY:
            print("TELEGRAM_OWNER_CHAT_ID not set; not sent")
    if not DRY:
        json.dump(st, open(STATE, "w"), indent=1)
    return lines


if __name__ == "__main__":
    run()
