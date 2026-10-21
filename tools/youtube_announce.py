"""Announce a new long-form YouTube video in @Mr_marketcap (free replacement for the Claude task).

Uses the channel RSS feed. Skips Shorts, videos older than 6 hours, and anything already in
youtube-posted.csv. Env: TELEGRAM_BOT_TOKEN (not needed with DRY_RUN=1).
"""
import csv, datetime as dt, html, http.client, os, re, sys, urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "youtube-posted.csv")
CHANNEL = "UCcHXsOPT4wACJI4hVh-zpTA"
CHAT = "@Mr_marketcap"
MAX_AGE = 6 * 3600
DRY = os.environ.get("DRY_RUN") == "1"
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "m": "http://search.yahoo.com/mrss/"}


def feed(url=f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL}"):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=20).read())
    out = []
    for e in root.findall("a:entry", NS):
        out.append({
            "id": e.find("yt:videoId", NS).text,
            "title": e.find("a:title", NS).text,
            "published": e.find("a:published", NS).text,
            "url": e.find("a:link", NS).attrib["href"],
            "desc": (e.find("m:group/m:description", NS).text or "") if e.find("m:group/m:description", NS) is not None else "",
        })
    return out


def is_short(vid):
    """True/False, or None if the check failed. /shorts/<id> answers 200 for Shorts, redirects otherwise."""
    try:
        c = http.client.HTTPSConnection("www.youtube.com", timeout=15)
        c.request("HEAD", f"/shorts/{vid}", headers={"User-Agent": "Mozilla/5.0"})
        s = c.getresponse().status
        return True if s == 200 else False if s in (301, 302, 303, 307, 308) else None
    except Exception:
        return None


def teaser(desc, limit=300):
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n", desc) if p.strip()]
    keep = []
    for p in paras:
        if re.search(r"https?://|^#|\d{1,2}:\d{2}|@\w+", p):
            continue
        keep.append(p)
        if len(" ".join(keep)) >= 120:
            break
    t = " ".join(keep)
    if len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0] + "…"
    return t


def caption(v):
    t = teaser(v["desc"])
    parts = [f"<b>{html.escape(v['title'])}</b>", ""]
    if t:
        parts += [f"<blockquote>{html.escape(t)}</blockquote>"]
    parts += [f'<b><a href="{html.escape(v["url"])}">⏯️ تماشا در یوتیوب</a></b>', "", "@Mr_marketcap"]
    return "\n".join(parts)


def run(now=None, get_feed=feed, short_check=is_short):
    now = now or dt.datetime.now(dt.timezone.utc)
    seen = {r["video_id"] for r in csv.DictReader(open(LOG, encoding="utf-8"))}
    out = []
    for v in sorted(get_feed(), key=lambda x: x["published"]):
        age = (now - dt.datetime.fromisoformat(v["published"])).total_seconds()
        if v["id"] in seen or age > MAX_AGE or age < -300:
            continue
        s = short_check(v["id"])
        if s is not False:
            print(v["id"], "short or unknown:", s)
            continue
        cap = caption(v)
        print("NEW VIDEO", v["id"], "\n" + cap)
        out.append(v)
        if DRY:
            continue
        mid = tg_post(v, cap)
        with open(LOG, "a", newline="", encoding="utf-8") as f:
            csv.writer(f, lineterminator="\n").writerow(
                [v["id"], v["published"], v["title"].replace(",", "،"), mid, now.strftime("%Y-%m-%dT%H:%M:%SZ")])
    if not out:
        print("no new long video")
    return out


def tg_post(v, cap):
    import requests
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    for q in ("maxresdefault", "hqdefault"):
        r = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto",
                          data={"chat_id": CHAT, "photo": f"https://i.ytimg.com/vi/{v['id']}/{q}.jpg",
                                "caption": cap, "parse_mode": "HTML"}, timeout=60)
        if r.ok:
            mid = r.json()["result"]["message_id"]
            print("sent", mid)
            return mid
        print("photo failed", q, r.text[:200])
    r.raise_for_status()


if __name__ == "__main__":
    run()
