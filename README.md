# Herendi–Zsolnay vételkereső

Magyar piactereken (elsődlegesen Vatera, másodlagosan Jófogás) keres potenciálisan alulárazott Herendi és Zsolnay porcelánt. A magyarországi és az amerikai továbbértékesítést külön értékeli: piaci értékbecslés, becslési intervallum, validált megbízhatóság, költség utáni nettó nyereség konzervatív forgatókönyvvel, és kattintható link az eredeti hirdetésre.

![Dashboard](docs/screenshots/main.png)

> **Állapot (2026-09-28):** az adatgyűjtési, képfeldolgozási, becslési, rangsorolási és dashboard-infrastruktúra működik és tesztelt. A modell **KÍSÉRLETI**, mert eddig csak kínálati árakon tanulhatott: realizált eladási ár még nincs. Részletek: [Mi működik valós adattal](#mi-működik-valós-adattal-és-mi-nem) és [docs/ADATFORRASOK.md](docs/ADATFORRASOK.md).

## Gyors indítás

```bash
pip install -r requirements.txt            # Python 3.11+; CPU elég
cp config/settings.example.toml config/settings.toml   # opcionális: saját költségek, árfolyam
python -m porcelan setup-models            # CLIP ViT-B/32 súlyok (605 MB, GitHub, SHA-256 ellenőrzés)
python -m porcelan import-repo             # a repóban lévő valós Vatera-adatok (2026-09-16/19) importja
python -m porcelan score                   # becslés a verziózott modellel (models/CURRENT) – nincs újratanítás
python -m porcelan serve                   # dashboard: http://127.0.0.1:8000
```

Friss adat (olyan gépről, ahonnan a Vatera elérhető):

```bash
python -m porcelan crawl --source vatera   # teljes, folytatható bejárás; Ctrl+C után folytatja
python -m porcelan images                  # képletöltés, duplikátumszűrés, CLIP-beágyazás, képi előszűrés
python -m porcelan score                   # csak a változott hirdetéseket becsüli újra
```

A dashboardról ugyanez gombokkal indítható („Adatgyűjtés indítása”, „CSV import”, „Újrapontozás”, „Tanítás”). A feladatok háttérfolyamatként futnak, folyamatjelzővel.

## Használat a dashboardon

1. Válaszd ki a gyártót (Herendi / Zsolnay), a vételárat (< 20 000 Ft, < 50 000 Ft vagy egyedi) és a célpiacot (magyar / amerikai).
2. Állíts be minimum árengedményt, konzervatív nettó nyereséget és megbízhatóságot. Szűrhetsz forrásra és hirdetéstípusra (fix / alku / aukció), és többféleképpen rendezhetsz.
3. A kártyákon látszik a kép, a megnevezés, az ár és a típus, a magyar és az amerikai érték intervallummal, a nettó nyereség és a megtérülés (alap és konzervatív), aukciónál a max. javasolt licit, a rövid indoklás, a kockázatok, az utolsó ellenőrzés ideje és a **Hirdetés megnyitása** gomb.
4. A **Részletek** nézet tartalmazza az összes képet, a leírást, a tételes költségszámítást mindkét forgatókönyvre, a feltételezéseket, az összehasonlítható tételeket (ártípussal és dátummal), az árkövetést és a visszakövethetőséget (modellverzió, bemenet-hash, forrás-azonosító).
5. A fejléc mutatja a modell státuszát és verzióját, az utolsó sikeres adatgyűjtést és az adatok frissességét. Hiányzó modell, régi adat vagy hibás adatforrás esetén figyelmeztetés jelenik meg.

Jelzések:
- **Ajánlott**: a konzervatív (alsó becslésű) forgatókönyv is legalább 5000 Ft nettó nyereséget ad, és a validált megbízhatóság eléri a küszöböt.
- **Jelölt – bizonytalan**: a várható eladási érték alatt van, és alapesetben nyereséges, de a megbízhatóság a küszöb alatt marad.
- **Nincs ajánlás**: a rendszer tartózkodik. Ennek oka lehet nem azonosított gyártó, sérült tárgy, kevés hasonló tétel, csak csoportmedián becslés, inaktív hirdetés vagy hiányzó ár.
- Az „USA-érték alatt” és az „USA-ba nyereséges” külön jelzés.
- Aukciónál a nyereség feltételes („ha ezen a licitten nyered”), és a rendszer a maximális javasolt licitet adja meg. Rögzített áron megszerezhető nyereséget nem ígér.

## Architektúra

```
Adatgyűjtés ──► tisztítás ──► képfeldolgozás ──► azonosítás ──► árbecslés ──► költség ──► rangsor ──► dashboard
crawler.py      text.py       images.py          text.py        predict.py    costs.py    ranking.py   api.py + web/
sources/*       importers.py  vision.py (CLIP)   vision.py      model.py                              jobs.py (háttér)
   │                                                               ▲
   └──────── SQLite (data/hzfinder.sqlite): listings · observations · images · embeddings · price_records
             · crawl_runs · frontier · coverage · estimates · recommendation_log · jobs
                                                                   │
                         train.py ──► models/<verzió>/ (manifest, súlyok, pipeline, index, tanítóadat) ──► models/CURRENT
```

| Modul | Feladat |
|---|---|
| `porcelan/sources/vatera.py` | Keresés 55 névváltozatra, elírásra és kapcsolódó kifejezésre (herendy, zsolnai, zolnay, eozin, pirogránit, halpikkelyes…). Kategóriafelfedezés és -bejárás, teljes lapozás a valódi végéig, a jelzett találatszám kiolvasása. Termékoldal: eladási típus, ár, szállítási díj, licit, lejárat, képek, kategória, készlet, státusz. |
| `porcelan/crawler.py` | SQLite-frontier prioritással: a releváns keresések előbb jönnek, a teljes katalógus (`--full-catalog`) alacsony prioritással. Folytatható futás, inkrementális (a részletes oldalt csak új, megváltozott vagy 72 óránál régebben ellenőrzött hirdetéshez tölti le), árkövetés (`observations`). Státuszok: active / ended / sold / disappeared / removed. Lezárult aukciónál rögzíti a záró licitet. Lefedettséget mér keresésenként; részleges futást nem nevez teljesnek. |
| `porcelan/net.py` | Átlátható User-Agent, hostonkénti késleltetés, robots.txt, cache. 403/429/CAPTCHA esetén leáll (`blocked`), nem kerüli meg. |
| `porcelan/sources/jofogas.py`, `ebay.py` | Jófogás mint második forrás (`jofogas.enabled`). eBay Browse API (hivatalos, US aktív kínálat). |
| `porcelan/importers.py` | Régi `run.py` CSV-k, riport-táblák, PicClick-összehasonlítók, általános ár-CSV (realizált, leütési, kínálati ár). Idempotens. |
| `porcelan/images.py` | Letöltés, normalizált tárolás, sha256 és pHash, közel azonos képek duplikátumszűrése. |
| `porcelan/vision.py` | OpenCLIP ViT-B/32 (LAION-400M), fagyasztott enkóder. Kép- és szövegbeágyazás cache-sel; zero-shot képi előszűrés a márkanév nélküli porcelánhirdetésekhez. |
| `porcelan/text.py` | Gyártó, tárgytípus, dekor, méret, darabszám, állapot (sérült, javított, hiányos), jelzések (talpjelzés, kézzel festett, aranyozott, szignó, antik), utánzat- és nem-porcelán-szűrés, kanonikus angol leírás a CLIP-hez. |
| `porcelan/dataset.py` | Ártípus-kezelés, piaconkénti pénznem, újrahirdetés-szűrés. Csoportképzés közös kép és közel azonos cím alapján. Csoportszintű train/val/test felosztás; időbeli teszt, ha az adat legalább 30 napot lefed. |
| `porcelan/model.py`, `train.py` | Csoportmedián-baseline, GBM kvantilis-regresszió, multimodális neurális modell (CLIP kép + szöveg + TF-IDF + strukturált + visszakeresett hasonló tételek; közös törzs, HU/US kvantilisfejek, 5 tagú ensemble), ablation CLIP nélkül. Konformális intervallum-kalibráció, validációs megbízhatóság, bootstrap CI, „validált” kapu. |
| `porcelan/costs.py`, `ranking.py` | Célpiaconkénti költségek (szállítás, csomagolás, platform- és fizetési díj, devizaváltás, USA vám/tarifa, adó, kockázati tartalék), alap és konzervatív forgatókönyv, max. licit, tartózkodási szabályok, indoklás, kockázatok, hiányzó információk. |

## Parancsok

| Parancs | Mit csinál |
|---|---|
| `python -m porcelan crawl [--source vatera\|jofogas] [--full-catalog] [--max-requests N] [--time-budget S] [--no-resume]` | adatgyűjtés; kilépési kód 2 blokkolásnál vagy hibánál |
| `python -m porcelan import-repo` | a repóban tárolt valós adatok importja |
| `python -m porcelan import-csv out/run_*/vatera_osszes.csv` | régi scrape CSV-k importja |
| `python -m porcelan import-prices eladasok.csv` | realizált, leütési vagy kínálati árak (`config/prices.example.csv` fejléc) |
| `python -m porcelan import-ebay` | eBay Browse API (EBAY_CLIENT_ID / EBAY_CLIENT_SECRET) |
| `python -m porcelan images` | képek, dedup, CLIP-beágyazás, képi előszűrés |
| `python -m porcelan train [--seed 42] [--seeds 5] [--no-clip]` | reprodukálható tanítás és értékelés → `models/<verzió>/EVALUATION.md` |
| `python -m porcelan score [--force]` | becslések (változatlan bemenetre és modellre kihagyja) |
| `python -m porcelan top --brand Herendi --max-price 50000 --market HU` | a legjobb találatok a parancssorban |
| `python -m porcelan status` / `evaluate-recommendations` | állapot; ajánlások utólagos ellenőrzése lezárult aukciókon |
| `python -m porcelan serve [--host 127.0.0.1 --port 8000]` | dashboard |
| `python -m pytest -q tests` | tesztek (50 db, hálózat nélkül; a képi teszt CLIP-súlyokat igényel) |

Konfiguráció: `config/settings.example.toml` (másold `config/settings.toml` néven). Itt állíthatók a keresőkifejezések, a kategóriák, a lekérési gyakoriság és a cache, az árfolyam, a HU/US költségek és adók, a rangsorolási küszöbök és a validációs feltételek. A költség-feltételezések a dashboardon ideiglenesen felülírhatók.

## Modell és mért eredmények

Az aktuális verzió: `models/v20260928-1432-cfe8ba3f` (teljes riport: [EVALUATION.md](models/v20260928-1432-cfe8ba3f/EVALUATION.md), [docs/MODELL_ERTEKELES.md](docs/MODELL_ERTEKELES.md)).

A mérés tesztkészleten készült (csoportszintű, a tanítástól és a validációtól elkülönítve), a célváltozó **kínálati ár**. Az intervallumok a validációs halmazon kalibráltak.

| Modell | Piac | n | MAE | MdAPE (95% CI) | ±25%-on belül | 80%-os int. lefedettség |
|---|---|---:|---:|---:|---:|---:|
| Csoportmedián (baseline) | HU | 252 | 46 159 Ft | 66,6% (60–73%) | 21,4% | 83,3% |
| GBM kvantilis | HU | 252 | 36 859 Ft | 45,6% (39–54%) | 32,5% | 86,5% |
| **Multimodális neurális** | HU | 252 | **34 667 Ft** | **43,8% (37–52%)** | 26,2% | 86,5% |
| Neurális, CLIP nélkül (★ validáció alapján választva) | HU | 252 | 35 473 Ft | 45,2% (42–51%) | 28,6% | 82,1% |
| Csoportmedián (★) | US | 17 | 235 USD | 74,9% (45–149%) | 11,8% | 88,2% |
| GBM kvantilis | US | 17 | 153 USD | 37,2% (34–65%) | 23,5% | 94,1% |

Gyártónként (HU, multimodális): Herendi MdAPE 40,7% (n = 151), Zsolnay 47,8% (n = 101).

Értelmezés:
- A mély tanulásos megoldás a HU piacon **érdemben jobb a baseline-nál**: a MAE 25%-kal, az MdAPE 23 százalékponttal kisebb, a bootstrap-intervallumok nem fedik át egymást. A GBM-hez képest a különbség a bizonytalanságon belül van.
- A CLIP szövegbeágyazás hozzájárulása kicsi (43,8% vs 45,2%, átfedő CI). A képi ág **még nem tanult**, mert nincs letöltött kép (lásd lent). A mechanikáját szintetikus képekkel teszteltük.
- A modellválasztás a validációs halmazon történik, nem a teszten. Ezért választotta HU-n a CLIP nélküli változatot és US-en a baseline-t, jóllehet a teszten más modellek jobbak voltak.
- Az intervallumok lefedettsége a kalibráció után a teszten 82–87% (névleges 80%). A megbízhatósági jelzés kalibrált: az átlagos jelzett érték 20%, a tényleges találati arány (±25%-on belül) 29%.
- **Ajánlások találati pontossága: nem mérhető.** Nincs még olyan ellenőrző adat (lezárult aukció vagy realizált továbbértékesítés), amely egy korábbi ajánláshoz kapcsolódna. A mérés automatikus: `recommendation_log` és `evaluate-recommendations`.
- A US-adat (117 sor, 17 tesztminta) túl kevés: az amerikai becslés tájékoztató jellegű. Ahol csak csoportmedián van, a rendszer nem ad ajánlást.

## Mi működik valós adattal, és mi nem

**Valós adattal működik és ellenőrzött:**
- A 2026-09-16-i élő Vatera-futás 2321 elfogadott hirdetésének importja, valamint 14 részletes termékoldal (2026-09-19) és 155 eBay-kínálati ár.
- Tanítás, értékelés, verziózott mentés és betöltés, becslés mind a 2174 aktívként tárolt hirdetésre (kb. 19 s), inkrementális újrapontozás (0 újrabecslés változatlan bemenetnél).
- A dashboard minden szűrővel, rendezéssel és a részletes nézettel. A háttérfeladat-indítás az API-n keresztül külön folyamatban fut. Mobil nézet vízszintes görgetés nélkül.
- Élő bejárási kísérlet: a Vatera ebből a környezetből nem érhető el (hálózati szabályzat, proxy 403). A crawler ezt `failed` állapotként, folytatható módon rögzíti, és a dashboard hibás adatforrásként jelzi.

**Offline tesztekkel ellenőrzött, élesben még nem futott:**
- A Vatera találati és termékoldal-parsere. A kártyaattribútumok (`data-product-id`, `data-gtm-*`) és a termékoldal-jelek a korábbi élő futásokból ismertek, de a lapozás-, kategória- és képlinkformátumot élesben kell ellenőrizni (`python diagnose.py`, majd `python -m porcelan crawl --max-requests 20`).
- A Jófogás-adapter (tűrő parser, élesben nem ellenőrzött).
- Képletöltés, pHash-dedup, CLIP-beágyazás, zero-shot előszűrés és képes tanítás (szintetikus képekkel tesztelve; a képi előszűrés küszöbe nincs validálva).

**Korlátok:**
- A modell **kísérleti**: kínálati árakon tanult. Egy drága aktív hirdetés nem bizonyítja a piaci értéket, ezért a várható eladási bevétel = becslés × 0,85 (konfigurálható, **nem mért** feltételezés).
- Az importált adatok 9–12 naposak. A tárolt „active” hirdetések azóta elkelhettek; a dashboard erre figyelmeztet.
- Időbeli teszt nem volt lehetséges: a megfigyelések csak 3 napot fednek le.
- A tanítóhalmazban szereplő hirdetésekre adott becslés a saját árukhoz húz, ami az alulárazottságot konzervatívan alulbecsli.
- A becslés nem garantálja az eredetiséget, az állapotot vagy a nyereséget. A költség- és adófeltételezések tervezési értékek (`as_of` dátummal).

A validált modellhez vezető út (élő bejárás, amely automatikusan gyűjti a záró liciteket; aukciósházi eredmények CSV-importja; képek; újratanítás): [docs/ADATFORRASOK.md](docs/ADATFORRASOK.md).

## Elfogadási feltételek – hol ellenőrizhető

| Feltétel | Teszt / bizonyíték |
|---|---|
| Lapozás, lefedettségmérés, folytatás | `tests/test_platform.py::CrawlTest` |
| Duplikáció- és újrahirdetés-szűrés, csoportszivárgás | `DatasetTest`, `ImportTest`, `ImageTest` (pHash) |
| Ár- és pénznemkezelés, időzóna | `ParsingTest` |
| Aukciók elkülönítése (záró licit ≠ kínálati ár, max. licit) | `CrawlTest`, `CostTest.test_asking_basis_and_auction` |
| CSV-import | `ImportTest` |
| Modellbetöltés újratanítás nélkül, inkrementális pontozás | `ModelAndApiTest` |
| Nyereségszámítás | `CostTest` |
| Dashboard-szűrés és -rendezés | `ModelAndApiTest` (API), `docs/screenshots/` |
| Képi ág | `tests/test_vision.py` |

## Régi eszközök

A korábbi `run.py` (Vatera-scrape → CSV → opcionális Claude-elemzés), a `diagnose.py`, az `elemzes/` szkriptek, a `riport/` és a `dashboard/` (három kézzel választott jelölt statikus oldala) megmaradt. A régi `run.py` CSV-kimenete a `import-csv` paranccsal betölthető az új rendszerbe. Hitelesítés és kérésfolyam: [AUTHENTICATION.md](AUTHENTICATION.md).
