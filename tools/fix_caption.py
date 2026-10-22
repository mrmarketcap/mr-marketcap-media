"""One-off: remove «وسط روز» and «چرا امروز؟» from an already published channel caption."""
import os, re, sys, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tgfmt import bold_first, RLM
T = os.environ["TELEGRAM_BOT_TOKEN"]; OWNER = os.environ["TELEGRAM_OWNER_CHAT_ID"]
CH = "-1003926910242"; MID = int(os.environ["MSG_ID"])
api = lambda m, **k: requests.post(f"https://api.telegram.org/bot{T}/{m}", json=k, timeout=30).json()
f = api("forwardMessage", chat_id=OWNER, from_chat_id=CH, message_id=MID, disable_notification=True)
assert f.get("ok"), f
cap = f["result"].get("caption") or f["result"].get("text") or ""
api("deleteMessage", chat_id=OWNER, message_id=f["result"]["message_id"])
old = cap
new = cap.replace(RLM, "").replace("\u200e", "")
new = new.replace(" وسط روز", "").replace("وسط روز ", "")
new = re.sub(r"چرا امروز\s*[؟?]\s*", "", new)
new = new.replace("ذره‌بین :", "ذره‌بین:")
new = re.sub(r"\n{3,}", "\n\n", new)
print("OLD:\n" + old + "\n\nNEW:\n" + new)
if os.environ.get("APPLY") == "true":
    m = "editMessageCaption" if "caption" in f["result"] else "editMessageText"
    key = "caption" if m == "editMessageCaption" else "text"
    r = api(m, chat_id=CH, message_id=MID, parse_mode="HTML", **{key: bold_first(new)})
    print("EDIT:", r.get("ok"), r.get("description"))
