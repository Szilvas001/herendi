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


def futtat(nev: str, argumentumok: list[str], blokkolasra_all: bool) -> bool:
    """True: mehet a következő lépés. False: a lánc megáll."""
    jegyzet(f"START – {nev}: python -m porcelan {' '.join(argumentumok)}")
    proc = subprocess.run([str(PY), "-m", "porcelan", *argumentumok],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=ROOT, env={**__import__("os").environ, "PYTHONUTF8": "1"})
    kimenet = (proc.stdout or "") + (proc.stderr or "")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(kimenet[-20000:] + "\n")

    if blokkolasra_all:
        try:
            adat = json.loads(kimenet[kimenet.index("{"):kimenet.rindex("}") + 1])
        except (ValueError, json.JSONDecodeError):
            adat = {}
        if adat.get("status") == "blocked":
            jegyzet(f"LEÁLLÁS – {nev}: a forrás korlátozta a hozzáférést. "
                    "Nem kerüljük meg; később újraindítva folytatódik.")
            return False
        jegyzet(f"KÉSZ – {nev}: status={adat.get('status')} "
                f"kártya={adat.get('stats', {}).get('cards')} "
                f"termékoldal={adat.get('stats', {}).get('detail_pages')}")
        return True

    jegyzet(f"KÉSZ – {nev}: kilépési kód {proc.returncode}")
    return proc.returncode == 0


def main() -> int:
    jegyzet("=== Adatgyűjtési lánc indul ===")
    for nev, argumentumok, blokkolasra_all in LEPESEK:
        if not futtat(nev, argumentumok, blokkolasra_all):
            jegyzet("=== A lánc megállt ===")
            return 1
    jegyzet("=== A lánc végigfutott ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
