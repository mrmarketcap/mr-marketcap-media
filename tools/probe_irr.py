import requests, json, re
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
d = requests.get("https://call2.tgju.org/ajax.json", headers=H, timeout=20).json()
print("top keys", list(d.keys())[:10], len(d))
cur = d.get("current", d)
print("current keys", len(cur))
for k in ["price_dollar_rl", "price_eur", "geram18", "sekee", "ons", "crypto-bitcoin", "price_dollar_soleymani", "sana_buy_usd"]:
    print(k, json.dumps(cur.get(k), ensure_ascii=False))
print([k for k in cur if "dollar" in k or "usd" in k.lower()][:30])
print(json.dumps({k: v for k, v in d.items() if k != "current"}, ensure_ascii=False)[:600])
t = requests.get("https://alanchand.com/currencies-price/usd", headers=H, timeout=20).text
for m in re.finditer(r"(\d{3},\d{3})", t):
    print("alanchand", m.group(1)); 
    if m.start() > 200000: break
