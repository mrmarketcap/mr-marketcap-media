import requests, re
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
for u in ["https://alanchand.com/gold-price", "https://alanchand.com/gold-price/18k", "https://alanchand.com/gold-price/sekkeh", "https://alanchand.com/gold-price/sekke", "https://alanchand.com/"]:
    r = requests.get(u, headers=H, timeout=25)
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", r.text, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t); t = re.sub(r"\s+", " ", t)
    print("==", u, r.status_code, len(t))
    for m in re.finditer(r"(طلا[^۰-۹]{0,40}|سکه[^۰-۹]{0,40})([۰-۹]{1,3}(,[۰-۹]{3})+)", t):
        print("  ", m.group(0)[:100])
    print(t[:500])
