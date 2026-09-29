"""A gép ne aludjon el, amíg a gyűjtés fut.

A 2026-09-29-i futásban a gép 4:26-kor alvó állapotba ment és 20:06-kor ébredt,
ezzel 16 óra gyűjtés kiesett. A tétlenségi alvás ki volt kapcsolva, tehát a
rendszer magától tette, vagy a fedél lehajtása váltotta ki.

Ez a modul a futás idejére kéri a Windowstól, hogy ne altassa el a rendszert
(`SetThreadExecutionState`). A kérés a folyamat élettartamáig szól, és a
kilépéskor magától megszűnik: semmilyen tartós rendszerbeállítást nem írunk át.

Amit ez NEM old meg: a fedél lehajtását és a kézi altatást. Azok közvetlen
felhasználói műveletek, a rendszer akkor is alszik.
"""
from __future__ import annotations

import ctypes
import logging
import sys

log = logging.getLogger(__name__)

ES_CONTINUOUS = 0x80000000        # a beállítás a szál élettartamára szól
ES_SYSTEM_REQUIRED = 0x00000001   # ne menjen alvó állapotba a rendszer
ES_AWAYMODE_REQUIRED = 0x00000040  # médialejátszás-szerű "távolléti" mód


def ebren_tart() -> bool:
    """Alvásgátlás kérése. True, ha sikerült. Nem Windowson nem csinál semmit."""
    if not sys.platform.startswith("win"):
        return False
    try:
        allapot = ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED)
        if not allapot:
            # az away mode nem minden gépen engedélyezett; próbáljuk nélküle
            allapot = ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        if allapot:
            log.info("Alvásgátlás bekapcsolva a gyűjtés idejére.")
            return True
        log.warning("Az alvásgátlást a rendszer nem fogadta el.")
    except (AttributeError, OSError) as exc:
        log.warning("Alvásgátlás nem kérhető: %s", exc)
    return False


def elenged() -> None:
    """Az alvásgátlás feloldása (a folyamat kilépésekor amúgy is megszűnik)."""
    if not sys.platform.startswith("win"):
        return
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except (AttributeError, OSError):
        pass


def _fut_amig_gyujtunk() -> None:
    """Önálló őrfolyamat: tartja az alvásgátlást, amíg a gyűjtés fut.

    A már elindított gyűjtésekre visszamenőleg nem lehet alvásgátlást tenni,
    ezért ez a folyamat tartja helyettük. Ha egyik lánc sem fut, kilép.
    """
    import subprocess
    import time

    def gyujtes_fut() -> bool:
        ki = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -like '*run_korpusz.py*' -or "
             "$_.CommandLine -like '*run_gyujtes.py*' }).Count"],
            capture_output=True, text=True)
        return (ki.stdout or "0").strip() not in ("", "0")

    if not ebren_tart():
        return
    try:
        while gyujtes_fut():
            time.sleep(120)
    finally:
        elenged()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _fut_amig_gyujtunk()
