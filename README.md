# Vatera – Herendi & Zsolnay deal finder

Vatera piactér scraper + Claude Opus 5 elemzés: kigyűjti a **Herendi** és
**Zsolnay** porcelán hirdetéseket, eladási típus szerint szétválogatva tárolja
őket, majd a három listát külön-külön átadja a Claude API-nak, ami kiválasztja
az **áron aluli**, illetve az **amerikai / európai piacon jól eladható**
tételeket – konkrét Vatera linkekkel.

## Futás egy sorban

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python run.py
```

## Mi történik futáskor

1. **Vatera scrape** – a `porcelan/config.py`-ban felsorolt keresőkifejezésekre
   (herendi / zsolnay + minta- és tárgytípus variánsok) végigjárja a találati
   oldalakat, összeszedi a termékoldal-linkeket, majd párhuzamosan letölti és
   elemzi őket. A letöltött HTML lemezre cache-elődik (`.cache_vatera/`,
   alapból 6 óra), így az ismételt futás gyors és kíméli a Vaterát.
2. **Szeparált tárolás** – minden hirdetés **konkrét linkkel**, eladási típus
   szerint külön CSV-be:
   | fájl | tartalom |
   |---|---|
   | `vatera_aukcio.csv` | licitálós aukciók (aktuális licit, kikiáltási ár, licitszám, aukció vége) |
   | `vatera_fix.csv` | fix áras, alku nélküli tételek |
   | `vatera_alku.csv` | alkuképes / irányáras / „ajánlatot tehetsz” tételek |
   | `vatera_ismeretlen.csv` | csak ha az oldalból nem derült ki a típus |
   | `vatera_osszes.csv` / `.json` | a három lista együtt |
   | `vatera_elutasitott.csv` | kiszűrt tételek (utánzat, könyv/katalógus stb.) – **ezt érdemes átnézni** |
3. **Claude Opus 5 elemzés** – a három lista **három külön részként** megy fel
   az API-ra (nagy lista esetén típuson belül további adagokban,
   `--chunk-size`). A modell csak a bemenetben szereplő hirdetéseket adhatja
   vissza; a program ellenőrzi, hogy a kapott URL tényleg a scrape-ből való
   (hallucinált link nem kerül a kimenetbe).
4. **Kimenet** – `riport.md` (olvasható összefoglaló, linkekkel),
   `deals.csv` (javaslatok táblázatban), `ai_nyers.json` (a modell nyers válasza).

Minden futás saját mappába kerül: `out/run_<időbélyeg>/`.

## Kapcsolók

```
python run.py --brand zsolnay        # csak Zsolnay keresőszavak
python run.py --pages 10             # több találati oldal keresőszavanként
python run.py --limit 50             # csak 50 hirdetés (gyors próba)
python run.py --no-ai                # csak scrape + CSV, API hívás nélkül
python run.py --chunk-size 40        # kisebb adagok az API felé
python run.py --workers 4            # párhuzamos letöltő szálak
python run.py --no-cache             # friss letöltés, cache megkerülése
python run.py --offline-dir tests/fixtures   # demó futás hálózat nélkül
```

Környezeti változók (mind opcionális): `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`
(alap: `claude-opus-5`), `VATERA_WORKERS`, `VATERA_DELAY`, `VATERA_MAX_PAGES`,
`VATERA_CACHE_TTL`, `VATERA_OUT_DIR`, `CLAUDE_CHUNK_SIZE`.

## Hogyan dől el az eladási típus

A Vatera termékoldalán a legstabilabb jel a `fix_price`, illetve `bid` token;
emellett a látható szöveg kulcsszavait is nézzük:

* **aukció** – „Aktuális licit”, „Kikiáltási ár”, „Licitálok”, `bid` token
* **alku** – „Ajánlatot tehetsz”, „irányár”, „alkudható”, „megegyezés szerint”
  (fix áras oldalon is: ha alkulehetőség van, ide kerül)
* **fix** – `fix_price` token / „Fix ár”, alkujelzés nélkül

Ha egy aukciónál van „azonnali vétel” ár, az tételként aukcióban marad, de a
`buy_now_huf` oszlopban megjelenik.

## Szűrés (és mit kell review-zni)

* Csak akkor kerül be egy tétel, ha **Herend(i)** vagy **Zsolnay** szerepel benne.
* Kizárjuk: „stílusú”, „jellegű”, „utánzat”, „replika”, „másolat”, valamint a
  nem porcelán tételeket (könyv, katalógus, képeslap, plakát…). Ezek nem
  vesznek el: a `vatera_elutasitott.csv`-ben a `reject_reason` oszloppal
  visszanézhetők, és a szólisták a `porcelan/config.py`-ban bővíthetők.
* Jelöljük, de nem zárjuk ki: `damage_flags` (sérült, csorba, repedt, javított)
  és `suspect_flags` (pl. „mintás”, „jelzetlen”) – mindkettő felmegy a
  modellnek is, mert az árazásnál döntő.

## Költség / API

A Claude hívások száma: eladási típusonként `ceil(tételszám / chunk-size)`,
tehát ~180 hirdetés és 60-as adag mellett tipikusan 3–6 hívás. A hívás
`claude-opus-5` modellel, adaptív gondolkodással, `json_schema` strukturált
kimenettel és szerveroldali fallback-kel megy (ha a fallback beta nem elérhető,
automatikusan sima hívásra vált). API kulcs nélkül a program a scrape-et és a
CSV-ket így is elkészíti, csak az elemzést hagyja ki.

## Tesztek

```bash
python -m unittest discover -s tests -v
```

A tesztek a `tests/fixtures/` alatti Vatera-szerű HTML-eken futnak (aukciós,
fix áras, irányáras, utánzat és nem porcelán példa), az AI réteget pedig stub
klienssel ellenőrzik – hálózat és API kulcs nélkül.

## Ha az éles futás nem hoz találatot: diagnózis

```bash
python diagnose.py                          # alap keresés ellenőrzése
python diagnose.py --save-dir diag_html     # + a letöltött HTML-ek mentése
python diagnose.py --url <hirdetés URL>     # egy konkrét hirdetés vizsgálata
```

Végigmegy a scraper feltevésein, és megmondja, melyik bukik el:
a találati oldal státusza és mérete, anti-bot oldal-e, hány termék-link
található (és milyen módszerrel), majd termékoldalanként: megvan-e a
`fix_price` / `bid` token, a „Fix ár” / „Aktuális licit” / „Ajánlatot tehetsz”
felirat, sikerült-e az eladási típus, az ár és a márka. Az összegzés
konkrét teendőt ír. A `--save-dir` mappából a HTML-ek egy az egyben
tesztfixture-nek használhatók, így a parser hálózat nélkül is hangolható.

## Korlátok, tudnivalók

* **A Vatera HTML-je változhat.** A parser tokenekre és látható szövegre
  („Fix ár:”, „Aktuális licit:”) épít, nem törékeny CSS osztályokra, de élesben
  érdemes egy `--limit 20 --no-ai` próbafutással ellenőrizni az első CSV-ket.
  Ha üres az eredmény, valószínűleg anti-bot oldal jön vissza: kevesebb szál
  (`--workers 2`), nagyobb késleltetés (`VATERA_DELAY=1.5`) segít.
* A fejlesztői környezetben a `vatera.hu` hálózati szinten nem volt elérhető,
  ezért a scraper **élesben még nem lett lefuttatva** – az offline fixture-ökön
  a teljes lánc (scrape → 3 CSV → AI → riport) végigmegy.
* A becsült nyugati árak a modell szakértői becslései, nem valós idejű
  piaci adatok; nagy értékű vásárlás előtt érdemes eBay „sold” listákkal
  ellenőrizni.
* Kérlek, tartsd tiszteletben a Vatera felhasználási feltételeit: a program
  udvariassági késleltetéssel és cache-sel dolgozik, ne told fel a szálak
  számát.
