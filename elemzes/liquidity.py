import json, math, re, sys, subprocess, urllib.parse
D = sys.argv[1]
comps = json.load(open(f"{D}/comps.json"))
HUF_EUR, EUR_USD = 395, 1.15
FEE = {"eBay.com": .15, "eBay.de": .13, "Etsy": .12, "Catawiki": .125}
# listing_id: (piactér, comps kulcs vagy None, kezdő hirdetési ár a piactér devizájában)
ITEMS = {
 "3501767960": ("eBay.com", "jay", 595), "3499799522": ("eBay.com", "jay", 395), "3501768152": ("eBay.com", "foxterrier", 450),
 "3526894709": ("eBay.com", "hussar", 250), "3527136749": ("Etsy", None, 95), "3487249883": ("eBay.com", "goose_boy", 320),
 "3526021535": ("eBay.com", "ro_tureen", 1450), "3528645125": ("eBay.com", "vbo_tureen", 750), "3528644864": ("eBay.com", "ro_tureen", 950),
 "3527661473": ("eBay.com", "aog_tureen", 850), "3491251307": ("Catawiki", None, 4500), "3493100438": ("eBay.com", "ro_tea", 1950),
 "3487243616": ("eBay.com", "ap_vase", 750), "3487346153": ("eBay.com", "ap_vase", 450), "3524724029": ("Etsy", "av_vase", 150),
 "3524920469": ("Etsy", "ap_vase", 150), "3528588389": ("Etsy", "bs_vase", 170), "3527536409": ("Etsy", "av_vase", 130),
 "3493102247": ("Etsy", "parrot", 140), "3272242091": ("eBay.com", None, 450), "3464572610": ("Etsy", "bird", 160),
 "3502089875": ("Catawiki", "antique_plates", 600), "3527645609": ("eBay.de", None, 290), "3526996043": ("Catawiki", None, 1000),
 "3273802046": ("Catawiki", "z_eosin_vase", 1100), "3274129457": ("Catawiki", "z_eosin_vase", 950), "3273802028": ("eBay.de", "z_bison", 450),
 "3483997382": ("eBay.de", "z_crab", 240), "3487243697": ("Catawiki", "z_faience", 350), "3528589049": ("eBay.de", None, 350),
 "3487247150": ("eBay.de", None, 380),
}
rows = {}
import csv
for r in csv.DictReader(open(f"{D}/herendi/out/run_20260916_085427/vatera_osszes.csv", encoding="utf-8-sig")):
    rows[r["listing_id"]] = r

def cur(platform): return "USD" if platform in ("eBay.com", "Etsy") else "EUR"
def to_cur(huf, c): return huf / HUF_EUR * (EUR_USD if c == "USD" else 1)
def rnd(x): step = 5 if x < 200 else 10 if x < 1000 else 50; return int(math.ceil(x / step) * step)

def prices_for(key, c):
    if not key: return []
    html_prices = comps[key]
    return html_prices

# az aktív árak teljes listája kell a percentilishez: újra kiolvassuk a mentett mintából nem lehet, ezért p25/med/p75 alapján sávosítunk
def band(price, cp, c):
    if not cp or not cp["relevans"]: return None
    conv = 1.0
    if cp["cur"] != c: conv = (1/EUR_USD) if c == "EUR" else EUR_USD
    p25, med, p75 = cp["p25"]*conv, cp["median"]*conv, cp["p75"]*conv
    if price <= p25: return 1
    if price <= med: return 2
    if price <= p75: return 3
    return 4

LIQ = {1: ("magas", "1–4 hét"), 2: ("közepes–magas", "3–8 hét"), 3: ("közepes", "1–3 hónap"), 4: ("alacsony", "3–6+ hónap")}
out = {}
for lid, (plat, key, ask) in ITEMS.items():
    c = cur(plat); cost = to_cur(int(rows[lid]["price_huf"]), c)
    breakeven = cost / (1 - FEE[plat]); floor = rnd(breakeven * 1.10)
    cp = comps.get(key) if key else None
    ba, bf = band(ask, cp, c), band(floor, cp, c)
    out[lid] = {"platform": plat, "cur": c, "vatera_huf": int(rows[lid]["price_huf"]), "koltseg": round(cost), "fedezet": round(breakeven),
                "ask": ask, "floor": floor, "ask_band": ba, "floor_band": bf, "comps": key,
                "comps_txt": (f"{cp['relevans']} db, medián {cp['median']} {cp['cur']} ({cp['p25']}–{cp['p75']})" if cp and cp["relevans"] else "nincs összehasonlítható")}
    print(f"{lid} {plat:8} költség {round(cost):>5} {c} fedezet {round(breakeven):>5} floor {floor:>5} ask {ask:>5} | band ask {ba} floor {bf} | {out[lid]['comps_txt']} | {rows[lid]['title'][:45]}")
json.dump(out, open(f"{D}/liquidity.json", "w"), ensure_ascii=False, indent=1)
