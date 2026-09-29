"""Teljes adatgyűjtési lánc egyben, blokkolás esetén azonnali megállással.

Sorrend: Herendi/Zsolnay kínálat -> általános porcelán korpusz -> herend.com
katalógus -> képek -> azonosítás -> pontozás. Minden lépés folytatható: újra
indítva ott veszi fel a fonalat, ahol abbamaradt.

Ha a Vatera bot-ellenőrzést ad (a crawler "blocked" státusza), a lánc leáll, és
a korlátozást nem kerüljük meg.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
LOG = ROOT / "gyujtes.log"

LEPESEK = [
    ("Vatera: Herendi/Zsolnay kínálat", ["crawl", "--source", "vatera"], True),
    ("Vatera: általános porcelán korpusz", ["crawl", "--source", "vatera", "--corpus", "general"], True),
    ("herend.com katalógus", ["crawl-catalog"], False),
    ("Képek + CLIP-beágyazás", ["images"], False),
    ("Termékazonosítás", ["identify"], False),
    ("Pontozás", ["score"], False),
]


def jegyzet(uzenet: str) -> None:
    sor = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {uzenet}"
    print(sor, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(sor + "\n")


HALOZATI_UJRAPROBA = 12          # átmeneti hálózati hiba esetén ennyiszer
UJRAPROBA_SZUNET_SEC = 600       # 10 perc két próbálkozás között


def _egyszer(nev: str, argumentumok: list[str]) -> tuple[str, dict]:
    """Egy lefutás. Visszaadja a kimenetből kiolvasott státuszt és statisztikát."""
    proc = subprocess.run([str(PY), "-m", "porcelan", *argumentumok],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=ROOT, env={**__import__("os").environ, "PYTHONUTF8": "1"})
    kimenet = (proc.stdout or "") + (proc.stderr or "")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(kimenet[-20000:] + "\n")
    try:
        adat = json.loads(kimenet[kimenet.index("{"):kimenet.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        adat = {}
    halozati = "nem érhető el" in kimenet or "NetworkError" in kimenet
    allapot = adat.get("status") or ("halozati" if halozati and proc.returncode else
                                     ("ok" if proc.returncode == 0 else "hiba"))
    if allapot == "failed" and halozati:
        allapot = "halozati"
    return allapot, adat


def futtat(nev: str, argumentumok: list[str], blokkolasra_all: bool) -> bool:
    """True: mehet a következő lépés. False: a lánc megáll.

    Átmeneti hálózati hiba (DNS, időtúllépés) esetén vár és újrapróbál; a bejárás
    folytatható, ezért nem veszik el munka. Bot-ellenőrzésnél viszont azonnal
    megáll, és nem kerüljük meg.
    """
    for proba in range(1, HALOZATI_UJRAPROBA + 1):
        jegyzet(f"START – {nev} ({proba}. próba): python -m porcelan {' '.join(argumentumok)}")
        allapot, adat = _egyszer(nev, argumentumok)

        if allapot == "blocked":
            jegyzet(f"LEÁLLÁS – {nev}: a forrás korlátozta a hozzáférést. "
                    "Nem kerüljük meg; később újraindítva folytatódik.")
            return False

        if allapot == "halozati":
            if proba == HALOZATI_UJRAPROBA:
                jegyzet(f"LEÁLLÁS – {nev}: a hálózat {HALOZATI_UJRAPROBA} próbálkozás után sem jött vissza.")
                return False
            jegyzet(f"VÁRAKOZÁS – {nev}: hálózati hiba, "
                    f"{UJRAPROBA_SZUNET_SEC // 60} perc múlva újra.")
            time.sleep(UJRAPROBA_SZUNET_SEC)
            continue

        if blokkolasra_all:
            jegyzet(f"KÉSZ – {nev}: status={allapot} "
                    f"kártya={adat.get('stats', {}).get('cards')} "
                    f"termékoldal={adat.get('stats', {}).get('detail_pages')}")
            # "interrupted" = kéréskeret/időkeret; ilyenkor ugyanez a lépés folytatja
            if allapot == "interrupted":
                continue
            return True

        jegyzet(f"KÉSZ – {nev}: {allapot}")
        return allapot == "ok"
    return False


def main() -> int:
    jegyzet("=== Adatgyűjtési lánc indul ===")
    sys.path.insert(0, str(ROOT))
    from porcelan import ebren
    if ebren.ebren_tart():
        jegyzet("Alvásgátlás bekapcsolva: a rendszer nem alszik el a futás alatt.")
    else:
        jegyzet("FIGYELEM: az alvásgátlást nem sikerült bekapcsolni.")
    for nev, argumentumok, blokkolasra_all in LEPESEK:
        if not futtat(nev, argumentumok, blokkolasra_all):
            jegyzet("=== A lánc megállt ===")
            return 1
    jegyzet("=== A lánc végigfutott ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
