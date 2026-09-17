"""Központi beállítások: keresőkifejezések, szűrőszavak, futási paraméterek."""
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Vatera
# ---------------------------------------------------------------------------
BASE_URL = "https://www.vatera.hu"
LISTING_URL = f"{BASE_URL}/listings/index.php"

# Termékoldal URL minta: ...-123456789.html
PRODUCT_URL_RE = r"-\d{6,}\.html$"

SEARCH_TERMS_HEREND = [
    "herendi porcelan",
    "herendi",
    "herend porcelan",
    "herendi figura",
    "herendi vaza",
    "herendi keszlet",
    "herendi tanyer",
    "herendi apponyi",
    "herendi rothschild",
    "herendi victoria",
]

SEARCH_TERMS_ZSOLNAY = [
    "zsolnay porcelan",
    "zsolnay",
    "zsolnay eozin",
    "zsolnay figura",
    "zsolnay vaza",
    "zsolnay keszlet",
    "zsolnay szobor",
    "zsolnay pecs",
]

SEARCH_TERMS = SEARCH_TERMS_HEREND + SEARCH_TERMS_ZSOLNAY

# ---------------------------------------------------------------------------
# Márkafelismerés
# ---------------------------------------------------------------------------
BRAND_HEREND = "Herendi"
BRAND_ZSOLNAY = "Zsolnay"

# Ezek jelenléte kell ahhoz, hogy egyáltalán márkás tételnek tekintsük.
BRAND_TOKENS = {
    BRAND_HEREND: ["herend", "herendi"],
    BRAND_ZSOLNAY: ["zsolnay"],
}

# "Herendi STÍLUSÚ" = nem herendi. Ezek a hirdetést kizárják (elutasított CSV).
FAKE_CUES = [
    "stilusu", "stilusban", "jellegu", "utanzat", "replika", "masolat",
    "hasonmas", "kinai masolat", "nem herendi", "nem zsolnay",
    "herend style", "zsolnay style", "herend stil", "zsolnay stil",
]

# Gyanús, de önmagában nem kizáró (pl. "Rothschild mintás" valódi tétel is lehet).
# Csak megjelöljük, hogy kézi review-nál és az AI-nak feltűnjön.
SUSPECT_CUES = [
    "mintas", "mintaju", "mintajara", "gyari hiba nelkuli utangyartas",
    "utangyartott", "jelzes nelkul", "jelzetlen", "nincs jelzese",
]

# Nem maga a porcelán, hanem róla szóló/hozzá kapcsolódó papír-áru.
NON_PORCELAIN_CUES = [
    "konyv", "katalogus", "arjegyzek", "kepeslap", "levelezolap", "matrica",
    "plakat", "naptar", "prospektus", "ujsag", "folyoirat", "belyeg",
    "szakkonyv", "album", "poszter", "dvd", "cd ", "fotó", "fenykep",
]

# Sérülés jelzők – nem zárnak ki, csak jelöljük (az árazás miatt fontos).
DAMAGE_CUES = [
    "serult", "serulés", "repedt", "repedes", "hajszalrepedes", "csorba",
    "csorbult", "torott", "hibas", "javitott", "ragasztott", "kopott",
    "lepattant", "hianyzik", "hianyos", "restauralt", "matt",
]

# Ismert Herendi / Zsolnay minták, dekorok – az AI-nak és a szűrésnek is segít.
DECOR_HINTS = [
    "apponyi", "rothschild", "victoria", "viktoria", "waldstein", "nanking",
    "siang jaune", "gödöllő", "godollo", "esterhazy", "chanterelle", "fortuna",
    "cornicello", "eozin", "pirogranit", "szecesszio", "art deco", "millennium",
    "pajzspecset", "kezzel festett", "aranyozott", "jelzett",
]

# ---------------------------------------------------------------------------
# Eladási típusok (3 külön "kosár")
# ---------------------------------------------------------------------------
SALE_AUCTION = "aukcio"      # licitálós
SALE_FIX = "fix"             # fix áras, alku nélkül
SALE_OFFER = "alku"          # alkuképes / irányáras / ajánlatot tehetsz
SALE_UNKNOWN = "ismeretlen"

SALE_TYPES = [SALE_AUCTION, SALE_FIX, SALE_OFFER]

SALE_TYPE_LABELS = {
    SALE_AUCTION: "Aukció (licit)",
    SALE_FIX: "Fix áras",
    SALE_OFFER: "Alkuképes / irányáras",
    SALE_UNKNOWN: "Ismeretlen",
}

# ---------------------------------------------------------------------------
# Futás / hálózat
# ---------------------------------------------------------------------------
USER_AGENT = os.environ.get(
    "VATERA_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36",
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "hu-HU,hu;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CACHE_DIR = Path(os.environ.get("VATERA_CACHE_DIR", ".cache_vatera"))
CACHE_TTL_SEC = int(os.environ.get("VATERA_CACHE_TTL", "21600"))   # 6 óra
WORKERS = int(os.environ.get("VATERA_WORKERS", "6"))
REQUEST_DELAY = float(os.environ.get("VATERA_DELAY", "0.4"))       # udvariassági szünet
MAX_PAGES = int(os.environ.get("VATERA_MAX_PAGES", "5"))
HTTP_TIMEOUT = int(os.environ.get("VATERA_TIMEOUT", "20"))
HTTP_RETRIES = int(os.environ.get("VATERA_RETRIES", "3"))

OUT_DIR = Path(os.environ.get("VATERA_OUT_DIR", "out"))

# ---------------------------------------------------------------------------
# Keresési profilok
# ---------------------------------------------------------------------------
# "porcelan": az eredeti Herendi/Zsolnay beállítás (a fenti listák).
# "likvid": magyar piacon jellemző, nyugaton likvid tételek (csövek, szovjet/NDK
# optika, órák, távcsövek). A márkanévnek a CÍMBEN kell szerepelnie, mert a teljes
# oldalszövegben az ajánlósáv más termékei is előfordulnak.
PROFILE = "porcelan"
BRAND_IN_TITLE_ONLY = False
NO_BRAND_LABEL = "nincs herendi/zsolnay megnevezes"
FAKE_LABEL = "utanzat gyanu"
NON_ITEM_LABEL = "nem porcelan tetel"

LIKVID_SEARCH_TERMS = [
    # A Vatera keresője a számos modellneveket ("helios 44", "tungsram el34") alig
    # találja, ezért főleg egy-két szavas márka- és kategórianevekkel keresünk; a pontos
    # modellt az elemzés a címből ismeri fel.
    # --- Órák ---
    "poljot", "poljot chronograph", "polet óra", "sturmanskie", "okean óra", "buran óra",
    "aviator óra", "vostok", "komandirskie", "amphibia", "raketa", "raketa óra",
    "pobeda", "slava", "orosz karóra", "szovjet karóra", "szovjet óra", "chronograph karóra",
    "seiko", "seiko automata", "junghans", "certina", "tissot", "doxa", "orient automata",
    # --- Filmes fényképezőgépek ---
    "rolleiflex", "rollei", "contax", "leica", "zeiss ikon", "voigtländer", "minox",
    "hasselblad", "mamiya", "yashica", "olympus", "olympus mju", "olympus om", "olympus pen",
    "canon ae-1", "canon fényképezőgép", "nikon fm", "nikon fényképezőgép", "pentax",
    "minolta", "konica", "praktica", "exakta", "zenit", "kiev", "horizont", "lomo", "zorki",
    "fed fényképezőgép", "analóg fényképezőgép", "filmes fényképezőgép",
    # --- Objektívek ---
    "helios", "jupiter", "industar", "tair", "mir-1", "mir-24", "zenitar", "carl zeiss",
    "zeiss jena", "pancolar", "flektogon", "sonnar", "biotar", "biometar", "tessar",
    "meyer optik", "trioplan", "orestor", "pentacon", "takumar", "nikkor", "rokkor",
    "m42 objektív", "objektív",
    # --- Csövek, hifi, retró elektronika ---
    "tungsram", "elektroncső", "elektroncsövek", "rádiócső", "walkman", "discman",
    "game boy", "nintendo", "sega", "commodore", "amiga", "atari", "playstation 1",
    # --- Tollak ---
    "pelikan töltőtoll", "parker 51", "töltőtoll",
    # --- Távcsövek ---
    "jenoptem", "dekarem", "binoctem", "nobilem", "zeiss távcső",
]

LIKVID_BRAND_TOKENS = {
    "Tungsram cső": ["tungsram"],
    "Óra": ["poljot", "polet", "sturmanskie", "okean", "buran", "vostok", "wostok", "vosztok",
            "komandirskie", "amphibia", "raketa", "pobeda", "slava", "seiko", "junghans",
            "certina", "tissot", "doxa", "orient"],
    "Fényképezőgép": ["rolleiflex", "rollei", "contax", "leica", "zeiss ikon", "voigtlander",
                      "minox", "hasselblad", "mamiya", "yashica", "olympus", "canon", "nikon",
                      "pentax", "minolta", "konica", "praktica", "exakta", "zenit", "kiev",
                      "horizont", "lomo", "zorki"],
    "Objektív": ["helios", "jupiter", "industar", "pancolar", "flektogon", "sonnar", "biotar",
                 "biometar", "tessar", "trioplan", "orestor", "domiplan", "tair", "zenitar",
                 "mir-1", "mir-24", "meyer", "pentacon", "takumar", "nikkor", "rokkor"],
    "Retró elektronika": ["walkman", "discman", "game boy", "gameboy", "nintendo", "sega",
                          "commodore", "amiga", "atari", "playstation"],
    "Töltőtoll": ["pelikan", "parker"],
    "Zeiss távcső": ["jenoptem", "dekarem", "binoctem", "nobilem"],
    "Carl Zeiss": ["zeiss"],
}

LIKVID_EXCLUDE_CUES = [
    "hibas", "alkatresz", "nem mukodik", "javitasra", "hianyos", "torott", "repedt",
    "penesz", "gombas", "homalyos", "karcos lencse", "adapter", "napellenzo", "kupak",
    "csak tok", "ures doboz", "doboz nelkul csak", "oraszij", "szamlap",
    "szerkezet", "utanzat", "replika", "masolat", "kinai",
    "toltokabel", "tapegyseg", "kontroller", "joystick", "emulator",
    "klon", "utangyartott", "csak doboz", "alkatreszek", "bontott",
]
LIKVID_NON_ITEM_CUES = [
    "konyv", "katalogus", "prospektus", "plakat", "kepeslap", "matrica", "naptar",
    "ujsag", "folyoirat", "kezelesi utmutato",
]


def apply_profile(name: str) -> None:
    """A kiválasztott keresési profil beállításait élesíti (a modul globálisait írja)."""
    global PROFILE, SEARCH_TERMS, BRAND_TOKENS, FAKE_CUES, NON_PORCELAIN_CUES
    global BRAND_IN_TITLE_ONLY, NO_BRAND_LABEL, FAKE_LABEL, NON_ITEM_LABEL
    if name == "porcelan":
        return
    if name != "likvid":
        raise ValueError(f"ismeretlen profil: {name}")
    PROFILE = name
    SEARCH_TERMS = LIKVID_SEARCH_TERMS
    BRAND_TOKENS = LIKVID_BRAND_TOKENS
    FAKE_CUES = LIKVID_EXCLUDE_CUES
    NON_PORCELAIN_CUES = LIKVID_NON_ITEM_CUES
    BRAND_IN_TITLE_ONLY = True
    NO_BRAND_LABEL = "nincs keresett marka/tipus a cimben"
    FAKE_LABEL = "hibas / alkatresz / kiegeszito"
    NON_ITEM_LABEL = "nem maga a termek"

# ---------------------------------------------------------------------------
# Claude API
# ---------------------------------------------------------------------------
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")
CLAUDE_MAX_TOKENS = int(os.environ.get("CLAUDE_MAX_TOKENS", "32000"))
# Hány hirdetés menjen egy API hívásban (a 3 rész ezen belül tovább darabolódik).
AI_CHUNK_SIZE = int(os.environ.get("CLAUDE_CHUNK_SIZE", "60"))
# Leírásból ennyi karaktert küldünk fel (token spórolás).
AI_DESC_CHARS = int(os.environ.get("CLAUDE_DESC_CHARS", "700"))
