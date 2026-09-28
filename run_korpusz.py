"""A teljes kép-ár korpusz begyűjtése minden forrásból, PostgreSQL-be.

Az üzleti cél két vételi jelzést kíván, ezért kétféle piaci ár kell:
  - magyar használt piaci ár (Vatera, Galéria Savaria, Darabanth),
  - nyugati piaci ár (Chairish; az eBay API-kulcsot igényel).

Mindkét piacon kétféle korpusz gyűlik:
  - relevant: Herendi/Zsolnay, a finomhangoláshoz,
  - general:  teljes porcelán/kerámia kínálat, az előtanításhoz. Ez adja a
    tömeget, amiből a modell megtanulja, mitől drága egy darab.

A lépések sorrendje a hasznosság szerint van: előbb a márkás és a realizált
árat hozó források, aztán a nagy általános korpuszok. Minden lépés folytatható.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
LOG = ROOT / "korpusz.log"

HALOZATI_UJRAPROBA = 8
UJRAPROBA_SZUNET_SEC = 600

LEPESEK = [
    ("Vatera átemelése + Darabanth realizált árak",
     ["harvest-pg", "--from-sqlite", "--source", "darabanth"]),
    ("Galéria Savaria: márkás", ["harvest-pg", "--source", "galeriasavaria"]),
    ("Chairish: márkás (nyugati ár)", ["harvest-pg", "--source", "chairish"]),
    ("Chairish: általános porcelán korpusz", ["harvest-pg", "--source", "chairish",
                                              "--corpus", "general"]),
    ("Galéria Savaria: általános porcelán korpusz", ["harvest-pg", "--source", "galeriasavaria",
                                                     "--corpus", "general"]),
]


def jegyzet(uzenet: str) -> None:
    sor = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {uzenet}"
    print(sor, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(sor + "\n")


def _egyszer(argumentumok: list[str]) -> tuple[str, dict]:
    proc = subprocess.run([str(PY), "-m", "porcelan", *argumentumok],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=ROOT, env={**os.environ, "PYTHONUTF8": "1"})
    kimenet = (proc.stdout or "") + (proc.stderr or "")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(kimenet[-8000:] + "\n")
    try:
        adat = json.loads(kimenet[kimenet.index("{"):kimenet.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        adat = {}
    halozati = "nem érhető el" in kimenet or "NetworkError" in kimenet
    blokkolt = any(v.get("status") == "blocked" for v in adat.values() if isinstance(v, dict))
    if blokkolt:
        return "blocked", adat
    if halozati and proc.returncode:
        return "halozati", adat
    megszakadt = any(v.get("status") == "interrupted" for v in adat.values() if isinstance(v, dict))
    return ("interrupted" if megszakadt else "ok"), adat


def futtat(nev: str, argumentumok: list[str]) -> bool:
    for proba in range(1, HALOZATI_UJRAPROBA + 1):
        jegyzet(f"START – {nev} ({proba}. próba)")
        allapot, adat = _egyszer(argumentumok)

        if allapot == "blocked":
            jegyzet(f"KIHAGYVA – {nev}: a forrás bot-ellenőrzést adott. "
                    "Nem kerüljük meg; a lánc a következő forrással megy tovább.")
            return True          # egy forrás korlátozása ne állítsa meg a többit
        if allapot == "halozati":
            if proba == HALOZATI_UJRAPROBA:
                jegyzet(f"LEÁLLÁS – {nev}: a hálózat nem jött vissza.")
                return False
            jegyzet(f"VÁRAKOZÁS – {nev}: hálózati hiba, {UJRAPROBA_SZUNET_SEC // 60} perc múlva újra.")
            time.sleep(UJRAPROBA_SZUNET_SEC)
            continue
        if allapot == "interrupted":
            jegyzet(f"FOLYTATÁS – {nev}: keret elérve, újraindítom ugyanezt a lépést.")
            continue

        osszeg = {k: (v.get("bekerult") if isinstance(v, dict) else None)
                  for k, v in adat.items() if isinstance(v, dict) and "bekerult" in v}
        jegyzet(f"KÉSZ – {nev}: {osszeg}")
        return True
    return False


def main() -> int:
    jegyzet("=== Korpuszgyűjtés indul ===")
    for nev, argumentumok in LEPESEK:
        if not futtat(nev, argumentumok):
            jegyzet("=== A lánc megállt ===")
            return 1
        _egyszer(["pg-status"])
    jegyzet("=== A lánc végigfutott ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
