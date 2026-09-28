# Modellértékelés

Ez a fájl a `models/v20260928-1810-522878a8/EVALUATION.md` másolata; a teljes gépi riport a `models/v20260928-1810-522878a8/manifest.json`-ban van. A tanulási görbe: `models/learning_curve/`. A ±10%-os cél módszertana: [PONTOS_PIACI_AR.md](PONTOS_PIACI_AR.md).


**Státusz: KÍSÉRLETI**

Miért nem validált:
- HU: pontos (cikkszám-szintű) értékelés: 0 azonosított, összehasonlítható eladás < 30 – a ±10%-os cél nem mérhető
- US: pontos (cikkszám-szintű) értékelés: 0 azonosított, összehasonlítható eladás < 30 – a ±10%-os cél nem mérhető
- képes Herendi/Zsolnay tanítósor: 0 < 10000 (képalapú becsléshez sok tízezer képes adat kell)
- HU: 1167 tanítósor < 10000
- US: 84 tanítósor < 10000
- HU: a célváltozó kínálati ár, nem realizált eladási ár
- HU: MdAPE 43% > 10%
- US: a célváltozó kínálati ár, nem realizált eladási ár
- US/Herendi: 19 tesztminta < 50
- US/Zsolnay: 0 tesztminta < 50
- US: MdAPE 75% > 10%
- US: 80%-os intervallum tényleges lefedettsége 63%
- US: a választott modell nem jobb az alapmodellnél a teszten

## Adat

- Nyers ár-rekordok: 2438; típus szerint: herend_zsolnay/HU/asking_active: 2113, herend_zsolnay/HU/auction_start_price: 206, herend_zsolnay/US/asking_active: 119
- Tanításra használt sorok (duplikátumszűrés után): 1793, csoportok: 1627
- Korpusz × piac: herend_zsolnay/HU: 1677, herend_zsolnay/US: 116
- Herendi/Zsolnay tanítósor: 1251 (ebből képes: 0); általános előtanító sor: 0 (képes: 0)
- Piac × márka: HU/Herendi: 981, HU/Zsolnay: 696, US/Herendi: 97, US/Zsolnay: 19
- Célváltozó alapja: HU: KÍNÁLATI ár, US: KÍNÁLATI ár
- Kiszűrve: {'no_price_or_currency': 0, 'out_of_range': 8, 'relisting_duplicates': 430, 'fake_or_non_item': 1}
- Megfigyelési napok: 2026-09-16, 2026-09-19
- Képpel rendelkező tanítósor: 0
- Felosztás: csoportszintű véletlen (a megfigyelések csak 3 napot fednek le; időbeli teszt nem lehetséges); {'train': 1251, 'val': 277, 'test': 265}
- Adat-ujjlenyomat: `522878a8f0adfc10`, seed 42, git `8d3d45752e`

> HU: 0 realizált Herendi/Zsolnay ár < 200 → kínálati áron tanul (kísérleti)
> US: 0 realizált Herendi/Zsolnay ár < 200 → kínálati áron tanul (kísérleti)

## Tesztmetrikák (a validáción kalibrált intervallumokkal)

| Modell | Piac | n | MAE | Medián AE | MdAPE (95% CI) | ±25%-on belül | 80%-os int. lefedettség | átl. megbízhatóság | tényleges találat |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_group_median | HU | 246 | 51 088 Ft | 18 200 Ft | 67.1% (61–75%) | 17.5% | 78.9% | 18.4% | 17.5% |
| baseline_group_median | US | 19 | 470 USD | 176 USD | 70.7% (58–148%) | 15.8% | 84.2% | 20.0% | 15.8% |
| gbm_quantile | HU | 246 | 41 042 Ft | 12 184 Ft | 46.8% (39–52%) | 30.9% | 76.8% | 28.2% | 30.9% |
| gbm_quantile | US | 19 | 454 USD | 181 USD | 80.8% (52–116%) | 21.1% | 84.2% | 13.3% | 21.1% |
| deep_multimodal ★ | HU | 246 | 40 426 Ft | 11 782 Ft | 43.4% (38–47%) | 29.3% | 76.0% | 30.1% | 29.3% |
| deep_multimodal ★ | US | 19 | 454 USD | 126 USD | 75.4% (47–196%) | 15.8% | 63.2% | 13.3% | 15.8% |
| deep_no_clip | HU | 246 | 40 927 Ft | 13 487 Ft | 42.2% (38–48%) | 26.8% | 72.4% | 28.3% | 26.8% |
| deep_no_clip | US | 19 | 450 USD | 134 USD | 65.0% (39–217%) | 15.8% | 63.2% | 13.3% | 15.8% |

★ = a validációs pinball-veszteség alapján kiválasztott, élesben használt modell.

## Gyártónként (teszt)

| Modell | Piac | Gyártó | n | MdAPE | MAE | 80%-os lefedettség |
|---|---|---|---:|---:|---:|---:|
| baseline_group_median | HU | Herendi | 141 | 66.7% | 50 432 | 78.0% |
| baseline_group_median | HU | Zsolnay | 105 | 67.5% | 51 970 | 80.0% |
| baseline_group_median | US | Herendi | 19 | 70.7% | 470 | 84.2% |
| gbm_quantile | HU | Herendi | 141 | 48.2% | 39 306 | 76.6% |
| gbm_quantile | HU | Zsolnay | 105 | 45.4% | 43 373 | 77.1% |
| gbm_quantile | US | Herendi | 19 | 80.8% | 454 | 84.2% |
| deep_multimodal | HU | Herendi | 141 | 43.1% | 37 474 | 75.2% |
| deep_multimodal | HU | Zsolnay | 105 | 43.5% | 44 391 | 77.1% |
| deep_multimodal | US | Herendi | 19 | 75.4% | 454 | 63.2% |
| deep_no_clip | HU | Herendi | 141 | 44.1% | 39 097 | 66.0% |
| deep_no_clip | HU | Zsolnay | 105 | 39.9% | 43 385 | 81.0% |
| deep_no_clip | US | Herendi | 19 | 65.0% | 450 | 63.2% |

## Pontos termék → pontos piaci ár (cikkszám-szint, cél: ±10%)

- Formaszámmal azonosított rekord: 55, kiértékelhető (van azonos termék/formaszám másik eladása): 0; csoportonként kihagyásos értékelés.


A termék piaci árának hibagörbéje még nem mérhető: nincs olyan cikkszám, amelynek legalább 6 eladása lenne az adatban.

Piaci zajszint (azonos termék eladásai egymáshoz képest):
- HU: 0 cikkszámnak van ≥3 eladása – a zajszint még nem mérhető
- US: 0 cikkszámnak van ≥3 eladása – a zajszint még nem mérhető

Szükséges eladásszám ugyanabból a termékből (a mért vagy alapértelmezett szórásból):
- HU: σ=0.35 (alapértelmezett) → ≥7 eladás a 10%-os mediánhibához, ≥34 eladás ahhoz, hogy az esetek 90%-a ±10%-on belül legyen. Egyetlen eladás árát ennél pontosabban nem lehet eltalálni: ~27% MdAPE.
- US: σ=0.35 (alapértelmezett) → ≥7 eladás a 10%-os mediánhibához, ≥34 eladás ahhoz, hogy az esetek 90%-a ±10%-on belül legyen. Egyetlen eladás árát ennél pontosabban nem lehet eltalálni: ~27% MdAPE.

## Ajánlások találati pontossága

Nem mérhető: nincs olyan ellenőrző adat (később realizált eladás / továbbértékesítés), amely megmutatná, hogy egy ajánlott vétel valóban nyereséges lett. A `python -m porcelan evaluate-recommendations` parancs ezt méri, amint lezárult aukciók vagy importált eladások kapcsolódnak korábban ajánlott hirdetésekhez.

## Korlátok

- A kínálati ár nem bizonyított piaci érték; a kínálati áron tanított modell a *hirdetési árszintet* becsüli.
- A metrikák a tesztsorok számához képest bizonytalanok; kis n mellett (különösen US) csak irányt mutatnak.
- Képi jellemzők csak akkor hatnak, ha a tanítóadatban van letöltött kép; ennek száma fent szerepel.
- Az eredetiséget és az állapotot a modell nem igazolja.

## Tanulási görbe – mennyi adat kell?

Készült: 2026-09-28T15:06:43+00:00. Teszthalmaz: csoportszintű véletlen (a megfigyelések csak 3 napot fednek le; időbeli teszt nem lehetséges).

| Változat | Piac | Tanítósor | Tesztminta | MdAPE | MAE | 80%-os lefedettség |
|---|---|---:|---:|---:|---:|---:|
| csak Herendi/Zsolnay | HU | 128 | 246 | 60.0% | 46 181 | 79% |
| csak Herendi/Zsolnay | US | 5 | 19 | 86.4% | 481 | 84% |
| csak Herendi/Zsolnay | HU | 308 | 246 | 55.0% | 46 101 | 71% |
| csak Herendi/Zsolnay | US | 15 | 19 | 75.0% | 463 | 84% |
| csak Herendi/Zsolnay | HU | 603 | 246 | 48.5% | 43 762 | 74% |
| csak Herendi/Zsolnay | US | 35 | 19 | 75.9% | 448 | 79% |
| csak Herendi/Zsolnay | HU | 1167 | 246 | 44.1% | 40 567 | 76% |
| csak Herendi/Zsolnay | US | 84 | 19 | 73.3% | 453 | 68% |

## Extrapoláció (MdAPE ≈ a·n^(−b) + c)

- HU/hz_only: a=1.21, b=0.142, aszimptota c=0.0% → ~6 211 tanítósor kellene 35% MdAPE-hez
- US/hz_only: MEGBÍZHATATLAN extrapoláció (tesztminta 19, legfeljebb 84 tanítósor) – nincs értelmes becslés.

Extrapoláció kevés pontból: nagyságrendi becslés, nem ígéret.
