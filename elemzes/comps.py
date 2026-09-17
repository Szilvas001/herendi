import json, re, statistics, subprocess, sys, time, urllib.parse
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
Q = [  # (kulcs, domain, keresés, kötelező regex a címben, kizáró regex)
 ("jay", "com", "herend jay", r"jay", r"mini|miniature|small"),
 ("foxterrier", "com", "herend fox terrier", r"terrier", r""),
 ("hussar", "com", "herend hussar", r"hussar|hadik", r""),
 ("knight", "com", "herend knight figurine", r"knight|ladislaus|king", r""),
 ("goose_boy", "com", "herend goose boy", r"goose|matyi", r""),
 ("ro_tureen", "com", "herend rothschild tureen", r"tureen", r"mini|condiment|sauce|sugar"),
 ("vbo_tureen", "com", "herend queen victoria tureen", r"tureen", r"mini|condiment|sauce|sugar"),
 ("aog_tureen", "com", "herend chinese bouquet rust tureen", r"tureen", r"mini|condiment|sauce|sugar"),
 ("ro_dinner", "com", "herend rothschild bird dinner plates set", r"plate|set|service|dinnerware", r"single|1 plate|one plate"),
 ("ro_tea", "com", "herend rothschild tea set", r"tea set|teapot|tea service|coffee set", r"cup only|single cup"),
 ("ap_vase", "com", "herend apponyi purple vase", r"vase", r"mini|miniature|bud"),
 ("av_vase", "com", "herend apponyi green vase", r"vase", r""),
 ("bs_vase", "com", "herend bouquet de saxe vase", r"vase", r""),
 ("parrot", "com", "herend parrot", r"parrot|macaw|cockatoo", r"fishnet"),
 ("nude", "com", "herend nude figurine", r"nude|woman|lady", r""),
 ("bird", "com", "herend bird figurine", r"bird", r"fishnet|mini|rothschild"),
 ("antique_plates", "com", "antique herend plates", r"plate", r""),
 ("z_lizard", "de", "zsolnay eidechse", r"eidechse|lizard|salamander", r""),
 ("z_eosin_vase", "de", "zsolnay eosin vase", r"vase", r""),
 ("z_eosin_vase_us", "com", "zsolnay eosin vase", r"vase", r""),
 ("z_bison", "de", "zsolnay bison", r"bison|büffel|buffalo|wisent", r""),
 ("z_crab", "de", "zsolnay eosin schale", r"krebs|krabbe|hummer|crab|lobster|schale", r""),
 ("z_bears", "de", "zsolnay bär", r"bär|baer|bear", r""),
 ("z_pompadour", "de", "zsolnay pompadour", r"pompadour", r""),
 ("z_faience", "com", "antique zsolnay vase", r"vase", r"eosin"),
 ("z_nikelszky", "com", "zsolnay nikelszky", r"nikelszky|vase", r""),
]
out = {}
for key, dom, q, inc, exc in Q:
    url = f"https://picclick.{dom}/?q={urllib.parse.quote_plus(q)}"
    html = subprocess.run(["curl", "-s", "-L", "--max-time", "25", "-A", UA, url], capture_output=True, text=True, errors="ignore").stdout
    total = re.search(r"innerHTML='(\d[\d.,]*)", html)
    rows = []
    for m in re.finditer(r'<h3 title="([^"]*)">.*?<div class="price"><strong>([^<]*)</strong>', html, re.S):
        title, price = m.group(1), m.group(2)
        if not re.search(inc, title, re.I) or (exc and re.search(exc, title, re.I)):
            continue
        num = re.sub(r"[^\d,\.]", "", price)
        num = num.replace(".", "").replace(",", ".") if dom == "de" else num.replace(",", "")
        try:
            rows.append((float(num), title))
        except ValueError:
            pass
    p = sorted(r[0] for r in rows)
    q4 = lambda f: round(p[min(len(p)-1, int(f*(len(p)-1)))]) if p else None
    out[key] = {"url": url, "cur": "EUR" if dom == "de" else "USD", "oldalon": total.group(1) if total else None,
                "relevans": len(p), "p25": q4(.25), "median": round(statistics.median(p)) if p else None, "p75": q4(.75),
                "min": round(p[0]) if p else None, "max": round(p[-1]) if p else None,
                "minta": [f"{round(v)} | {t[:70]}" for v, t in sorted(rows)[:: max(1, len(rows)//6)]][:7]}
    print(key, out[key]["cur"], "oldalon:", out[key]["oldalon"], "relevans:", len(p), "p25/med/p75:", out[key]["p25"], out[key]["median"], out[key]["p75"], "min-max:", out[key]["min"], out[key]["max"], flush=True)
    time.sleep(2)
json.dump(out, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
