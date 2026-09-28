"""Szövegből kinyert tárgyjellemzők: gyártó, típus, dekor, méret, darabszám, állapot.

Magyar és angol címekre is működik (az amerikai összehasonlító adatok angolok).
A kimenet egy kanonikus angol leírást is ad, amelyet a CLIP szövegenkódere és a
képi modell közös térben használ.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

BRAND_HEREND = "Herendi"
BRAND_ZSOLNAY = "Zsolnay"


def strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(ch))


def norm(s: str) -> str:
    s = (s or "").replace("\xa0", " ").lower()
    s = strip_accents(s)
    s = re.sub(r"[^\w\s.,/x×\-\"']", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# --- Gyártó --------------------------------------------------------------------
# Elírások és névváltozatok. A "herend" szó önmagában helység is, ezért a címben
# elfogadjuk, a leírásban csak porcelán-kontextussal.
BRAND_PATTERNS = {
    BRAND_HEREND: [r"\bo?-?herend\w*", r"\bherendy\b", r"\bherendi\w*"],
    BRAND_ZSOLNAY: [r"\bzsolnay\w*", r"\bzsolnai\w*", r"\bzsolney\w*", r"\bzolnay\w*", r"\bzsolnaj\w*"],
}
FAKE_CUES = ["stilusu", "stilusban", "jellegu", "utanzat", "replika", "masolat", "hasonmas",
             "nem herendi", "nem zsolnay", "herend style", "zsolnay style", "in the style of",
             "herend stil", "zsolnay stil", "mintajara", "reproduction", "replica"]
NON_ITEM_CUES = ["konyv", "katalogus", "arjegyzek", "kepeslap", "levelezolap", "matrica", "plakat",
                 "naptar", "prospektus", "ujsag", "folyoirat", "belyeg", "szakkonyv", "poszter",
                 "dvd", "fenykep", "book", "catalog", "postcard", "magazine", "hutomagnes", "magnes",
                 "kituzo", "jelveny", "nem futott", "futott", "kepeslap", "cegtabla"]


def detect_brand(title: str, body: str = "") -> tuple[str | None, str]:
    """(márka, alap): az alap 'title' ha a címben szerepel, 'text' ha csak a leírásban."""
    t = norm(title)
    for brand, pats in BRAND_PATTERNS.items():
        if any(re.search(p, t) for p in pats):
            return brand, "title"
    b = norm(body)
    for brand, pats in BRAND_PATTERNS.items():
        for p in pats:
            m = re.search(p, b)
            if m:
                window = b[max(0, m.start() - 60): m.end() + 60]
                if re.search(r"porcel|keramia|jelzes|jelzett|pecset|eozin|festett|figur|vaza", window):
                    return brand, "text"
    return None, "none"


# --- Tárgytípus ----------------------------------------------------------------
OBJECT_TYPES = [
    # (kód, angol név, minták)
    ("tureen", "soup tureen", [r"levesestal", r"leveses tal", r"tureen", r"bogracs"]),
    ("dinner_set", "dinner service set", [r"etkeszlet", r"etkezo keszlet", r"dinner (set|service)", r"dinnerware"]),
    ("ashtray", "ashtray", [r"hamutal", r"hamutarto", r"ashtray", r"csikknyomo", r"dohanyzo keszlet"]),
    ("tea_set", "tea or coffee set", [r"teas\w* garnitura", r"kaves\w* garnitura", r"kakaos keszlet", r"teas szett",
                                      r"kaves szett", r"szendvicses keszlet", r"kompotos keszlet", r"teaskeszlet", r"teas keszlet", r"kaveskeszlet", r"kaves keszlet",
                                      r"mokkas keszlet", r"reggeliz\w* keszlet", r"tea set", r"coffee set", r"tea service"]),
    ("cup", "cup and saucer", [r"csesze", r"bogre", r"\bcup\b", r"mug", r"pohar"]),
    ("teapot", "teapot or jug", [r"teaskanna", r"kiont\w*", r"kanna", r"teapot", r"\bjug\b", r"pitcher", r"kancso",
                                 r"korso", r"kulacs", r"karaff", r"cukortarto", r"tejszines", r"sugar bowl", r"creamer"]),
    ("vase", "vase", [r"vaza", r"\bvase\b", r"urna", r"amfora"]),
    ("figurine", "figurine", [r"figur", r"szobor", r"szobr", r"nipp", r"statue", r"figurine", r"sculpture",
                              r"\bnyul\b", r"madar", r"\bkutya", r"\bmacska", r"\bmedve", r"\bbear\b", r"\bbird\b",
                              r"rabbit", r"\bdog\b", r"\bcat\b", r"papagaj", r"parrot", r"\bsas\b", r"eagle",
                              r"\bbeka\b", r"frog", r"\bhal\b", r"\bfish\b", r"elefant", r"elephant", r"\blo\b",
                              r"horse", r"\bkakas", r"rooster", r"teknos", r"turtle", r"gyik", r"lizard",
                              r"bagoly", r"owl", r"huszar", r"hussar", r"\bakt\b", r"nude", r"bika", r"bison",
                              r"oroszlan", r"lion", r"tigris", r"tiger", r"roka", r"fox", r"csiga", r"snail",
                              r"malac", r"pig", r"vaddiszno", r"nyuszi", r"tacsko", r"ozike", r"\boz\b", r"kandur", r"\bliba",
                              r"suszter", r"paraszt", r"lakodalmas", r"szerelmespar", r"deryne", r"\banya\b", r"\bno\b",
                              r"dinnyeevo", r"kleopatra", r"csibe", r"kacsa", r"duck", r"goose", r"\bmajom", r"monkey",
                              r"zsiraf", r"giraffe", r"szarvas", r"deer", r"pava", r"peacock", r"galamb", r"dove",
                              r"cinege", r"pinty", r"feng", r"fazan", r"pheasant", r"harkaly", r"jay\b", r"szajko",
                              r"terrier", r"puli", r"vizsla", r"agar", r"parrot", r"kakadu", r"csiko", r"csikos",
                              r"juhasz", r"pasztor", r"tancos", r"dancer", r"angyal", r"angel", r"baba\b", r"cica", r"kolyok", r"\blany\b", r"\bfiu\b", r"girl", r"boy"]),
    ("bonbonniere", "bonbonniere or lidded box", [r"bonbon", r"bonbonier", r"doboz", r"szelence", r"box\b", r"trinket"]),
    ("flower", "porcelain flower", [r"\brozsa", r"\bvirag\b", r"viragcsokor", r"\brose\b", r"flower"]),
    ("basket", "basket", [r"kosar", r"basket"]),
    ("bell", "bell", [r"csengo", r"\bbell\b"]),
    ("small_holder", "small holder or box", [r"gyufatarto", r"fogpiszkalo", r"fogvajo", r"teafu tarto", r"vajtarto",
                                             r"pastetom", r"sotarto", r"fuszer", r"tolltarto"]),
    ("plate", "plate or platter", [r"tanyer", r"\btal\b", r"\btalk", r"tal\b", r"tal\s", r"talca", r"tortatal", r"kinalo", r"plate", r"platter",
                                   r"dish", r"charger", r"sutemenyes", r"falitanyer", r"diszitanyer"]),
    ("bowl", "bowl", [r"\btal\b", r"bowl", r"kaspo", r"cachepot", r"planter", r"gyumolcsos", r"salatas"]),
    ("candle", "candle holder", [r"gyertya", r"candle"]),
    ("tile", "tile or plaque", [r"csempe", r"pirogranit", r"plakett", r"plaque", r"tile\b", r"relief", r"dombormu"]),
    ("jewelry", "jewelry", [r"medal", r"fulbevalo", r"bross", r"pendant", r"brooch", r"gyuru"]),
    ("egg", "decorative egg", [r"tojas", r"\begg\b"]),
    ("clock", "clock", [r"\bora\b", r"clock"]),
    ("lamp", "lamp", [r"lampa", r"\blamp\b"]),
]

DECORS = [
    # (kanonikus név, minták)
    ("Apponyi", [r"apponyi", r"\bav\b", r"\bap\b", r"\bavh\b"]),
    ("Rothschild", [r"rothschild", r"rotschild", r"rotchild", r"\bro\b"]),
    ("Queen Victoria", [r"viktoria", r"victoria", r"\bvbo\b"]),
    ("Waldstein", [r"waldstein", r"\bwa\b"]),
    ("Chinese Bouquet", [r"chinese bouquet", r"kinai bokreta", r"\baog\b"]),
    ("Fishnet", [r"fishnet", r"halpikkely", r"pikkelyes", r"halo mintas", r"\bvh\w*\b"]),
    ("Siang Jaune", [r"siang", r"sjaune"]),
    ("Gödöllő", [r"godollo", r"\bgo\b"]),
    ("Esterházy", [r"esterhazy"]),
    ("Nanking", [r"nanking", r"nankin"]),
    ("Tulipe", [r"tulipan", r"tulipe"]),
    ("Printemps", [r"printemps"]),
    ("Indian Basket", [r"indiai kosar", r"indian basket", r"\bib\b"]),
    ("Bouquet de Saxe", [r"bouquet de saxe", r"\bbs\b"]),
    ("Eosin", [r"eozin", r"eosin", r"eozinmaz"]),
    ("Pyrogranite", [r"pirogranit", r"pyrogranit"]),
    ("Art Nouveau", [r"szecesszi", r"art nouveau", r"jugendstil"]),
    ("Art Deco", [r"art deco"]),
    ("Butterfly", [r"pillangos", r"butterfly"]),
    ("Pompadour", [r"pompadour"]),
    ("Petit Point", [r"petit point"]),
]

MARK_CUES = {
    "hand_painted": [r"kezzel festett", r"kezi festes", r"hand ?painted", r"kezzelfestett"],
    "gilded": [r"aranyozott", r"arany\w* szegely", r"gilt", r"gold trim", r"gilded"],
    "marked": [r"jelzett", r"jelzessel", r"pajzspecset", r"pecsetes", r"otornyos", r"otornyu", r"marked",
               r"backstamp", r"stamp", r"hallmark", r"talpjelzes", r"jelzes van"],
    "numbered": [r"sorszam", r"szamozott", r"formaszam", r"numbered", r"\b\d{4,5}\b\s*/"],
    "signed": [r"szignalt", r"signed", r"szignos", r"alairt"],
    "antique": [r"antik", r"antique", r"19\. sz", r"szazadfordulo", r"o-herendi", r"oherend", r"1[89]\d\d\b"],
    "boxed": [r"dobozaban", r"eredeti doboz", r"original box", r"certificate", r"tanusitvany"],
}
DAMAGE_CUES = {
    "damaged": [r"restauralasra", r"javitasra", r"serult", r"serules", r"csorb", r"lepattan", r"torott", r"eltort", r"chip", r"crack",
                r"damage", r"broken", r"hibas\b", r"kopott", r"kopas", r"karcos", r"hajszalrepedes", r"repedt",
                r"repedes"],
    "repaired": [r"javitott", r"ragasztott", r"restaural", r"repaired", r"restored", r"glued"],
    "missing": [r"hianyzik", r"hianyos", r"fedo nelkul", r"missing", r"lid missing", r"nincs fedele"],
    "second_quality": [r"masodosztaly", r"ii\. osztaly", r"2\. osztaly", r"selejt", r"second quality"],
}
PERFECT_CUES = [r"hibatlan", r"serulesmentes", r"mint condition", r"\bmint\b", r"perfect", r"flawless",
                r"excellent condition", r"ujszeru", r"karcmentes"]
NEGATED_DAMAGE = [r"(nincs|nem|semmi)\s+(\w+\s+){0,2}(serul|csorb|repedes|javit|hiba)",
                  r"(serules|csorbulas|repedes|hiba)\s*(es\s+\w+\s*)?(nelkul|mentes)", r"no (chips|cracks|damage)",
                  r"without (chips|cracks|damage)"]
SUSPECT_CUES = [r"jelzetlen", r"jelzes nelkul", r"nincs jelzes", r"unmarked", r"mintas\b.*(nem|nincs)",
                r"utangyart", r"kinai", r"feliratlan"]


def _any(patterns, text):
    return [p for p in patterns if re.search(p, text)]


def object_type(text_norm: str) -> str:
    for code, _, pats in OBJECT_TYPES:
        if _any(pats, text_norm):
            return code
    return "other"


def object_type_label(code: str) -> str:
    for c, label, _ in OBJECT_TYPES:
        if c == code:
            return label
    return "porcelain object"


def decors(text_norm: str) -> list[str]:
    found = []
    for name, pats in DECORS:
        if _any(pats, text_norm):
            found.append(name)
    return found


_SIZE_RE = re.compile(r"(\d{1,3}(?:[.,]\d)?)\s*(?:x\s*\d{1,3}(?:[.,]\d)?\s*)?(cm|mm|\"|inch|in\b|col)")
_HEIGHT_RE = re.compile(r"(?:magas\w*|height|hossz\w*|atmero\w*|szeles\w*|m\s*:)\s*:?\s*(\d{1,3}(?:[.,]\d)?)\s*(cm|mm|\"|inch|in\b)?")


def size_cm(text_norm: str) -> float | None:
    vals = []
    for m in list(_HEIGHT_RE.finditer(text_norm)) + list(_SIZE_RE.finditer(text_norm)):
        try:
            v = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        unit = (m.group(2) or "cm").strip()
        if unit == "mm":
            v /= 10
        elif unit in ('"', "inch", "in", "col"):
            v *= 2.54
        if 1.5 <= v <= 150:
            vals.append(v)
    return round(max(vals), 1) if vals else None


_PIECES_RE = re.compile(r"(\d{1,3})\s*(?:db|darab\w*|reszes|pcs|pieces|piece|szem\w*)")
_PERSONS_RE = re.compile(r"(\d{1,2})\s*(?:szem\w*|sz\.|sz\b|fos|person|persons)")


def pieces(text_norm: str) -> int | None:
    vals = [int(m.group(1)) for m in _PIECES_RE.finditer(text_norm) if 0 < int(m.group(1)) <= 200]
    persons = [int(m.group(1)) for m in _PERSONS_RE.finditer(text_norm) if 0 < int(m.group(1)) <= 24]
    if vals:
        return max(vals)
    if persons:
        return persons[0] * 3
    if re.search(r"\bpar\b|\bpair\b|\bpar\s", text_norm):
        return 2
    return None


def condition(text_norm: str) -> tuple[str, list[str]]:
    flags = []
    cleaned = text_norm
    for p in NEGATED_DAMAGE:
        cleaned = re.sub(p, " ", cleaned)
    for name, pats in DAMAGE_CUES.items():
        if _any(pats, cleaned):
            flags.append(name)
    if "damaged" in flags:
        cond = "serult"
    elif "repaired" in flags:
        cond = "javitott"
    elif flags:
        cond = "serult"
    elif _any(PERFECT_CUES, text_norm):
        cond = "hibatlan"
    else:
        cond = "ismeretlen"
    return cond, flags


def marks(text_norm: str) -> list[str]:
    return [name for name, pats in MARK_CUES.items() if _any(pats, text_norm)]


def fake_hits(title_norm: str) -> list[str]:
    return [c for c in FAKE_CUES if c in title_norm]


def non_item_hits(title_norm: str) -> list[str]:
    return [c for c in NON_ITEM_CUES if re.search(rf"\b{re.escape(c)}", title_norm)]


def suspect_hits(text_norm: str) -> list[str]:
    return [p.replace("\\b", "") for p in SUSPECT_CUES if re.search(p, text_norm)]


def extract(title: str, description: str = "", category: str = "") -> dict:
    """Minden jellemző egy lépésben. A leírás csak kiegészíti a címet."""
    tn = norm(title)
    dn = norm(description)
    full = f"{tn} {dn} {norm(category)}".strip()
    brand, basis = detect_brand(title, f"{description} {category}")
    otype = object_type(tn)
    if otype == "other":
        otype = object_type(full)
    dec = decors(tn) or decors(full)
    cond, dmg = condition(full)
    mk = marks(full)
    fake = fake_hits(tn)
    non_item = non_item_hits(tn)
    feats = {
        "brand": brand,
        "brand_basis": basis,
        "object_type": otype,
        "decor": ", ".join(dec[:3]) if dec else None,
        "size_cm": size_cm(tn) or size_cm(dn),
        "pieces": pieces(tn) or pieces(dn),
        "condition": cond,
        "damage_flags": ", ".join(dmg) or None,
        "mark_flags": ", ".join(mk) or None,
        "suspect_flags": ", ".join(suspect_hits(full)) or None,
        "fake_hits": fake,
        "non_item_hits": non_item,
    }
    feats["canonical_en"] = canonical_description(feats)
    return feats


def canonical_description(f: dict) -> str:
    """Egységes angol leírás a multimodális (CLIP) szövegbeágyazáshoz."""
    brand = {"Herendi": "Herend", "Zsolnay": "Zsolnay"}.get(f.get("brand") or "", "")
    parts = [f"a {brand} porcelain" if brand else "a porcelain", object_type_label(f.get("object_type") or "other")]
    if f.get("decor"):
        parts.append(f"with {f['decor']} decor")
    marks_ = (f.get("mark_flags") or "")
    if "hand_painted" in marks_:
        parts.append("hand painted")
    if "gilded" in marks_:
        parts.append("gilded")
    if "antique" in marks_:
        parts.append("antique")
    if f.get("size_cm"):
        parts.append(f"{round(f['size_cm'])} cm")
    if f.get("pieces") and f["pieces"] > 1:
        parts.append(f"set of {f['pieces']} pieces")
    if f.get("condition") in ("serult", "javitott"):
        parts.append("damaged" if f["condition"] == "serult" else "repaired")
    return " ".join(parts)


def relevance(title: str, feats: dict) -> tuple[str, str]:
    """(accepted | rejected | visual_candidate, ok)."""
    reasons = []
    if feats["fake_hits"]:
        reasons.append("utánzat-gyanú: " + ", ".join(feats["fake_hits"]))
    if feats["non_item_hits"]:
        reasons.append("nem porcelán tárgy: " + ", ".join(feats["non_item_hits"]))
    if reasons:
        return "rejected", "; ".join(reasons)
    if not feats["brand"]:
        return "visual_candidate", "nincs gyártónév; képi előszűrésre vár"
    return "accepted", ""


def dedup_key(title: str, price: float | None = None, seller: str | None = None) -> str:
    """Újrahirdetések összevonásához: normalizált cím (számok nélkül) + eladó."""
    t = re.sub(r"\d+", "#", norm(title))
    t = re.sub(r"[^a-z# ]", "", t)
    tokens = sorted(set(t.split()))
    base = " ".join(tokens) + "|" + (seller or "")
    return hashlib.sha1(base.encode()).hexdigest()[:16]


def title_tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", norm(title))}
