# Pontos piaci ár képből és leírásból – cél: ±10%

## A cél pontos meghatározása

**Hibametrika:** adott termékre a modell által mondott piaci ár és a termék valódi piaci ára közötti eltérés, |becsült / valódi − 1|. A cél: legfeljebb 10%.

**Valódi piaci ár:** ugyanannak a terméknek a tipikus (medián) realizált eladási ára, azonos állapotban. „Ugyanaz a termék” azonos gyártót, formaszámot és mintakódot jelent (Herendnél a cikkszám, pl. `711-0-00 VBO`).

Két dolgot külön kell kezelni, mert másra vonatkoznak:

| Mit hasonlítunk | Elérhető pontosság |
|---|---|
| a becslést **egy konkrét eladás** árához | nem lehet jobb, mint a piac saját szórása: ha azonos termék két eladása tipikusan 20–30%-kal tér el egymástól, egyetlen eladást egyetlen modell sem talál el 10%-on belül |
| a becslést **a termék piaci árához** (sok eladás mediánjához) | elegendő azonos-termék eladással 10% alá vihető (lent számszerűen) |

A rendszer mindkettőt méri, és a „pontos ár” jelzést csak a második értelemben adja.

## Miért kell ehhez pontos termékazonosítás

Az általános képi vagy szöveges modell („ez egy Herendi váza”) a mostani adaton 43% mediánhibát ér el. Egy „Herendi váza” 8 000 és 300 000 Ft között bármi lehet. A 10%-hoz a modellnek tudnia kell, **melyik** vázáról van szó. Ezért a lánc:

1. **Azonosítás kép és leírás alapján** (`porcelan/identify.py`, `porcelan/catalog.py`)
   - Szövegből: teljes cikkszám (`711-0-00 VBO`), formaszám és mintakód párok (`749/AP`, `(AV 7183)`, `1711 / VBO`), önálló formaszám, mintakód és magyar mintanév (Viktória → VBO, Apponyi zöld/narancs/purpur → AV/AOG/AP, Rothschild → RO, halpikkelyes kék → VHB…). Az eladói leltárkódokat (`ZAL-R 91989`, `1S089`), az évszámokat és a méreteket kiszűri.
   - Képből: a CLIP-képbeágyazás a katalógusképekhez és a szövegből biztosan azonosított hirdetések képeihez hasonlítva szavaz a cikkszámra. A képi azonosítást csak abban a pontszámsávban fogadja el, ahol a kihagyásos mérés szerint legalább 95%-os a pontossága.
2. **Piaci ár cikkszám-szinten** (`porcelan/sku_model.py`): log-skálán, bizonytalansággal súlyozva kombinálja a következőket:
   - azonos cikkszám eladásai (szórás σ: a piac saját szórása, az adatból becsülve),
   - azonos formaszám más mintával (szórás √(σ² + σ_minta²)),
   - a kép+szöveg neurális modell becslése (a saját kalibrált bizonytalanságával).
   Állapot-korrekció (sérült / javított) az adatból. Kimenet: piaci ár, 80%-os intervallum, **P(|hiba| ≤ 10%)**.
3. **„Pontos ár (±10%)” jelzés:** csak akkor, ha P(|hiba| ≤ 10%) ≥ 90%, ÉS a cikkszám-szintű validáció (legalább 30 kiértékelt eladás) szerint a „pontos” becslések legalább 90%-a valóban ±10%-on belül volt. Máshol a rendszer sávot mond, és jelzi, mi hiányzik (formaszám, minta, kép, eladások).
4. **Csak ezután** jön az összevetés a hirdetési árral (`ranking.py`).

## Mennyi adat kell – számszerűen

Ha azonos termék eladásai σ log-szórással ingadoznak, akkor n eladás átlagával a piaci ár hibájának szórása σ/√n. Szimulációval és képlettel (`sku_model.sales_needed`):

| Piaci szórás σ | Egyetlen eladás „zajszintje” (MdAPE) | Eladás/termék a 10%-os mediánhibához | Eladás/termék, hogy az esetek 90%-a ±10%-on belül legyen |
|---:|---:|---:|---:|
| 0,2 | 14% | 3 | 11 |
| 0,3 | 22% | 5 | 25 |
| 0,4 | 31% | 9 | 44 |
| 0,5 | 40% | 13 | 68 |

Egy tipikus Herend-kínálatban termékenként (formaszám × minta) több ezer változat forog. Ha a gyakori termékek 1000–3000 cikkszámára egyenként 10–40 realizált eladás kell, az **tízezres nagyságrendű, cikkszámmal azonosított, realizált eladási adatot** jelent. Ehhez jön a képi azonosításhoz szükséges, cikkszámmal címkézett képállomány (katalógusképek és azonosított hirdetésképek).

A mérés szintetikus adaton igazolja a módszert (`tests/test_identify.py`). σ = 0,2 és cikkszámonként 25 eladás mellett:
- egy konkrét eladáshoz mérve a hiba a zajszint közelében marad (>10%),
- a termék piaci árához mérve 10 eladásból már 10% alatti.

## A mostani valós adat

- **Azonosítás:** a 2319 Vatera-címből 28-ban van teljes cikkszám, további ~30-ban csak formaszám. A címek szinte soha nem azonosítják pontosan a terméket; ehhez a termékoldal leírása (gyakran benne van a formaszám) és a kép kell.
- **Ismételt eladás:** 0 olyan cikkszám van, amelynek legalább 2 független eladása lenne. Ezért a ±10%-os cél a mostani adaton **nem mérhető és nem érhető el**. A tanítási riport (`models/<verzió>/EVALUATION.md`) ezt minden tanításnál kiírja, a mért σ-ból számolt szükséges eladásszámmal együtt.

## Mit kell tenni a 10%-hoz

1. **Katalógus** (`import-catalog`): cikkszám, név, méret, hivatalos ár és kép a gyártói webshopokból (herend.com, herend.at), CSV-exportból vagy saját gyűjtésből. Ez a képi azonosítás mintatára.
2. **Termékoldalak és képek** (`crawl`, `images`): a Vatera termékoldali leírásából és képeiből azonosítható a formaszám és a minta.
3. **Realizált eladások cikkszámmal** (`crawl`: lezárult aukciók záró licitjei; `import-prices`: LiveAuctioneers/Axioart leütési árak, eBay-eladások exportja, saját eladások). A cél: a gyakori cikkszámokra egyenként 10–40 eladás.
4. **Azonosítás és értékelés** (`identify`, `sku-eval`, `train`): a riport mutatja a ±10%-on belüli arányt, a piaci zajszintet és a hibagörbét az eladásszám függvényében. A „validált” státuszhoz a „pontos ár” becslések legalább 90%-ának ±10%-on belül kell lennie, legalább 30 kiértékelt eladáson.
