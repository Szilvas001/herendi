"""Reject obvious accessories, broken items and cross-category model collisions."""
import re
from elemzes.likvid_analyze import norm


def screening_reason(title, model):
    t = norm(title)
    # A conservative screening gate: some complete bundles can be excluded too.
    if re.search(r"\b(?:dvd|cd|buch|book|kezikonyv|alaplap|toner|nyomtato|repro|"
                 r"memoria|rom|chips?|bovito|markolat\w*|elemtarto\w*|csuklopant|"
                 r"bortok|kozgyuru|strap|lunetta|dreamkey|cartridge|kazetta|lemez)\b|"
                 r"sun cover|nem kapcsol be|serult|dobozok", t):
        return "Alkatrész/kiegészítő/szoftver vagy hibás termék"
    for brand in ("Olympus", "Nikon", "Mamiya", "Canon", "Rolleiflex"):
        if model.startswith(brand) and norm(brand) not in t:
            return "Modellazonosító más termékkategóriában"
    if model == "Horizont" and not re.search(r"fenykepez|kamera|camera|panoram", t):
        return "Nem igazolt fényképezőgép"
    if model == "Olympus OM-10" and re.search(r"om\s*-?\s*101", t):
        return "OM-101 nem OM-10"
    if model == "Flektogon 35" and not re.search(r"\b35\b", t):
        return "Eltérő gyújtótávolság"
    if model.startswith(("Game Boy", "Sega", "Nintendo", "Super Nintendo", "PlayStation")):
        if not re.search(r"\b(?:konzol|console|mukodik)\b", t) or re.search(r"konzol\s+jatek\b", t):
            return "Nem igazolt teljes konzol"
    return None
