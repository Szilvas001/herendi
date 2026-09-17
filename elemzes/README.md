# Elemző scriptek és adatok

A `riport/` mappa táblázatai ezekkel a scriptekkel készültek. A scriptek a repó gyökeréből, a scraper kimenetével futnak.

**Scriptek**
- `compact.py`: a `vatera_osszes.csv` tömörítése soronként egy hirdetésre, kézi átnézéshez.
- `comps.py`: Herendi/Zsolnay tételek eBay/Etsy-összevetése PicClicken keresztül (→ `comps.json`).
- `liquidity.py`: piactér, kezdő ár, legkisebb elfogadható ár és eladási idő becslése (→ `liquidity.json`, `placement*.json`).
- `likvid_analyze.py`: a likvid profil hirdetéseinek modellfelismerése, eBay-összevetése és szűrése (→ `likvid.json`).
- `review_prep.py`: a kiválasztott tételek leírásának és fotóinak letöltése kézi ellenőrzéshez.
- `build_report.py`: a `riport/README.md` és a többi riportfájl előállítása.

**Adatok:** `picks.json` (Herendi/Zsolnay válogatás), `comps.json`, `liquidity.json`, `placement.json`, `placement2.json`,
`likvid.json` (a kézi ellenőrzésen átment likvid tételek), `likvid_kizart.json` (a kizárt tételek, indoklással).

**Futtatás sorrendje (likvid tételek)**
1. `python run.py --profile likvid --no-ai --pages 3 --out-dir out_likvid2`
2. `python elemzes/likvid_analyze.py out_likvid2/run_*/vatera_osszes.csv likvid.json`
3. `python elemzes/review_prep.py likvid.json .cache_vatera review 25 3`, majd kézi ellenőrzés: leírás, fotók, lezárt eladási árak. A rossz tételeket töröld a `likvid.json`-ból, és írd be őket a `likvid_kizart.json`-ba.
4. `python elemzes/build_report.py <herendi_run> picks.json <kimenet> placement.json likvid.json`
