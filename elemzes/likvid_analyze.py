"""Likvid profil: Vatera tételek -> modell -> aktív eBay-kínálat (PicClick) -> fedezet, likviditás.

Használat: python likvid_analyze.py <vatera_osszes.csv> <kimenet.json>
"""
import csv, json, math, re, statistics, subprocess, sys, time, unicodedata, urllib.parse

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
HUF_PER_USD = 395 / 1.15          # 1 EUR = 395 Ft, 1 EUR = 1,15 USD
FEE = 0.15                        # eBay.com értékesítési + nemzetközi díj
MIN_COMPS, MIN_MARGIN_PCT, MIN_MARGIN_USD = 10, 0.60, 40
EBAY_EXCLUDE = r"parts|repair|broken|not work|fungus|haze|hazy|as is|as-is|for spares|adapter|hood|cap only|case only|box only|strap only|dial only|movement only|manual|book|replica|copy"


def norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()


def tube_model(t):
    m = re.search(r"\b(ecc8[1-8]|e88cc|e188cc|el3[46]|el8[46]|el50[49]|el519|ef8[06]|ecl8[026]|ecf8[02]|pcl8[2456]|pcf80|pl50[04]|ez8[01]|gz3[24]|6l6\w*|kt88|6550|el156|ecc40|ecc91|eabc80|ebf89|ey88|py88|pl36|el95|6n14p)\b", t)
    return m.group(1) if m else None


def qty(t):
    m = re.search(r"\b(\d{1,2})\s*(?:db|darab|pcs)\b", t)
    if m and 1 < int(m.group(1)) <= 24:
        return int(m.group(1))
    if re.search(r"\bpar\b|\bparban\b|\bpair\b", t):
        return 2
    return 1


# (név, cím-regex, eBay keresés, eBay-cím kötelező regex) – az első egyező szabály nyer
RULES = [
    # Fényképezőgépek (előbb, mert a szettekben objektívnév is van)
    ("Lomo LC-A", r"\blc-?a\b", "lomo lc-a", r"lc-?a"),
    ("Kiev 88", r"kiev\s*-?88", "kiev 88 camera", r"kiev.?88"),
    ("Kiev 60", r"kiev\s*-?60", "kiev 60 camera", r"kiev.?60"),
    ("Zenit 122", r"zenit\s*-?122", "zenit 122", r"zenit.?122"),
    ("Zenit ET", r"zenit\s*-?et\b", "zenit et camera", r"zenit.?et\b"),
    ("Zenit E", r"zenit\s*-?e\b", "zenit e camera", r"zenit.?e\b"),
    ("Praktica MTL", r"praktica\s*mtl", "praktica mtl", r"mtl"),
    ("Praktica LTL", r"praktica\s*ltl", "praktica ltl", r"ltl"),
    ("Praktica B200", r"praktica\s*b\s*200", "praktica b200", r"b.?200"),
    ("Exakta Varex", r"exakta\s*varex", "exakta varex", r"varex"),
    ("Zorki 4", r"zorki\s*-?4", "zorki 4 camera", r"zorki.?4"),
    ("Zenit TTL", r"zenit\s*-?ttl", "zenit ttl camera", r"zenit.?ttl"),
    ("Kine Exakta", r"kine\s*exakta", "kine exakta camera", r"kine.?exakta"),
    ("Zeiss Super Ikonta 533/16", r"super\s*ikonta.*533", "zeiss super ikonta 533/16", r"533"),
    ("Zeiss Ikonta 521", r"ikonta.*521", "zeiss ikonta 521", r"521"),
    ("Rollei SL35 + Planar 50", r"sl\s*35.*planar|planar.*sl\s*35", "rollei sl35 planar 50mm", r"sl.?35"),
    # Filmes fényképezőgépek (nyugaton keresett)
    ("Rolleiflex 2.8", r"rolleiflex.*2[,.]8", "rolleiflex 2.8 tlr", r"rolleiflex.*2\.8"),
    ("Rolleiflex 3.5", r"rolleiflex.*3[,.]5", "rolleiflex 3.5 tlr", r"rolleiflex.*3\.5"),
    ("Rolleiflex", r"rolleiflex", "rolleiflex tlr camera", r"rolleiflex"),
    ("Rolleicord", r"rolleicord", "rolleicord camera", r"rolleicord"),
    ("Rollei 35", r"rollei\s*35", "rollei 35 camera", r"rollei 35"),
    ("Contax T2", r"contax\s*t2", "contax t2", r"contax t2"),
    ("Contax G2", r"contax\s*g2", "contax g2", r"contax g2"),
    ("Contax G1", r"contax\s*g1", "contax g1", r"contax g1"),
    ("Contax 139", r"contax\s*139", "contax 139 quartz", r"139"),
    ("Contax RTS", r"contax\s*rts", "contax rts", r"rts"),
    ("Zeiss Ikon Contessa", r"contessa", "zeiss ikon contessa", r"contessa"),
    ("Zeiss Ikon Ikonta", r"ikonta", "zeiss ikon ikonta", r"ikonta"),
    ("Zeiss Ikon Contaflex", r"contaflex", "zeiss ikon contaflex", r"contaflex"),
    ("Voigtländer Bessa", r"bessa", "voigtlander bessa", r"bessa"),
    ("Voigtländer Vito", r"\bvito\b", "voigtlander vito", r"vito"),
    ("Voigtländer Vitessa", r"vitessa", "voigtlander vitessa", r"vitessa"),
    ("Minox 35", r"minox.*35", "minox 35 camera", r"minox 35"),
    ("Minox B", r"minox", "minox b spy camera", r"minox"),
    ("Hasselblad 500", r"hasselblad.*500", "hasselblad 500c/m", r"500"),
    ("Mamiya RB67", r"rb\s*67", "mamiya rb67", r"rb67"),
    ("Mamiya 645", r"mamiya.*645", "mamiya 645", r"645"),
    ("Mamiya C330", r"c\s*330|c\s*220", "mamiya c330", r"c330|c220"),
    ("Yashica Mat 124G", r"yashica.*mat.*124", "yashica mat 124g", r"124"),
    ("Yashica Mat", r"yashica.*mat", "yashica mat tlr", r"yashica.?mat"),
    ("Yashica T4", r"yashica.*t4|yashica.*t5", "yashica t4", r"t4|t5"),
    ("Yashica Electro 35", r"electro\s*35", "yashica electro 35", r"electro 35"),
    ("Olympus mju II", r"mju\s*-?\s*(ii|2)\b|μ\s*ii|stylus epic", "olympus mju ii", r"mju.?ii|mju.?2|stylus epic"),
    ("Olympus mju", r"\bmju\b|\bμ\b", "olympus mju 35mm", r"mju"),
    ("Olympus XA", r"olympus\s*xa", "olympus xa camera", r"\bxa"),
    ("Olympus OM-1", r"om\s*-?\s*1\b", "olympus om-1", r"om-?1\b"),
    ("Olympus OM-2", r"om\s*-?\s*2", "olympus om-2", r"om-?2"),
    ("Olympus OM-10", r"om\s*-?\s*10", "olympus om-10", r"om-?10"),
    ("Olympus Pen F", r"pen\s*-?f\b|pen\s*ft", "olympus pen f", r"pen.?f"),
    ("Olympus Pen EE", r"pen\s*-?\s*ee", "olympus pen ee", r"pen.?ee"),
    ("Olympus Trip 35", r"trip\s*35", "olympus trip 35", r"trip 35"),
    ("Canon AE-1 Program", r"ae\s*-?1\s*program", "canon ae-1 program", r"ae-?1 program"),
    ("Canon AE-1", r"ae\s*-?1\b", "canon ae-1 camera", r"ae-?1"),
    ("Canon A-1", r"canon\s*a\s*-?1\b", "canon a-1 camera", r"a-1"),
    ("Canon F-1", r"canon\s*f\s*-?1\b", "canon f-1 camera", r"f-1"),
    ("Canon AV-1", r"canon.*\bav\s*-?1\b", "canon av-1", r"av-?1"),
    ("Canonet QL17", r"canonet", "canonet ql17", r"canonet"),
    ("Nikon FM2", r"\bfm\s*2", "nikon fm2", r"fm2"),
    ("Nikon FM", r"nikon\s*fm\b", "nikon fm camera", r"\bfm\b"),
    ("Nikon FE", r"nikon\s*fe\b", "nikon fe camera", r"\bfe\b"),
    ("Nikon F3", r"nikon\s*f3", "nikon f3", r"f3"),
    ("Nikon F2", r"nikon\s*f2", "nikon f2", r"f2"),
    ("Nikon EM", r"nikon\s*em\b", "nikon em camera", r"\bem\b"),
    ("Pentax K1000", r"k\s*1000", "pentax k1000", r"k1000"),
    ("Pentax Spotmatic", r"spotmatic", "pentax spotmatic", r"spotmatic"),
    ("Pentax ME Super", r"me\s*super", "pentax me super", r"me super"),
    ("Pentax MX", r"pentax\s*mx\b", "pentax mx", r"\bmx\b"),
    ("Pentax Espio", r"espio", "pentax espio", r"espio"),
    ("Minolta X-700", r"x\s*-?700", "minolta x-700", r"x-?700"),
    ("Minolta XD", r"minolta\s*xd", "minolta xd", r"\bxd"),
    ("Konica Big Mini", r"big\s*mini", "konica big mini", r"big mini"),
    ("Konica C35", r"konica\s*c\s*35", "konica c35", r"c35"),
    ("Horizont", r"horizont|horizon\s*202|horizon\s*perfekt", "horizon 202 panoramic", r"horizon"),
    # Objektívek
    ("Helios 44", r"helios\s*-?44", "helios 44 lens", r"helios.?44"),
    ("Helios 40", r"helios\s*-?40", "helios 40-2 85mm", r"helios.?40"),
    ("Jupiter 3", r"jupiter\s*-?3\b", "jupiter 3 50mm", r"jupiter.?3\b"),
    ("Tair 33", r"tair\s*-?33", "tair 33 300mm", r"tair.?33"),
    ("Mir-24", r"mir\s*-?24", "mir-24 35mm", r"mir.?24"),
    ("Biometar 80", r"biometar.*80", "biometar 80mm 2.8", r"biometar.*80"),
    ("Biometar 120", r"biometar.*120", "biometar 120mm", r"biometar.*120"),
    ("Sonnar 180", r"sonnar.*180|180.*sonnar", "carl zeiss jena sonnar 180 2.8", r"sonnar.*180|180.*sonnar"),
    ("Tessar 50", r"tessar.*50|50.*tessar", "carl zeiss jena tessar 50mm 2.8", r"tessar"),
    ("Takumar 50 1.4", r"takumar.*50.*1[,.]4|takumar.*1[,.]4.*50", "super takumar 50mm 1.4", r"50.*1\.4"),
    ("Takumar 55 1.8", r"takumar.*55", "super takumar 55mm 1.8", r"55"),
    ("Nikkor 50 1.4", r"nikkor.*50.*1[,.]4|nikkor.*1[,.]4.*50", "nikon nikkor 50mm 1.4 ai", r"50.*1\.4"),
    ("Nikkor 105 2.5", r"nikkor.*105", "nikon nikkor 105mm 2.5", r"105"),
    ("Rokkor 58 1.2", r"rokkor.*58.*1[,.]2", "minolta rokkor 58mm 1.2", r"58.*1\.2"),
    ("Rokkor 58 1.4", r"rokkor.*58", "minolta rokkor 58mm 1.4", r"58"),
    ("Jupiter 9", r"jupiter\s*-?9\b", "jupiter 9 85mm", r"jupiter.?9\b"),
    ("Jupiter 37", r"jupiter\s*-?37", "jupiter 37a 135mm", r"jupiter.?37"),
    ("Jupiter 8", r"jupiter\s*-?8\b", "jupiter 8 50mm", r"jupiter.?8\b"),
    ("Jupiter 11", r"jupiter\s*-?11", "jupiter 11 135mm", r"jupiter.?11"),
    ("Mir-1", r"\bmir\s*-?1", "mir-1b 37mm", r"mir.?1"),
    ("Industar 61", r"industar\s*-?61", "industar 61 lens", r"industar.?61"),
    ("Tair 11", r"tair\s*-?11", "tair 11 135mm", r"tair.?11"),
    ("Tair 3", r"tair\s*-?3\b", "tair 3 300mm", r"tair.?3\b"),
    ("Zenitar 16", r"zenitar", "zenitar 16mm fisheye", r"zenitar"),
    ("Trioplan 100", r"trioplan.*100", "meyer trioplan 100mm", r"trioplan.*100"),
    ("Trioplan 50", r"trioplan", "meyer trioplan 50mm", r"trioplan"),
    ("Orestor 135", r"orestor", "meyer orestor 135mm", r"orestor"),
    ("Domiplan 50", r"domiplan", "meyer domiplan 50mm", r"domiplan"),
    ("Flektogon 20", r"flektogon.*\b20\b", "flektogon 20mm", r"flektogon.*20"),
    ("Flektogon 35", r"flektogon", "flektogon 35mm", r"flektogon"),
    ("Pancolar 50", r"pancolar", "pancolar 50mm", r"pancolar"),
    ("Sonnar 135", r"sonnar.*135|135.*sonnar", "carl zeiss jena sonnar 135", r"sonnar"),
    ("Pentacon 135", r"pentacon.*135", "pentacon 135mm 2.8", r"pentacon.*135"),
    ("Pentacon 50", r"pentacon.*\b50\b", "pentacon 50mm 1.8", r"pentacon.*50"),
    ("Pentacon 29", r"pentacon.*\b29\b", "pentacon 29mm 2.8", r"pentacon.*29"),
    ("Industar 50", r"industar\s*-?50", "industar 50 lens", r"industar.?50"),
    ("Biotar 58", r"biotar", "carl zeiss biotar 58mm", r"biotar"),
    # Órák
    ("Poljot Okean", r"okean|океан", "poljot okean 3133", r"okean|ocean"),
    ("Poljot Buran", r"buran|буран", "poljot buran 3133", r"buran"),
    ("Poljot Aviator", r"aviator.*(3133|chrono)|poljot.*aviator", "poljot aviator 3133", r"aviator"),
    ("Poljot Kapitan", r"kapitan|kapit[aá]ny|капитан", "poljot kapitan chronograph 3133", r"kapitan|captain|kapit"),
    ("Poljot Admiral", r"admiral|адмирал", "poljot admiral chronograph", r"admiral"),
    ("Vostok Komandirskie", r"komandirs", "vostok komandirskie", r"komandirs"),
    ("Raketa Big Zero", r"big\s*zero", "raketa big zero", r"big zero"),
    ("Raketa Copernicus", r"copernicus|kopernik", "raketa copernicus", r"copernicus"),
    ("Seiko 6139", r"6139", "seiko 6139 chronograph", r"6139"),
    ("Seiko SKX", r"skx\s*0?07|skx\s*009|skx\s*013", "seiko skx007", r"skx"),
    ("Seiko 5 Sports", r"seiko\s*5\s*sports", "seiko 5 sports automatic", r"5 sports"),
    ("Junghans Max Bill", r"max\s*bill", "junghans max bill", r"max bill"),
    ("Poljot 3133", r"3133", "poljot 3133 chronograph", r"3133"),
    ("Poljot Chronograph", r"poljot.*c?h?ronograph", "poljot 3133 chronograph", r"3133|chronograph"),
    ("Sturmanskie", r"sturmanskie|shturmanskie", "sturmanskie watch", r"sturmanskie|shturmanskie"),
    ("Vostok Amphibia", r"amphibi", "vostok amphibia", r"amphibi"),
    # Retró elektronika
    ("Sony Walkman WM-D6C", r"wm\s*-?d6", "sony walkman wm-d6c", r"d6"),
    ("Sony Walkman WM-2", r"wm\s*-?2\b", "sony walkman wm-2", r"wm-?2\b"),
    ("Sony Walkman WM-DD", r"wm\s*-?dd", "sony walkman wm-dd", r"wm-?dd"),
    ("Sony Discman D-50", r"(discman|sony).*\bd\s*-?50\b", "sony discman d-50", r"d-?50"),
    ("Game Boy Advance SP", r"advance\s*sp|gba\s*sp", "game boy advance sp console", r"advance sp|gba sp"),
    ("Game Boy Advance", r"game\s*boy\s*advance|\bgba\b", "game boy advance console", r"advance"),
    ("Game Boy Color", r"game\s*boy\s*colou?r|gbc", "game boy color console", r"color|colour"),
    ("Game Boy Pocket", r"game\s*boy\s*pocket", "game boy pocket console", r"pocket"),
    ("Game Boy Classic", r"game\s*boy|gameboy|dmg\s*-?01", "nintendo game boy dmg-01 original", r"dmg|original|classic|1989"),
    ("Nintendo 64", r"nintendo\s*64|\bn64\b", "nintendo 64 console", r"64"),
    ("Super Nintendo", r"super\s*nintendo|\bsnes\b", "super nintendo snes console", r"snes|super nintendo"),
    ("Nintendo NES", r"\bnes\b|nintendo\s*entertainment", "nintendo nes console", r"\bnes\b"),
    ("GameCube", r"gamecube|game\s*cube", "nintendo gamecube console", r"gamecube"),
    ("Sega Mega Drive", r"mega\s*drive|sega.*genesis", "sega mega drive console", r"mega drive|genesis"),
    ("Sega Dreamcast", r"dreamcast", "sega dreamcast console", r"dreamcast"),
    ("Sega Master System", r"master\s*system", "sega master system console", r"master system"),
    ("Commodore 64", r"commodore\s*64|\bc\s*64\b|c64", "commodore 64 computer", r"64"),
    ("Commodore 1541", r"1541", "commodore 1541 disk drive", r"1541"),
    ("Amiga 500", r"amiga\s*500", "amiga 500 computer", r"500"),
    ("Amiga 1200", r"amiga\s*1200", "amiga 1200 computer", r"1200"),
    ("Atari 2600", r"atari\s*2600", "atari 2600 console", r"2600"),
    ("Atari 800XL", r"800\s*xl", "atari 800xl", r"800xl"),
    ("Atari 520ST", r"520\s*st", "atari 520st", r"520"),
    ("PlayStation 1", r"playstation\s*(1|one)\b|\bpsx\b|\bps1\b|scph", "sony playstation 1 console", r"playstation|ps1|psx|scph"),
    # Töltőtollak
    ("Pelikan M800", r"pelikan.*m\s*800", "pelikan m800", r"m800"),
    ("Pelikan M600", r"pelikan.*m\s*600", "pelikan m600", r"m600"),
    ("Pelikan M400", r"pelikan.*m\s*400", "pelikan m400", r"m400"),
    ("Pelikan M200", r"pelikan.*m\s*200", "pelikan m200", r"m200"),
    ("Parker 51", r"parker\s*51", "parker 51 fountain pen", r"51"),
    # Távcsövek
    ("Jenoptem 10x50", r"jenoptem.*10\s*x\s*50", "jenoptem 10x50", r"jenoptem.*10x50"),
    ("Jenoptem 7x50", r"jenoptem.*7\s*x\s*50", "jenoptem 7x50", r"jenoptem.*7x50"),
    ("Jenoptem 8x30", r"jenoptem.*8\s*x\s*30", "jenoptem 8x30", r"jenoptem.*8x30"),
    ("Dekarem 10x50", r"dekarem", "carl zeiss dekarem 10x50", r"dekarem"),
    ("Nobilem", r"nobilem", "carl zeiss jena nobilem", r"nobilem"),
    ("Binoctem 7x50", r"binoctem", "carl zeiss binoctem 7x50", r"binoctem"),
]

LENS_RULES = {"Jupiter 3", "Tair 33", "Mir-24", "Biometar 80", "Biometar 120", "Sonnar 180", "Tessar 50",
              "Takumar 50 1.4", "Takumar 55 1.8", "Nikkor 50 1.4", "Nikkor 105 2.5", "Rokkor 58 1.2", "Rokkor 58 1.4",
              "Helios 44", "Helios 40", "Jupiter 9", "Jupiter 37", "Jupiter 8", "Jupiter 11", "Mir-1", "Industar 61",
              "Tair 11", "Zenitar 16", "Trioplan 100", "Trioplan 50", "Orestor 135", "Domiplan 50", "Flektogon 20",
              "Flektogon 35", "Pancolar 50", "Sonnar 135", "Biotar 58", "Pentacon 135", "Pentacon 50", "Pentacon 29", "Industar 50", "Tair 3"}
WATCH_RULES = {"Poljot 3133", "Poljot Chronograph", "Sturmanskie", "Vostok Amphibia", "Poljot Okean", "Poljot Buran",
               "Poljot Aviator", "Poljot Kapitan", "Poljot Admiral", "Vostok Komandirskie", "Raketa Big Zero",
               "Raketa Copernicus", "Seiko 6139", "Seiko SKX", "Seiko 5 Sports", "Junghans Max Bill"}

def category(name):
    if name.startswith("Tungsram"):
        return "Tungsram cső"
    if name in LENS_RULES:
        return "Objektív"
    if name in WATCH_RULES:
        return "Szovjet óra"
    if any(k in name for k in ("Jenoptem", "Dekarem", "Binoctem", "Nobilem")):
        return "Zeiss távcső"
    if any(k in name for k in ("Walkman", "Discman", "Game Boy", "Nintendo", "GameCube", "Sega", "Commodore",
                               "Amiga", "Atari", "PlayStation")):
        return "Retró elektronika"
    if name.startswith(("Pelikan", "Parker")):
        return "Töltőtoll"
    return "Fényképezőgép"


_comps_cache = {}


def comps(query, include, single_tube=False):
    key = (query, include, single_tube)
    if key in _comps_cache:
        return _comps_cache[key]
    url = f"https://picclick.com/?q={urllib.parse.quote_plus(query)}"
    html = subprocess.run(["curl", "-s", "-L", "--max-time", "25", "-A", UA, url],
                          capture_output=True, text=True, errors="ignore").stdout
    prices = []
    for m in re.finditer(r'<h3 title="([^"]*)">.*?<div class="price"><strong>\$([\d,\.]+)</strong>', html, re.S):
        title = m.group(1)
        if not re.search(include, title, re.I) or re.search(EBAY_EXCLUDE, title, re.I):
            continue
        if single_tube and re.search(r"pair|quad|matched|lot|set of|\b\d\s*x\b|\bx\s*\d\b|\(\d\)|\d\s*pcs|\d\s*pieces", title, re.I):
            continue
        try:
            prices.append(float(m.group(2).replace(",", "")))
        except ValueError:
            pass
    prices.sort()
    res = None
    if prices:
        q = lambda f: prices[min(len(prices) - 1, int(f * (len(prices) - 1)))]
        res = {"n": len(prices), "p25": q(.25), "median": statistics.median(prices), "p75": q(.75), "url": url}
    _comps_cache[key] = res
    time.sleep(2)
    return res


def rnd(x):
    step = 5 if x < 200 else 10 if x < 1000 else 50
    return int(math.ceil(x / step) * step)


def band(price, c):
    return 1 if price <= c["p25"] else 2 if price <= c["median"] else 3 if price <= c["p75"] else 4


FLOOR_TXT = {1: ("1–4 hét", "magas"), 2: ("3–8 hét", "közepes–magas"), 3: ("1–3 hónap", "közepes"), 4: ("3–6+ hónap", "alacsony")}


def ask_txt(n):
    if n >= 30:
        return "2–6 hét", "magas"
    if n >= 15:
        return "3–8 hét", "közepes–magas"
    return "1–3 hónap", "közepes"


def main(src, dst):
    rows = list(csv.DictReader(open(src, encoding="utf-8-sig")))
    stats = {"osszes": len(rows), "nem_fix": 0, "nincs_modell": 0, "nincs_eleg_comps": 0, "kicsi_arres": 0, "floor_median_felett": 0, "kivalasztva": 0}
    out = []
    for r in rows:
        if r["sale_type"] not in ("fix", "alku") or not r["price_huf"] or int(r["price_huf"]) < 1000:
            stats["nem_fix"] += 1
            continue
        t = norm(r["title"])
        tm = tube_model(t) if "tungsram" in t else None
        if tm:
            name, query, include, single = f"Tungsram {tm.upper()}", f"tungsram {tm}", tm, True
        else:
            is_camera = re.search(r"fenykepezogep|fenykepezo|kamera|camera|zenit|praktica|kiev|zorki|altix|exakta|rolleiflex|yashica|olympus|canon|nikon\s*f|pentax|minolta|contax|\bvaz\b", t)
            is_watch = re.search(r"\bora\b|karora|watch|chronograph", t) and not re.search(r"ebreszto|asztali|vekker|falion|utazo", t)
            is_game = re.search(r"jatek|kazetta|cartridge|pokemon|mario|zelda|tetris|sonic|donkey|kirby|\bcd\b.*jatek", t)
            is_accessory = re.search(r"\btok\b|\btaska\b|\bvaku\b|\bkabel\b", t) and not re.search(r"fenykepezogep|kamera|\bgep\b|konzol", t)
            rule = next((x for x in RULES if re.search(x[1], t)
                         and not (x[0] in LENS_RULES and is_camera)
                         and not (x[0] in WATCH_RULES and not is_watch)
                         and not (category(x[0]) == "Retró elektronika" and is_game)
                         and not (category(x[0]) == "Fényképezőgép" and is_accessory)), None)
            if not rule:
                stats["nincs_modell"] += 1
                continue
            name, _, query, include = rule
            single = False
        c = comps(query, include, single)
        if not c or c["n"] < MIN_COMPS:
            stats["nincs_eleg_comps"] += 1
            continue
        n_units = qty(t) if tm else 1
        cost = int(r["price_huf"]) / HUF_PER_USD
        unit_cost = cost / n_units
        floor_unit = rnd(unit_cost / (1 - FEE) * 1.10)
        ask_unit = c["median"]
        margin = ask_unit * n_units * (1 - FEE) - cost
        if band(floor_unit, c) > 2:
            stats["floor_median_felett"] += 1
            continue
        if margin / cost < MIN_MARGIN_PCT or margin < MIN_MARGIN_USD:
            stats["kicsi_arres"] += 1
            continue
        stats["kivalasztva"] += 1
        a_time, a_liq = ask_txt(c["n"])
        f_time, f_liq = FLOOR_TXT[band(floor_unit, c)]
        out.append({
            "listing_id": r["listing_id"], "url": r["url"], "title": r["title"], "kategoria": category(name), "modell": name,
            "sale_type": r["sale_type"], "vatera_huf": int(r["price_huf"]), "koltseg_usd": round(cost), "db": n_units,
            "ask_usd": rnd(ask_unit * n_units), "ask_ido": a_time, "ask_liq": a_liq,
            "floor_usd": floor_unit * n_units, "floor_ido": f_time, "floor_liq": f_liq,
            "netto_haszon_usd": round(margin), "arres_pct": round(100 * margin / cost),
            "comps_txt": f"{c['n']} db, medián {round(c['median'])} USD ({round(c['p25'])}–{round(c['p75'])})" + (" / darab" if tm else ""),
            "comps_url": c["url"],
        })
        print(f"{name:16} {r['price_huf']:>7} Ft x{n_units} | ask {rnd(ask_unit*n_units):>5} floor {floor_unit*n_units:>5} | haszon {round(margin):>5} USD ({round(100*margin/cost)}%) | n={c['n']} | {r['title'][:60]}", flush=True)
    json.dump({"stats": stats, "tetelek": out}, open(dst, "w"), ensure_ascii=False, indent=1)
    print(stats)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
