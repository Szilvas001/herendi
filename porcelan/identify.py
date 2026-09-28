"""Pontos termékazonosítás: gyártó + formaszám + mintakód (cikkszám-kulcs).

A pontos piaci ár feltétele, hogy tudjuk, MELYIK termékről van szó. A Herend
cikkszám-rendszere: 5 jegyű formaszám (a vezető nullák elhagyhatók) + alkatrész-
kód + fogantyúkód + mintakód, pl. „711-0-00 VBO” = Viktória mintás kávéscsésze
aljjal. A hirdetések ezt sokféle alakban írják: „(AV 7183)”, „749/AP”,
„1711 / VBO”, „Apponyi Purpur (AP)”, vagy csak a magyar mintanévvel.

Kizárjuk az eladói leltárkódokat (ZAL-R 91989, 1S089, (D020)), az évszámokat
és a méret/ár/darabszám számokat.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .text import norm

# Mintakódok (Herend). A név csak tájékoztató; a kulcs a kód.
HEREND_PATTERNS = {
    "VBO": "Queen Victoria (Viktória)",
    "AV": "Apponyi / Chinese Bouquet zöld",
    "AOG": "Apponyi / Chinese Bouquet narancs",
    "AP": "Apponyi / Chinese Bouquet purpur",
    "RO": "Rothschild madaras",
    "SJ": "Siang Jaune",
    "GO": "Gödöllő",
}
# Magyar / angol mintanév → mintakód (csak egyértelmű esetek; a többi kódként kerül be, ha a címben szerepel)
NAME_TO_CODE = [
    (r"viktoria|victoria", "VBO"),
    (r"apponyi\W+(?:\w+\W+){0,2}(?:zold|vert|green)|(?:zold|green)\W+apponyi", "AV"),
    (r"apponyi\W+(?:\w+\W+){0,2}(?:narancs|orange|rozsda|rust)|narancs\W+apponyi", "AOG"),
    (r"apponyi\W+(?:\w+\W+){0,2}(?:purpur|pourpre|lila|purple|malna|voros|pur-pur|pur pur)"
     r"|(?:lila|purpur|voros|malna)\W+apponyi", "AP"),
    (r"rothschild|rotschild|rotchild", "RO"),
    (r"siang jaune", "SJ"),
    (r"godollo", "GO"),
]
FISHNET_COLORS = [(r"\bkek|\bblue", "VHB"), (r"fekete|black", "VHN"), (r"\bzold|green", "VHV"),
                  (r"rozsaszin|pink", "VHP"), (r"piros|voros|\bred\b", "VHR"), (r"sarga|yellow", "VHJ"),
                  (r"narancs|orange", "VHOR"), (r"szurke|grey|gray", "VHG"), (r"barna|brown", "VHM"),
                  (r"arany|gold", "VHOR")]

_NOT_CODES = {"ANTIK", "II", "III", "IV", "USA", "CM", "MM", "DB", "FT", "EUR", "HUF", "USD", "ZS", "ZSOLNAY",
              "HERENDI", "HEREND", "PORCELAN", "MCD", "OK", "XL", "XXL", "NEW", "RARE", "VINTAGE", "SET", "LOT",
              "AS", "AL", "AT", "BT", "AF", "ES", "AN", "AX", "AG", "PMSC", "ZOVA", "I"}
# eladói leltár- és hirdetéskódok: betű(k) + szám keverék, ill. ZAL-R 12345
_SELLER_CODE = re.compile(r"\b[A-Z]{1,4}-[A-Z]\s*\d{4,6}\b|\b\d[A-Z]\d{3}\b|\([A-Z]\d{3}\)|\b[A-Z]\d{3}\b")
_YEAR_CTX = re.compile(r"(\d{4})\s*(?:-?(?:es|as|ös|os)\b|k\.|korul|korüli|evek|evi|evbol|ota|\b-ben|\b-ban)")


@dataclass
class Identity:
    brand: str | None
    form_no: str | None = None        # vezető nullák nélkül: "711", "5236"
    part: str | None = None           # "0" = teljes tárgy
    pattern: str | None = None        # mintakód: VBO, AV, AP, VHB …
    pattern_source: str | None = None  # code (a szövegben kódként) / name (mintanévből)
    confidence: float = 0.0
    basis: list = field(default_factory=list)

    @property
    def sku_key(self) -> str | None:
        if not self.brand or not self.form_no:
            return None
        return f"{self.brand}|{self.form_no}|{self.pattern or '-'}"

    @property
    def form_key(self) -> str | None:
        return f"{self.brand}|{self.form_no}" if self.brand and self.form_no else None

    def as_dict(self) -> dict:
        return {"brand": self.brand, "form_no": self.form_no, "part": self.part, "pattern": self.pattern,
                "pattern_source": self.pattern_source, "sku_key": self.sku_key, "form_key": self.form_key,
                "confidence": round(self.confidence, 2), "basis": self.basis}


def _clean_form(num: str) -> str | None:
    n = num.lstrip("0")
    return n if n and len(n) <= 5 else None


def identify_text(title: str, description: str = "", brand: str | None = None) -> Identity:
    """Formaszám + mintakód a címből (elsődleges) és a leírásból."""
    from .text import detect_brand
    brand = brand or detect_brand(title, description)[0]
    ident = Identity(brand=brand)
    raw = f"{title} \n {description[:1500]}"
    upper = _SELLER_CODE.sub(" ", raw)
    years = {m.group(1) for m in _YEAR_CTX.finditer(norm(raw))}

    # 1) teljes Herend cikkszám: 711-0-00 VBO, 05236-0-00
    m = re.search(r"\b(\d{3,5})-(\d)-(\d{2})(?:\s*/?\s*([A-Z]{2,6}))?\b", upper)
    if m:
        ident.form_no, ident.part = _clean_form(m.group(1)), m.group(2)
        if m.group(4) and m.group(4) not in _NOT_CODES:
            ident.pattern, ident.pattern_source = m.group(4), "code"
        ident.basis.append("teljes cikkszám")
    # 2) formaszám + kód egymás mellett: 749/AP, 1711 / VBO, (AV 7183), 7074/AP
    if not ident.form_no:
        for m in re.finditer(r"\b(\d{3,5})\s*/\s*([A-Z]{2,6})\b|\b([A-Z]{2,6})\s+(\d{3,5})\b|\b(\d{3,5})\s+([A-Z]{2,6})\b",
                             upper):
            num = m.group(1) or m.group(4) or m.group(5)
            code = m.group(2) or m.group(3) or m.group(6)
            if code in _NOT_CODES or num in years:
                continue
            ident.form_no, ident.part = _clean_form(num), "0"
            ident.pattern, ident.pattern_source = code, "code"
            ident.basis.append("formaszám+mintakód")
            break
    # 3) önálló formaszám: zárójelben "(7705)", vagy a cím elején "6052 Herendi …", "#5236", "formaszám: 5236"
    if not ident.form_no:
        cands = []
        for rx in (r"\((\d{3,5})\)", r"^\s*(\d{4,5})\s+(?=\D)", r"#\s?(\d{3,5})\b",
                   r"(?:herendi?|zsolnay)\s+(\d{4,5})\b(?!\s*(?:cm|mm|ft|db|-?es|-?as|\.))",
                   r"(?:formaszam|forma szam|model(?:l)?szam|cikkszam|form no\.?|item no\.?)\s*:?\s*(\d{3,5})\b"):
            src = upper if rx.startswith(r"\(") or rx.startswith("^") or rx.startswith("#") else norm(raw)
            for mm in re.finditer(rx, src, flags=re.I):
                num = mm.group(1)
                if num in years or (len(num) == 4 and 1800 <= int(num) <= 2030 and rx.startswith("^") is False
                                    and "formaszam" not in rx):
                    continue
                cands.append(num)
        # utolsó szám a címben, ha a cím "... 1726" formában végződik (csésze + alj 1726)
        mm = re.search(r"(\s-\s*)?\b(\d{3,4})\s*$", title.strip())
        if (mm and not mm.group(1) and mm.group(2) not in years
                and not (len(mm.group(2)) == 4 and 1800 <= int(mm.group(2)) <= 2030)
                and not re.search(r"(cm|mm|ft|db)\s*$", title.lower())):
            cands.append(mm.group(2))
        if cands:
            ident.form_no, ident.part = _clean_form(cands[0]), "0"
            ident.basis.append("formaszám")
    # 4) mintakód szövegből, ha még nincs: "(AP)", "VBO", "RO-DOX", "KÉK VH (VHB)"
    if not ident.pattern:
        for mm in re.finditer(r"\(([A-Z]{2,5})\)|\b(VBO|AOG|VH[A-Z]{1,2}|RO|AV|AP|SJ|GO|PBR)\b", upper):
            code = mm.group(1) or mm.group(2)
            if code and code not in _NOT_CODES:
                ident.pattern, ident.pattern_source = code, "code"
                break
    # 5) mintakód a mintanévből
    t = norm(raw)
    if not ident.pattern:
        for rx, code in NAME_TO_CODE:
            if re.search(rx, t):
                ident.pattern, ident.pattern_source = code, "name"
                break
    if not ident.pattern and re.search(r"halpikkely|pikkelyes|fishnet|halo mintas", t):
        code = next((c for rx, c in FISHNET_COLORS if re.search(rx, t)), "VH")
        ident.pattern, ident.pattern_source = code, "name"

    if ident.form_no and ident.pattern:
        ident.confidence = 0.9 if ident.pattern_source == "code" else 0.75
    elif ident.form_no:
        ident.confidence = 0.55
    elif ident.pattern:
        ident.confidence = 0.2
    if ident.pattern:
        ident.basis.append(f"minta: {ident.pattern}")
    return ident


def pattern_name(code: str | None) -> str | None:
    if not code:
        return None
    if code.startswith("VH"):
        return "Halpikkelyes (Fishnet)"
    return HEREND_PATTERNS.get(code)
