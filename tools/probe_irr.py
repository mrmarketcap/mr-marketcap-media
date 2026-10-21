import requests
urls = ["https://call2.tgju.org/ajax.json", "https://call5.tgju.org/ajax.json", "https://www.tgju.org/profile/price_dollar_rl",
        "https://bonbast.com/", "https://api.alanchand.com/?type=currencies", "https://alanchand.com/currencies-price/usd",
        "https://www.bon-bast.com/", "https://api.tgju.org/v1/market/indicator/summary-table-data/price_dollar_rl"]
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
for u in urls:
    try:
        r = requests.get(u, headers=H, timeout=20)
        t = r.text
        i = t.find("price_dollar_rl")
        print(u, r.status_code, len(t), (t[i:i+250].replace("\n", " ") if i >= 0 else t[:150].replace("\n", " ")))
    except Exception as e:
        print(u, "ERR", str(e)[:100])
