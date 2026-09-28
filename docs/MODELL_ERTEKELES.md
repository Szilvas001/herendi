# Modellértékelés

Ez a fájl a `models/v20260928-1432-cfe8ba3f/EVALUATION.md` másolata; a teljes gépi riport (minden metrika, kalibráció, adatstatisztika) a `models/v20260928-1432-cfe8ba3f/manifest.json`-ban van.

Megismétlés: `python -m porcelan import-repo && python -m porcelan train --seed 42 --seeds 5` – azonos adat-ujjlenyomat és seed mellett ugyanezeket a számokat adja (CPU, determinisztikus torch-beállítás).


**Státusz: KÍSÉRLETI**

Miért nem validált:
- HU: a célváltozó kínálati ár, nem realizált eladási ár
- HU: MdAPE 45% > 35%
- US: a célváltozó kínálati ár, nem realizált eladási ár
- US/Herendi: 14 tesztminta < 50
- US/Zsolnay: 3 tesztminta < 50
- US: MdAPE 75% > 35%

## Adat

- Nyers ár-rekordok: 2438; típus szerint: HU/asking_active: 2113, HU/auction_start_price: 206, US/asking_active: 119
- Tanításra használt sorok (duplikátumszűrés után): 1794, csoportok: 1623
- Piac × márka: HU/Herendi: 981, HU/Zsolnay: 696, US/Herendi: 98, US/Zsolnay: 19
- Célváltozó alapja: HU: KÍNÁLATI ár, US: KÍNÁLATI ár
- Kiszűrve: {'no_price_or_currency': 0, 'out_of_range': 8, 'relisting_duplicates': 430}
- Megfigyelési napok: 2026-09-16, 2026-09-19
- Képpel rendelkező tanítósor: 0
- Felosztás: csoportszintű véletlen (a megfigyelések csak 3 napot fednek le; időbeli teszt nem lehetséges); {'train': 1258, 'test': 269, 'val': 267}
- Adat-ujjlenyomat: `cfe8ba3fb2fc78f1`, seed 42, git `335a4e7058`

> HU: 0 realizált ár < 200 → kínálati áron tanul (kísérleti)
> US: 0 realizált ár < 200 → kínálati áron tanul (kísérleti)

## Tesztmetrikák (a validáción kalibrált intervallumokkal)

| Modell | Piac | n | MAE | Medián AE | MdAPE (95% CI) | ±25%-on belül | 80%-os int. lefedettség | átl. megbízhatóság | tényleges találat |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_group_median | HU | 252 | 46 159 Ft | 18 000 Ft | 66.6% (60–73%) | 21.4% | 83.3% | 20.3% | 21.4% |
| baseline_group_median ★ | US | 17 | 235 USD | 150 USD | 74.9% (45–149%) | 11.8% | 88.2% | 25.0% | 11.8% |
| gbm_quantile | HU | 252 | 36 859 Ft | 13 313 Ft | 45.6% (39–54%) | 32.5% | 86.5% | 25.1% | 32.5% |
| gbm_quantile | US | 17 | 153 USD | 108 USD | 37.2% (34–65%) | 23.5% | 94.1% | 60.0% | 23.5% |
| deep_multimodal | HU | 252 | 34 667 Ft | 12 212 Ft | 43.8% (37–52%) | 26.2% | 86.5% | 18.8% | 26.2% |
| deep_multimodal | US | 17 | 197 USD | 141 USD | 60.9% (46–110%) | 11.8% | 70.6% | 30.0% | 11.8% |
| deep_no_clip ★ | HU | 252 | 35 473 Ft | 12 832 Ft | 45.2% (42–51%) | 28.6% | 82.1% | 20.3% | 28.6% |
| deep_no_clip | US | 17 | 193 USD | 130 USD | 60.2% (40–112%) | 11.8% | 70.6% | 35.0% | 11.8% |

★ = a validációs pinball-veszteség alapján kiválasztott, élesben használt modell.

## Gyártónként (teszt)

| Modell | Piac | Gyártó | n | MdAPE | MAE | 80%-os lefedettség |
|---|---|---|---:|---:|---:|---:|
| baseline_group_median | HU | Herendi | 151 | 61.5% | 49 573 | 81.5% |
| baseline_group_median | HU | Zsolnay | 101 | 76.3% | 41 055 | 86.1% |
| baseline_group_median | US | Herendi | 14 | 69.6% | 268 | 85.7% |
| baseline_group_median | US | Zsolnay | 3 | 86.7% | 81 | 100.0% |
| gbm_quantile | HU | Herendi | 151 | 45.5% | 38 495 | 87.4% |
| gbm_quantile | HU | Zsolnay | 101 | 49.4% | 34 414 | 85.1% |
| gbm_quantile | US | Herendi | 14 | 35.6% | 149 | 92.9% |
| gbm_quantile | US | Zsolnay | 3 | 171.5% | 172 | 100.0% |
| deep_multimodal | HU | Herendi | 151 | 40.7% | 36 321 | 82.8% |
| deep_multimodal | HU | Zsolnay | 101 | 47.8% | 32 193 | 92.1% |
| deep_multimodal | US | Herendi | 14 | 58.9% | 207 | 64.3% |
| deep_multimodal | US | Zsolnay | 3 | 247.9% | 149 | 100.0% |
| deep_no_clip | HU | Herendi | 151 | 44.3% | 36 659 | 80.1% |
| deep_no_clip | HU | Zsolnay | 101 | 49.6% | 33 699 | 85.1% |
| deep_no_clip | US | Herendi | 14 | 57.4% | 201 | 71.4% |
| deep_no_clip | US | Zsolnay | 3 | 259.7% | 152 | 66.7% |

## Ajánlások találati pontossága

Nem mérhető: nincs olyan ellenőrző adat (később realizált eladás / továbbértékesítés), amely megmutatná, hogy egy ajánlott vétel valóban nyereséges lett. A `python -m porcelan evaluate-recommendations` parancs ezt méri, amint lezárult aukciók vagy importált eladások kapcsolódnak korábban ajánlott hirdetésekhez.

## Korlátok

- A kínálati ár nem bizonyított piaci érték; a kínálati áron tanított modell a *hirdetési árszintet* becsüli.
- A metrikák a tesztsorok számához képest bizonytalanok; kis n mellett (különösen US) csak irányt mutatnak.
- Képi jellemzők csak akkor hatnak, ha a tanítóadatban van letöltött kép; ennek száma fent szerepel.
- Az eredetiséget és az állapotot a modell nem igazolja.
