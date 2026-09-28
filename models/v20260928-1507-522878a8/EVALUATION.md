# Modellértékelés – v20260928-1507-522878a8

**Státusz: KÍSÉRLETI**

Miért nem validált:
- képes Herendi/Zsolnay tanítósor: 0 < 10000 (képalapú becsléshez sok tízezer képes adat kell)
- HU: 1167 tanítósor < 10000
- US: 84 tanítósor < 10000
- HU: a célváltozó kínálati ár, nem realizált eladási ár
- HU: MdAPE 43% > 35%
- US: a célváltozó kínálati ár, nem realizált eladási ár
- US/Herendi: 19 tesztminta < 50
- US/Zsolnay: 0 tesztminta < 50
- US: MdAPE 75% > 35%
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
- Adat-ujjlenyomat: `522878a8f0adfc10`, seed 42, git `5156205138`

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

## Ajánlások találati pontossága

Nem mérhető: nincs olyan ellenőrző adat (később realizált eladás / továbbértékesítés), amely megmutatná, hogy egy ajánlott vétel valóban nyereséges lett. A `python -m porcelan evaluate-recommendations` parancs ezt méri, amint lezárult aukciók vagy importált eladások kapcsolódnak korábban ajánlott hirdetésekhez.

## Korlátok

- A kínálati ár nem bizonyított piaci érték; a kínálati áron tanított modell a *hirdetési árszintet* becsüli.
- A metrikák a tesztsorok számához képest bizonytalanok; kis n mellett (különösen US) csak irányt mutatnak.
- Képi jellemzők csak akkor hatnak, ha a tanítóadatban van letöltött kép; ennek száma fent szerepel.
- Az eredetiséget és az állapotot a modell nem igazolja.
